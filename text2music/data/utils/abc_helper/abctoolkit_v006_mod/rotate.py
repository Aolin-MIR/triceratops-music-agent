import os
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.utils import find_all_abc, extract_barline_and_bartext_dict, extract_barline_and_bartext_dict_rotated
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.check import check_alignment_unrotated


def rotate_abc(abc_lines: list):

    metadata_lines, prefix_dict, left_barline_dict, bar_text_dict, right_barline_dict = \
        extract_barline_and_bartext_dict(abc_lines)

    # _, bar_no_equal_flag, bar_dur_equal_flag = check_alignment_unrotated(abc_lines)
    # if not bar_no_equal_flag:
    #     raise Exception('Unequal bar number')
    # if not bar_dur_equal_flag:
    #     raise Exception('Unequal bar duration (unaligned)')

    rotated_abc_lines = metadata_lines
    for i, line in enumerate(rotated_abc_lines):
        if not line.endswith('\n'):
            rotated_abc_lines[i] = line + '\n'
    # 处理第0小节
    line_0 = ''
    for symbol in prefix_dict.keys():
        part_patch = '[' + symbol + ']'
        part_patch += prefix_dict[symbol]
        part_patch += left_barline_dict[symbol][0]
        part_patch += bar_text_dict[symbol][0]
        part_patch += right_barline_dict[symbol][0]
        line_0 += part_patch
    line_0 += '\n'
    rotated_abc_lines.append(line_0)

    for i in range(1, len(bar_text_dict['V:1'])):
        line = ''
        for symbol in prefix_dict.keys():
            part_patch = '[' + symbol + ']'
            part_patch += bar_text_dict[symbol][i]
            part_patch += right_barline_dict[symbol][i]
            line += part_patch
        line += '\n'
        rotated_abc_lines.append(line)

    return rotated_abc_lines


def unrotate_abc(abc_lines: list):

    metadata_lines, prefix_dict, left_barline_dict, bar_text_dict, right_barline_dict = \
        extract_barline_and_bartext_dict_rotated(abc_lines)

    unrotated_abc_lines = metadata_lines
    for i, line in enumerate(unrotated_abc_lines):
        if not line.endswith('\n'):
            unrotated_abc_lines[i] = line + '\n'

    for symbol in prefix_dict.keys():
        unrotated_abc_lines.append(symbol + '\n')
        bar_index = 0
        line_len = 0
        line = prefix_dict[symbol] + left_barline_dict[symbol][0] + ' '
        while bar_index < len(bar_text_dict[symbol]):
            bar = bar_text_dict[symbol][bar_index] + ' ' + \
                  right_barline_dict[symbol][bar_index] + ' '
            if line_len == 0 or line_len + len(bar) <= 100:
                line += bar
                line_len += len(bar)
                bar_index += 1
            else:
                line += '\n'
                unrotated_abc_lines.append(line)
                line = ' '
                line_len = 0
        if line.strip() != '':
            line += '\n'
            unrotated_abc_lines.append(line)

    return unrotated_abc_lines


if __name__ == '__main__':
    ori_folder = r'D:\Research\Projects\MultitrackComposer\dataset\06_abc_text-filtered\musescoreV2'
    des_folder = r'D:\Research\Projects\MultitrackComposer\dataset\08_abc_rotated_CLAMP\musescoreV2'
    if not os.path.exists(des_folder):
        os.mkdir(des_folder)

    count = 0
    for abc_path in find_all_abc(r'D:\Research\Projects\MultitrackComposer\dataset\06_abc_text-filtered\musescoreV2'):
        count += 1
        if count % 1000 == 0:
            print(count)
        filename = os.path.split(abc_path)[-1]
        des_path = os.path.join(des_folder, filename)

        if not os.path.exists(des_path):

            with open(abc_path, 'r', encoding='utf-8') as f:
                abc_lines = f.readlines()
            try:
                rotated_abc_lines = rotate_abc(abc_lines)
            except Exception as e:
                print(filename, e)
                continue

            if rotated_abc_lines is not None:

                with open(des_path, 'w', encoding='utf-8') as w:
                    w.writelines(rotated_abc_lines)
            else:
                print(filename)

    # abc_path = os.path.join(ori_folder, '1051916.abc')
    #
    # with open(abc_path, 'r', encoding='utf-8') as f:
    #     abc_lines = f.readlines()
    #
    # rotated_abc_lines = rotate_abc(abc_lines)
