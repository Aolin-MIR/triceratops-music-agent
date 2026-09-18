import os
import gc
import time
import weakref
import json
import wandb
import torch
import random
import pickle
import numpy as np
from utils import *
from config import *
from text2music.data.utils.xml2plan import get_partial_plan_text, get_full_plan_text
from text2music.data.utils.abci_augment import read_abci_with_pitch_shift
from tqdm import tqdm
from torch.amp import autocast, GradScaler
from torch.utils.data import Dataset, DataLoader
from transformers import GPT2Config, get_scheduler, get_constant_schedule_with_warmup
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data.distributed import DistributedSampler
import torch.multiprocessing as mp

# Set up distributed training
world_size = int(os.environ['WORLD_SIZE']) if 'WORLD_SIZE' in os.environ else 1
global_rank = int(os.environ['RANK']) if 'RANK' in os.environ else 0
local_rank = int(os.environ['LOCAL_RANK']) if 'LOCAL_RANK' in os.environ else 0

if world_size > 1:
    torch.cuda.set_device(local_rank)
    device = torch.device("cuda", local_rank)
    dist.init_process_group(backend='nccl') if world_size > 1 else None
else:
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

# Set random seed
seed = 0 + global_rank
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed_all(seed)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

batch_size = BATCH_SIZE

patchilizer = Patchilizer()

patch_config = GPT2Config(num_hidden_layers=PATCH_NUM_LAYERS,
                          max_length=PATCH_LENGTH,
                          max_position_embeddings=PATCH_LENGTH,
                          n_embd=HIDDEN_SIZE,
                          num_attention_heads=HIDDEN_SIZE // 64,
                          vocab_size=1)
char_config = GPT2Config(num_hidden_layers=CHAR_NUM_LAYERS,
                         max_length=PATCH_SIZE + 1,
                         max_position_embeddings=PATCH_SIZE + 1,
                         hidden_size=HIDDEN_SIZE,
                         num_attention_heads=HIDDEN_SIZE // 64,
                         vocab_size=128)


def clear_unused_tensors():
    gc.disable()  # Temporarily disable garbage collection
    try:
        # Get the set of tensor ids used by the model
        if hasattr(model, "module"):
            model_tensors = {id(p) for p in model.module.parameters()}
        else:
            model_tensors = {id(p) for p in model.parameters()}

        # Get the set of tensor ids used by the optimizer
        optimizer_tensors = {
            id(state)
            for state_dict in optimizer.state.values()
            for state in state_dict.values()
            if isinstance(state, torch.Tensor)  # Ensure only tensors are considered
        }

        # List of all CUDA tensors currently in memory
        tensors = [obj for obj in gc.get_objects() if isinstance(obj, torch.Tensor) and obj.is_cuda]

        # Create weak references to avoid interfering with garbage collection
        tensor_refs = [weakref.ref(tensor) for tensor in tensors]

        for tensor_ref in tensor_refs:
            tensor = tensor_ref()  # Dereference the weak reference
            if tensor is not None and id(tensor) not in model_tensors and id(tensor) not in optimizer_tensors:
                # Mark the tensor for deletion
                tensor.detach_()  # Detach from computation graph
                del tensor  # Delete the tensor reference
    except:
        pass

    finally:
        gc.enable()  # Re-enable garbage collection
        gc.collect()  # Force a garbage collection
        torch.cuda.empty_cache()  # Clear the CUDA cache


def collate_batch(input_batches):

    input_patches, input_plan, input_masks = zip(*input_batches)
    input_patches = torch.nn.utils.rnn.pad_sequence(input_patches, batch_first=True, padding_value=0)
    input_plan = torch.nn.utils.rnn.pad_sequence(input_plan, batch_first=True, padding_value=0)
    input_masks = torch.nn.utils.rnn.pad_sequence(input_masks, batch_first=True, padding_value=0)

    return input_patches, input_plan, input_masks


