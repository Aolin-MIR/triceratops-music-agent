from os import path
import os
import mido


def str_to_msg(str_msg):
    type = str_msg.split(" ")[0]
    try:
        msg = mido.Message(type)
    except:
        msg = mido.MetaMessage(type)

    if type in ["text", "copyright", "track_name", "instrument_name", "lyrics", "marker", "cue_marker", "device_name"]:
        values = [
            type, " ".join(str_msg.split(" ")[1:-1]).encode('utf-8').decode('unicode_escape'),
            str_msg.split(" ")[-1]
        ]
    elif "[" in str_msg or "(" in str_msg:
        is_bracket = "[" in str_msg
        left_idx = str_msg.index("[") if is_bracket else str_msg.index("(")
        right_idx = str_msg.index("]") if is_bracket else str_msg.index(")")
        list_str = [int(num) for num in str_msg[left_idx + 1:right_idx].split(", ")]
        if not is_bracket:
            list_str = tuple(list_str)
        values = str_msg[:left_idx].split(" ") + [list_str] + str_msg[right_idx + 1:].split(" ")
        values = [value for value in values if value != ""]
    else:
        values = str_msg.split(" ")

    if len(values) != 1:
        for idx, (key, content) in enumerate(msg.__dict__.items()):
            if key == "type":
                continue
            value = values[idx]
            if isinstance(content, int) or isinstance(content, float):
                float_value = float(value)
                value = float_value
                if value % 1 == 0:
                    value = int(value)
            setattr(msg, key, value)

    return msg


def mtf2midi(input_file: str, output_file: str):
    assert path.exists(input_file)
    input_file = path.abspath(input_file)
    os.makedirs(path.dirname(output_file), exist_ok=True)

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            msg_list = f.read().splitlines()

        # Build a new MIDI file based on the MIDI messages
        new_mid = mido.MidiFile()
        new_mid.ticks_per_beat = int(msg_list[0].split(" ")[1])

        track = mido.MidiTrack()
        new_mid.tracks.append(track)

        for msg in msg_list[1:]:
            if "unknown_meta" in msg:
                continue
            new_msg = str_to_msg(msg)
            track.append(new_msg)

        new_mid.save(output_file)
        return output_file
    except Exception as e:
        with open('logs/mtf2midi_error_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"Error processing {input_file}: {str(e)}\n")
        return None
