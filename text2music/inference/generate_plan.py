import json
import os
from tqdm import tqdm
from openai import OpenAI
from text2music.inference.prompt import get_llm_prompt
import argparse


def save_json(data, output_json):
    output_dir = os.path.dirname(output_json)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    tmp_json = f"{output_json}.tmp"

    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_json, output_json)


if __name__ == "__main__":

    # Define args
    parser = argparse.ArgumentParser()
    parser.add_argument('--api_key', type=str, required=False, help='OpenAI API key for verifying the header')
    parser.add_argument('--input_json', type=str, default="/data/home/acw769/text2score/text2music/artifacts/prompts/prompts_with_ids.json", help='Path to the json file containing the prompt information')
    parser.add_argument('--output_json', type=str, default="/data/home/acw769/text2score/text2music/artifacts/prompts/prompts_with_plan.json", help='Path to the json file to save the prompt information with plans')
    parser.add_argument('--resume', action='store_true', help='Resume from output_json if it already exists')
    args = parser.parse_args()

    client = OpenAI(api_key=args.api_key)

    # 1. Read the JSON file
    input_json = args.output_json if args.resume and os.path.exists(args.output_json) else args.input_json
    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    save_json(data, args.output_json)

    for item in tqdm(data):

        if "openai_plan" not in item.keys():
        
            prompt = get_llm_prompt(item['prompt'])
        
            plan = client.responses.create(
                model="gpt-5.1",
                input=prompt
            )
            item["openai_plan"] = plan.output_text

        save_json(data, args.output_json)
