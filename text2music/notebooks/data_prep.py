import os
import json
import random
import pandas as pd
from tqdm import tqdm

# --- 1. Define Paths ---
csv_path = "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/PDMX_MXL_abci/PDMX.csv"
train_in_path = "/data/home/acw769/text2score/text2music/data/train.jsonl"
train_out_path = "/data/home/acw769/text2score/text2music/data/train_with_genres.jsonl"
val_out_path = "/data/home/acw769/text2score/text2music/data/validation_with_genres.jsonl"

VAL_SIZE = 10000  # Desired validation sample size
RANDOM_SEED = 42

# --- 2. Build Genre Lookup Map from CSV ---
print(f"Building genre lookup map from {csv_path}...")
genre_map = {}

try:
    df = pd.read_csv(csv_path, low_memory=False)
    if 'path' not in df.columns or 'genres' not in df.columns:
        raise ValueError(f"Missing required columns 'path' or 'genres' in {csv_path}")

    df['basename'] = df['path'].apply(lambda x: os.path.splitext(os.path.basename(str(x)))[0])
    df['genres'] = df['genres'].replace('NA', pd.NA).where(pd.notna, None)
    genre_map = df.set_index('basename')['genres'].to_dict()
    print(f"✅ Created genre map with {len(genre_map)} entries.")
except Exception as e:
    print(f"❌ Error building genre map: {e}")
    exit(1)

# --- 3. Load Train JSONL ---
print(f"\nLoading {train_in_path}...")
try:
    with open(train_in_path, 'r') as f:
        train_lines = [json.loads(line.strip()) for line in f if line.strip()]
    print(f"✅ Loaded {len(train_lines)} training samples.")
except Exception as e:
    print(f"❌ Failed to load {train_in_path}: {e}")
    exit(1)

# --- 4. Split Train → Train/Validation ---
random.seed(RANDOM_SEED)
if len(train_lines) <= VAL_SIZE:
    print(f"⚠️ Train set has only {len(train_lines)} samples — using all for training, none for validation.")
    val_lines = []
else:
    val_lines = random.sample(train_lines, VAL_SIZE)
    val_ids = set(id(entry) for entry in val_lines)
    train_lines = [entry for entry in train_lines if id(entry) not in val_ids]
    print(f"✅ Split: {len(train_lines)} train / {len(val_lines)} validation samples.")

# --- 5. Define Helper for Genre Assignment ---
def assign_genre(entry):
    file_path = entry.get('path')
    genre_info = None

    if file_path:
        if 'SymphonyNet_Dataset_MXL_abci' in file_path:
            genre_info = 'symphony'
        elif 'ASAP_MXL_abci' in file_path:
            genre_info = 'classical piano'
        else:
            basename = os.path.splitext(os.path.basename(file_path))[0]
            raw_genre = genre_map.get(basename)
            genre_info = None if pd.isna(raw_genre) else raw_genre
    entry['genre'] = genre_info
    return entry

# --- 6. Process and Write Both Files ---
def process_and_write(data, output_path, name):
    print(f"\nProcessing {name} set ({len(data)} samples)...")
    updated_entries = []

    with open(output_path, 'w', encoding='utf-8') as f_out:
        for entry in tqdm(data, desc=f"Writing {name}"):
            entry = assign_genre(entry)
            f_out.write(json.dumps(entry) + '\n')
            if len(updated_entries) < 5:
                updated_entries.append(entry)

    print(f"✅ Wrote {len(data)} {name} samples to {output_path}")
    print(f"--- {name.capitalize()} sample preview ---")
    for e in updated_entries:
        print(json.dumps(e, ensure_ascii=False))
    print()

process_and_write(train_lines, train_out_path, "train")
process_and_write(val_lines, val_out_path, "validation")

print("🎉 All done! Both train_with_genres.jsonl and validation_with_genres.jsonl have been created.")