class NotaGenDataset(Dataset):

    def __init__(self, filenames, data_root, pitch_shift_range=(0, 0), split="train"):
        """
        Args:
            filenames (list): List of dictionaries containing file paths and other metadata.
            pitch_shift_range (tuple): Range of random pitch shift in semitones.
                Default is (0, 0) meaning no transposition.
        """
        # Tmp: Remove all augmented from filenames
        # filenames = [file for file in filenames if 'augmented' not in file['path'].lower()]

        if split == "train":
            self.all_files = filenames
            self.unique_files = [file for file in filenames if 'augmented' not in file['path'].lower()]
            print(f"Number of unique training files: {len(self.unique_files)}")
            # Sample length of unique files from all files
            self.filenames = random.choices(self.all_files, k=len(self.unique_files))
        else:
            self.filenames = filenames
        self.pitch_shift_range = pitch_shift_range
        self.data_root = data_root

    def __len__(self):
        return len(self.filenames)

    def on_epoch_end(self):
        # Take new sample of augmented files
        self.filenames = random.choices(self.all_files, k=len(self.unique_files))
        print("New sample of augmented files taken for training.")

    def __getitem__(self, idx):

        filepath = self.filenames[idx]['path']
        filepath = os.path.join(self.data_root, filepath)
        genre = self.filenames[idx].get('genre', None)

        pitch_shift = 0 if self.pitch_shift_range == (0, 0) else random.randint(*self.pitch_shift_range)
        abc_text = read_abci_with_pitch_shift(filepath, pitch_shift=pitch_shift)  # 10 ms

        pkl_path = filepath.replace('.abci', '.pkl')
        if os.path.exists(pkl_path):
            with open(pkl_path, 'rb') as f:
                plan = pickle.load(f)

            plan = get_full_plan_text(pkl_path, pitch_shift=pitch_shift, genre=genre)
            # Encode the plan text
            file_plan = patchilizer.encode_plan(plan)
        else:
            file_plan = patchilizer.encode_plan("")

        file_bytes = patchilizer.encode_train(abc_text)
        file_masks = [1] * len(file_bytes)

        file_bytes = torch.tensor(file_bytes, dtype=torch.long)
        file_masks = torch.tensor(file_masks, dtype=torch.long)

        return file_bytes, file_plan, file_masks


def process_one_batch(batch, plan=None):
    input_patches, input_masks = batch
    
    return model(plan, input_patches, input_masks).loss


# do one epoch for training
def train_epoch(epoch):
    tqdm_train_set = tqdm(train_set)
    total_train_loss = 0
    iter_idx = 1
    model.train()
    
    optimizer.zero_grad(set_to_none=True)
    train_steps = (epoch - 1) * len(train_set)

    for i, batch in enumerate(tqdm_train_set):
        input_patches, plan, input_masks = batch[0].to(device), batch[1].to(device), batch[2].to(device)
        
        with autocast("cuda", dtype=torch.bfloat16):
            # Calculate loss
            loss = process_one_batch((input_patches, input_masks), plan)
            # Scale loss for gradient accumulation
            loss = loss / ACCUMULATION_STEPS
        
        loss.backward()
        
        # Track loss for logging (multiply back to get real scale)
        current_loss = loss.item() * ACCUMULATION_STEPS
        total_train_loss += current_loss

        if (i + 1) % ACCUMULATION_STEPS == 0:
            # Gradient clipping is often good practice in DDP, though optional
            # torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            
            optimizer.step()
            lr_scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            train_steps += 1

            if global_rank == 0 and WANDB_LOGGING:
                wandb.log({"train_loss": total_train_loss / iter_idx}, step=train_steps)

        tqdm_train_set.set_postfix({str(global_rank) + '_train_loss': total_train_loss / iter_idx})
        iter_idx += 1
        
        del loss, input_patches, input_masks, batch, plan
        if iter_idx % 50 == 0: # Increased interval to reduce overhead
            torch.cuda.empty_cache()

    # Process remaining gradients
    if len(train_set) % ACCUMULATION_STEPS != 0:
        optimizer.step()
        lr_scheduler.step()
        optimizer.zero_grad(set_to_none=True)

    return total_train_loss / (iter_idx - 1)


# do one epoch for eval
def eval_epoch():
    tqdm_eval_set = tqdm(eval_set)
    model.eval()
    
    # Use tensors for metrics so we can easily reduce them across GPUs later
    total_eval_loss = torch.tensor(0.0, device=device)
    total_steps = torch.tensor(0.0, device=device)
    
    for batch in tqdm_eval_set:
        input_patches, plan, input_masks = batch[0].to(device), batch[1].to(device), batch[2].to(device)
        
        with torch.no_grad():
            with autocast("cuda", dtype=torch.bfloat16):
                loss = process_one_batch((input_patches, input_masks), plan)
        
        # Accumulate local loss (detach to save memory)
        total_eval_loss += loss.detach()
        total_steps += 1
        
        # Update progress bar with LOCAL loss (approximate, but fast)
        tqdm_eval_set.set_postfix({str(global_rank) + '_eval_loss': loss.item()})

    # --- SYNCHRONIZATION POINT ---
    # Sum the total loss and total steps from ALL GPUs
    if world_size > 1:
        dist.all_reduce(total_eval_loss, op=dist.ReduceOp.SUM)
        dist.all_reduce(total_steps, op=dist.ReduceOp.SUM)
    
    # Calculate global average
    avg_loss = total_eval_loss / total_steps
    return avg_loss.item()


