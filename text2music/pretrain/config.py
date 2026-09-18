import os

# Configuration for the data
DATA_TRAIN_INDEX_PATH = "text2music/data/train_with_genres.jsonl" 
DATA_EVAL_INDEX_PATH  = "text2music/data/validation_with_genres.jsonl"
DATA_ROOT = "/gpfs/scratch/acw769/ABC_Dataset/"               # Root directory for the data

# Configuration for the model
PATCH_STREAM = True
PATCH_SIZE = 16                                                 # Patch Size
PATCH_LENGTH = 2048                                             # Patch Length
CHAR_NUM_LAYERS = 6                                             # Number of layers in the decoder
PATCH_NUM_LAYERS = 20                                           # Number of layers in the encoder
HIDDEN_SIZE = 768                                               # Hidden Size

# Configuration for the training
BATCH_SIZE = 8         
LEARNING_RATE = 1e-4   
NUM_EPOCHS = 40                                                 # Number of epochs to train for (if early stopping doesn't intervene)
ACCUMULATION_STEPS = 4                                          # Accumulation steps to simulate large batch size
PATCH_SAMPLING_BATCH_SIZE = 0                                   # Batch size for patch during training, 0 for full conaudio
LOAD_FROM_CHECKPOINT = True                                    # Whether to load weights from a checkpoint
WANDB_LOGGING = False                                           # Whether to log to wandb
WANDB_KEY = '<your_wandb_key>'
DEBUG = False                                                    # Whether to run in debug mode (smaller dataset, more logging)

EXP_TAG = 'pretrain'                                            # Experiment tag for differentiation
NAME =  EXP_TAG + \
        "_p_size_" + str(PATCH_SIZE) + \
        "_p_length_" + str(PATCH_LENGTH) + \
        "_p_layers_" + str(PATCH_NUM_LAYERS) + \
        "_c_layers_" + str(CHAR_NUM_LAYERS) + \
        "_h_size_" + str(HIDDEN_SIZE) + \
        "_lr_" + str(LEARNING_RATE) + \
        "_batch_" + str(BATCH_SIZE)

WEIGHTS_PATH = "weights_notagen_" + NAME + ".pth"                  # Path to save weights
WEIGHTS_PATH = "/data/home/acw769/text2score/text2music/artifacts/logs_notagen_pretrain_p_size_16_p_length_2048_p_layers_20_c_layers_6_h_size_768_lr_0.0001_batch_16.pth"
LOGS_PATH    = "logs_notagen_"    + NAME + ".txt"                     # Path to save logs
LOGS_PATH    = "/data/home/acw769/text2score/text2music/artifacts/logs_notagen_pretrain_p_size_16_p_length_2048_p_layers_20_c_layers_6_h_size_768_lr_0.0001_batch_16.txt" 
WANDB_NAME = NAME

                                                                                   
