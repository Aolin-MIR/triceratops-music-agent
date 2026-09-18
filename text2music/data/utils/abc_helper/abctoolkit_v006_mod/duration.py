import re
from fractions import Fraction
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.utils import SquareBracket_re, remove_square_bracket_information_field, remove_wrapped_content


def calculate_single_note_duration(note_text: str):
    note_text = note_text.strip()
    dur_text = re.sub(r'[a-zA-Z]', '', note_text)
    if dur_text == '':
        dur = Fraction('1')
    elif dur_text == '/':
        dur = Fraction('1/2')
    elif dur_text.startswith('/'):
        dur = Fraction('1' + dur_text)
    else:
        dur = Fraction(dur_text)
    return dur


def round_fraction(f: Fraction, tolerance=Fraction(1, 64)):
    # 只用于连音组合的时值，如果离最近的整数距离<=1/64，则约减为这个整数
    nearest_int = round(float(f))
    if abs(f - nearest_int) <= tolerance:
        return Fraction(nearest_int)
    else:
        return f


def calculate_bartext_duration(bar_text: str):
    # 尝试仅使用文本方法计算小节时值
    # print(bar_text)
    original_bartext = bar_text

    note_set = ['A', 'a', 'B', 'b', 'C', 'c', 'D', 'd', 'E', 'e', 'F', 'f', 'G', 'g', 'X', 'x', 'Z', 'z']
    useless_char_set = ['P', 'S', 'O', 's', 'o', 'u', 'v', 'U', 'V', 'T', 'M', '.', '-', ')']
    # pitch_sign_set = ['_', '=', '^', '\'', ',']
    pitch_sign_set = ['_', '=', '^', '\'', ',', '~']  # <--- FIX 2025-05-22

    # 删掉 !! "" {} 内容
    bar_text = remove_wrapped_content(bar_text, ['!!', '{}', '""'])

    # 处理[]内容
    # 删掉[]元信息
    bar_text = remove_square_bracket_information_field(bar_text)

    # 如果是和弦，则 打印
    bracket_contents = re.findall(SquareBracket_re, bar_text)
    if len(bracket_contents) > 0:
        for bracket_content in bracket_contents:
            # 经检查，[]内容不会超出以下范围: note_set +  pitch_sign_set + '[' + ']' + '-'
            # 故可将[]内容替换为 C
            for char in bracket_content:
                if char not in note_set + pitch_sign_set + ['[', ']', '-']:
                    raise Exception('Illegal symbol in [] {}'.format(bracket_content))
            bar_text = bar_text.replace(bracket_content, 'C')

    # 将x,z换成A
    bar_text = bar_text.replace('x', 'z')
    bar_text = bar_text.replace('X', 'z')

    try:
        # 替换无用字符和音高表示字符
        for char in useless_char_set + pitch_sign_set:
            bar_text = bar_text.replace(char, '')
        # 处理(，如果(后面跟了数字，则留下，否则删掉
        index_to_detele = []
        for i, char in enumerate(bar_text):
            if bar_text[i] == '(' and (len(bar_text) == i + 1 or not bar_text[i + 1].isnumeric()):
                index_to_detele.append(i)
        bar_text_list = list(bar_text)
        # print(bar_text_list, index_to_detele)
        for index in reversed(index_to_detele):
            bar_text_list.pop(index)

        bar_text = ''.join(bar_text_list)

        ele_list = []  # 存放：音符、时值组合、附点大小于号
        # 处理各个字符，整理进入note_list
        index = 0
        for i, char in enumerate(bar_text):
            if i < index:
                continue
            # 遇到音名，往后试探，直到遇到:音名, >, <, (，断开
            if char in note_set:
                index = i + 1
                while index < len(bar_text):
                    if bar_text[index] in note_set + ['(', '<', '>']:
                        break
                    index += 1
                ele_list.append(bar_text[i:index])
            elif char == '(':  # 三连音之类的
                # 判断时值组合方式（截到最后一个数字和冒号）
                index = i + 1
                while bar_text[index].isnumeric() or bar_text[index] == ':':
                    index += 1
                ele_list.append(bar_text[i:index])
            elif char in ['<', '>']:  # 附点，截到非<>的字符
                index = i + 1
                while bar_text[index] in ['<', '>']:
                    index += 1
                ele_list.append(bar_text[i:index])

        ele_list = [ele.strip() for ele in ele_list]
        dur_list = [-1] * len(ele_list)  # -1 表示元素时值未定

        # 先统计每个音符的时值
        for i, ele in enumerate(ele_list):
            if ele[0].isalpha():
                dur = calculate_single_note_duration(ele)
                dur_list[i] = dur

        # 统计附点组合的时值，清除附点两侧的音符时值（置0），附点组合时值记录在附点处
        for i, ele in enumerate(ele_list):
            if ele[0] in ['<', '>']:
                dur_list[i] = dur_list[i - 1] + dur_list[i + 1]
                dur_list[i - 1] = 0
                dur_list[i + 1] = 0

        # 统计连音组合的时值，清除属于连音组合的音符的时值（置0），连音组合时值记录在连音处
        # 如果存在连音套连音的情况，里面的连音时值划为置0
        # 理论上此时应该只有连音组合元素的dur为-1，立一个flag，做嵌套
        uncertain_flag = True if -1 in dur_list else False

        while uncertain_flag:
            uncertain_flag = False
            for i, ele in enumerate(ele_list):
                if dur_list[i] == -1 and ele[0] == '(':
                    uncertain_flag = True
                    # 经检查，好像只有(3会简写，其他都会写成(p:q:n的标准格式，肥肠好
                    if ele == '(3':
                        p, q, r = 3, 2, 3
                    else:
                        p = int(ele.lstrip('(').split(':')[0])
                        q = int(ele.lstrip('(').split(':')[1])
                        r = int(ele.lstrip('(').split(':')[2])
                    if p == 0 or q == 0 or r == 0:
                        raise Exception('Illegal (p:q:r ' + '({}:{}:{}'.format(p, q, r))
                    # 往后找r个音，划定计算范围
                    left_bound = i + 1
                    index = i + 1
                    note_count = 0
                    local_uncertain_flag = False  # 局部范围内若有未定元素，则退出，算下一个连音组合
                    while note_count < r:
                        if ele_list[index][0].isalpha():
                            note_count += 1
                        elif dur_list[index] == -1:
                            local_uncertain_flag = True
                            break
                        index += 1
                    right_bound = index
                    if local_uncertain_flag:
                        continue
                    else:  # 局部范围内时值均确定，计算时值，范围内所有元素时值置0
                        dur_list[i] = sum(dur_list[left_bound:right_bound]) * Fraction(numerator=q, denominator=p)
                        dur_list[i] = round_fraction(dur_list[i])  # 做一波约减
                        dur_list[left_bound:right_bound] = [0] * (right_bound - left_bound)
                elif dur_list[i] == -1:  # 未定元素但非连音，报错
                    raise Exception('Uncertain element')

        bar_duration = sum(dur_list)

    except Exception as e:
        print(original_bartext, e)
        return None

    return bar_duration


if __name__ == '__main__':
    '''
    (2:2:14A(1:1:2c/B/ (1:1:11c(2:2:2B/c/ (4:4:4B/A/B/c/ (4:4:4d/e/f/g/
    z edc (3:2:5B2 A2 (1:1:3G43/64F43/64A43/64
     b4 (3:2:16b(1:1:3a21/64b21/64a21/64(1:1:3g21/64a21/64g21/64 (1:1:3f21/64g21/64f21/64(1:1:3e21/64g21/64b21/64(1:1:3d21/64c21/64b21/64
     z2 z3 (2:1:3z D/E/ (12:6:16z/4 z/4 z/4 z/4 z/4 z/4 z/4 z/4 z/4 z/4 z/4 z/4 z/4 z/4 (0:0:2D/4 E/4
     (3:2:7z/z/z/z/(1:1:3z21/64z21/64z21/64 z/4z/4z/4z/4z/4z/4z/4z/4 z/4z/4z/4z/4z/4z/4z/4z/4
     b4(
    '''

    bartext = 'b4('

    dur = calculate_bartext_duration(bartext)
    print(dur)
