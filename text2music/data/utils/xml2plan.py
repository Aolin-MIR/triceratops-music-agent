import partitura as pt
import xml.etree.ElementTree as ET
from typing import Dict, Optional
import random
import pickle
import math
# Ignore user warnings
import warnings
warnings.filterwarnings("ignore", category=UserWarning)


def safe_int_or_none(value):
    """Safely converts a value to int. Returns None if value is NaN, None, or invalid."""
    try:
        if value is None:
            return None
        # Check for NaN (float('nan') != float('nan'))
        if isinstance(value, float) and value != value:
            return None
        return int(value)
    except (ValueError, TypeError):
        return None

def find_tempo_in_measure(measure_element: ET.Element) -> Optional[int]:
    """Checks for tempo markings within a single measure element."""
    # Tempo is often specified in a <direction> element.
    for direction in measure_element.findall('direction'):
        # It can be in a <sound> element's 'tempo' attribute.
        sound_element = direction.find('sound')
        if sound_element is not None and 'tempo' in sound_element.attrib:
            try:
                return int(float(sound_element.attrib['tempo']))
            except (ValueError, TypeError):
                continue # Ignore if tempo is not a valid number

        # Or it can be in a <metronome> element.
        direction_type = direction.find('direction-type')
        if direction_type is not None:
            metronome = direction_type.find('metronome')
            if metronome is not None:
                per_minute = metronome.find('per-minute')
                if per_minute is not None and per_minute.text:
                    try:
                        return int(per_minute.text)
                    except (ValueError, TypeError):
                        continue # Ignore if not a valid number
    return None

