import os
import json
import argparse
import music21
import re
from tqdm import tqdm
from vllm import LLM, SamplingParams

def get_llm_prompt(user_prompt, generated_instruments_list):
    """Generates the raw text prompt for the LLM."""
    return f"""
    You are an expert musicologist and sheet music librarian. Your task is to evaluate the "Instrument Adherence" of a generated symbolic music score based on a user's textual prompt.

    You will be provided with:
    1. The original TEXT PROMPT written by the user.
    2. A list of GENERATED UNIQUE INSTRUMENTS extracted from the resulting MusicXML file.

    Your job is to determine how accurately the generated instruments match the ensemble or solo constraints requested in the text prompt. 

    ### Rules for Evaluation:
    1. Semantic Matching: MusicXML instrument names are often non-standard (e.g., "Acoustic Grand" = "Piano", "Violoncel" = "Cello", "Voice" = "Soprano"). Use your musical knowledge to match these semantically.
    2. Ensemble Knowledge: If the prompt asks for a standard ensemble (e.g., "String Quartet"), expect the standard instrumentation (2 Violins, Viola, Cello).
    3. The "Solo" Constraint: If the prompt explicitly requests a "Solo" instrument, the generated list MUST contain ONLY that instrument. The presence of any background instruments (e.g., drums, synth pads) is a major violation.
    4. Penalties: Deduct points for missing requested instruments, and deduct points for hallucinated/additional instruments that were not requested. If instruments are all grouped in a single part (e.g., Melody (Trumpets/Violins)), that is a partial violation, as it does not reflect the requested ensemble structure.

    ### Scoring Rubric (1 to 10):
    * [10] Perfect Match: The generated instruments perfectly map to the requested ensemble or solo instrument. No missing instruments, no extra instruments.
    * [8-9] Minor Variations: The core ensemble is present, but there is a very minor addition or omission (e.g., requested a symphony orchestra, missing a tuba; or requested a trio, got the trio plus an appropriate auxiliary percussion).
    * [5-7] Partial Match: Some requested instruments are present, but there are glaring omissions or significant unwarranted additions.
    * [2-4] Major Violation: The generated instruments barely reflect the prompt. (e.g., requested a "Solo Piano", but generated "Piano, Drum Kit, Electric Bass").
    * [1] Complete Mismatch: None of the requested instruments are present (e.g., requested "Choir", generated "Brass Quintet").

    ### Output Format:
    You must return your evaluation strictly as a valid JSON object with exactly two keys:
    - "reasoning": A brief 1-2 sentence explanation of your evaluation, noting any missing or hallucinated instruments.
    - "score": An integer from 1 to 10.

    ---
    INPUT DATA:
    TEXT PROMPT: "{user_prompt}"
    GENERATED UNIQUE INSTRUMENTS: {generated_instruments_list}
    """

