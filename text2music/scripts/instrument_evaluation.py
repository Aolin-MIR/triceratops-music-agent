import os
import json
from groq import Groq
import argparse
import music21
import re
from tqdm import tqdm

def llm_instrument_evaluation(client, user_prompt, generated_instruments_list):
    llm_prompt = """
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
    """.format(user_prompt=user_prompt, generated_instruments_list=generated_instruments_list)

    completion = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{"role": "user", "content": llm_prompt}],
        temperature=0.6,
        max_completion_tokens=4096,
        top_p=0.95,
        reasoning_effort="default",
        stream=False,
        stop=None
    )

    score = completion.choices[0].message.content

    return score

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
    parser.add_argument('--api_key', type=str, required=True, help='Groq API key for instrument evaluation')
    parser.add_argument('--input_json', type=str, default="/data/home/acw769/text2score/text2music/artifacts/evaluation/prompts_with_plan_v3.json", help='Path to the json file containing the prompt information')
    parser.add_argument('--input_dir', type=str, default="/gpfs/scratch/acw769/text2score/text2score_v3/", help='Directory containing the generated MusicXML files')
    parser.add_argument('--output_json', type=str, default="/data/home/acw769/text2score/text2music/scripts/results/text2score_v3_inst_adherence.json", help='Path to save the final evaluation results')
    parser.add_argument('--resume', action='store_true', help='Whether to resume from an existing output file if it exists. If set, the script will skip already evaluated items and continue from where it left off.')
    args = parser.parse_args()

    with open(args.input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    client = Groq(api_key=args.api_key)

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

    # Wrap data in tqdm for a nice progress bar
    for item in tqdm(data, desc="Evaluating Instruments"):
        item_id = str(item.get('id'))
        
        # Skip if already processed
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
            # Unique instruments only
            extracted_instruments = list(set(extracted_instruments))
            if len(extracted_instruments) == 0:
                continue
        except Exception as e:
            print(f"\nError parsing XML for ID {item_id}: {e}")
            continue

        instruments_string = ", ".join(extracted_instruments) if extracted_instruments else "None Detected"

        # Call the LLM
        try:
            raw_response = llm_instrument_evaluation(client, user_prompt, instruments_string)
            
            if "</think>" in raw_response:
                raw_response = raw_response.split("</think>")[-1]
            
            match = re.search(r'\{[\s\S]*\}', raw_response)
            if not match:
                raise ValueError(f"No JSON object found in the response.")
                
            clean_json_str = match.group(0)
            parsed_response = json.loads(clean_json_str)
            
            item_score = int(parsed_response.get("score", 0))
            item_reasoning = parsed_response.get("reasoning", "No reasoning provided.")
            
            # --- SUCCESSFUL EVALUATION ---
            evaluation_results.append({
                "id": item_id,
                "filepath": xml_path,
                "prompt": user_prompt,
                "extracted_instruments": extracted_instruments,
                "llm_reasoning": item_reasoning,
                "llm_score": item_score
            })
            processed_ids.add(item_id)
            
            # INCREMENTAL SAVE: Save progress immediately
            save_progress(args.output_json, evaluation_results)

        except json.JSONDecodeError:
            print(f"\nParse error on ID {item_id}. Skipping so it doesn't penalize the score.")
            continue # Skip to next item, do not save

        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str or "quota" in error_str or "insufficient" in error_str:
                print(f"\n[!] API Limit Reached (Rate/Quota). Saving progress and exiting gracefully. Run again later to resume.")
                print(f"Error details: {e}")
                break # Exit the loop, preserving what we have
            else:
                print(f"\nUnexpected API Error on ID {item_id}: {e}. Skipping.")
                continue

    print("\n=== EVALUATION RUN CONCLUDED ===")
    
    # Final printout
    if len(evaluation_results) > 0:
        avg = sum(item["llm_score"] for item in evaluation_results) / len(evaluation_results)
        print(f"Total Valid Files Evaluated So Far: {len(evaluation_results)}")
        print(f"Current Average Score: {avg:.2f} / 10 ({(avg/10)*100:.2f}%)")
    else:
        print("No valid evaluations completed.")