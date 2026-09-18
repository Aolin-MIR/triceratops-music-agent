import music21
import json
import os
import argparse
import re
from tqdm import tqdm
from collections import Counter
from scipy import stats

# Configuration: (Min MIDI, Max MIDI, Max Chord Interval, is_monophonic)
INSTRUMENT_CONSTRAINTS = {
    # Strings
    "violin":   {"range": (55, 105), "max_span": 13, "mono": False},
    "viola":    {"range": (48, 91), "max_span": 13, "mono": False},
    "cello":    {"range": (36, 76),  "max_span": 12, "mono": False},
    "contrabass": {"range": (28, 67),  "max_span": 8, "mono": False},
    # Woodwinds
    "flute":    {"range": (60, 96),  "max_span": 0,  "mono": True},
    "clarinet": {"range": (50, 94),  "max_span": 0,  "mono": True},
    "oboe":    {"range": (58, 92),  "max_span": 0,  "mono": True},
    "bassoon":  {"range": (34, 82),  "max_span": 0,  "mono": True},
    "piccolo": {"range": (72, 108), "max_span": 0,  "mono": True},
    # Brass
    "saxophone": {"range": (50, 94),  "max_span": 0,  "mono": True},
    "sax": {"range": (50, 94),  "max_span": 0,  "mono": True},
    "tenor sax": {"range": (44, 87),  "max_span": 0,  "mono": True},
    "alto sax": {"range": (49, 92),  "max_span": 0,  "mono": True},
    "trumpet":  {"range": (55, 86),  "max_span": 0,  "mono": True},
    "trombone": {"range": (40, 72),  "max_span": 0,  "mono": True},
    "tuba":     {"range": (28, 60),  "max_span": 0,  "mono": True},
    "horn":     {"range": (31, 77),  "max_span": 0,  "mono": True},
    "brass":    {"range": (28, 94),  "max_span": 0,  "mono": True},
    # Keyboards & Others
    "piano":    {"range": (21, 108), "max_span": 15, "mono": False},
    "synth": {"range": (21, 108), "max_span": 15, "mono": False},
    "pad": {"range": (21, 108), "max_span": 15, "mono": False},
    "organ":    {"range": (21, 108), "max_span": 15, "mono": False},
    "accordion": {"range": (53, 93), "max_span": 13, "mono": False},
    "harp":     {"range": (24, 104), "max_span": 12, "mono": False},
    # Plucked
    "guitar":   {"range": (40, 88),  "max_span": 17, "mono": False},
    # Vocals
    "voice":    {"range": (40, 84),  "max_span": 0,  "mono": True},
    "soprano":  {"range": (60, 84),  "max_span": 0,  "mono": True},
    "alto":     {"range": (55, 74),  "max_span": 0,  "mono": True},
    "tenor":    {"range": (48, 72),  "max_span": 0,  "mono": True},
    # Percussion
    "drum":      {"range": (35, 81),  "max_span": 4,  "mono": False},
    "kit":     {"range": (35, 81),  "max_span": 0,  "mono": False},
    "percussion": {"range": (35, 81),  "max_span": 0,  "mono": False},
}

