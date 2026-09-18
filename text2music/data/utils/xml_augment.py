#!/usr/bin/env python3
"""
transpose_musicxml.py

Transposes a MusicXML file by a given number of semitones while ensuring
accidental sign matches the active key signature:

- If active <fifths> is negative -> prefer flat spellings (alter <= 0)
- If active <fifths> is positive -> prefer sharp spellings (alter >= 0)
- If active == 0 -> prefer naturals (alter == 0) if possible

Usage:
    python transpose_musicxml.py --in input.xml --out output.xml --semitones -1
"""
import xml.etree.ElementTree as ET
import argparse
import sys

NOTE_TO_MIDI_BASE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SEMITONE_TO_FIFTHS = {
    0: 0, 1: -5, 2: 2, 3: -3, 4: 4, 5: -1,
    6: 6, 7: 1, 8: -4, 9: 3, 10: -2, 11: 5
}

# Sharp-preferred spellings for each pitch-class
SHARP_MIDI_TO_NOTE = {
    0: ('C', 0), 1: ('C', 1), 2: ('D', 0), 3: ('D', 1),
    4: ('E', 0), 5: ('F', 0), 6: ('F', 1), 7: ('G', 0),
    8: ('G', 1), 9: ('A', 0), 10: ('A', 1), 11: ('B', 0)
}

# Flat-preferred spellings for each pitch-class
FLAT_MIDI_TO_NOTE = {
    0: ('C', 0), 1: ('D', -1), 2: ('D', 0), 3: ('E', -1),
    4: ('E', 0), 5: ('F', 0), 6: ('G', -1), 7: ('G', 0),
    8: ('A', -1), 9: ('A', 0), 10: ('B', -1), 11: ('B', 0)
}

def find_percussion_parts(root: ET.Element) -> set:
    """Return set of part ids that are percussion (skip these when transposing)."""
    percussion_ids = set()
    score_part_list = root.find('part-list')
    if score_part_list is None:
        return percussion_ids

    for score_part in score_part_list.findall('score-part'):
        pid = score_part.get('id')
        if not pid:
            continue
        part_node = root.find(f"part[@id='{pid}']")
        if part_node is None:
            continue

        is_perc = False
        if part_node.find('.//unpitched') is not None:
            is_perc = True
        midi_chan = score_part.find('.//midi-channel')
        if midi_chan is not None and midi_chan.text == '10':
            is_perc = True
        clef_sign = part_node.find('.//clef/sign')
        if clef_sign is not None and clef_sign.text == 'percussion':
            is_perc = True

        if is_perc:
            percussion_ids.add(pid)

    return percussion_ids

def transpose_keys(root: ET.Element, semitones: int):
    """Transpose every <key><fifths> element by semitones using SEMITONE_TO_FIFTHS."""
    for key in root.findall('.//key'):
        fifths_elem = key.find('fifths')
        if fifths_elem is None:
            continue
        try:
            current_fifths = int(fifths_elem.text)
            current_key_pc = (current_fifths * 7) % 12
            new_key_pc = (current_key_pc + semitones) % 12
            new_fifths = SEMITONE_TO_FIFTHS[new_key_pc]
            fifths_elem.text = str(new_fifths)
        except Exception:
            # ignore malformed key
            continue

def choose_spelling_for_pc(pc: int, active_fifths: int):
    """
    Return (step, alter) for the given pitch-class (pc) according to active_fifths:
      - active_fifths < 0 -> use FLAT_MIDI_TO_NOTE
      - active_fifths > 0 -> use SHARP_MIDI_TO_NOTE
      - active_fifths == 0 -> prefer natural, otherwise minimal abs(alter), prefer flats on tie
    """
    sharp_step, sharp_alter = SHARP_MIDI_TO_NOTE[pc]
    flat_step, flat_alter = FLAT_MIDI_TO_NOTE[pc]

    if active_fifths < 0:
        return flat_step, flat_alter
    if active_fifths > 0:
        return sharp_step, sharp_alter

    # active_fifths == 0: prefer natural (alter == 0)
    if sharp_alter == 0:
        return sharp_step, 0
    if flat_alter == 0:
        return flat_step, 0
    # otherwise choose the one with smaller absolute alter; if tie prefer flat
    if abs(flat_alter) <= abs(sharp_alter):
        return flat_step, flat_alter
    return sharp_step, sharp_alter

