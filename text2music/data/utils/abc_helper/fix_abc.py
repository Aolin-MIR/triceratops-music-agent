"""
This code fixes various issues with ABCnotation dataset and abctoolkit 0.0.6.

"""

import re


def fix_missing_voice_field(abc_lines):
    """
    Fix missing voice field in ABC notation:
    - Insert 'V:1 clef=treble' after the key signature.
    - Insert 'V:1' before the first note line.
    - Ensure note lines start with '|', without affecting header lines.
    """

    # Check if voice fields (e.g., V:1) already exist. If so, do nothing.
    if any(line.strip().startswith('V:') for line in abc_lines):
        return abc_lines

    # Step 1: Remove empty lines
    abc_lines = [line for line in abc_lines if line.strip()]

    # Step 2: Find 'K:' line (key signature)
    key_idx = next((i for i, line in enumerate(abc_lines) if line.startswith('K:')), -1)
    if key_idx == -1:
        raise ValueError("No key signature (K:) found.")

    # Step 3: Insert 'V:1 clef=treble' after key signature
    abc_lines.insert(key_idx + 1, 'V:1\n')

    # Step 4: Insert 'V:1' before the first music line (not a header line)
    def is_music_line(line):
        return not re.match(r'^[A-Za-z]:', line) and re.search(r'[A-Ga-gz]', line)

    for i in range(key_idx + 2, len(abc_lines)):
        if is_music_line(abc_lines[i]):
            abc_lines.insert(i, 'V:1\n')
            break

    # Step 5: Add '|' at beginning of music lines if missing
    for i in range(len(abc_lines)):
        line = abc_lines[i]
        if is_music_line(line):
            stripped = line.strip()
            if not stripped.startswith('|') and not stripped.startswith('[|') and not stripped.startswith(
                    ':|') and not stripped.startswith('|:'):
                abc_lines[i] = '|' + stripped + '\n'
            elif not line.endswith('\n'):
                abc_lines[i] = line + '\n'

    return abc_lines


def remove_empty_lines(abc_lines):
    # Remove lines that are completely empty or contain only whitespace
    return [line for line in abc_lines if line.strip()]
