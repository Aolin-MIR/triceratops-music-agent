"""
This code is based on PyPI package abctoolkit==0.0.6.
We fixed the missing last bar ending in the Wikifonia dataset by modifying lines 488–489.
"""
import os
import re
import jellyfish
from unidecode import unidecode
from rapidfuzz import fuzz

Barlines = ["||:", ":||", "[|:", ":|]", "|]:", ":[|", "|:", "::", ":|", "[|", "||", "|]", "|"]
Barline_regexPattern = '(' + '|'.join(map(re.escape, Barlines)) + ')'

Exclaim_re = r'![^!]+!'
Quote_re = r'"[^"]*"'
SquareBracket_re = r'\[[^\]]+\]'
Brace_re = r'\{[^}]+\}'


def find_all_abc(directory):
    for root, directories, files in os.walk(directory):
        for filename in files:
            file_path = os.path.join(root, filename)
            if file_path.endswith('.abc') or file_path.endswith('txt'):
                yield file_path


def extract_metadata_and_tunebody(abc_lines: list):
    # 分割为 metadata 和 tunebody
    tunebody_index = None
    for i, line in enumerate(reversed(abc_lines)):
        if line.strip() == 'V:1':
            tunebody_index = len(abc_lines) - 1 - i
            break
    if tunebody_index is None:
        raise Exception('tunebody index not found.')

    metadata_lines = abc_lines[:tunebody_index]
    tunebody_lines = abc_lines[tunebody_index:]

    return metadata_lines, tunebody_lines


def extract_metadata_and_tunebody_rotated(abc_lines: list):
    # 分割为 metadata 和 tunebody（rotate过后的版本）
    tunebody_index = None
    for i, line in enumerate(abc_lines):
        if '[V:1]' in line:
            tunebody_index = i
            break

    metadata_lines = abc_lines[:tunebody_index]
    tunebody_lines = abc_lines[tunebody_index:]

    return metadata_lines, tunebody_lines


def extract_metadata_and_parts(abc_lines: list):

    metadata_lines, tunebody_lines = extract_metadata_and_tunebody(abc_lines)

    part_symbol_list = []
    part_text_list = []

    last_start_index = None
    for i, line in enumerate(tunebody_lines):
        if i == 0:
            last_start_index = 1
            part_symbol_list.append(line.strip())
            continue
        if line.startswith('V:'):
            last_end_index = i
            part_text_list.append(''.join(tunebody_lines[last_start_index:last_end_index]))
            part_symbol_list.append(line.strip())
            last_start_index = i + 1
    part_text_list.append(''.join(tunebody_lines[last_start_index:]))

    part_text_dict = {}
    for i in range(len(part_symbol_list)):
        part_text_dict[part_symbol_list[i]] = part_text_list[i]

    return metadata_lines, part_text_dict


def extract_barline_and_bartext_dict(abc_lines: list):
    '''
    提取 metadatalines，以及各个声部的 part_text, prefix, left_barline, bar_text, right_barline
    '''
    metadata_lines, part_text_dict = extract_metadata_and_parts(abc_lines)

    prefix_dict = {key: '' for key in part_text_dict.keys()}
    left_barline_dict = {key: [] for key in part_text_dict.keys()}
    right_barline_dict = {key: [] for key in part_text_dict.keys()}
    bar_text_dict = {key: [] for key in part_text_dict.keys()}

    for symbol, voice_text in part_text_dict.items():
        prefix, left_barlines, bar_texts, right_barlines = split_into_bars_and_barlines(voice_text)
        prefix_dict[symbol] = prefix
        left_barline_dict[symbol] = left_barlines
        right_barline_dict[symbol] = right_barlines
        bar_text_dict[symbol] = bar_texts

    return metadata_lines, prefix_dict, left_barline_dict, bar_text_dict, right_barline_dict


def merge_barline_and_bartext_dict(metadata_lines, prefix_dict, left_bar_line_dict, bar_text_dict, right_barline_dict):

    # 重新组装，每列不要超过100字符
    abc_lines = metadata_lines
    for symbol in prefix_dict.keys():
        abc_lines.append(symbol + '\n')
        bar_index = 0
        line_len = 0
        line = prefix_dict[symbol] + left_bar_line_dict[symbol][0] + ' '
        while bar_index < len(bar_text_dict[symbol]):
            bar = bar_text_dict[symbol][bar_index] + ' ' + \
                  right_barline_dict[symbol][bar_index] + ' '
            if line_len == 0 or line_len + len(bar) <= 100:
                line += bar
                line_len += len(bar)
                bar_index += 1
            else:
                line += '\n'
                abc_lines.append(line)
                line = ' '
                line_len = 0
        if line.strip() != '':
            line += '\n'
            abc_lines.append(line)

    return abc_lines