def get_playability_metrics(xml_path):
    score = music21.converter.parse(xml_path)
    total_measures = max([len(p.getElementsByClass(music21.stream.Measure)) for p in score.parts])
    if total_measures == 0: total_measures = 1 
    
    results = {}

    for part in score.parts:
        name = part.partName.lower() if part.partName else "unknown"
        config = next((v for k, v in INSTRUMENT_CONSTRAINTS.items() if k in name), None)
        if not config: continue

        measures = part.getElementsByClass(music21.stream.Measure)
        elements = part.flatten().notes
        total_elements = len(elements)
        
        measures_with_notes = [m.measureNumber for m in measures if len(m.flatten().notes) > 0]
        
        if not measures_with_notes:
            utilization_score = 0.0
            density_span_score = 0.0
        else:
            first_m = min(measures_with_notes)
            last_m = max(measures_with_notes)
            persistence_range = (last_m - first_m) + 1
            utilization_score = (persistence_range / total_measures) * 100
            density_span_score = (len(measures_with_notes) / total_measures) * 100

        violations = {
            "pitch_range": 0,
            "monophonic_correctness": 0,
            "pitch_span": 0,
            "rhythmic_overlap": 0
        }

        last_end = 0
        for el in elements:
            pitches = [p.ps for p in el.pitches]
            
            if any(p < config["range"][0] or p > config["range"][1] for p in pitches):
                violations["pitch_range"] += 1
            if config["mono"] and isinstance(el, music21.chord.Chord):
                violations["monophonic_correctness"] += 1
            if not config["mono"] and isinstance(el, music21.chord.Chord):
                span = max(pitches) - min(pitches)
                if span > config["max_span"]:
                    violations["pitch_span"] += 1
            if config["mono"] and el.offset < last_end:
                violations["rhythmic_overlap"] += 1
            
            last_end = el.offset + el.duration.quarterLength

        if total_elements > 0:
            metrics = {
                "pitch_range": (1 - (violations["pitch_range"] / total_elements)) * 100,
                "monophonic_correctness": (1 - (violations["monophonic_correctness"] / total_elements)) * 100,
                "pitch_span": (1 - (violations["pitch_span"] / total_elements)) * 100,
                "rhythmic_overlap": (1 - (violations["rhythmic_overlap"] / total_elements)) * 100,
            }
        else:
            metrics = {k: 100.0 for k in violations}

        metrics["total_playability_score"] = sum(metrics.values()) / 4
        metrics["instrument_utilization"] = round(utilization_score, 2)
        metrics["instrument_note_density_span"] = round(density_span_score, 2)
        metrics["violation_counts"] = violations
        
        results[part.partName if part.partName else "Unknown"] = metrics

    return results

def get_readability_metrics(xml_path, score_obj=None):
    score = score_obj if score_obj else music21.converter.parse(xml_path)
    results = {}

    global_ks = score.flatten().getElementsByClass(music21.key.KeySignature)
    global_key = global_ks[0] if len(global_ks) > 0 else music21.key.KeySignature(0)
    
    for part in score.parts:
        elements = part.flatten().notes
        total_elements = len(elements)
        
        counts = {
            "rhythmic_complexity": 0,
            "micro_rhythmic_jitter": 0,
            "accidental_consistency": 0,
            "enharmonic_directionality": 0
        }
        
        ks = part.flatten().getElementsByClass(music21.key.KeySignature)
        active_ks = ks[0] if len(ks) > 0 else global_key
        key_obj = active_ks.asKey()
        diatonic_names = [p.name for p in key_obj.pitches]
        
        key_type = 'neutral'
        if active_ks.sharps > 0: key_type = 'sharp'
        elif active_ks.sharps < 0: key_type = 'flat'

        for el in elements:
            if el.tie is not None:
                counts["rhythmic_complexity"] += 1

            if el.duration.quarterLength <= 0.0625 or (el.offset % 0.0625) != 0:
                counts["micro_rhythmic_jitter"] += 1

            pitches = el.pitches if hasattr(el, 'pitches') else []
            if any(p.name not in diatonic_names for p in pitches):
                counts["accidental_consistency"] += 1
            
            for p in pitches:
                if p.accidental:
                    acc_name = p.accidental.name
                    if key_type == 'sharp' and 'flat' in acc_name:
                        counts["enharmonic_directionality"] += 1
                    elif key_type == 'flat' and 'sharp' in acc_name:
                        counts["enharmonic_directionality"] += 1

        if total_elements > 0:
            metrics = {k: (1 - (v / total_elements)) * 100 for k, v in counts.items()}
            metrics["total_readability_score"] = sum(metrics.values()) / 4
            metrics["violation_counts"] = counts 
        else:
            metrics = {k: 100.0 for k in counts} | {"total_readability_score": 100.0, "violation_counts": counts}

        results[part.partName if part.partName else "Unknown"] = metrics

    return results

def validate_musicxml_metadata(xml_path, expected_tempo, expected_key, expected_ts):
    score = music21.converter.parse(xml_path)
    
    all_ts = score.flatten().getElementsByClass(music21.meter.TimeSignature)
    ts_actual = all_ts[0] if len(all_ts) > 0 else None
    ts_score = 1 if (ts_actual and ts_actual.ratioString == expected_ts) else 0

    all_ks = score.flatten().getElementsByClass(music21.key.KeySignature)
    ks_actual = all_ks[0] if len(all_ks) > 0 else None
    
    key_score = 0
    if ks_actual:
        actual_key_obj = ks_actual.asKey()
        relative_key_obj = actual_key_obj.relative
        
        actual_name = actual_key_obj.name.lower().replace('-', 'b')
        relative_name = relative_key_obj.name.lower().replace('-', 'b')
        clean_expected = expected_key.lower().replace('-', 'b')
        
        if actual_name == clean_expected or relative_name == clean_expected:
            key_score = 1
            
    all_metronomes = score.flatten().getElementsByClass(music21.tempo.MetronomeMark)
    tempo_actual = all_metronomes[0] if len(all_metronomes) > 0 else None
    
    tempo_score = 0
    if tempo_actual:
        if abs(float(tempo_actual.number) - float(expected_tempo)) <= 1.0:
            tempo_score = 1
    else:
        all_text = score.flatten().getElementsByClass(music21.expressions.TextExpression)
        for t in all_text:
            if "BPM" in t.content or "=" in t.content:
                match = re.search(r'\d+', t.content)
                if match and abs(float(match.group()) - float(expected_tempo)) <= 1.0:
                    tempo_score = 1

    return {
        "tempo_match": tempo_score,
        "key_match": key_score,
        "time_sig_match": ts_score
    }

