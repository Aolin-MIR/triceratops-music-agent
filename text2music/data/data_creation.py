from glob import glob
from tqdm import tqdm
import os
import pickle
import json
import numpy as np
import random
from concurrent.futures import ProcessPoolExecutor, as_completed

# DATA_ROOT_DIR = "/import/c4dm-datasets/ABC_Dataset"


dirs = [
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/"
]

files = []
for d in dirs:
    files.extend(glob(f"{d}/**/*.abci", recursive=True))

# Create train and val sets
random.shuffle(files)
n_val_files = 10000
train_files = files[:-n_val_files]
val_files = files[-n_val_files:]
print(f"Number of train files: {len(train_files)}")
print(f"Number of validation files: {len(val_files)}")

# Read abci file and get key which is usually given in the header as K:E
# The header is usually the first couple of lines
def read_abci_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    key = None
    for line in lines:
        if line.startswith("K:"):
            key = line.split(":")[1].strip()
            break
    return key


def create_jsonl_with_keys(files, output_path):
    """
    Creates a JSONL file where each line is a JSON object with 'path' and 'key'.
    
    Args:
        files (list): List of file paths to process.
        output_path (str): Output path for the .jsonl file.
    """
    with open(output_path, 'w', encoding='utf-8') as f_out:
        for file in tqdm(files, desc="Processing files"):
            key = read_abci_file(file)
            rel_path = os.path.relpath(file, start=os.path.dirname("/data/scratch/eey549/ABC_Dataset/ABC_Dataset/"))
            entry = {
                "path": rel_path,
                "key": key if key else "None"
            }
            json_line = json.dumps(entry)
            f_out.write(json_line + '\n')

# Main function to create the JSON file
def main():

    create_jsonl_with_keys(val_files, "validation.jsonl")
    create_jsonl_with_keys(train_files, "train.jsonl")

if __name__ == "__main__":
    main()
    print("JSON file with keys created successfully.")