from text2music.data.utils.abc_helper.abctoolkit_v006_mod.utils import extract_barline_and_bartext_dict, extract_barline_and_bartext_dict_rotated, fast_ld_sim
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.duration import calculate_bartext_duration


def check_alignment_according_to_barline_and_bartext_dict(left_barline_dict, bar_text_dict, right_barline_dict):

    barline_equal_flag = True
    bar_no_equal_flag = True
    bar_dur_equal_flag = True

    for symbol in left_barline_dict.keys():
        if left_barline_dict[symbol] != left_barline_dict['V:1']:
            barline_equal_flag = False
        if right_barline_dict[symbol] != right_barline_dict['V:1']:
            barline_equal_flag = False
        if len(bar_text_dict[symbol]) != len(bar_text_dict['V:1']):
            bar_no_equal_flag = False

    for i in range(len(bar_text_dict['V:1'])):
        ref_dur = calculate_bartext_duration(bar_text_dict['V:1'][i])
        if ref_dur is None:
            bar_dur_equal_flag = False
            break
        for symbol in bar_text_dict.keys():
            if symbol == 'V:1':
                continue
            if calculate_bartext_duration(bar_text_dict[symbol][i]) != ref_dur:
                print('Odd bar duration ', symbol, ' bar ', i)
                bar_dur_equal_flag = False

    return barline_equal_flag, bar_no_equal_flag, bar_dur_equal_flag


def check_alignment_unrotated(abc_lines: list):
    '''
    检查各声部小节线是否相等、小节数是否相等、每个小节各个声部时值是否相等
    '''
    _, _, left_barline_dict, bar_text_dict, right_barline_dict = extract_barline_and_bartext_dict(abc_lines)

    return check_alignment_according_to_barline_and_bartext_dict(left_barline_dict, bar_text_dict, right_barline_dict)


def check_alignment_rotated(abc_lines: list, delete_last_line=False):
    '''
    检查各声部小节线是否相等、小节数是否相等、每个小节各个声部时值是否相等 (rotated版)
    '''
    if delete_last_line:
        # 统一删掉abc的最后一行，避免有因为patch_length不够没生成全的情况
        abc_lines = abc_lines[:-1]

    _, _, left_barline_dict, bar_text_dict, right_barline_dict = extract_barline_and_bartext_dict_rotated(abc_lines)

    return check_alignment_according_to_barline_and_bartext_dict(left_barline_dict, bar_text_dict, right_barline_dict)


def check_plagiarism(abc_1: str, abc_2: str):
    return fast_ld_sim(abc_1, abc_2) >= 0.85