def get_complete_evaluation(xml_path, expected_meta=None):
    score = music21.converter.parse(xml_path)
    p_results = get_playability_metrics(xml_path)
    r_results = get_readability_metrics(xml_path, score_obj=score)
    
    piece_violation_summary = Counter()
    total_p_score, total_r_score, instr_count = 0, 0, len(p_results)

    for name, p_data in p_results.items():
        r_data = r_results.get(name, {})
        
        total_p_score += p_data.get('total_playability_score', 0)
        total_r_score += r_data.get('total_readability_score', 0)
        
        if "violation_counts" in p_data:
            piece_violation_summary.update(p_data["violation_counts"])
        if "violation_counts" in r_data:
            piece_violation_summary.update(r_data.get("violation_counts", {}))

    report = {
        "piece_summary": {
            "overall_score": 0,
            "total_playability": 0,
            "total_readability": 0,
            "dissected_violation_counts": dict(piece_violation_summary)
        },
        "metadata_validation": {},
        "instruments": {}
    }

    if instr_count > 0:
        avg_p = total_p_score / instr_count
        avg_r = total_r_score / instr_count
        report["piece_summary"]["total_playability"] = round(avg_p, 2)
        report["piece_summary"]["total_readability"] = round(avg_r, 2)
        report["piece_summary"]["overall_score"] = round((avg_p + avg_r) / 2, 2)

    if expected_meta:
        report["metadata_validation"] = validate_musicxml_metadata(
            xml_path, expected_meta['tempo'], expected_meta['key'], expected_meta['ts']
        )

    for name in p_results:
        report["instruments"][name] = {
            "playability": p_results[name],
            "readability": r_results.get(name, {})
        }

    return report

def evaluate_model_directory(model_name, root_dir, metadata_list):
    """Processes an entire directory and returns the lists of scores for statistical testing."""
    all_scores = {
        "overall_score": [], "total_playability": [], "total_readability": [],
        "pitch_range": [], "monophonic_correctness": [], "pitch_span": [], "rhythmic_overlap": [],
        "instrument_utilization": [], "instrument_note_density_span": [],
        "rhythmic_complexity": [], "micro_rhythmic_jitter": [],
        "accidental_consistency": [], "enharmonic_directionality": [],
        "tempo_match": [], "key_match": [], "time_sig_match": []
    }
    
    valid_files = 0
    
    for entry in tqdm(metadata_list, desc=f"Evaluating {model_name}"):
        item_id = str(entry['id'])
        xml_folder = os.path.join(root_dir, item_id, "xml")
        
        if not os.path.exists(xml_folder): 
            continue

        xml_files = [f for f in os.listdir(xml_folder) if f.lower().endswith('.xml')]
        for xml_file in xml_files:
            xml_path = os.path.join(xml_folder, xml_file)
            expected_meta = {'tempo': entry['tempo'], 'key': entry['key_signature'], 'ts': entry['time_signature']}

            try:
                eval_results = get_complete_evaluation(xml_path, expected_meta)

                # Skip if no valid instruments were successfully evaluated
                if not eval_results["instruments"]:
                    continue
                
                valid_files += 1
                
                # Global Averages
                sum_dat = eval_results["piece_summary"]
                all_scores["overall_score"].append(sum_dat["overall_score"])
                all_scores["total_playability"].append(sum_dat["total_playability"])
                all_scores["total_readability"].append(sum_dat["total_readability"])

                # Granular Instrument Metrics
                for instr in eval_results["instruments"].values():
                    for category in ["playability", "readability"]:
                        for metric, val in instr[category].items():
                            if metric in all_scores:
                                all_scores[metric].append(val)

                # Metadata Accuracy
                meta_val = eval_results.get("metadata_validation", {})
                if meta_val:
                    for k in ["tempo_match", "key_match", "time_sig_match"]:
                        all_scores[k].append(meta_val.get(k, 0) * 100)

            except Exception as e:
                pass # Suppress individual file errors to keep output clean

    return all_scores, valid_files

