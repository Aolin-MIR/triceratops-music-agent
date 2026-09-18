import os
import re
import shutil
import subprocess
from tqdm import tqdm
from multiprocessing import Pool
import argparse

# ====== WORKERS ======

def clean_abc_worker(file_list):
    """
    Step 1: Clean ABCI files and move them to the 'abc' folder.
    """
    for file_path in file_list:
        try:
            # file_path: .../[num]/interleaved/file.abc
            numbered_dir = os.path.dirname(os.path.dirname(file_path))
            abc_dir = os.path.join(numbered_dir, "abc")
            os.makedirs(abc_dir, exist_ok=True)
            
            filename = os.path.basename(file_path)
            clean_abc_path = os.path.join(abc_dir, filename)

            with open(file_path, 'r', encoding='utf-8') as f:
                data = f.read()
            
            # Logic from convert_abci_to_abc_logic
            data = re.sub(r'%\d+', '', data)
            data = re.sub(r'(?<!\n)(\[V:\d+\])', r'\n\1', data)
            data = re.sub(r'\n{2,}', '\n', data)
            lines = [line.strip() for line in data.splitlines()]
            cleaned_data = "\n".join(lines)
            
            with open(clean_abc_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_data)
        except Exception as e:
            with open("logs/combined_error_log.txt", "a") as f:
                f.write(f"CLEAN ERROR: {file_path} {str(e)}\n")

def convert_to_xml_worker(file_list):
    """
    Step 2: Convert 'abc_injected' files to 'xml'.
    """
    cmd_base = 'python text2music/data/utils/abc_helper/abc2xml.py '
    
    for file_path in file_list:
        try:
            # file_path: .../[num]/abc_injected/file.abc
            numbered_dir = os.path.dirname(os.path.dirname(file_path))
            xml_dir = os.path.join(numbered_dir, "xml")
            os.makedirs(xml_dir, exist_ok=True)
            
            filename = os.path.basename(file_path)
            base_name = os.path.splitext(filename)[0]
            xml_output_path = os.path.join(xml_dir, base_name + ".xml")

            p = subprocess.Popen(cmd_base + '"' + file_path + '"', 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE, 
                                 shell=True)
            stdout, stderr = p.communicate()
            output = stdout.decode('utf-8')

            if not output:
                with open("logs/combined_error_log.txt", "a") as f:
                    f.write(f"XML EMPTY: {file_path} - {stderr.decode('utf-8')}\n")
            else:
                with open(xml_output_path, 'w', encoding='utf-8') as f:
                    f.write(output)
        except Exception as e:
            with open("logs/combined_error_log.txt", "a") as f:
                f.write(f"XML CONVERT ERROR: {file_path} {str(e)}\n")

# ====== MAIN ======

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root_folder', type=str, default="./text2music/artifacts/output/")
    args = parser.parse_args()

    ROOT_FOLDER = args.root_folder
    os.makedirs("logs", exist_ok=True)
    cpu_count = os.cpu_count() or 4

    # 1. FIND FILES
    interleaved_files = []
    for item in os.listdir(ROOT_FOLDER):
        subdir = os.path.join(ROOT_FOLDER, item)
        if os.path.isdir(subdir):
            inter_path = os.path.join(subdir, "interleaved")
            if os.path.exists(inter_path):
                # Clean old output dirs
                for fld in ["abc", "abc_injected", "xml"]:
                    target = os.path.join(subdir, fld)
                    if os.path.exists(target): shutil.rmtree(target)
                
                for f in os.listdir(inter_path):
                    if f.endswith(".abc"):
                        interleaved_files.append(os.path.join(inter_path, f))

    if not interleaved_files:
        print("No files found.")
        exit()

    # 2. RUN CLEANING (Step 1)
    print(f"🧹 Cleaning {len(interleaved_files)} files...")
    chunks = [interleaved_files[i::cpu_count] for i in range(cpu_count)]
    with Pool(cpu_count) as pool:
        pool.map(clean_abc_worker, chunks)

    # 3. RUN MIDI INJECTION (Step 2)
    # This runs once on the whole directory as requested
    print(f"🎹 Injecting MIDI programs in {ROOT_FOLDER}...")
    injection_cmd = f"python text2music/data/utils/inject_midi_program.py --data_dir {ROOT_FOLDER}"
    subprocess.run(injection_cmd, shell=True)

    # 4. FIND INJECTED FILES FOR XML CONVERSION
    injected_files = []
    for item in os.listdir(ROOT_FOLDER):
        injected_path = os.path.join(ROOT_FOLDER, item, "abc_injected")
        if os.path.exists(injected_path):
            for f in os.listdir(injected_path):
                if f.endswith(".abc"):
                    injected_files.append(os.path.join(injected_path, f))

    # 5. CONVERT TO XML (Step 3)
    print(f"🎼 Converting {len(injected_files)} injected files to XML...")
    injected_chunks = [injected_files[i::cpu_count] for i in range(cpu_count)]
    with Pool(cpu_count) as pool:
        pool.map(convert_to_xml_worker, injected_chunks)

    print("✅ Done! Sequence: interleaved -> abc -> abc_injected -> xml")