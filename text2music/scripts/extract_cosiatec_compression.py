# module load openjdk/17.0.11_9-gcc-14.2.0

# java -jar /data/home/acw769/omnisia-recursia-rrt-mml-2019/omnisia.jar \
# -i /gpfs/scratch/acw769/text2score/infer_align/1/mid/midi.mid \
# -o /gpfs/scratch/acw769/text2score/infer_align/1/structure/


import os
import sys
import subprocess
import glob
import math

def run_omnisia(jar_path, midi_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "java",
        "-jar",
        jar_path,
        "-i",
        midi_path,
        "-o",
        output_dir
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print(f"Failed on {midi_path}")
        return False

    return True


def find_cos_file(structure_dir):

    timestamp_dirs = glob.glob(os.path.join(structure_dir, "*"))

    if not timestamp_dirs:
        return None

    timestamp_dirs.sort(key=os.path.getmtime, reverse=True)

    for d in timestamp_dirs:
        cos_files = glob.glob(os.path.join(d, "*.cos"))

        if cos_files:
            return cos_files[0]

    return None


def extract_compression_ratio(cos_path):

    with open(cos_path, "r") as f:
        for line in f:
            if line.startswith("compressionRatio"):
                parts = line.strip().split()

                if len(parts) == 2:
                    return float(parts[1])

    return None


def main():

    if len(sys.argv) != 4:
        print("Usage:")
        print("python script.py <root_dir> <omnisia.jar> <output_txt>")
        sys.exit(1)

    root_dir = sys.argv[1]
    jar_path = sys.argv[2]
    output_txt = sys.argv[3]

    ratios = []

    folders = sorted([
        d for d in os.listdir(root_dir)
        if os.path.isdir(os.path.join(root_dir, d)) and d.isdigit()
    ], key=lambda x: int(x))


    for folder in folders:

        base_path = os.path.join(root_dir, folder)

        midi_dir = os.path.join(base_path, "mid")
        structure_dir = os.path.join(base_path, "structure")

        midi_files = glob.glob(os.path.join(midi_dir, "*.mid"))

        if not midi_files:
            print(f"No midi in {folder}")
            continue

        midi_file = midi_files[0]

        print(f"Processing {folder}")

        success = run_omnisia(jar_path, midi_file, structure_dir)

        if not success:
            continue

        cos_file = find_cos_file(structure_dir)

        if cos_file is None:
            print(f"No cos file in {folder}")
            continue

        ratio = extract_compression_ratio(cos_file)

        if ratio is not None:
            ratios.append(ratio)
            print(f"Compression ratio: {ratio}")
        else:
            print(f"Ratio missing in {folder}")


    valid_ratios = [r for r in ratios if not math.isnan(r)]

    if not valid_ratios:
        print("No ratios found")
        return

    avg = sum(valid_ratios) / len(valid_ratios)

    with open(output_txt, "w") as f:

        f.write("Compression ratios:\n")

        for r in ratios:
            f.write(f"{r}\n")

        f.write("\n")
        f.write(f"Average compression ratio: {avg}\n")
        f.write(f"Total files: {len(ratios)}\n")
        f.write(f"Valid files in average: {len(valid_ratios)}\n")

    print(f"Average: {avg}")


if __name__ == "__main__":
    main()
