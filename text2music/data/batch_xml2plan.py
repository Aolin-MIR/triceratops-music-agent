from utils.xml2plan import get_full_plan_pipeline
from glob import glob
from tqdm import tqdm
import os
import pickle
import json
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed

def convert_numpy(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(i) for i in obj]
    elif isinstance(obj, set):
        return [convert_numpy(i) for i in obj]  # Convert set to list
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

dirs = [
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/ABC_Notation_Dataset_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/Wikifonia_Dataset_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/PDMX_MXL_abci/mxl_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/SymphonyNet_Dataset_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/ASAP_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/MS3_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/Augmented_Datasets/Wikifonia_Dataset_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/Augmented_Datasets/PDMX_MXL_abci/mxl_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/Augmented_Datasets/SymphonyNet_Dataset_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/Augmented_Datasets/ASAP_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/Augmented_Datasets/MS3_MXL_abci"
]

files = []
for d in dirs:
    files.extend(glob(f"{d}/**/*.xml", recursive=True))

# files = files[:5]  # Limit to first 5 files for testing

def process_file(file):
    # if file.endswith(".mxl"):
        # json_path = file.replace(".mxl", ".json")
        # pkl_path = file.replace(".mxl", ".pkl")
    if file.endswith(".xml"):
        # json_path = file.replace(".xml", ".json")
        pkl_path = file.replace(".xml", ".pkl")
    else:
        return f"Skipped unsupported format: {file}"

    try:
        plan = get_full_plan_pipeline(file)
        plan = convert_numpy(plan)
        # with open(json_path, "w") as f:
        #     json.dump(plan, f, indent=2, ensure_ascii=False)
        with open(pkl_path, "wb") as f:
            pickle.dump(plan, f)
        return f"Processed {pkl_path}"
    except Exception as e:
        return f"Error processing {file}: {e}"

def main():
    results = []
    with ProcessPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(process_file, f): f for f in files}
        with tqdm(total=len(futures), desc="Processing XML files") as pbar:
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                pbar.update(1)

    for r in results:
        print(r)

if __name__ == "__main__":
    main()
