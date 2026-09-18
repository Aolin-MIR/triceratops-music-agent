import os
from copy import deepcopy
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.transpose_mod import transpose_to_abc_lines_with_offset
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.rotate import rotate_abc, unrotate_abc
from text2music.data.utils.abci_diff import abci_diff
from unidecode import unidecode


def transpose_abci_lines_with_offset(abci_lines, key_offset):
    """
    Transpose ABC interleaved lines with a given key offset.

    Args:
        abci_lines (list): List of strings containing the ABC interleaved notation.
        key_offset (int): The number of semitones to transpose. Positive for up, negative for down.

    Returns:
        list: List of transposed ABC interleaved lines.
    """
    abc_lines = unrotate_abc(abci_lines)
    transposed_abc_lines = transpose_to_abc_lines_with_offset(abc_lines, key_offset)
    transposed_abci_lines = rotate_abc(transposed_abc_lines)
    return transposed_abci_lines

def read_abci_with_pitch_shift(filepath, pitch_shift=0, return_lines=False):
    """
    Read an ABC interleaved file and apply a pitch shift (key transpose w/ offset).

    Args:
        filepath (str): Path to the ABC interleaved file.
        pitch_shift (int): The number of semitones to shift the pitch. Default is 0 (no shift).
        return_lines (bool): If True, return the lines instead of the text. Default is False.

    Returns:
        str: The transposed ABC interleaved text or list of lines (if return_lines is True).
    """
    assert os.path.exists(filepath), f"File {filepath} does not exist."

    with open(filepath, 'r', encoding='utf-8') as f:
        abci_lines = f.readlines()
    
    # Normalize, strip, and exclude empty or title lines
    abci_lines = [
        unidecode(line)
        for line in abci_lines
        if line.strip() and not line.strip().startswith("T:") and not line.strip().startswith("C:")
    ]

    if pitch_shift == 0:
        if return_lines:
            return abci_lines
        return "".join(abci_lines)

    transposed_abci_lines = transpose_abci_lines_with_offset(abci_lines, pitch_shift)
    if return_lines:
        return transposed_abci_lines
    transposed_abci_text = "".join(transposed_abci_lines)
    return transposed_abci_text


def test_round_trip():
    """
    Test the round-trip conversion of ABC interleaved files with pitch shifting.
    """
    from utils.convert_formats import convert_abc2xml

    file = 'utils/examples/bwv_846.abci'  # org_key = 'C'

    # Original ABCi
    with open(file, 'r', encoding='utf-8') as f:
        org_abci_text = f.read()
    convert_abc2xml(file, 'utils/examples/org.xml')

    # Apply pitch shift +3 semitones
    transposed_abci_lines = read_abci_with_pitch_shift(file, pitch_shift=3, return_lines=True)
    with open('utils/examples/trans_p3.abc', 'w', encoding='utf-8') as f:
        f.writelines(transposed_abci_lines)
    convert_abc2xml('utils/examples/trans_p3.abc', 'utils/examples/trans_p3.xml')

    # Re-apply pitch shift +2 semitones
    transposed_abci_lines = transpose_abci_lines_with_offset(transposed_abci_lines, key_offset=2)
    with open('utils/examples/trans_p5.abc', 'w', encoding='utf-8') as f:
        f.writelines(transposed_abci_lines)
    convert_abc2xml('utils/examples/trans_p5.abc', 'utils/examples/trans_p5.xml')

    # Re-aaply ptich shift -5 semitones
    transposed_abci_lines = transpose_abci_lines_with_offset(transposed_abci_lines, key_offset=-5)
    recon_abci_text = "".join(transposed_abci_lines)
    with open('utils/examples/recon.abc', 'w', encoding='utf-8') as f:
        f.write(recon_abci_text)
    convert_abc2xml('utils/examples/recon.abc', 'utils/examples/recon.xml')

    # Visualize the differences
    abci_diff(org_abci_text, recon_abci_text)
