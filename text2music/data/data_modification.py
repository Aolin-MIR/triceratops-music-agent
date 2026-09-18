import os
import json
import random
import re
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor

# -------------------------
# Configuration
# -------------------------
DATA_ROOT = "/data/scratch/eey549/ABC_Dataset/ABC_Dataset"

TRAIN_IN = "/data/home/acw769/text2score/text2music/data/train_with_genres.jsonl"
VAL_IN = "/data/home/acw769/text2score/text2music/data/validation_with_genres.jsonl"

TRAIN_OUT = "/data/home/acw769/text2score/text2music/data/train_new.jsonl"
VAL_OUT = "/data/home/acw769/text2score/text2music/data/validation_new.jsonl"

PDMX_CSV = "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/PDMX_MXL_abci/PDMX.csv"
RECENT_PKL_LIST = "recent_pkls.txt"

RANDOM_SEED = 42
NUM_WORKERS = min(8, os.cpu_count())

AUGMENT_RE = re.compile(r"_augmented_.*$")

# -------------------------
# Utilities
# -------------------------
def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]

def write_jsonl(path, data):
    with open(path, "w") as f:
        for entry in data:
            f.write(json.dumps(entry) + "\n")

def read_abci_key_fast(path):
    try:
        with open(path, "r") as f:
            for _ in range(20):
                line = f.readline()
                if not line:
                    break
                if line.startswith("K:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "None"

def build_entry(abs_abci_path):
    rel_path = os.path.relpath(abs_abci_path, DATA_ROOT)
    key = read_abci_key_fast(abs_abci_path)
    return {"path": rel_path, "key": key}

# -------------------------
# PKL → ABCI filtering (fast)
# -------------------------
def load_recent_abci_paths(pkl_list_path):
    abci_paths = set()
    with open(pkl_list_path) as f:
        for line in f:
            pkl = line.strip()
            if pkl.endswith(".pkl"):
                abci = pkl[:-4] + ".abci"
                abci_paths.add(os.path.relpath(abci, DATA_ROOT))
    return abci_paths

# -------------------------
# Genre handling
# -------------------------
def build_genre_map(csv_path):
    df = pd.read_csv(csv_path, low_memory=False)
    df["basename"] = df["path"].apply(
        lambda x: os.path.splitext(os.path.basename(str(x)))[0]
    )
    df["genres"] = df["genres"].replace("NA", pd.NA).where(pd.notna, None)
    return df.set_index("basename")["genres"].to_dict()

# def strip_augmentation(basename):
#     return AUGMENT_RE.sub("", basename)

def normalize_basename(basename):
    # remove augmentation suffix
    basename = re.sub(r"_augmented_.*$", "", basename)
    # remove trailing numeric or movement suffixes
    basename = re.sub(r"[_-]\d+$", "", basename)
    return basename

# def assign_genre(entry, genre_map):
#     path = entry["path"]

#     if "SymphonyNet_Dataset_MXL_abci" in path:
#         entry["genre"] = "symphony"
#         return entry

#     if "ASAP_MXL_abci" in path:
#         entry["genre"] = "classical piano"
#         return entry

#     basename = os.path.splitext(os.path.basename(path))[0]
#     basename = strip_augmentation(basename)
#     entry["genre"] = genre_map.get(basename)

#     return entry

def assign_genre(entry, genre_map):
    path = entry["path"]

    if "SymphonyNet_Dataset_MXL_abci" in path:
        entry["genre"] = "symphony"
        return entry

    if "ASAP_MXL_abci" in path:
        entry["genre"] = "classical piano"
        return entry

    basename = os.path.splitext(os.path.basename(path))[0]
    basename = normalize_basename(basename)

    entry["genre"] = genre_map.get(basename)
    return entry

# -------------------------
# Main
# -------------------------
def main():
    random.seed(RANDOM_SEED)

    print("Loading existing train/validation splits...")
    train_existing = read_jsonl(TRAIN_IN)
    val_existing = read_jsonl(VAL_IN)

    existing_paths = {e["path"] for e in train_existing + val_existing}
    val_size = len(val_existing)

    print(f"Existing split: {len(train_existing)} train / {len(val_existing)} validation")

    print("Loading recent PKL-derived ABCI paths...")
    recent_abci = load_recent_abci_paths(RECENT_PKL_LIST)
    print(f"Recent eligible files: {len(recent_abci)}")

    new_rel_paths = list(recent_abci - existing_paths)
    print(f"New files to consider: {len(new_rel_paths)}")

    new_abs_paths = [os.path.join(DATA_ROOT, p) for p in new_rel_paths]

    print("Extracting keys (parallel, header-only)...")
    with ProcessPoolExecutor(NUM_WORKERS) as ex:
        new_entries = list(
            tqdm(ex.map(build_entry, new_abs_paths), total=len(new_abs_paths))
        )

    random.shuffle(new_entries)

    n_new_val = max(0, val_size - len(val_existing))
    new_val = new_entries[:n_new_val]
    new_train = new_entries[n_new_val:]

    train_all = train_existing + new_train
    val_all = val_existing + new_val

    print(f"Final split: {len(train_all)} train / {len(val_all)} validation")

    print("Assigning genres...")
    genre_map = build_genre_map(PDMX_CSV)

    train_all = [assign_genre(e, genre_map) for e in tqdm(train_all)]
    val_all = [assign_genre(e, genre_map) for e in tqdm(val_all)]

    print("Writing output files...")
    write_jsonl(TRAIN_OUT, train_all)
    write_jsonl(VAL_OUT, val_all)

    print("Done.")

if __name__ == "__main__":
    main()