def extract_barline_and_bartext_dict_rotated(abc_lines: list):
    '''
    提取 metadatalines，以及各个声部的 part_text, prefix, left_barline, bar_text, right_barline (rotated版)
    '''

    metadata_lines, tunebody_lines = extract_metadata_and_tunebody_rotated(abc_lines)

    part_symbol_list = []
    for line in metadata_lines:
        if line.startswith('V:'):
            part_symbol_list.append(line.split()[0])
    part_symbol_list = sorted(part_symbol_list, key=lambda x: int(x[2:]))

    prefix_dict = {key: '' for key in part_symbol_list}
    left_barline_dict = {key: [] for key in part_symbol_list}
    right_barline_dict = {key: [] for key in part_symbol_list}
    bar_text_dict = {key: [] for key in part_symbol_list}

    for i, line in enumerate(tunebody_lines):

        for j, symbol in enumerate(part_symbol_list):

            start_sign = '[' + part_symbol_list[j] + ']'
            start_index = line.index(start_sign) + len(start_sign)
            if j < len(part_symbol_list) - 1:
                end_sign = '[' + part_symbol_list[j + 1] + ']'
                end_index = line.index(end_sign)
                bar_patch = line[start_index:end_index]
            else:
                bar_patch = line[start_index:]

            bar_eles = re.split(Barline_regexPattern, bar_patch)
            bar_eles[-2] = bar_eles[-2] + bar_eles[-1]  # 必为 right_barline
            bar_eles = bar_eles[:-1]

            if i == 0:  # 第一行，需要单独考虑 prefix 和 left_barline
                if len(bar_eles) == 4:  # 有prefix（可能为空）和left_barline
                    prefix_dict[symbol] = bar_eles[0]
                    # 处理 left_barline
                    if re.match(r'\d', bar_eles[2]) or bar_eles[2][0] == ':':
                        k = 0
                        for k in range(len(bar_eles[2])):
                            if not bar_eles[2][k] in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '.', '-', ':']:
                                break
                        affix = bar_eles[2][:k]
                        bar_eles[2] = bar_eles[2][k:].strip()
                        bar_eles[1] = bar_eles[1] + affix
                    left_barline_dict[symbol].append(bar_eles[1])
                elif len(bar_eles) == 3 or len(bar_eles) == 2:  # 无 prefix 和 left_barline
                    left_barline_dict[symbol].append('')
                else:
                    print(bar_eles)
                    raise Exception('这什么情况我真没见过')
            else:
                left_barline_dict[symbol].append(right_barline_dict[symbol][-1])  # 上一小节的右小节线

            bar_text_dict[symbol].append(bar_eles[-2])
            right_barline_dict[symbol].append(bar_eles[-1])

    return metadata_lines, prefix_dict, left_barline_dict, bar_text_dict, right_barline_dict


def extract_global_and_local_metadata(metadata_lines: list):
    '''
    提取 global metadata 和各声部的 local_metadata
    '''
    for i, line in enumerate(metadata_lines):
        if line.startswith('V:'):
            global_metadata_index = i
            break

    global_metadata_lines = metadata_lines[:global_metadata_index]
    local_metadata_lines = metadata_lines[global_metadata_index:]

    global_metadata_dict = {}
    for i, line in enumerate(global_metadata_lines):
        if line.startswith('%%'):
            key = line.split()[0]
            value = line[len(key):].strip()
            global_metadata_dict[key] = value
        elif line[0].isalpha and line[1] == ':':
            key = line[0]
            if key not in global_metadata_dict.keys():
                global_metadata_dict[key] = []
            value = line[2:].strip()
            global_metadata_dict[key].append(value)

    local_metadata_dict = {}
    for i, line in enumerate(local_metadata_lines):
        if line.startswith('V:'):
            symbol = line.split()[0]
            local_metadata_dict[symbol] = {}
            key = 'V'
            value = line[len(symbol):].strip()
            local_metadata_dict[symbol][key] = value
        elif line[0].isalpha and line[1] == ':':
            key = line[0]
            value = line[2:].strip()
            if key not in local_metadata_dict[symbol].keys():
                local_metadata_dict[symbol][key] = []
            local_metadata_dict[symbol][key].append(value)

    return global_metadata_dict, local_metadata_dict


def merge_global_and_local_metadata(global_metadata_dict, local_metadata_dict):
    metadata_lines = []

    for key, value in global_metadata_dict.items():
        if key.startswith('%%'):
            line = key + ' ' + value
            metadata_lines.append(line + '\n')
        else:
            if isinstance(value, str):
                line = key + ':' + value
                metadata_lines.append(line + '\n')
            elif isinstance(value, list):
                for v in value:
                    line = key + ':' + v
                    metadata_lines.append(line + '\n')

    for symbol in local_metadata_dict.keys():
        for key in local_metadata_dict[symbol].keys():
            if key == 'V':
                line = symbol + ' ' + local_metadata_dict[symbol][key]
                metadata_lines.append(line + '\n')
            else:
                for value in local_metadata_dict[symbol][key]:
                    line = key + ':' + value
                    metadata_lines.append(line + '\n')

    return metadata_lines