# train and eval
if __name__ == "__main__":

    # Initialize wandb
    if WANDB_LOGGING and global_rank == 0:
        wandb.login(key=WANDB_KEY)
        wandb.init(project="notagen", name=WANDB_NAME)

    # load data
    with open(DATA_TRAIN_INDEX_PATH, "r", encoding="utf-8") as f:
        print("Loading Data...")
        train_files = []
        for line in f:
            train_files.append(json.loads(line))

    with open(DATA_EVAL_INDEX_PATH, "r", encoding="utf-8") as f:
        print("Loading Data...")
        eval_files = []
        for line in f:
            eval_files.append(json.loads(line))

    train_batch_nums = int(len(train_files) / batch_size)
    eval_batch_nums = int(len(eval_files) / batch_size)

    random.shuffle(train_files)
    random.shuffle(eval_files)

    train_files = train_files[:train_batch_nums * batch_size]
    eval_files = eval_files[:eval_batch_nums * batch_size]

    if DEBUG:
        # Reduce eval set size for faster testing
        train_files = train_files[:1000]
        eval_files = eval_files[:200]

    # train_set = NotaGenDataset(train_files, DATA_ROOT, pitch_shift_range=(-5, 5))
    train_set = NotaGenDataset(train_files, DATA_ROOT, pitch_shift_range=(0, 0), split="train")
    eval_set = NotaGenDataset(eval_files, DATA_ROOT, pitch_shift_range=(0, 0), split="eval")

    del train_files, eval_files

    train_sampler = DistributedSampler(train_set, num_replicas=world_size, rank=local_rank)
    eval_sampler = DistributedSampler(eval_set, num_replicas=world_size, rank=local_rank)

    train_set = DataLoader(train_set,
                           batch_size=batch_size,
                           collate_fn=collate_batch,
                           num_workers=4,
                           sampler=train_sampler,
                           shuffle=(train_sampler is None))
    eval_set = DataLoader(eval_set,
                          batch_size=batch_size,
                          collate_fn=collate_batch,
                          num_workers=4,
                          sampler=eval_sampler,
                          shuffle=(train_sampler is None))

    model = CustomLMHeadModel(encoder_config=patch_config, decoder_config=char_config)
    # print parameter number
    print("Parameter Number: "+str(sum(p.numel() for p in model.parameters() if p.requires_grad)))
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    lr_scheduler = get_constant_schedule_with_warmup(optimizer=optimizer, num_warmup_steps=1000)
    scaler = GradScaler()

    pre_epoch = 0
    best_epoch = 0
    min_eval_loss = 100

    if LOAD_FROM_CHECKPOINT and os.path.exists(WEIGHTS_PATH):
        checkpoint = torch.load(WEIGHTS_PATH, map_location='cpu')
        
        # Use a more robust way to load DDP models
        state_dict = checkpoint['model']
        if any(key.startswith('module.') for key in state_dict.keys()):
            # A DDP model was saved, so strip 'module.' prefix
            from collections import OrderedDict
            new_state_dict = OrderedDict()
            for k, v in state_dict.items():
                name = k[7:] # remove `module.`
                new_state_dict[name] = v
            model.load_state_dict(new_state_dict)
        else:
            # A non-DDP model was saved
            model.load_state_dict(state_dict)
            
        optimizer.load_state_dict(checkpoint['optimizer'])
        lr_scheduler.load_state_dict(checkpoint['lr_sched'])
        pre_epoch = checkpoint['epoch']
        best_epoch = checkpoint['best_epoch']
        # min_eval_loss = checkpoint['min_eval_loss']
        print(f"Successfully Loaded Checkpoint from Epoch {pre_epoch}")
        del checkpoint, state_dict # Free up memory
        gc.collect()
        torch.cuda.empty_cache()

    # Now move the fully configured model to the correct GPU device
    model = model.to(device)

    # Move optimizer state to the correct GPU device
    for state in optimizer.state.values():
        for k, v in state.items():
            if isinstance(v, torch.Tensor):
                state[k] = v.to(device)

    # Finally, wrap the model with DDP
    if world_size > 1:
        model = DDP(model, device_ids=[local_rank], output_device=local_rank, find_unused_parameters=True)

    for epoch in range(1 + pre_epoch, NUM_EPOCHS + 1):
        train_sampler.set_epoch(epoch)
        eval_sampler.set_epoch(epoch)
        print('-' * 21 + "Epoch " + str(epoch) + '-' * 21)
        if hasattr(train_set.dataset, "on_epoch_end"):
            train_set.dataset.on_epoch_end()
        train_loss = train_epoch(epoch)
        eval_loss = eval_epoch()
        if global_rank == 0:
            with open(LOGS_PATH, 'a') as f:
                f.write("Epoch " + str(epoch) + "\ntrain_loss: " + str(train_loss) + "\neval_loss: " + str(eval_loss) +
                        "\ntime: " + time.asctime(time.localtime(time.time())) + "\n\n")
            if eval_loss < min_eval_loss:
                best_epoch = epoch
                min_eval_loss = eval_loss
                checkpoint = {
                    'model': model.module.state_dict() if hasattr(model, "module") else model.state_dict(),
                    'optimizer': optimizer.state_dict(),
                    'lr_sched': lr_scheduler.state_dict(),
                    'epoch': epoch,
                    'best_epoch': best_epoch,
                    'min_eval_loss': min_eval_loss
                }
                torch.save(checkpoint, WEIGHTS_PATH)

        if world_size > 1:
            dist.barrier()

    if global_rank == 0:
        print("Best Eval Epoch : " + str(best_epoch))
        print("Min Eval Loss : " + str(min_eval_loss))