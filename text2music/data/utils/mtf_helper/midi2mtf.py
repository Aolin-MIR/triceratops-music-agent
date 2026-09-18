from typing import Optional
from os import path
import os
import mido

m3_compatible = True  # Set to True for M3 compatibility; set to False to retain all MIDI information during conversion.


def msg_to_str(msg):
    str_msg = ""
    for key, value in msg.dict().items():
        str_msg += " " + str(value)
    return str_msg.strip().encode('unicode_escape').decode('utf-8')


def load_midi(filename):
    # Load a MIDI file
    mid = mido.MidiFile(filename)
    msg_list = ["ticks_per_beat " + str(mid.ticks_per_beat)]

    # Traverse the MIDI file
    for msg in mid.merged_track:
        if m3_compatible:
            if msg.is_meta:
                if msg.type in [
                        "text", "copyright", "track_name", "instrument_name", "lyrics", "marker", "cue_marker",
                        "device_name", "sequencer_specific"
                ]:
                    continue
            else:
                if msg.type in ["sysex"]:
                    continue
        str_msg = msg_to_str(msg)
        msg_list.append(str_msg)

    return "\n".join(msg_list)


def midi2mtf(input_file: str, output_file: Optional[str] = None):
    assert path.exists(input_file)
    input_file = path.abspath(input_file)

    try:
        output = load_midi(input_file)
        log_path = os.path.join("logs", "midi2mtf_error_log.txt")
        if output == '':
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(input_file + 'error: file is empty' + '\n')
            error = 'file is empty'
            return None, error
    except Exception as e:
        log_path = os.path.join("logs", "midi2mtf_error_log.txt")
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(input_file + " " + str(e) + '\n')
        error = str(e)
        return None, error

    if output_file is not None:
        os.makedirs(path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
    return output, None
