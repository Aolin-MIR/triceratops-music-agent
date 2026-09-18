import os
import math
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.transpose import transpose_an_abc_text
from text2music.data.utils.abc_helper.abctoolkit_v006_mod.utils import find_all_abc
from multiprocessing import Pool
from tqdm import tqdm

KEY_CHOICES = ["Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#"]

ORI_DIR = r'D:\Research\Projects\MultitrackComposer\dataset\06_abc_text-filtered\musescoreV2'
AUGMENTED_DIR = r'D:\Research\Projects\MultitrackComposer\dataset\08_abc_key-augmented\musescoreV2'


def split_list_by_cpu(lst: list):
    num_cpus = os.cpu_count()
    split_lists = [[] for _ in range(num_cpus)]
    index = 0

    for item in lst:
        split_lists[index].append(item)
        index = (index + 1) % num_cpus

    return split_lists, num_cpus


def key_augment_an_abc_file(abc_path, des_folder):
    for key in KEY_CHOICES:
        with open(abc_path, 'r', encoding='utf-8') as f:
            abc_text_lines = f.readlines()

        ori_filename = os.path.splitext(os.path.split('\\')[-1])[0]

        try:
            transposed_abc_text, ori_key, des_key = transpose_an_abc_text(abc_text_lines, key)
            if ori_key == des_key:
                filename = ori_filename + '_original_' + des_key
            else:
                filename = ori_filename + '_transposed_' + des_key
            transposed_filepath = os.path.join(des_folder, filename + '.abc')
            with open(transposed_filepath, 'w', encoding='utf-8') as f:
                f.write(transposed_abc_text)
        except Exception as e:
            print(abc_path, e)


def key_augment_abcs(abc_paths: list, des_folder):
    for abc in tqdm(abc_paths):
        key_augment_an_abc_file(abc_path=abc, des_folder=des_folder)


def batch_transpose(ori_folder, des_folder):

    if not os.path.exists(des_folder):
        os.mkdir(des_folder)

    file_list = []
    for abc_path in find_all_abc(ori_folder):
        file_list.append(abc_path)

    num_cpu = os.cpu_count()
    arg_lists = [[] for _ in range(num_cpu)]
    for i in range(num_cpu):
        start_idx = int(math.floor(i * len(file_list) / os.cpu_count()))
        end_idx = int(math.floor((i + 1) * len(file_list) / os.cpu_count()))
        arg_lists[i].append((file_list[start_idx:end_idx], des_folder))

    pool = Pool(processes=os.cpu_count())
    pool.map(key_augment_abcs, arg_lists)


if __name__ == '__main__':
    pass
