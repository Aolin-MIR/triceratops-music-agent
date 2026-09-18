import json
import os
import inspect
import re
import torch
import transformers
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM
from text2music.inference_ablation.prompt import get_llm_prompt
import argparse


def generate_plan(tokenizer, model, prompt, max_new_tokens, enable_thinking):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    chat_template_kwargs = {
        "tokenize": False,
        "add_generation_prompt": True,
    }

    # Only pass enable_thinking for models that support it (e.g. Gemma)
    if (
        enable_thinking
        and "enable_thinking"
        in inspect.signature(tokenizer.apply_chat_template).parameters
    ):
        chat_template_kwargs["enable_thinking"] = True

    text = tokenizer.apply_chat_template(
        messages,
        **chat_template_kwargs,
    )

    inputs = tokenizer(
        text,
        return_tensors="pt"
    ).to(model.device)

    input_len = inputs["input_ids"].shape[-1]

    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
    )

    response = tokenizer.decode(
        outputs[0][input_len:],
        skip_special_tokens=True,
    )

    return response.strip()


def generate_llama_plan(pipeline, prompt, max_new_tokens):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    outputs = pipeline(
        messages,
        max_new_tokens=max_new_tokens,
    )
    generated_text = outputs[0]["generated_text"]

    if isinstance(generated_text, list):
        response = generated_text[-1]
        if isinstance(response, dict):
            return response.get("content", "").strip()
        return str(response).strip()

    return str(generated_text).strip()


def extract_answer_text(text):
    answer_match = re.search(r"<answer>(.*?)</answer>", text, flags=re.DOTALL)
    if answer_match:
        return answer_match.group(1).strip()

    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def generate_glm_plan(processor, model, prompt, max_new_tokens):
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"You are a helpful assistant.\n\n{prompt}",
                }
            ],
        }
    ]

    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    generated_ids = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
    )

    output_text = processor.decode(
        generated_ids[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )

    return extract_answer_text(output_text)


def save_json(data, output_json):
    tmp_json = f"{output_json}.tmp"

    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_json, output_json)


def is_llama_model(model_id):
    return "llama" in model_id.lower()


def is_glm_model(model_id):
    return "glm" in model_id.lower()


def get_default_plan_key(model_id):
    if is_llama_model(model_id):
        return "llama_plan"

    if is_glm_model(model_id):
        return "glm_plan"

    model_name = (
        model_id
        .split("/")[-1]
        .lower()
        .replace("-", "_")
    )

    return f"{model_name}_plan"


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--input_json',
        type=str,
        default="/data/home/acw769/text2score/text2music/artifacts/prompts/prompts_with_ids.json",
        help='Path to input JSON file'
    )

    parser.add_argument(
        '--output_json',
        type=str,
        default="/data/home/acw769/text2score/text2music/artifacts/prompts/prompts_with_qwen_plan.json",
        help='Path to output JSON file'
    )

    parser.add_argument(
        '--model_id',
        type=str,
        default="Qwen/Qwen2.5-14B-Instruct",
        help='Hugging Face model id'
    )

    parser.add_argument(
        '--max_new_tokens',
        type=int,
        default=8192,
        help='Maximum number of tokens generated per plan'
    )

    parser.add_argument(
        '--enable_thinking',
        action='store_true',
        help='Enable thinking mode for supported models'
    )

    parser.add_argument(
        '--plan_key',
        type=str,
        default=None,
        help='JSON field name for generated plans'
    )

    args = parser.parse_args()


    if is_llama_model(args.model_id):
        pipeline = transformers.pipeline(
            "text-generation",
            model=args.model_id,
            model_kwargs={"torch_dtype": torch.bfloat16},
            device_map="auto",
        )
        tokenizer = None
        model = None
        processor = None
    elif is_glm_model(args.model_id):
        from transformers import AutoProcessor, Glm4vForConditionalGeneration

        processor = AutoProcessor.from_pretrained(
            args.model_id,
            use_fast=True,
        )

        model = Glm4vForConditionalGeneration.from_pretrained(
            pretrained_model_name_or_path=args.model_id,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )

        tokenizer = None
        pipeline = None
    else:
        tokenizer = AutoTokenizer.from_pretrained(
            args.model_id
        )

        model = AutoModelForCausalLM.from_pretrained(
            args.model_id,
            torch_dtype="auto",
            device_map="auto",
        )

        pipeline = None
        processor = None

    plan_key = args.plan_key or get_default_plan_key(args.model_id)


    # Read input JSON
    with open(args.input_json, "r", encoding="utf-8") as f:
        data = json.load(f)


    # Create initial output file
    save_json(data, args.output_json)


    for item in tqdm(data):

        if plan_key not in item:

            prompt = get_llm_prompt(
                item["prompt"]
            )

            if is_llama_model(args.model_id):
                item[plan_key] = generate_llama_plan(
                    pipeline,
                    prompt,
                    args.max_new_tokens,
                )
            elif is_glm_model(args.model_id):
                item[plan_key] = generate_glm_plan(
                    processor,
                    model,
                    prompt,
                    args.max_new_tokens,
                )
            else:
                item[plan_key] = generate_plan(
                    tokenizer,
                    model,
                    prompt,
                    args.max_new_tokens,
                    args.enable_thinking,
                )

        save_json(
            data,
            args.output_json
        )