def save_progress(filepath, results_list):
    """Calculates summary and saves the current progress to disk."""
    valid_evaluations = len(results_list)
    total_score = sum(item["llm_score"] for item in results_list)
    
    average_score = (total_score / valid_evaluations) if valid_evaluations > 0 else 0
    percentage_score = (average_score / 10) * 100

    final_output = {
        "summary": {
            "total_files_evaluated": valid_evaluations,
            "average_score_out_of_10": round(average_score, 2),
            "percentage_score": round(percentage_score, 2)
        },
        "detailed_results": results_list
    }

    with open(filepath, "w", encoding="utf-8") as out_file:
        json.dump(final_output, out_file, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Updated Arguments for vLLM
    parser.add_argument('--model', type=str, default="Qwen/Qwen2.5-32B-Instruct", help='HuggingFace model name or local path')
    parser.add_argument('--tensor_parallel_size', type=int, default=1, help='Number of GPUs to distribute the model across')
    parser.add_argument('--batch_size', type=int, default=32, help='Number of files to process before performing an incremental save')
    
    # Original Arguments
    parser.add_argument('--input_json', type=str, default="/data/home/acw769/text2score/text2music/artifacts/evaluation/prompts_with_plan_v3.json", help='Path to the json file containing the prompt information')
    parser.add_argument('--input_dir', type=str, default="/gpfs/scratch/acw769/text2score/text2score_v3/", help='Directory containing the generated MusicXML files')
    parser.add_argument('--output_json', type=str, default="/data/home/acw769/text2score/text2music/scripts/results/text2score_v3_inst_adherence.json", help='Path to save the final evaluation results')
    parser.add_argument('--resume', action='store_true', help='Whether to resume from an existing output file if it exists.')
    args = parser.parse_args()

    with open(args.input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    # If not resume, clear existing output file
    if not args.resume and os.path.exists(args.output_json):
        print(f"Output file {args.output_json} already exists. Deleting it to start fresh.")
        os.remove(args.output_json)

    # --- RESUME LOGIC ---
    evaluation_results = []
    processed_ids = set()

    if os.path.exists(args.output_json):
        try:
            with open(args.output_json, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if "detailed_results" in existing_data:
                    evaluation_results = existing_data["detailed_results"]
                    processed_ids = {str(item["id"]) for item in evaluation_results}
            print(f"Resuming progress: Found {len(processed_ids)} already evaluated items.")
        except json.JSONDecodeError:
            print("Warning: Output JSON exists but is corrupted. Starting fresh.")

    # --- STEP 1: PARSE ALL MUSICXML FILES ---
    # We do this first so the CPU doesn't interrupt the GPU during inference
    pending_items = []
    for item in tqdm(data, desc="Parsing XML Files"):
        item_id = str(item.get('id'))
        if item_id in processed_ids:
            continue

        user_prompt = item.get('prompt')
        xml_folder = os.path.join(args.input_dir, item_id, "xml")
        
        if not os.path.exists(xml_folder):
            continue
            
        xml_files = [f for f in os.listdir(xml_folder) if f.lower().endswith('.xml')]
        if not xml_files:
            continue
            
        xml_path = os.path.join(xml_folder, xml_files[0])

        try:
            score = music21.converter.parse(xml_path)
            extracted_instruments = [part.partName for part in score.parts if part.partName]
            extracted_instruments = [inst for inst in extracted_instruments if inst and inst.strip()]
            extracted_instruments = list(set(extracted_instruments))
            if len(extracted_instruments) == 0:
                continue
        except Exception as e:
            # Uncomment below if you want visibility on parsing errors
            # print(f"\nError parsing XML for ID {item_id}: {e}")
            continue

        instruments_string = ", ".join(extracted_instruments) if extracted_instruments else "None Detected"
        
        pending_items.append({
            "id": item_id,
            "prompt": user_prompt,
            "filepath": xml_path,
            "extracted_instruments": extracted_instruments,
            "instruments_string": instruments_string
        })

    if not pending_items:
        print("\nNo new files to evaluate. Exiting.")
        exit(0)

    # --- STEP 2: LOAD VLLM ---
    print(f"\nLoading vLLM with model: {args.model}")
    llm = LLM(model=args.model, tensor_parallel_size=args.tensor_parallel_size)
    tokenizer = llm.get_tokenizer()
    sampling_params = SamplingParams(
        temperature=0.6,
        top_p=0.95,
        max_tokens=4096
    )

    # --- STEP 3: BATCH GENERATION ---
    print("\nStarting LLM Evaluation batches...")
    
    # Process items in batches to allow for incremental saving
    for i in range(0, len(pending_items), args.batch_size):
        chunk = pending_items[i:i + args.batch_size]
        
        # 1. Apply Chat Template to format the prompt correctly for the model
        formatted_prompts = []
        for c in chunk:
            raw_text = get_llm_prompt(c["prompt"], c["instruments_string"])
            messages = [{"role": "user", "content": raw_text}]
            # apply_chat_template ensures Qwen's specific <|im_start|> tags are added
            formatted_prompt = tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            formatted_prompts.append(formatted_prompt)
            
        # 2. Run batched inference using vLLM
        outputs = llm.generate(formatted_prompts, sampling_params)
        
        # 3. Parse LLM outputs
        for c, output in zip(chunk, outputs):
            raw_response = output.outputs[0].text
            
            # Clean DeepSeek/Qwen thinking tokens if present
            if "</think>" in raw_response:
                raw_response = raw_response.split("</think>")[-1]
            
            # Extract JSON block
            match = re.search(r'\{[\s\S]*\}', raw_response)
            if not match:
                print(f"\nNo JSON object found for ID {c['id']}. Skipping.")
                continue
                
            try:
                clean_json_str = match.group(0)
                parsed_response = json.loads(clean_json_str)
                
                item_score = int(parsed_response.get("score", 0))
                item_reasoning = parsed_response.get("reasoning", "No reasoning provided.")
                
                # Append successful evaluation
                evaluation_results.append({
                    "id": c["id"],
                    "filepath": c["filepath"],
                    "prompt": c["prompt"],
                    "extracted_instruments": c["extracted_instruments"],
                    "llm_reasoning": item_reasoning,
                    "llm_score": item_score
                })
            except (json.JSONDecodeError, ValueError) as e:
                print(f"\nParse error on ID {c['id']}. LLM Output was malformed. Skipping.")
                continue

        # 4. Save progress incrementally at the end of the batch
        save_progress(args.output_json, evaluation_results)
        print(f"-> Batch {i//args.batch_size + 1} completed. Progress saved ({len(evaluation_results)} total completed).")

    print("\n=== EVALUATION RUN CONCLUDED ===")
    
    # Final printout
    if len(evaluation_results) > 0:
        avg = sum(item["llm_score"] for item in evaluation_results) / len(evaluation_results)
        print(f"Total Valid Files Evaluated: {len(evaluation_results)}")
        print(f"Final Average Score: {avg:.2f} / 10 ({(avg/10)*100:.2f}%)")
    else:
        print("No valid evaluations completed.")