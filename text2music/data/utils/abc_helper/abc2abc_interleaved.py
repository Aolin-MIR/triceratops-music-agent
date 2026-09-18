import os
import re
import random
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.utils import (find_all_abc, remove_information_field,
                                                                        remove_bar_no_annotations, Quote_re, Barlines,
                                                                        strip_empty_bars)
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.rotate import rotate_abc
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.check import check_alignment_unrotated


def abc2abc_interleaved(abc_lines):
    """
    Converts standard ABC notation to interleaved ABC notation.

    Args:
        abc_lines (list): List of strings containing the ABC notation.

    Returns:
        list: List of strings containing the interleaved ABC notation.
        error (str): Error message if any. None if successful.
    """
    abc_lines = [line for line in abc_lines if line.strip() != '']
    abc_lines = remove_information_field(abc_lines=abc_lines,
                                         info_fields=['X:', 'T:', 'C:', 'W:', 'w:', 'Z:', '%%MIDI'])
    # Modified to keep the information fields except for lyrics. T for title, C for composer,
    # abc_lines = remove_information_field(abc_lines=abc_lines, info_fields=['X:', 'W:', 'w:', 'Z:', '%%MIDI'])
    abc_lines = remove_bar_no_annotations(abc_lines)

    # Remove escaped quotes and clean up barlines inside quotes
    for i, line in enumerate(abc_lines):
        if not (re.search(r'^[A-Za-z]:', line) or line.startswith('%')):
            abc_lines[i] = line.replace(r'\"', '')
            quote_contents = re.findall(Quote_re, line)
            for quote_content in quote_contents:
                for barline in Barlines:
                    if barline in quote_content:
                        line = line.replace(quote_content, '')
                        abc_lines[i] = line

    error = None
    try:
        stripped_abc_lines, bar_counts = strip_empty_bars(abc_lines)
    except Exception as e:
        print('Error in stripping empty bars:', e)
        return None, 'Error in stripping empty bars'

    if stripped_abc_lines is None:
        print('Failed to strip')
        return None, 'Failed to strip'

    # Check alignment
    _, bar_no_equal_flag, bar_dur_equal_flag = check_alignment_unrotated(stripped_abc_lines)
    if not bar_no_equal_flag:
        print('Unequal bar number')
        error = 'Unequal bar number'
    if not bar_dur_equal_flag:
        print('Unequal bar duration (unaligned)')
        error = 'Unequal bar duration (unaligned)'

    try:
        rotated_abc_lines = rotate_abc(stripped_abc_lines)
    except Exception as e:
        print('Error in rotating:', e)
        return None, 'Error in rotating'

    if rotated_abc_lines is None:
        print('Failed to rotate')
        return None, 'Failed to rotate'

    return rotated_abc_lines, error