def transpose_notes(root: ET.Element, semitones: int, percussion_parts: set):
    """Transpose all <pitch> elements, using the measure's active key (fifths) to choose spelling."""
    for part in root.findall('part'):
        pid = part.get('id')
        if pid in percussion_parts:
            continue

        # default context: C major / A minor
        active_fifths = 0

        for measure in part.findall('measure'):
            # update context if a key shows up in this measure (works for attributes/key)
            key_elem = measure.find('.//key')  # finds key inside attributes or measure
            if key_elem is not None:
                fifths_elem = key_elem.find('fifths')
                if fifths_elem is not None:
                    try:
                        active_fifths = int(fifths_elem.text)
                    except Exception:
                        active_fifths = 0

            # choose spelling preference based on active_fifths
            for pitch in measure.findall('.//pitch'):
                step_elem = pitch.find('step')
                octave_elem = pitch.find('octave')
                alter_elem = pitch.find('alter')

                if step_elem is None or octave_elem is None:
                    # incomplete pitch; skip
                    continue

                try:
                    orig_step = step_elem.text
                    orig_oct = int(octave_elem.text)
                    orig_alter = int(alter_elem.text) if alter_elem is not None else 0
                except Exception:
                    continue

                # MIDI conversion: note number where C-1 = 0 in MusicXML convention here: (octave+1)*12 + base + alter
                old_midi = NOTE_TO_MIDI_BASE[orig_step] + ((orig_oct + 1) * 12) + orig_alter
                new_midi = old_midi + semitones

                new_pc = new_midi % 12
                new_oct = (new_midi // 12) - 1

                # get spelling that matches the key's sign
                new_step, new_alter = choose_spelling_for_pc(new_pc, active_fifths)

                # Update XML step / octave
                step_elem.text = new_step
                octave_elem.text = str(new_oct)

                # Update alter element (insert/remove/update)
                if new_alter != 0:
                    if alter_elem is None:
                        # insert alter after step (step is first child in pitch)
                        alter_elem = ET.Element('alter')
                        # Usually pitch children order: step, alter, octave. Insert at index 1.
                        children = list(pitch)
                        if len(children) >= 1:
                            pitch.insert(1, alter_elem)
                        else:
                            pitch.append(alter_elem)
                    alter_elem.text = str(new_alter)
                else:
                    # remove alter if present and not needed
                    if alter_elem is not None:
                        pitch.remove(alter_elem)

def transpose_musicxml(input_file: str, output_file: str, semitones: int):
    # parse
    try:
        ET.register_namespace('', "http://www.musicxml.org/xsd/musicxml.xsd")
        tree = ET.parse(input_file)
        root = tree.getroot()
    except (ET.ParseError, FileNotFoundError) as e:
        print(f"Error reading/parsing '{input_file}': {e}", file=sys.stderr)
        return

    percussion_parts = find_percussion_parts(root)

    # Pass 1: keys
    transpose_keys(root, semitones)

    # Pass 2: notes
    transpose_notes(root, semitones, percussion_parts)

    # write
    try:
        tree.write(output_file, encoding='UTF-8', xml_declaration=True)
        # print(f"Successfully wrote transposed file to '{output_file}'")
    except Exception as e:
        print(f"Error writing '{output_file}': {e}", file=sys.stderr)
    return


if __name__ == "__main__":
    transpose_musicxml("/data/scratch/eey549/ABC_Dataset/ABC_Dataset/SymphonyNet_Dataset_MXL_abci/outputs/2872886.xml", "/data/home/acw769/text2score/text2music/inference/output/augmented.xml", semitones=1)