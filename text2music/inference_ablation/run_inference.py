import os
import time
import torch
from utils import *
from config import *
from transformers import GPT2Config
import shutil
import argparse
import json
from tqdm import tqdm
from inference import inference_patch

# Define args
parser = argparse.ArgumentParser()
parser.add_argument('--prompt_path_json', type=str, default=None, help='Path to the json file containing the prompt information')
parser.add_argument('--output_folder', type=str, default=None, help='Folder to save the generated outputs')
parser.add_argument('--api_key', type=str, required=False, help='OpenAI API key for verifying the header')
parser.add_argument('--plan_name', type=str, default=None, help='Name of the plan to use for inference')
args = parser.parse_args()

if torch.cuda.is_available():
    device = torch.device("cuda")
else:
    device = torch.device("cpu")

patchilizer = Patchilizer()

patch_config = GPT2Config(num_hidden_layers=PATCH_NUM_LAYERS,
                          max_length=PATCH_LENGTH,
                          max_position_embeddings=PATCH_LENGTH,
                          n_embd=HIDDEN_SIZE,
                          num_attention_heads=HIDDEN_SIZE // 64,
                          vocab_size=1)
byte_config = GPT2Config(num_hidden_layers=CHAR_NUM_LAYERS,
                         max_length=PATCH_SIZE + 1,
                         max_position_embeddings=PATCH_SIZE + 1,
                         hidden_size=HIDDEN_SIZE,
                         num_attention_heads=HIDDEN_SIZE // 64,
                         vocab_size=128)

model = CustomLMHeadModel(encoder_config=patch_config, decoder_config=byte_config)

print("Parameter Number: " + str(sum(p.numel() for p in model.parameters() if p.requires_grad)))

checkpoint = torch.load(INFERENCE_WEIGHTS_PATH, map_location=torch.device(device))
model.load_state_dict(checkpoint['model'])
model = model.to(device)
model.eval()

with open(args.prompt_path_json, "r", encoding="utf-8") as f:
    data = json.load(f)

for item in tqdm(data):
    plan = item[args.plan_name]
    user_prompt = item['prompt']
    file_id = str(item['id'])
    sub_dir = os.path.join(args.output_folder, file_id)
    if not os.path.exists(sub_dir) or not os.path.exists(os.path.join(sub_dir, "original")) or not os.path.exists(os.path.join(sub_dir, "interleaved")):
        os.makedirs(sub_dir, exist_ok=True)
        os.makedirs(os.path.join(sub_dir, "original"), exist_ok=True)
        os.makedirs(os.path.join(sub_dir, "interleaved"), exist_ok=True)

    inference_patch(model, plan, user_prompt, [], pieces=NUM_SAMPLES, output_folder=sub_dir, output_filename=file_id + '_output.abc', device=device, api_key=args.api_key)