import argparse
from os import path, makedirs
from glob import glob
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import sys
sys.stdout.reconfigure(line_buffering=True)
from utils.xml_augment import transpose_musicxml

# Directories to search for XML files
dirs = [
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/Wikifonia_Dataset_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/PDMX_MXL_abci/mxl_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/SymphonyNet_Dataset_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/ASAP_MXL_abci",
    "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/MS3_MXL_abci"
]

# Gather all XML files recursively
files = []
for d in dirs:
    files.extend(glob(f"{d}/**/*.xml", recursive=True))


def augment_file(file: str, semitone_change: int):
    if not file.endswith(".xml"):
        return f"Skipped unsupported format: {file}"

    augmented_filepath = file.replace(
        "ABC_Dataset/ABC_Dataset", "ABC_Dataset/ABC_Dataset/Augmented_Datasets"
    )

    change = {
        -3: "down3",
        -2: "down2",
        -1: "down1",
        1: "up1",
        2: "up2",
        3: "up3"
    }.get(semitone_change, f"{semitone_change:+d}")

    augmented_filepath = augmented_filepath.replace(
        ".xml", f"_augmented_{change}.xml"
    )

    # Check if augmented file already exists
    if path.exists(augmented_filepath):
        return f"Skipped existing file: {augmented_filepath}"

    augmented_dir = path.dirname(augmented_filepath)
    if not path.exists(augmented_dir):
        makedirs(augmented_dir, exist_ok=True)

    try:
        transpose_musicxml(file, augmented_filepath, semitones=semitone_change)
        return f"Augmented {augmented_filepath}"
    except Exception as e:
        return f"Error augmenting {file} with {semitone_change:+d}: {e}"


def main():
    output_base_dir = "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/Augmented_Datasets"
    if not path.exists(output_base_dir):
        makedirs(output_base_dir)
        print(f"Created output directory: {output_base_dir}")
        
    semitone_changes = [-3, -2, -1, 1, 2, 3]
    results = []

    with ProcessPoolExecutor(max_workers=12) as executor:
        futures = {
            executor.submit(augment_file, f, s): (f, s)
            for f in files
            for s in semitone_changes
        }

        with tqdm(total=len(futures), desc="Processing XML files") as pbar:
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                pbar.update(1)

    for r in results:
        print(r)

    # Write results to a log file
    log_output_dir = "/data/scratch/eey549/ABC_Dataset/ABC_Dataset/"
    log_file = path.join(log_output_dir, "augmentation_log.txt")
    with open(log_file, "w") as logf:
        for r in results:
            logf.write(r + "\n")
    print(f"Augmentation log written to {log_file}")


if __name__ == "__main__":
    print(f"Found {len(files)} XML files to process.")
    main()