def extract(filepath: str) -> Dict[int, Optional[int]]:
    """
    Parses a MusicXML file and extracts tempo for each measure.

    Args:
        filepath: The path to the MusicXML file.

    Returns:
        A dictionary where keys are measure numbers (int) and values are
        the tempo in BPM (int), or None if no tempo has been set.
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
        return {}

    tempo_by_measure: Dict[int, Optional[int]] = {}
    current_tempo: Optional[int] = None

    # Tempo information is usually in the first part, so we only need to parse that.
    first_part = root.find('part')
    if first_part is None:
        print("No <part> elements found in the MusicXML file.")
        return {}

    measures = first_part.findall('measure')
    for measure_element in measures:
        measure_number_str = measure_element.get('number')
        if not measure_number_str:
            continue
        
        measure_number = int(measure_number_str)

        # Search for tempo markings within the measure
        # A new tempo found here will override the current_tempo
        found_tempo = find_tempo_in_measure(measure_element)
        if found_tempo is not None:
            current_tempo = found_tempo
        
        tempo_by_measure[measure_number] = current_tempo
        
    return tempo_by_measure


def get_raw_xml_info(musicxml_file: str, verbose: bool = False) -> list:
    """
    Extracts raw XML information from a MusicXML file.
    Returns None for missing/NaN values instead of defaults.
    """
    
    # Load the score
    score = pt.load_musicxml(musicxml_file)
    all_tempos = extract(musicxml_file)

    data = []
    # Iterate through all parts in the score
    for i, part in enumerate(score.parts):

        part_name = part.part_name
        if not part_name:
            part_name = f"Piano {i+1}" if i > 0 else "Piano"

        for p in data:
            n = 1
            if p['part_name'] == part_name:
                part_name += f" {n+1}"
                while any(p['part_name'] == part_name for p in data):
                    n += 1
                    part_name = f"{part.part_name} {n+1}"
        if verbose:
            print(f"Part Name: {part_name}")

        extended_score_note_array = pt.utils.music.ensure_notearray(
            part,
            include_pitch_spelling=True,
            include_key_signature=True,
            include_time_signature=True,
            include_metrical_position=True,
            include_grace_notes=True
        )

        measures = list(part.iter_all(pt.score.Measure, include_subclasses=True))
        part_dynamics = list(part.dynamics)

        if verbose:
            print(f"Number of measures in part: {len(measures)}")

        part_data = {
                "part_name": part_name,
                "measures": []
            }

        for measure in measures:
            # --- UPDATED: Use safe_int_or_none ---
            ts_num = safe_int_or_none(part.time_signature_map(measure.start.t)[0])
            ts_den = safe_int_or_none(part.time_signature_map(measure.start.t)[1])
            ts_beats = safe_int_or_none(part.time_signature_map(measure.start.t)[2])
            ks_fifths = safe_int_or_none(part.key_signature_map(measure.start.t)[0])
            ks_mode = safe_int_or_none(part.key_signature_map(measure.start.t)[1])
            
            # Extract Dynamics
            dynamics_in_measure = []
            for dynamic in part_dynamics:
                if measure.start.t <= dynamic.start.t < measure.end.t:
                    dynamics_in_measure.append({
                        "text": dynamic.text,
                        "start_time": dynamic.start.t,
                        "rel_onset_div": dynamic.start.t - measure.start.t
                    })

            measure_data = {
                    "measure": measure.number,
                    "start_time": measure.start.t,
                    "end_time": measure.end.t,
                    "ts_num": ts_num,
                    "ts_den": ts_den,
                    "ts_beats": ts_beats,
                    "ks_fifths": ks_fifths,
                    "ks_mode": ks_mode,
                    "tempo": all_tempos.get(measure.number, None),
                    "dynamics": dynamics_in_measure
                }
            
            notes_in_measure = [n for n in extended_score_note_array if measure.start.t <= n[4] < measure.end.t]
            notes = []
            for n, note in enumerate(notes_in_measure):
                note_data = {
                    "pitch": note['pitch'],
                    "start_time": note['onset_div'],
                    "end_time": note['onset_div'] + note['duration_div'],
                    "rel_onset_div": note['rel_onset_div'],
                    "tot_measure_div": note['tot_measure_div'],
                    "duration": note['duration_div'],
                    "is_grace": note['is_grace'],
                    "grace_type": note['grace_type']
                }
                notes.append(note_data)
            measure_data["notes"] = notes
            
            part_data["measures"].append(measure_data)
        data.append(part_data)

    return data

def combine_raw_xml_info(data):
    """
    Combines the raw XML information from multiple parts into a single dictionary.
    Includes an aggregated list of dynamics for each measure across all parts.

    Args:
        data: A list of dictionaries containing raw XML information for each part.

    Returns:
        A combined dictionary with all parts' data.
    """
    
    # 1. Pre-calculate the aggregated dynamics per measure
    aggregated_dynamics = {}
    
    for part_data in data:
        for measure_data in part_data['measures']:
            measure_num = measure_data['measure']
            if measure_num not in aggregated_dynamics:
                aggregated_dynamics[measure_num] = []
            
            # Collect dynamics from this part if they exist
            # (Assumes get_raw_xml_info has been updated to include 'dynamics')
            part_dyns = measure_data.get('dynamics', [])
            aggregated_dynamics[measure_num].extend(part_dyns)

    # 2. Sort the aggregated dynamics chronologically for each measure
    for measure_num in aggregated_dynamics:
        # Sort by global start_time to ensure chronological order across parts
        aggregated_dynamics[measure_num].sort(key=lambda x: x['start_time'])

    # 3. Build the combined structure
    combined_measures = {}
    for part_data in data:
        part_name = part_data['part_name']
        for measure_data in part_data['measures']:
            measure_num = measure_data['measure']
            if f"Measure: {measure_num}" not in combined_measures:
                combined_measures[f"Measure: {measure_num}"] = {}
            
            # Retrieve the pre-calculated aggregated list for this measure
            # We attach this list to every part so it's accessible regardless of which instrument is queried
            measure_aggregated_dyns = aggregated_dynamics.get(measure_num, [])

            combined_measures[f"Measure: {measure_num}"][part_name] = {
                'info': {
                    'start_time': measure_data['start_time'],
                    'end_time': measure_data['end_time'],
                    'ts_num': measure_data['ts_num'],
                    'ts_den': measure_data['ts_den'],
                    'ts_beats': measure_data['ts_beats'],
                    'ks_fifths': measure_data['ks_fifths'],
                    'ks_mode': measure_data['ks_mode'],
                    'tempo': measure_data['tempo'],
                    'notes': measure_data['notes'],
                    'dynamics': measure_aggregated_dyns  # Added aggregated dynamics
                }
            }

    return combined_measures


def get_full_plan(combined_data):
    """
    Generates a full plan from the combined data.
    - Handles NaN values by returning None.
    - Robustly handles None values during aggregation (e.g. max/min).
    """
    
    # Internal helper
    def safe_int_or_none(value):
        try:
            if value is None: return None
            if isinstance(value, float) and value != value: return None # Check NaN
            return int(value)
        except (ValueError, TypeError):
            return None

    plan = {}
    all_instruments = set()
    for measure in combined_data.keys():
        measure_info = combined_data[measure]
        plan[measure] = {}

        for instrument in measure_info.keys():
            all_instruments.add(instrument)

        plan[measure]['instruments'] = [
            instrument for instrument in combined_data[measure].keys() 
            if len(combined_data[measure][instrument]['info']['notes']) > 0
        ]
        
        # --- 1. PITCH RANGE ---
        # Logic update: Filter out None pitches before calculating min/max
        pitch_ranges = []
        for instrument in plan[measure]['instruments']:
            notes = combined_data[measure][instrument]['info']['notes']
            if notes:
                # Get pitches, filtering out any accidental Nones
                pitches = [safe_int_or_none(note['pitch']) for note in notes]
                pitches = [p for p in pitches if p is not None]
                
                if pitches:
                    max_pitch = max(pitches)
                    min_pitch = min(pitches)
                    pitch_ranges.append((min_pitch, max_pitch))
                    
        if pitch_ranges:
            plan[measure]['pitch_range'] = {
                'min': min(p[0] for p in pitch_ranges),
                'max': max(p[1] for p in pitch_ranges)
            }
        else:
            plan[measure]['pitch_range'] = {'min': None, 'max': None}
        
        # --- 2. NOTE DENSITY ---
        total_notes = sum(len(combined_data[measure][instrument]['info']['notes']) for instrument in plan[measure]['instruments'])
        if plan[measure]['instruments']:
            average_notes = float(round(total_notes / len(plan[measure]['instruments']), 2))
        else:
            average_notes = 0.0
        plan[measure]['note_density'] = average_notes
        
        # --- 3. TIME SIGNATURE ---
        plan[measure]['time_signature'] = None
        if plan[measure]['instruments']:
            first_instrument = plan[measure]['instruments'][0]
            # Retrieve values (which might be None now)
            ts_num = safe_int_or_none(combined_data[measure][first_instrument]['info']['ts_num'])
            ts_den = safe_int_or_none(combined_data[measure][first_instrument]['info']['ts_den'])
            
            # Only construct string if both exist
            if ts_num is not None and ts_den is not None:
                plan[measure]['time_signature'] = f"{ts_num}/{ts_den}" 
        
        # --- 4. KEY SIGNATURE ---
        instruments_to_exclude = ['Drum', 'Percussion', 'Drumset', 'Drums', 'Saxophone', 'Clarinet']
        plan[measure]['key_signature'] = None
        
        if 'Piano' in plan[measure]['instruments']:
            plan[measure]['key_signature'] = safe_int_or_none(combined_data[measure]['Piano']['info']['ks_fifths'])
        elif plan[measure]['instruments']:
            # Collect signatures, filtering out Nones
            key_signatures = [
                safe_int_or_none(combined_data[measure][instrument]['info']['ks_fifths'])
                for instrument in plan[measure]['instruments'] 
                if not any(excluded in instrument for excluded in instruments_to_exclude)
            ]
            # Remove Nones from the list
            key_signatures = [k for k in key_signatures if k is not None]
            
            if key_signatures:
                plan[measure]['key_signature'] = max(set(key_signatures), key=key_signatures.count)

        # --- 5. KEY MODE ---
        first_instrument = plan[measure]['instruments'][0] if plan[measure]['instruments'] else None
        if first_instrument and 'info' in combined_data[measure][first_instrument]:
            plan[measure]['key_mode'] = safe_int_or_none(combined_data[measure][first_instrument]['info']['ks_mode'])
        else:
            plan[measure]['key_mode'] = None

        # --- 6. TEMPO ---
        if first_instrument and 'info' in combined_data[measure][first_instrument]:
            tempo_val = combined_data[measure][first_instrument]['info']['tempo']
            plan[measure]['tempo'] = safe_int_or_none(tempo_val)
        else:
            plan[measure]['tempo'] = None

        # --- 7. DYNAMICS ---
        plan[measure]['dynamics'] = []
        if first_instrument and 'info' in combined_data[measure][first_instrument]:
            raw_dynamics = combined_data[measure][first_instrument]['info'].get('dynamics', [])
            clean_dynamics = []
            for d in raw_dynamics:
                onset = safe_int_or_none(d['rel_onset_div'])
                if onset is not None:
                    clean_dynamics.append({'onset': onset, 'value': str(d['text'])})
            plan[measure]['dynamics'] = clean_dynamics

        # --- 8. CHORDS ---
        plan[measure]['chords'] = []
        
        if not plan[measure]['instruments']:
            continue  

        onset_groups = {}

        for instrument in plan[measure]['instruments']:
            notes = combined_data[measure][instrument]['info']['notes']
            for note in notes:
                if note['is_grace'] == 0:
                    onset = note['rel_onset_div'] 
                    
                    # Check pitch validity before modulo
                    raw_pitch = safe_int_or_none(note['pitch'])
                    if raw_pitch is None:
                        continue
                        
                    note_pitch = int(raw_pitch % 12)

                    if onset not in onset_groups:
                        onset_groups[onset] = set()
                    
                    onset_groups[onset].add(note_pitch)

        unique_chords = []
        seen_chords = set()
        sorted_onsets = sorted(onset_groups.keys())

        for onset in sorted_onsets:
            current_chord_set = onset_groups[onset]
            
            if len(current_chord_set) < 2:
                continue

            chord_signature = tuple(sorted(current_chord_set))
            
            if chord_signature not in seen_chords:
                seen_chords.add(chord_signature)
                unique_chords.append(current_chord_set)

        plan[measure]['chords'] = unique_chords

    plan['all_instruments'] = list(all_instruments)

    return plan


def get_top_measures_instrument(full_plan, top_pct=10):
    """
    Get the top N measures based on note density.

    Args:
        full_plan: The full plan dictionary containing measure information.
        top_pct: The pct of top measures to return.

    Returns:
        A dict of measures
    """
    
    # Get change in instrument count compared to the previous measure across all measures
    instrument_count_changes = {}
    previous_instrument_count = 0
    for measure, info in full_plan.items():
        current_instrument_count = len(info['instruments'])
        if previous_instrument_count == 0:
            change = current_instrument_count  # First measure, no previous count
        else:
            change = current_instrument_count - previous_instrument_count
        instrument_count_changes[measure] = change
        previous_instrument_count = current_instrument_count

    # Sort the absolute values of instrument count changes by measure
    sorted_instrument_count_changes = sorted(instrument_count_changes.items(), key=lambda x: abs(x[1]), reverse=True)

    # Take the top 10% of measures with the largest absolute changes
    top_10_percent_count = max(5, len(sorted_instrument_count_changes) // top_pct)  # Ensure at least one measure is selected
    top_instrument_changes = sorted_instrument_count_changes[:top_10_percent_count]
    
    return {measure: change for measure, change in top_instrument_changes}


def get_top_measures_tempo(full_plan, top_pct=10):
    """
    Get the top N measures based on tempo changes.

    Args:
        full_plan: The full plan dictionary containing measure information.
        top_pct: The pct of top measures to return.

    Returns:
        A dict of measures
    """
    
    # Get change in tempo compared to the previous measure across all measures
    tempo_changes = {}
    previous_tempo = None
    for measure, info in full_plan.items():
        current_tempo = info.get('tempo', 0)
        if current_tempo is None:
            current_tempo = 0
        if previous_tempo is None:
            change = current_tempo  # First measure, no previous tempo
        else:
            change = (current_tempo - previous_tempo) if current_tempo is not None and previous_tempo is not None else 0
        tempo_changes[measure] = change
        previous_tempo = current_tempo

    # Sort the absolute values of tempo changes by measure
    sorted_tempo_changes = sorted(tempo_changes.items(), key=lambda x: abs(x[1]), reverse=True)

    # Take the top 10% of measures with the largest absolute changes
    top_10_percent_tempo_count = max(5, len(sorted_tempo_changes) // top_pct)  # Ensure at least one measure is selected
    top_tempo_changes = sorted_tempo_changes[:top_10_percent_tempo_count]
    
    return {measure: change for measure, change in top_tempo_changes}


def get_top_measures_key_signature(full_plan, top_pct=10):
    """
    Get the top N measures based on key signature changes.

    Args:
        full_plan: The full plan dictionary containing measure information.
        top_pct: The pct of top measures to return.

    Returns:
        A dict of measures
    """
    
    # Get change in key signature per measure across all measures
    key_signature_changes = {}
    previous_key_signature = None
    for measure, info in full_plan.items():
        current_key_signature = info.get('key_signature')
        if previous_key_signature is None:
            change = 1 #current_key_signature  # First measure, no previous key signature
        else:
            # change = (current_key_signature - previous_key_signature) if current_key_signature is not None and previous_key_signature is not None else 0
            change = 1 if current_key_signature is not None and previous_key_signature is not None and current_key_signature != previous_key_signature else 0
        key_signature_changes[measure] = change
        previous_key_signature = current_key_signature

    # Sort the absolute values of key signature changes by measure
    sorted_key_signature_changes = sorted(key_signature_changes.items(), key=lambda x: abs(x[1]), reverse=True)

    # Take the top 10% of measures with the largest absolute changes
    top_10_percent_key_signature_count = max(5, len(sorted_key_signature_changes) // top_pct)  # Ensure at least one measure is selected
    top_key_signature_changes = sorted_key_signature_changes[:top_10_percent_key_signature_count]
    
    return {measure: change for measure, change in top_key_signature_changes}


def get_top_measures_time_signature(full_plan, top_pct=10):
    """
    Get the top N measures based on time signature changes.

    Args:
        full_plan: The full plan dictionary containing measure information.
        top_pct: The pct of top measures to return.

    Returns:
        A dict of measures
    """
    
    # Get change in time signature per measure across all measures
    time_signature_changes = {}
    previous_time_signature = None  # Initialize previous time signature
    for measure, info in full_plan.items():
        current_time_signature = info.get('time_signature')
        if previous_time_signature is None:
            change = 1  # First measure, no previous time signature
        else:
            change = 1 if current_time_signature is not None and previous_time_signature is not None and current_time_signature != previous_time_signature else 0
        time_signature_changes[measure] = change
        previous_time_signature = current_time_signature

    # Sort the absolute values of time signature changes by measure
    sorted_time_signature_changes = sorted(time_signature_changes.items(), key=lambda x: abs(x[1]), reverse=True)

    # Take the top 10% of measures with the largest absolute changes
    top_10_percent_time_signature_count = max(5, len(sorted_time_signature_changes) // top_pct)  # Ensure at least one measure is selected
    top_time_signature_changes = sorted_time_signature_changes[:top_10_percent_time_signature_count]
    
    return {measure: change for measure, change in top_time_signature_changes}


def get_top_measures_note_density(full_plan, top_pct=10):
    """
    Get the top N measures based on note density.

    Args:
        full_plan: The full plan dictionary containing measure information.
        top_pct: The pct of top measures to return.

    Returns:
        A dict of measures
    """
    
    # Get change in note density across all measures
    note_density_changes = {}
    previous_note_density = 0
    for measure, info in full_plan.items():
        current_note_density = info.get('note_density', 0)
        change = current_note_density - previous_note_density
        note_density_changes[measure] = change
        previous_note_density = current_note_density

    # Sort the absolute values of note density changes by measure
    sorted_note_density_changes = sorted(note_density_changes.items(), key=lambda x: abs(x[1]), reverse=True)

    # Take the top 10% of measures with the largest absolute changes
    top_10_percent_note_density_count = max(5, len(sorted_note_density_changes) // top_pct)  # Ensure at least one measure is selected
    top_note_density_changes = sorted_note_density_changes[:top_10_percent_note_density_count]
    
    return {measure: change for measure, change in top_note_density_changes}


def get_top_measures_pitch_range(full_plan, top_pct=10):
    """
    Get the top N measures based on pitch range.

    Args:
        full_plan: The full plan dictionary containing measure information.
        top_pct: The pct of top measures to return.

    Returns:
        A dict of measures
    """
    
    # Get changes in pitch range per measure across all measures
    # Pitch range is highest pitch - lowest pitch in the measure
    pitch_range_changes = {}
    for measure, info in full_plan.items():
        current_pitch_range = info.get('pitch_range', {'min': None, 'max': None})
        if current_pitch_range['min'] is None or current_pitch_range['max'] is None:
            change = 0  # No pitch range defined
        else:
            change = current_pitch_range['max'] - current_pitch_range['min']
        pitch_range_changes[measure] = change

    # Sort the absolute values of pitch range changes by measure
    sorted_pitch_range_changes = sorted(pitch_range_changes.items(), key=lambda x: abs(x[1]), reverse=True)

    # Take the top 10% of measures with the largest absolute changes
    top_10_percent_pitch_range_count = max(5, len(sorted_pitch_range_changes) // top_pct)  # Ensure at least one measure is selected
    top_pitch_range_changes = sorted_pitch_range_changes[:top_10_percent_pitch_range_count]
    
    return {measure: change for measure, change in top_pitch_range_changes}


def get_priority_order(full_plan, top_pct=10, top_n=5):
    """
    Get the priority order of measures based on various musical features.

    Args:
        full_plan: The full plan dictionary containing measure information.
        top_pct: The pct of top measures to consider from each attribute.
        top_n: The number of top measures to return.

    Returns:
        A list of measures ordered by priority.
    """

    # Remove all_instruments from full_plan to avoid confusion
    if 'all_instruments' in full_plan:
        all_instruments = full_plan['all_instruments']
        del full_plan['all_instruments']
    
    top_instrument_changes = get_top_measures_instrument(full_plan, top_pct=top_pct)
    top_tempo_changes = get_top_measures_tempo(full_plan, top_pct=top_pct)
    top_key_signature_changes = get_top_measures_key_signature(full_plan, top_pct=top_pct)
    top_time_signature_changes = get_top_measures_time_signature(full_plan, top_pct=top_pct)
    top_note_density_changes = get_top_measures_note_density(full_plan, top_pct=top_pct)
    top_pitch_range_changes = get_top_measures_pitch_range(full_plan, top_pct=top_pct)

    weighting_1 = {
        'instrument_changes': 2,
        'tempo_changes': 5,
        'key_signature_changes': 3,
        'time_signature_changes': 4,
        'note_density_changes': 3,
        'pitch_range_changes': 1
    }

    weighting_2 = {
        'instrument_changes': 1,
        'tempo_changes': 1,
        'key_signature_changes': 1,
        'time_signature_changes': 1,
        'note_density_changes': 5,
        'pitch_range_changes': 5
    }

    weighting_3 = {
        'instrument_changes': 5,
        'tempo_changes': 1,
        'key_signature_changes': 1,
        'time_signature_changes': 1,
        'note_density_changes': 1,
        'pitch_range_changes': 1
    }

    weighting_4 = {
        'instrument_changes': 1,
        'tempo_changes': 2,
        'key_signature_changes': 5,
        'time_signature_changes': 5,
        'note_density_changes': 1,
        'pitch_range_changes': 1
    }

    # Get random weighting
    weighting = random.choice([weighting_1, weighting_2, weighting_3, weighting_4])

    priority_order = {}
    for measure, change in top_tempo_changes.items():
        priority_order[measure] = priority_order.get(measure, 0) + weighting['tempo_changes']
    for measure, change in top_time_signature_changes.items():
        priority_order[measure] = priority_order.get(measure, 0) + weighting['time_signature_changes']
    for measure, change in top_key_signature_changes.items():
        priority_order[measure] = priority_order.get(measure, 0) + weighting['key_signature_changes']
    for measure, change in top_note_density_changes.items():
        priority_order[measure] = priority_order.get(measure, 0) + weighting['note_density_changes']
    for measure, change in top_instrument_changes.items():
        priority_order[measure] = priority_order.get(measure, 0) + weighting['instrument_changes']
    for measure, change in top_pitch_range_changes.items():
        priority_order[measure] = priority_order.get(measure, 0) + weighting['pitch_range_changes']

    # Sort measures by priority score in descending order
    sorted_priority_order = sorted(priority_order.items(), key=lambda x: x[1], reverse=True)

    top_priority_measures = sorted_priority_order[:top_n] # Get the top n measures based on priority score

    # Sort the top priority measures by their measure number for better readability
    top_priority_measures.sort(key=lambda x: int(x[0].split(': ')[1]))

    # Return only the measure numbers in the order of priority
    return (top_priority_measures, all_instruments)


def get_consecutive_measures(full_plan, top_priority_measures):
    """
    Get consecutive measures based on the top priority measures.

    Args:
        full_plan: The full plan dictionary containing measure information.
        top_priority_measures: A list of top priority measures.

    Returns:
        A list of measures with consecutive measures appended.
    """

    # Remove all_instruments from full_plan to avoid confusion
    if 'all_instruments' in full_plan:
        del full_plan['all_instruments']

    # Randomly append a consecutive measure (above or below each measure) to the top priority measures
    top_priority_measures_with_consecutive = []
    for measure, priority in top_priority_measures:
        measure_num = int(measure.split(': ')[1])
        # Check if the next measure exists
        next_measure = f"Measure: {measure_num + 1}"
        previous_measure = f"Measure: {measure_num - 1}"

        # Append current measure
        if measure not in top_priority_measures_with_consecutive:
            top_priority_measures_with_consecutive.append((measure))
        
        # 50% chance to append the next measure if it exists, otherwise append the previous measure
        if next_measure in full_plan and next_measure not in top_priority_measures_with_consecutive and random.random() < 0.5:
            top_priority_measures_with_consecutive.append((next_measure))
        elif previous_measure in full_plan and previous_measure not in top_priority_measures_with_consecutive and random.random() < 0.5:
            top_priority_measures_with_consecutive.append((previous_measure))

    # Sort the top priority measures with consecutive measures by their measure number for better readability
    top_priority_measures_with_consecutive.sort(key=lambda x: int(x.split(': ')[1]))

    consecutive_measures = {measure: full_plan[measure] for measure in top_priority_measures_with_consecutive}

    return consecutive_measures

def get_measures(full_plan, top_priority_measures):
    """
    Get measures based on the top priority measures.

    Args:
        full_plan: The full plan dictionary containing measure information.
        top_priority_measures: A list of top priority measures.

    Returns:
        A list of measures with information.
    """

    # Remove all_instruments from full_plan to avoid confusion
    if 'all_instruments' in full_plan:
        del full_plan['all_instruments']

    # Randomly append a consecutive measure (above or below each measure) to the top priority measures
    selected_measures = []
    for measure, priority in top_priority_measures:
        measure_num = int(measure.split(': ')[1])

        # Append current measure
        if measure not in selected_measures:
            selected_measures.append((measure))

    # Sort the top priority measures with consecutive measures by their measure number for better readability
    selected_measures.sort(key=lambda x: int(x.split(': ')[1]))

    measures = {measure: full_plan[measure] for measure in selected_measures}

    return measures

def convert_plan_to_text(data, pitch_shift: int = 0, genre: str = None, plan_length: int = None):
    """
    Converts the plan dictionary to text.
    - Updated to handle dynamics as a list of strings.
    """
    
    # 1. Safely extract metadata
    all_instruments = data.get('all_instruments', [])
    
    # 2. Determine total measures
    if plan_length is None:
        # Count keys that look like "Measure: X"
        measure_keys = [k for k in data.keys() if k.startswith("Measure")]
        total_measures = len(measure_keys)
    else:
        total_measures = plan_length

    lines = []

    # 3. Build Header
    lines.append(f"Total Measures: {total_measures}")
    lines.append("")

    if genre:
        lines.append(f"Genre: {genre}")
        lines.append("")

    inst_str = ", ".join(sorted(list(all_instruments))) if all_instruments else "None"
    lines.append(f"Instruments: {inst_str}")
    lines.append("")

    # 4. Helper to sort measures numerically
    def measure_sort_key(k):
        try:
            return int(k.split(': ')[1])
        except (IndexError, ValueError):
            return float('inf')

    sorted_keys = sorted([k for k in data.keys() if k != 'all_instruments'], key=measure_sort_key)

    # 5. Process Measures
    for measure_key in sorted_keys:
        details = data[measure_key]
        
        # --- Density Mapping ---
        density_val = details.get('note_density', 0)
        if density_val <= 4:
            density_str = "Low"
        elif density_val <= 10:
            density_str = "Moderate"
        else:
            density_str = "High"

        # --- Pitch Shifting ---
        p_min = details['pitch_range']['min']
        p_max = details['pitch_range']['max']
        if p_min is not None and p_max is not None:
            range_str = f"{p_min + pitch_shift}–{p_max + pitch_shift}"
        else:
            range_str = "None"
        
        ks = details.get('key_signature')
        ks_str = str(ks + pitch_shift) if ks is not None else "None"
        
        # raw_chords = details.get('chords', [])
        # chord_strs = []
        # if raw_chords:
        #     for chord in raw_chords:
        #         shifted_chord = [(n + pitch_shift) % 12 for n in chord] 
        #         shifted_chord.sort()
        #         chord_strs.append(f"[{', '.join(map(str, shifted_chord))}]")
        
        # chords_line = ", ".join(chord_strs) if chord_strs else "None"
        raw_chords = details.get('chords', [])
        chords_line = "None"
        
        if raw_chords:
            # 1. Filter for chords with 3 or more notes
            triads_and_above = [c for c in raw_chords if len(c) >= 3]
            
            if triads_and_above:
                # Priority: Pick a random chord from those with 3+ notes
                selected_chord = random.choice(triads_and_above)
            else:
                # Fallback: No triads found, so pick the largest available (e.g., a dyad)
                selected_chord = max(raw_chords, key=len)
            
            # 2. Process the selected chord (Shift -> Modulo -> Sort)
            processed_chord = sorted([(n + pitch_shift) % 12 for n in selected_chord])
            
            # 3. Format the final string
            chords_line = f"[{', '.join(map(str, processed_chord))}]"

        tempo_val = details.get('tempo')
        tempo_str = f"{tempo_val} BPM" if tempo_val is not None else "None"
        
        ts_str = details.get('time_signature')
        if ts_str is None: ts_str = "None"

        meas_inst_str = ", ".join(details.get('instruments', []))

        # --- Append to output ---
        lines.append(f"{measure_key}")
        lines.append(f"  Instruments: {meas_inst_str}")
        lines.append(f"  Pitch Range: {range_str}")
        lines.append(f"  Note Density: {density_str}")
        lines.append(f"  Tempo: {tempo_str}")
        lines.append(f"  Time Signature: {ts_str}")
        lines.append(f"  Key Signature: {ks_str}")
        lines.append(f"  Chords: {chords_line}")
        
        # --- UPDATED DYNAMICS HANDLING ---
        if 'dynamics' in details and details['dynamics']:
            dyn_data = details['dynamics']
            dyn_strs = []
            for d in dyn_data:
                if isinstance(d, dict):
                     dyn_strs.append(f"{d.get('value', '')}")
                else:
                     dyn_strs.append(str(d))
            
            lines.append(f"  Dynamics: {', '.join(dyn_strs)}")

        lines.append("")

    return "\n".join(lines)


def convert_measures_to_text(data, all_instruments, pitch_shift: int = 0, genre: str = None, plan_length: int = None):
    """
    Converts a subset of measures to text.
    - Updated to handle dynamics as a list of strings.
    """
    lines = []

    total_measures = plan_length if plan_length is not None else len(data)
    lines.append(f"Total Measures: {total_measures}")
    lines.append("")

    if genre:
        lines.append(f"Genre: {genre}")
        lines.append("")

    if isinstance(all_instruments, list):
        inst_str = ", ".join(sorted(list(set(all_instruments))))
    else:
        inst_str = str(all_instruments)
    lines.append(f"Instruments: {inst_str}")
    lines.append("")

    def measure_sort_key(k):
        try:
            return int(k.split(': ')[1])
        except (IndexError, ValueError):
            return float('inf')

    sorted_keys = sorted(data.keys(), key=measure_sort_key)

    for measure_key in sorted_keys:
        details = data[measure_key]

        density_val = details.get('note_density', 0)
        if density_val <= 4:
            density_str = "Low"
        elif density_val <= 10:
            density_str = "Moderate"
        else:
            density_str = "High"

        p_min = details['pitch_range']['min']
        p_max = details['pitch_range']['max']
        if p_min is not None and p_max is not None:
            range_str = f"{p_min + pitch_shift}–{p_max + pitch_shift}"
        else:
            range_str = "None"
        
        # raw_chords = details.get('chords', [])
        # chord_strs = []
        # if raw_chords:
        #     for chord in raw_chords:
        #         shifted_chord = [(n + pitch_shift) % 12 for n in chord]
        #         shifted_chord.sort()
        #         chord_strs.append(f"[{', '.join(map(str, shifted_chord))}]")
        
        # chords_line = ", ".join(chord_strs) if chord_strs else "None"
        raw_chords = details.get('chords', [])
        chords_line = "None"
        
        if raw_chords:
            # 1. Filter for chords with 3 or more notes
            triads_and_above = [c for c in raw_chords if len(c) >= 3]
            
            if triads_and_above:
                # Priority: Pick a random chord from those with 3+ notes
                selected_chord = random.choice(triads_and_above)
            else:
                # Fallback: No triads found, so pick the largest available (e.g., a dyad)
                selected_chord = max(raw_chords, key=len)
            
            # 2. Process the selected chord (Shift -> Modulo -> Sort)
            processed_chord = sorted([(n + pitch_shift) % 12 for n in selected_chord])
            
            # 3. Format the final string
            chords_line = f"[{', '.join(map(str, processed_chord))}]"

        tempo_val = details.get('tempo')
        tempo_str = f"{tempo_val} BPM" if tempo_val is not None else "None"
        
        ts_str = details.get('time_signature')
        if ts_str is None: ts_str = "None"

        meas_inst = details.get('instruments', [])
        meas_inst_str = ", ".join(meas_inst) if meas_inst else "None"

        ks = details.get('key_signature')
        ks_str = str(ks + pitch_shift) if ks is not None else "None"

        lines.append(f"{measure_key}")
        lines.append(f"  Instruments: {meas_inst_str}")
        lines.append(f"  Pitch Range: {range_str}")
        lines.append(f"  Note Density: {density_str}")
        lines.append(f"  Tempo: {tempo_str}")
        lines.append(f"  Time Signature: {ts_str}")
        lines.append(f"  Key Signature: {ks_str}") 
        lines.append(f"  Chords: {chords_line}")

        # --- UPDATED DYNAMICS HANDLING ---
        if 'dynamics' in details and details['dynamics']:
            dyn_data = details['dynamics']
            dyn_strs = []
            for d in dyn_data:
                if isinstance(d, dict):
                     dyn_strs.append(f"{d.get('value', '')}")
                else:
                     dyn_strs.append(str(d))
            
            lines.append(f"  Dynamics: {', '.join(dyn_strs)}")

        lines.append("")

    return "\n".join(lines)

def get_full_plan_pipeline(musicxml_file: str):
    """
    Pipeline to get the full plan from a MusicXML file.

    Args:
        musicxml_file: The path to the MusicXML file.

    Returns:
        A dictionary representing the full plan.
    """
    data = get_raw_xml_info(musicxml_file)
    combined_data = combine_raw_xml_info(data)
    full_plan = get_full_plan(combined_data)
    return full_plan

def get_text_from_xml(musicxml_file: str, pitch_shift: int = 0):
    """
    Extracts text representation from a MusicXML file.

    Args:
        musicxml_file: The path to the MusicXML file.

    Returns:
        A string containing the text representation of the measures.
    """
    data = get_raw_xml_info(musicxml_file)
    combined_data = combine_raw_xml_info(data)
    full_plan = get_full_plan(combined_data)
    top_priority_measures, all_instruments = get_priority_order(full_plan, top_pct=10, top_n=5)
    consecutive_measures = get_consecutive_measures(full_plan, top_priority_measures)
    return convert_measures_to_text(consecutive_measures, all_instruments, pitch_shift=pitch_shift)

def get_partial_plan_text(pkl_file: str, pitch_shift: int = 0, genre: str = None):
    """
    Extracts text representation from a pickled full plan file.

    Args:
        pkl_file: The path to the pickled full plan file.

    Returns:
        A string containing the text representation of the measures.
    """
    with open(pkl_file, 'rb') as f:
        full_plan = pickle.load(f)

    # Get length of full_plan excluding 'all_instruments'
    plan_length = len(full_plan) - 1 if 'all_instruments' in full_plan else len(full_plan)
    
    # Randomly choose top_n between 5 and 10
    top_n = random.randint(5, 10)
    top_priority_measures, all_instruments = get_priority_order(full_plan, top_pct=10, top_n=top_n)
    consecutive_measures = get_measures(full_plan, top_priority_measures)
    return convert_measures_to_text(consecutive_measures, all_instruments, pitch_shift=pitch_shift, genre=genre, plan_length=plan_length)

def get_full_plan_text(pkl_file: str, pitch_shift: int = 0, genre: str = None):
    """
    Extracts text representation from a pickled full plan file.

    Args:
        pkl_file: The path to the pickled full plan file.

    Returns:
        A string containing the text representation of the measures.
    """
    import pickle
    with open(pkl_file, 'rb') as f:
        full_plan = pickle.load(f)

    # Get length of full_plan excluding 'all_instruments'
    plan_length = len(full_plan) - 1 if 'all_instruments' in full_plan else len(full_plan)
    
    return convert_plan_to_text(full_plan, pitch_shift=pitch_shift, genre=genre, plan_length=plan_length)


if __name__ == "__main__":
    # Example usage
    filepath = "/data/scratch/acw769/ABC_Dataset/SymphonyNet_Dataset_MXL_abci/outputs/1203.pkl"
    text = get_full_plan_text(filepath)
    print(text)

    # data = get_raw_xml_info(musicxml_file)
    # combined_data = combine_raw_xml_info(data)
    # full_plan = get_full_plan(combined_data)

    # # Example usage of get_priority_order
    # top_priority_measures, all_instruments = get_priority_order(full_plan, top_pct=10, top_n=5)
    # print("Top Priority Measures:", top_priority_measures)

    # # Example usage of get_consecutive_measures
    # consecutive_measures = get_consecutive_measures(full_plan, top_priority_measures)
    # print("Consecutive Measures:", consecutive_measures)

    # # Example usage of convert_measures_to_text
    # text_representation = convert_measures_to_text(consecutive_measures)
    # print("Text Representation of Measures:\n", text_representation)