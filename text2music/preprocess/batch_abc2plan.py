import os
from glob import glob
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

# Import your preprocessor functions
from text2music.preprocess.abci2abc import convert_abci_list_to_abc
from text2music.preprocess.abc2xml import convert_abc_list_to_xml
from text2music.preprocess.xml2plan import convert_xml_list_to_plan_pkl

# -----------------------------------------------------
# DIRECTORIES CONTAINING .abci FILES
# -----------------------------------------------------
ABCI_DIRS = [
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

# -----------------------------------------------------
# RESOLVE ABC2XML SCRIPT PATH RELATIVE TO THIS FILE
# -----------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
ABC2XML_SCRIPT = os.path.join(PROJECT_ROOT, "data", "utils", "abc_helper", "abc2xml.py")

# -----------------------------------------------------
# PROCESS A SINGLE ABCI FILE
# -----------------------------------------------------
def process_one_abci_file(abci_path):
    try:
        # 1. ABCI → ABC
        convert_abci_list_to_abc([abci_path])

        abc_path = abci_path.replace(".abci", ".abc")
        if not os.path.exists(abc_path):
            return False, f"ABCI→ABC FAILED for {abci_path}"

        # 2. ABC → XML
        # IMPORTANT: do NOT fully suppress subprocess stdout
        # with suppress_subprocess():  
        convert_abc_list_to_xml([abc_path], abc2xml_script="text2music/data/utils/abc_helper/abc2xml.py")

        xml_path = abc_path.replace(".abc", ".xml")
        if not os.path.exists(xml_path):
            return False, f"ABC→XML FAILED for {abc_path}"

        # 3. XML → PKL
        convert_xml_list_to_plan_pkl([xml_path])

        pkl_path = xml_path.replace(".xml", ".pkl")
        if not os.path.exists(pkl_path):
            return False, f"XML→PKL FAILED for {xml_path}"

        # 4. CLEAN UP
        try:
            os.remove(abc_path)
            os.remove(xml_path)
        except:
            pass

        return True, f"SUCCESS {abci_path}"

    except Exception as e:
        return False, f"ERROR processing {abci_path}: {e}"

# -----------------------------------------------------
# MAIN PARALLEL PIPELINE
# -----------------------------------------------------
def main():
    # Collect all .abci files
    abci_files = []
    for d in ABCI_DIRS:
        abci_files.extend(glob(f"{d}/**/*.abci", recursive=True))

    print(f"Found {len(abci_files)} .abci files.")

    # Setup logs
    log_folder = os.path.join(PROJECT_ROOT, "preprocess", "logs")
    os.makedirs(log_folder, exist_ok=True)
    success_log_path = os.path.join(log_folder, "success_log.txt")
    failure_log_path = os.path.join(log_folder, "failure_log.txt")
    open(success_log_path, "w").close()
    open(failure_log_path, "w").close()

    max_workers = min(90, os.cpu_count())
    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for success, message in tqdm(
            executor.map(process_one_abci_file, abci_files),
            total=len(abci_files),
            desc="Full ABCI → PKL Pipeline",
            dynamic_ncols=True
        ):
            results.append((success, message))
            if success:
                with open(success_log_path, "a") as f:
                    f.write(message + "\n")
            else:
                with open(failure_log_path, "a") as f:
                    f.write(message + "\n")

    print("\n--- PIPELINE COMPLETED ---")
    print(f"Successes logged at: {success_log_path}")
    print(f"Failures logged at: {failure_log_path}")


if __name__ == "__main__":
    main()
