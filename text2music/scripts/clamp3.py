import argparse
import json
import os
import shutil


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json-file",
        default="/data/home/acw769/text2score/text2music/artifacts/evaluation/prompts_with_qwen_plan.json",
        help="Path to the JSON file containing prompt/id entries.",
    )
    parser.add_argument(
        "--in-directory",
        default="/gpfs/scratch/acw769/text2score/Qwen2.5-14B-Instruct/",
        help="Input directory to search recursively for .mid files.",
    )
    parser.add_argument(
        "--out-directory",
        default="/gpfs/scratch/acw769/text2score/Qwen2.5-14B-Instruct_clamp/",
        help="Output directory where query_dir and ref_dir will be created.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    prompts = {}
    for item in data:
        item_prompt = item["prompt"]
        item_id = item["id"]
        prompts[item_id] = item_prompt

    # Get all mid files in the input directory recursively
    mid_files = []
    for root, dirs, files in os.walk(args.in_directory):
        for file in files:
            if file.endswith(".mid"):
                mid_files.append(os.path.join(root, file))

    # /gpfs/scratch/acw769/text2score/text2score/69/mid/69_output.mid

    # This is an example output file path. We want to read the mid file, extract the ID (69 in this case), and then use that ID to get the corresponding prompt from the prompts dictionary. We will then write the prompt to a new text file in the output directory.
    # The output directory should have a query_dir and a ref_dir. The query_dir will contain the prompts as txt files (sample1.txt, etc.) and the ref_dir will contain the mid files (sample1.mid).
    for mid_file in mid_files:
        # Extract the ID from the file path
        file_name = os.path.basename(mid_file) # Example: 69_output.mid
        # File id is in the filepath before mid and after the last slash.
        file_id = mid_file.split("/")[-3] # Example: 69

        # Get the corresponding prompt from the prompts dictionary
        prompt = prompts[int(file_id)]

        # Write the prompt to a new text file in the output directory
        query_dir = os.path.join(args.out_directory, "query_dir")
        ref_dir = os.path.join(args.out_directory, "ref_dir")

        # Create the directories if they don't exist
        os.makedirs(query_dir, exist_ok=True)
        os.makedirs(ref_dir, exist_ok=True)

        # Write the prompt to a text file in the query directory
        with open(os.path.join(query_dir, f"{file_id}.txt"), "w", encoding="utf-8") as f:
            f.write(prompt)

        # Copy the mid file to the ref directory
        # os.system(f"cp {mid_file} {os.path.join(ref_dir, f'{file_id}.mid')}")
        shutil.copy(mid_file, os.path.join(ref_dir, f'{file_id}.mid'))


if __name__ == "__main__":
    main()