# 连歌词一块提取
def extract_barline_bartext_lyrics_dict(abc_lines):

    # 去掉%注释
    for i, line in enumerate(abc_lines):
        abc_lines[i] = re.sub(r'%\d+\n$', '\n', line)

    metadata_lines, tunebody_lines = extract_metadata_and_tunebody(abc_lines)
    lines_wo_lyrics = metadata_lines  # 去除歌词行的 abc_lines

    part_text_dict = {}
    lyrics_dict = {}  # 可能有多个w行，那就里面多个list

    w_index = -1  # 歌词行号
    for i in range(len(tunebody_lines)):
        line = tunebody_lines[i]
        if line.startswith('V:'):
            part_symbol = line.strip()
            part_text_dict[part_symbol] = ''
            lyrics_dict[part_symbol] = []
            lines_wo_lyrics.append(tunebody_lines[i])
        elif not line.startswith('w:'):  # 正常曲调行
            part_text_dict[part_symbol] += line
            w_index = -1
            lines_wo_lyrics.append(tunebody_lines[i])
        else:  # 歌词行
            w_index += 1
            if w_index >= len(lyrics_dict[part_symbol]):
                lyrics_dict[part_symbol].append(line[2:].strip())  # 去掉行尾\n
            else:
                lyrics_dict[part_symbol][w_index] += line[2:].strip()

    metadata_lines, prefix_dict, left_barline_dict, bar_text_dict, right_barline_dict = \
        extract_barline_and_bartext_dict(lines_wo_lyrics)

    # 按小节拆分歌词
    for symbol, lyrics_list in lyrics_dict.items():
        for i in range(len(lyrics_list)):
            lyrics = lyrics_dict[symbol][i]
            lyrics_dict[symbol][i] = lyrics.split('|')[:-1]  # 去掉最后一个''
            if len(lyrics_dict[symbol][i]) != len(bar_text_dict[symbol]):
                raise Exception

    return metadata_lines, prefix_dict, left_barline_dict, bar_text_dict, right_barline_dict, lyrics_dict


def merge_barline_bartext_lyrics_dict(metadata_lines, prefix_dict, left_barline_dict, bar_text_dict, right_barline_dict,
                                      lyrics_dict):
    # 重新组装，每列不要超过100字符
    abc_lines = metadata_lines
    for symbol in prefix_dict.keys():
        abc_lines.append(symbol + '\n')
        bar_index = 0
        line_len = 0
        line = prefix_dict[symbol] + left_barline_dict[symbol][0] + ' '
        line_start_bar_index = 0  # 每行第一个小节对应的index
        while bar_index < len(bar_text_dict[symbol]):
            bar = bar_text_dict[symbol][bar_index] + ' ' + \
                right_barline_dict[symbol][bar_index] + ' '
            if line_len == 0 or line_len + len(bar) <= 100:
                line += bar
                line_len += len(bar)
                bar_index += 1
            else:
                line += '\n'
                abc_lines.append(line)
                line = ' '
                line_len = 0
                # 加歌词行
                for lyrics_list in lyrics_dict[symbol]:
                    lyrics_line = 'w: ' + '|'.join(lyrics_list[line_start_bar_index:bar_index]) + '|\n'
                    abc_lines.append(lyrics_line)
                line_start_bar_index = bar_index
        if line.strip() != '':
            line += '\n'
            abc_lines.append(line)
            for lyrics_list in lyrics_dict[symbol]:
                lyrics_line = 'w: ' + '|'.join(lyrics_list[line_start_bar_index:bar_index]) + '|\n'
                abc_lines.append(lyrics_line)

    return abc_lines


def extract_a_part(abc_lines: list, part: str):
    '''
    在多轨abc中提取某一个声部，结合 global 和 local metadata，生成一条完整的单轨的abc
    '''
    pass


def remove_information_field(abc_lines: list, info_fields: list):
    # info_fields: ['X:', 'T:', 'C:', '%%MIDI', ...]
    filtered_abc_lines = []
    for line in abc_lines:
        save_flag = True
        for symbol in info_fields:
            if line.startswith(symbol):
                save_flag = False
        if save_flag:
            filtered_abc_lines.append(line)

    return filtered_abc_lines


def remove_bar_no_annotations(abc_lines: list):
    # 去掉行末的小节号

    metadata_lines, tunebody_lines = extract_metadata_and_tunebody(abc_lines)

    for i, line in enumerate(tunebody_lines):
        tunebody_lines[i] = re.sub(r'%\d+\n$', '\n', line)
    abc_lines = metadata_lines + tunebody_lines

    return abc_lines