def calculate_p_value(main_scores, baseline_scores):
    """Safely calculates Welch's t-test p-value."""
    if not main_scores or not baseline_scores:
        return float('nan')
    if len(main_scores) < 2 or len(baseline_scores) < 2:
        return float('nan')
    try:
        # equal_var=False enforces Welch's t-test for unequal variances/sample sizes
        stat, p_val = stats.ttest_ind(main_scores, baseline_scores, equal_var=False, nan_policy='omit')
        return p_val
    except Exception:
        return float('nan')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate main model vs baselines with statistical significance.")
    parser.add_argument("--main_root", type=str, required=True, help="Root directory for the Main Model (Text2Score).")
    parser.add_argument("--main_name", type=str, default="Text2Score", help="Display name for the main model.")
    parser.add_argument("--baseline_roots", type=str, nargs='+', required=True, help="List of root directories for Baseline Models.")
    parser.add_argument("--metadata", type=str, required=True, help="Path to the metadata JSON file.")
    parser.add_argument("--output_txt", type=str, required=True, help="Filepath for the summary report.")
    args = parser.parse_args()

    with open(args.metadata, 'r', encoding='utf-8') as f:
        metadata_list = json.load(f)

    # 1. Evaluate Main Model
    print(f"\n--- Processing Main Model: {args.main_name} ---")
    main_scores, main_valid_count = evaluate_model_directory(args.main_name, args.main_root, metadata_list)
    
    # 2. Evaluate Baseline Models
    baseline_data = {}
    for b_path in args.baseline_roots:
        b_name = os.path.basename(os.path.normpath(b_path))
        print(f"\n--- Processing Baseline Model: {b_name} ---")
        b_scores, b_valid_count = evaluate_model_directory(b_name, b_path, metadata_list)
        baseline_data[b_name] = {
            "scores": b_scores,
            "valid_count": b_valid_count
        }

    # 3. Generate Report
    metrics_list = list(main_scores.keys())
    
    with open(args.output_txt, 'w', encoding='utf-8') as f:
        f.write("=== GLOBAL OBJECTIVE EVALUATION & SIGNIFICANCE REPORT ===\n\n")
        
        # Write Valid Generation Summary
        f.write("Valid Files Generated:\n")
        f.write(f"- {args.main_name}: {main_valid_count}\n")
        for b_name, b_info in baseline_data.items():
            f.write(f"- {b_name}: {b_info['valid_count']}\n")
        f.write("\n" + "=" * 120 + "\n")
        
        # Table Header
        baseline_headers = [f"{b_name} Mean (p-val)" for b_name in baseline_data.keys()]
        header_str = f"{'Metric':<30} | {args.main_name + ' Mean':<20} | " + " | ".join([f"{h:<25}" for h in baseline_headers])
        f.write(header_str + "\n")
        f.write("-" * len(header_str) + "\n")
        
        # Table Rows
        for metric in metrics_list:
            # Main Model Mean
            m_list = main_scores[metric]
            main_mean = (sum(m_list) / len(m_list)) if m_list else 0.0
            
            row_str = f"{metric:<30} | {main_mean:>18.2f}% | "
            
            # Baseline Means & P-Values
            b_strings = []
            for b_name, b_info in baseline_data.items():
                b_list = b_info["scores"][metric]
                b_mean = (sum(b_list) / len(b_list)) if b_list else 0.0
                p_val = calculate_p_value(m_list, b_list)
                
                # Format p-value string
                if str(p_val) == 'nan':
                    p_str = "(N/A)"
                elif p_val < 0.001:
                    p_str = "(p<0.001)"
                else:
                    p_str = f"(p={p_val:.3f})"
                    
                b_strings.append(f"{b_mean:>7.2f}% {p_str:<17}")
                
            row_str += " | ".join(b_strings)
            f.write(row_str + "\n")
            
        f.write("=" * 120 + "\n")
        f.write("\nNote: p-values are calculated using Welch's independent t-test (unequal variances).\n")
        f.write("A p-value < 0.05 generally indicates a statistically significant difference from the Main Model.\n")