def remove_wrapped_content(abc_text: str, wrap_symbols: list):
    '''
    注意！本函数非常粗放：[]会移除多音和弦，""会移除和弦记号，请谨慎使用
    '''

    if r'""' in wrap_symbols:
        abc_text = re.sub(Quote_re, '', abc_text)
    if r"!!" in wrap_symbols:
        abc_text = re.sub(Exclaim_re, '', abc_text)
    if r"[]" in wrap_symbols:
        abc_text = re.sub(SquareBracket_re, '', abc_text)
    if r"{}" in wrap_symbols:
        abc_text = re.sub(Brace_re, '', abc_text)

    return abc_text


def remove_square_bracket_information_field(abc_text: str):
    # 去掉[]包裹的 information field，如[K:][M:]
    square_bracket_matches = re.findall(SquareBracket_re, abc_text)
    for match in square_bracket_matches:
        if match[1].isalpha() and match[2] == ':':
            abc_text = abc_text.replace(match, '')

    return abc_text


def remove_quote_text_annotations(abc_text: str):
    # 移除""包裹的 text annotation，不移除和弦记号
    quote_matches = re.findall(Quote_re, abc_text)
    for match in quote_matches:
        if match[1] in ['^', '_', '<', '>', '@']:
            abc_text = abc_text.replace(match, '')

    return abc_text


def split_into_bars(abc_text: str):
    '''
    Split a voice text into bars (with barline on right side)
    '''

    bars = re.split(Barline_regexPattern, abc_text.strip())
    bars = [bar for bar in bars if bar.strip() != '']  # remove empty strings
    bars = [bars[0]] + [bars[i] for i in range(1, len(bars)) if bars[i] != bars[i - 1]]  # 防止出现连续小节线的情况

    if bars[0] in Barlines:
        bars[1] = bars[0] + bars[1]
        bars = bars[1:]
    elif remove_square_bracket_information_field(bars[0]).strip() == '':  # 如果开头是纯[information field]
        bars[2] = bars[0] + bars[1] + bars[2]

    bars = [bars[i * 2] + bars[i * 2 + 1] for i in range(len(bars) // 2)]

    for j in range(len(bars)):
        bars[j] = bars[j].strip().replace('\n', '')  # strip，去掉\n
        # 如果以数字或冒号开头，则提取数字之后的字符串，直到非数字/,/./-出现，把它加到上一个patch末尾
        if re.match(r'\d', bars[j]) or bars[j][0] == ':':
            k = 0
            for k in range(len(bars[j])):
                if not bars[j][k] in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '.', '-', ':']:
                    break
            affix = bars[j][:k]
            bars[j] = bars[j][k:].strip()
            bars[j - 1] = bars[j - 1] + affix

    return bars


# Fixing split_into_bars_and_barlines(...) to avoid '|:\n:|` issues.
def split_into_bars_and_barlines(abc_text: str):
    '''
    Split an ABC notation voice line into prefix, left_barlines, bar contents, and right_barlines.
    Robust to newlines inside barlines (e.g., "|:\n:|").
    '''

    # 1. Normalize and collapse newlines inside potential barlines (e.g., '|:\n:|' -> '|::|')
    abc_text = re.sub(r'([|:])\s*\n\s*([|:])', r'\1\2', abc_text)

    # 2. Remove standalone newlines (they're not meaningful structurally)
    abc_text = abc_text.replace('\n', ' ')
    abc_text = re.sub(r'\s+', ' ', abc_text).strip()

    # 3. Split based on barlines
    bars = re.split(Barline_regexPattern, abc_text)
    bars = [bar.strip() for bar in bars if bar.strip() != '']  # Remove empty segments
    bars = [bars[0]] + [bars[i] for i in range(1, len(bars)) if bars[i] != bars[i - 1]]  # Remove consecutive duplicates

    # 4. Handle prefix (e.g., [K:C]) at the beginning
    prefix = ''
    if bars[0] in Barlines:
        bar_content_start_id = 1
    elif remove_square_bracket_information_field(bars[0]).strip() == '':
        bar_content_start_id = 2
        prefix = bars[0].strip()
    else:
        bar_content_start_id = 0

    # 5. Preprocess potential bar-related affixes
    j = bar_content_start_id
    while j < len(bars):
        bars[j] = bars[j].strip()
        # If the bar content starts with digits or colons, attach them to the previous barline
        if bars[j] and (re.match(r'\d', bars[j]) or bars[j][0] == ':'):
            k = 0
            for k in range(len(bars[j])):
                if bars[j][k] not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '.', '-', ':']:
                    break
            else:
                k += 1
            affix = bars[j][:k]
            bars[j] = bars[j][k:].strip()
            bars[j - 1] = bars[j - 1] + affix
        j += 2

    # 6. Ensure even length to allow clean triplets of left_barline, bar_text, right_barline
    if len(bars) % 2 == 0:
        bars.append('|')  # Add dummy right barline

    # 7. Parse into left_barlines, bar_texts, right_barlines
    if bars[0] in Barlines:
        left_barlines = [bars[i * 2] for i in range(len(bars) // 2)]
        bar_texts = [bars[i * 2 + 1] for i in range(len(bars) // 2)]
        right_barlines = [bars[i * 2 + 2] for i in range(len(bars) // 2)]
    elif prefix == '':
        left_barlines = [''] + [bars[i * 2 + 1] for i in range(len(bars) // 2 - 1)]
        bar_texts = [bars[i * 2] for i in range(len(bars) // 2)]
        right_barlines = [bars[i * 2 + 1] for i in range(len(bars) // 2)]
    else:
        left_barlines = [bars[i * 2 + 1] for i in range(len(bars) // 2 - 1)]
        bar_texts = [bars[i * 2 + 2] for i in range(len(bars) // 2 - 1)]
        right_barlines = [bars[i * 2 + 3] for i in range(len(bars) // 2 - 1)]

    # 8. Consistency check
    if not (len(left_barlines) == len(bar_texts) == len(right_barlines)):
        raise Exception('Unequal bar elements')

    return prefix, left_barlines, bar_texts, right_barlines


# Below is the original code from abctoolkit 0.0.6
#
# def split_into_bars_and_barlines(abc_text: str):
#     '''
#     Split a voice text into bars / left_barlines / right_barlines
#     '''

#     bars = re.split(Barline_regexPattern, abc_text.strip())
#     bars = [bar for bar in bars if bar.strip() != '']  # remove empty strings
#     bars = [bars[0]] + [bars[i] for i in range(1, len(bars)) if bars[i] != bars[i - 1]]  # 防止出现连续小节线的情况

#     prefix = ''  # 前缀，用来容纳最开头的[K:]这种
#     if bars[0] in Barlines:
#         bar_content_start_id = 1
#     elif remove_square_bracket_information_field(bars[0]).strip() == '':
#         bar_content_start_id = 2
#         prefix = bars[0].strip()
#     else:
#         bar_content_start_id = 0

#     j = bar_content_start_id
#     while j < len(bars):
#         bars[j] = bars[j].strip().replace('\n', '')  # strip，去掉\n
#         # 如果以数字或冒号开头，则提取数字之后的字符串，直到非数字/,/./-出现，把它加到上一个小节线的末尾
#         if re.match(r'\d', bars[j]) or bars[j][0] == ':':
#             k = 0
#             for k in range(len(bars[j])):
#                 if not bars[j][k] in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '.', '-', ':']:
#                     break
#             affix = bars[j][:k]
#             bars[j] = bars[j][k:].strip()
#             bars[j - 1] = bars[j - 1] + affix
#         j += 2

#     # Fix: Ensure bars has odd length to prevent IndexError in right_barlines extraction
#     if len(bars) % 2 == 0:
#         bars.append('|')

#     if bars[0] in Barlines:
#         left_barlines = [bars[i * 2] for i in range(len(bars) // 2)]
#         bar_texts = [bars[i * 2 + 1] for i in range(len(bars) // 2)]
#         right_barlines = [bars[i * 2 + 2] for i in range(len(bars) // 2)]
#     elif prefix == '':
#         left_barlines = [''] + [bars[i * 2 + 1] for i in range(len(bars) // 2 - 1)]
#         bar_texts = [bars[i * 2] for i in range(len(bars) // 2)]
#         right_barlines = [bars[i * 2 + 1] for i in range(len(bars) // 2)]
#     else:
#         left_barlines = [bars[i * 2 + 1] for i in range(len(bars) // 2 - 1)]
#         bar_texts = [bars[i * 2 + 2] for i in range(len(bars) // 2 - 1)]
#         right_barlines = [bars[i * 2 + 3] for i in range(len(bars) // 2 - 1)]

#     if not (len(left_barlines) == len(bar_texts) == len(right_barlines)):
#         raise Exception('Unequal bar elements')

#     return prefix, left_barlines, bar_texts, right_barlines


def strip_empty_bars(abc_lines: list):
    '''
    Strip empty bars in an abc piece. Retain the first left barline and the last right barline.
    '''

    metadata_lines, prefix_dict, left_barline_dict, bar_text_dict, right_barline_dict = \
        extract_barline_and_bartext_dict(abc_lines)

    # 这里小小检查一下各声部小节线和小节长度是否相等。
    # 小节线不相等问题不大，只是提示一下
    # 小节长度不相等则返回None
    barline_equal_flag = True
    bar_no_equal_flag = True
    for symbol in prefix_dict.keys():
        if left_barline_dict[symbol] != left_barline_dict['V:1']:
            barline_equal_flag = False
        if right_barline_dict[symbol] != right_barline_dict['V:1']:
            barline_equal_flag = False
        if len(bar_text_dict[symbol]) != len(bar_text_dict['V:1']):
            bar_no_equal_flag = False
    if not barline_equal_flag:
        print('Unequal barlines.')
    if not bar_no_equal_flag:
        print('Unequal bar numbers.')
        return None, None

    # 寻找各个声部非空bar index范围，然后得到一个并集
    left_valid_index_4all = len(bar_text_dict['V:1'])
    right_valid_index_4all = -1

    for symbol in bar_text_dict.keys():
        left_valid_index, right_valid_index = find_valid_bar_index(bar_text_dict[symbol])
        if left_valid_index < left_valid_index_4all:
            left_valid_index_4all = left_valid_index
        if right_valid_index > right_valid_index_4all:
            right_valid_index_4all = right_valid_index

    if left_valid_index_4all >= right_valid_index_4all:
        print('Empty piece.')
        return None, None

    stripped_left_barline_dict = {key: [] for key in prefix_dict.keys()}
    stripped_right_barline_dict = {key: [] for key in prefix_dict.keys()}
    stripped_bar_text_dict = {key: [] for key in prefix_dict.keys()}

    for symbol in prefix_dict.keys():
        stripped_left_barline_dict[symbol] = [left_barline_dict[symbol][0]] + \
                                             left_barline_dict[symbol][left_valid_index_4all + 1 : right_valid_index_4all]
        stripped_right_barline_dict[symbol] = right_barline_dict[symbol][left_valid_index_4all : right_valid_index_4all - 1] + \
                                              [right_barline_dict[symbol][-1]]
        stripped_bar_text_dict[symbol] = bar_text_dict[symbol][left_valid_index_4all:right_valid_index_4all]

    # 重新组装，每列不要超过100字符
    stripped_abc_lines = merge_barline_and_bartext_dict(metadata_lines, prefix_dict, stripped_left_barline_dict,
                                                        stripped_bar_text_dict, stripped_right_barline_dict)

    return stripped_abc_lines, right_valid_index_4all - left_valid_index_4all


def strip_empty_voices(abc_lines):
    # 去掉空白声部，然后需要更改编号以及%%score行
    metadata_lines, prefix_dict, left_barline_dict, bar_text_dict, right_barline_dict = extract_barline_and_bartext_dict(
        abc_lines)

    empty_voice_symbols = []
    for symbol in bar_text_dict.keys():
        empty_flag = True
        for bar_text in bar_text_dict[symbol]:
            bar_text = remove_wrapped_content(abc_text=bar_text, wrap_symbols=['!!'])
            bar_text = remove_square_bracket_information_field(bar_text)  # 右侧要滤掉[]，因为如果后面都是休止符，也没什么意思
            bar_text = remove_quote_text_annotations(bar_text)
            for char in bar_text:
                if re.match(r'^[A-Ga-g]$', char):
                    empty_flag = False
                    break
            if not empty_flag:
                break
        if empty_flag:  # 声部为空
            empty_voice_symbols.append(symbol)

    symbol_list = list(bar_text_dict.keys())
    symbol_list.sort(key=lambda x: int(x[2:]))
    cur_index = 0
    substitute_dict = {}  # 声部替换字典，删掉空声部的symbol，剩余声部紧凑往前排
    for symbol in symbol_list:
        if symbol not in empty_voice_symbols:
            substitute_dict[symbol] = symbol_list[cur_index]
            cur_index += 1
        else:
            pass

    altered_metadata_lines = []
    for line in metadata_lines:
        delete_flag = False
        if line.startswith('%%score'):  # score行，比较麻烦
            # 删掉空声部的数字
            for empty_symbol in empty_voice_symbols:
                line = line.replace(' ' + empty_symbol[2:] + ' ', ' ')  # 前后要加空格，避免误删
            # 替换
            for ori_symbol, sub_symbol in substitute_dict.items():
                if ori_symbol != sub_symbol:
                    line = line.replace(' ' + ori_symbol[2:] + ' ', ' ' + sub_symbol[2:] + ' ')

            # 处理小括号情况：如果小括号里只有一个数字，则去掉外层小括号
            line = re.sub(r'\(\s*(\d+)\s*\)', r'\1', line)

            # 中括号花括号啥的暂时先不管

        elif line.startswith('V:'):
            line_symbol = line.split()[0]
            line_content = line[len(line_symbol):]
            if line_symbol in substitute_dict.keys():
                line = substitute_dict[line_symbol] + line_content
            else:
                delete_flag = True
        if not delete_flag:
            altered_metadata_lines.append(line)

    altered_prefix_dict = {sub_symbol: prefix_dict[ori_symbol] for ori_symbol, sub_symbol in substitute_dict.items()}
    altered_left_barline_dict = {
        sub_symbol: left_barline_dict[ori_symbol] for ori_symbol, sub_symbol in substitute_dict.items()
    }
    altered_bar_text_dict = {sub_symbol: bar_text_dict[ori_symbol] for ori_symbol, sub_symbol in substitute_dict.items()}
    altered_right_barline_dict = {
        sub_symbol: right_barline_dict[ori_symbol] for ori_symbol, sub_symbol in substitute_dict.items()
    }

    altered_abc_lines = merge_barline_and_bartext_dict(altered_metadata_lines, altered_prefix_dict, altered_left_barline_dict,
                                                       altered_bar_text_dict, altered_right_barline_dict)

    return altered_abc_lines


def find_valid_bar_index(bar_text_list: list):

    left_valid_index = -1
    right_valid_index = len(bar_text_list)

    left_valid_flag = False
    while not left_valid_flag:
        left_valid_index += 1
        if left_valid_index >= len(bar_text_list):
            break
        bar_text = bar_text_list[left_valid_index]
        bar_text = remove_wrapped_content(abc_text=bar_text, wrap_symbols=['!!'])
        # bar_text = remove_square_bracket_information_field(bar_text)  # 这里做一下区别对待：左侧如有[]，则视为有效小节，因为可能对后续小节有影响
        bar_text = remove_quote_text_annotations(bar_text)
        for char in bar_text:
            if char.isalpha() and not char in ['Z', 'z', 'X', 'x']:
                left_valid_flag = True
                break

    right_valid_flag = False
    while not right_valid_flag:
        right_valid_index -= 1
        if right_valid_index < 0:
            break
        bar_text = bar_text_list[right_valid_index]
        bar_text = remove_wrapped_content(abc_text=bar_text, wrap_symbols=['!!'])
        bar_text = remove_square_bracket_information_field(bar_text)  # 右侧要滤掉[]，因为如果后面都是休止符，也没什么意思
        bar_text = remove_quote_text_annotations(bar_text)
        for char in bar_text:
            if re.match(r'^[A-Ga-g]$', char):
                right_valid_flag = True
                break

    return left_valid_index, right_valid_index + 1


def ld_sim(str_a: str, str_b: str):
    ld = jellyfish.levenshtein_distance(str_a, str_b)
    sim = 1 - ld / (max(len(str_a), len(str_b)))
    return sim


def fast_ld_sim(str_a: str, str_b: str):
    return fuzz.ratio(str_a, str_b) / 100


def add_control_codes(abc):
    meta_data, merged_body_data = split_abc_original(abc)
    control_codes, abc = add_tokens(meta_data, merged_body_data)

    return control_codes, abc


def extract_notes(input_string):
    # Regular expression pattern for single notes, rests, and decorated notes
    note_pattern = r"(x[0-9]*/*[0-9]*|z[0-9]*/*[0-9]*|[\^_=]*[A-G][,']*[0-9]*/*[0-9]*\.*|[\^_=]*[a-g][']*/*[0-9]*/*[0-9]*\.*)"

    # Regular expression pattern for chord notes
    chord_note_pattern = r"(?<!:)\[[^\]]*\]"

    # Regular expression pattern for headers
    header_pattern = r"\[[A-Za-z]:[^\]]*\]"

    # Regular expression pattern for decorations
    decoration_pattern = r"!.*?!"

    # Regular expression pattern for quoted content
    quoted_pattern = r"\".*?\""

    # Remove quoted content from input
    input_string = re.sub(quoted_pattern, '', input_string)

    # Remove decoration information from input
    input_string = re.sub(decoration_pattern, '', input_string)

    # Remove header information from input
    input_string = re.sub(header_pattern, '', input_string)

    # Extract notes, rests, and decorated notes using regex
    note_matches = re.findall(note_pattern, input_string)

    # Extract chord notes using regex
    chord_notes = re.findall(chord_note_pattern, input_string)

    # Combine single notes, rests, decorated notes, and chord notes
    notes = [note for note in note_matches if note.strip() != '']

    notes = notes + chord_notes

    return notes


def num_alph(line):
    num_flag = False
    alpha_flag = False
    valid_flag = False

    for char in line:
        if char.isnumeric() and alpha_flag == False and valid_flag == False:
            return True
        elif char.isalpha() and num_flag == False:
            return False
        elif char == '(' or char == '\"' or char == '!':
            valid_flag = True


def split_abc_original(abc):
    lines = re.split('(\n)', abc)
    lines = [lines[i * 2] + lines[i * 2 + 1] for i in range(int(len(lines) / 2))]
    meta_flag = False
    meta_idx = 0

    for line in lines:
        if len(line) > 1 and line[0].isalpha() and line[1] == ':':
            meta_idx += 1
            meta_flag = True
        else:
            if meta_flag:
                break
            else:
                meta_idx += 1

    meta_data = ''.join(lines[:meta_idx])
    body_data = abc[len(meta_data):]

    delimiters = ":|", "||", "|]", "::", "|:", "[|"
    regexPattern = '(' + '|'.join(map(re.escape, delimiters)) + ')'
    body_data = re.split(regexPattern, body_data)
    body_data = list(filter(lambda a: a != '', body_data))
    if len(body_data) == 1:
        body_data = [abc[len(meta_data):][::-1].replace('|', ']|', 1)[::-1]]
    else:
        if body_data[0] in delimiters:
            body_data[1] = body_data[0] + body_data[1]
            body_data = body_data[1:]
        body_data = [body_data[i * 2] + body_data[i * 2 + 1] for i in range(int(len(body_data) / 2))]

    merged_body_data = []

    for line in body_data:
        if num_alph(line):
            try:
                merged_body_data[-1] += line
            except:
                return None, None
        else:
            merged_body_data.append(line)

    return meta_data, merged_body_data


def run_strip(line, delimiters):
    for delimiter in delimiters:
        line = line.strip(delimiter)
        line = line.replace(delimiter, '|')
    return line


def add_tokens(meta_data, merged_body_data):
    if merged_body_data == None:
        return "", ""
    delimiters = ":|", "||", "|]", "::", "|:", "[|"
    sec = len(merged_body_data)
    bars = []
    sims = []

    for line in merged_body_data:
        line = run_strip(line, delimiters)
        bars.append(line.count('|') + 1)

    for anchor_idx in range(1, len(merged_body_data)):
        sim = []
        for compar_idx in range(anchor_idx):
            sim.append(ld_sim(merged_body_data[anchor_idx], merged_body_data[compar_idx]))
        sims.append(sim)

    header = "S:" + str(sec) + "\n"
    for i in range(len(bars)):
        if i > 0:
            for j in range(len(sims[i - 1])):
                header += "E:" + str(round(sims[i - 1][j] * 10)) + "\n"
        header += "B:" + str(bars[i]) + "\n"
    return unidecode(header), unidecode(meta_data + ''.join(merged_body_data))


if __name__ == '__main__':

    abc_lines = [
        '%%score { ( 1 4 ) | ( 2 3 ) }\n', 'L:1/8\n', 'Q:1/4=92\n', 'M:2/4\n', 'K:Cb\n', 'V:1 treble nm="Piano" snm="Pno."\n',
        'V:4 treble \n', 'V:2 bass \n', 'V:3 bass\n', '[V:1]"^Andante cantabile"!p! G2|[V:2]z2|[V:3]x2|[V:4]x2|\n',
        '[V:1]G2 EE|[V:2]C,4|[V:3]C,G,CG,|[V:4]x4|\n', '[V:1]F2 DD|[V:2]C,4|[V:3]C,G,B,G,|[V:4]x4|\n',
        '[V:1]E2 G2|[V:2]C,4|[V:3]C,G,CG,|[V:4]x4|\n', '[V:1]E2 z!<(! G|[V:2]C,4|[V:3]C,G,CG,|[V:4]x4|\n',
        '[V:1]G2!<)! E!>(!E|[V:2]C,4|[V:3]C,G,CG,|[V:4]x4|\n', '[V:1]F2!>)! DD|[V:2]C,4|[V:3]C,G,B,G,|[V:4]x4|\n',
        '[V:1]E2 G2|[V:2]C,4|[V:3]C,G,CG,|[V:4]x4|\n', '[V:1]E2 z2|[V:2]C,4|[V:3]C,G,CG,|[V:4]x4|\n',
        '[V:1]E2 DD|[V:2]C,4|[V:3]C,G,B,G,|[V:4]x4|\n', '[V:1]F2 DD|[V:2]C,4|[V:3]C,F,A,F,|[V:4]x4|\n',
        '[V:1]E2 DD|[V:2]C,4|[V:3]C,F,A,F,|[V:4]x4|\n', '[V:1]C2 z2|[V:2]C,4|[V:3]C,E,G,E,|[V:4]x4|\n',
        '[V:1]!<(! E2 DD|[V:2][C,G,]2 [C,F,][C,F,]|[V:3]x4|[V:4]x4|\n',
        '[V:1]F2!<)!!>(! DD!>)!|[V:2][C,A,]2 [C,F,][C,F,]|[V:3]x4|[V:4]x4|\n',
        '[V:1]!<(! E2 DD|[V:2][C,G,]2 [C,F,][C,F,]|[V:3]x4|[V:4]x4|\n',
        '[V:1]C2 !fermata!z2!<)!|][V:2][C,E,]2 !fermata!z2|][V:3]x4|][V:4]x4|]\n'
    ]

    extract_barline_and_bartext_dict_rotated(abc_lines)
