from typing import Optional
import os
import subprocess
from os import path
from text2music.data.utils.abc_helper.abc2abc_interleaved import abc2abc_interleaved
from text2music.data.utils.mtf_helper.midi2mtf import midi2mtf
from text2music.data.utils.mtf_helper.mtf2midi import mtf2midi
from text2music.data.utils.abc_helper.fix_abc import fix_missing_voice_field, remove_empty_lines


def convert_abc2abc_interleaved(input_file: str,
                                output_file: Optional[str] = None,
                                fix_abc: bool = True) -> Optional[list[str]]:
    """
    Convert ABC file to interleaved format for M3 model.

    Args:
        input_file (str): Path to the ABC file.
        output_file (Optional[str]): Path to save the interleaved file (.abci). If None, no file is saved.
        fix_abc (bool): Whether to fix the ABC file. Default is True.
    Returns:
        Optional[list[str]]: Interleaved ABC lines if successful, None if an error occurs.
    """
    assert path.exists(input_file)
    abc_lines = open(path.abspath(input_file), 'r', encoding='utf-8').readlines()

    if fix_abc:
        abc_lines = fix_missing_voice_field(abc_lines)
        abc_lines = remove_empty_lines(abc_lines)

    interleaved_abc_lines, error = abc2abc_interleaved(abc_lines)

    if not error:
        if output_file:
            os.makedirs(path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as w:
                w.writelines(interleaved_abc_lines)
        return interleaved_abc_lines

    os.makedirs("logs", exist_ok=True)
    with open("logs/abc2abc_error_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{input_file} {error}\n")
    return None


from pathlib import Path
import subprocess
from typing import Optional, List
from .abc_helper.abc2abc_interleaved import abc2abc_interleaved


def convert_xml2abc_interleaved(input_file: str,
                                output_file: Optional[str] = None,
                                fix_abc: bool = True) -> Optional[List[str]]:
    """
    Convert XML files to ABC format (interleaved) for the M3 model.
    
    Args:
        input_file (str): Path to the XML file.
        output_file (str): Path to save the interleaved ABC file, typically with a .abci extension.
            If None, no file is saved.
        fix_abc (bool): Whether to fix the ABC file. Default is True.

    Returns:
        list: List of strings containing the interleaved ABC notation. None if unsuccessful.
    """
    # Ensure input file exists and convert to absolute path
    input_path = Path(input_file).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file {input_file} does not exist")

    # Create output directory if specified
    if output_file is not None:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    # Dynamically construct path to xml2abc.py
    script_dir = Path(__file__).parent  # text2music/data/utils
    project_root = script_dir.parent.parent  # text2score_new/text2music
    xml2abc_path = project_root / "data" / "utils" / "abc_helper" / "xml2abc.py"

    # Verify xml2abc.py exists
    if not xml2abc_path.exists():
        raise FileNotFoundError(f"xml2abc.py not found at {xml2abc_path}")

    # Build command to run xml2abc.py
    cmd = f'python "{xml2abc_path}" -d 8 -c 6 -x "{input_path}"'

    # Run the command
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=True  # Raises CalledProcessError if the command fails
        )
        abc_lines = result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Error converting {input_file}: {e.stderr}")
        Path("logs").mkdir(exist_ok=True)
        with open("logs/xml2abc_error_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{input_file} {e.stderr}\n")
        return None
    except Exception as e:
        print(f"Error converting {input_file}: {e}")
        Path("logs").mkdir(exist_ok=True)
        with open("logs/xml2abc_error_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{input_file} {str(e)}\n")
        return None

    # Check if ABC output is empty
    if not abc_lines:
        print(f"Error converting {input_file}: No ABC output")
        Path("logs").mkdir(exist_ok=True)
        with open("logs/xml2abc_error_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{input_file} No ABC output\n")
        return None

    # Convert ABC to interleaved ABC
    if fix_abc:
        abc_lines = fix_missing_voice_field(abc_lines)
        abc_lines = remove_empty_lines(abc_lines)

    interleaved_abc_lines, error = abc2abc_interleaved(abc_lines)

    if error is not None:
        print(f"Error interleaving ABC for {input_file}: {error}")
        Path("logs").mkdir(exist_ok=True)
        with open("logs/xml2abc_error_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{input_file} {error}\n")
        return None

    # Save interleaved ABC if output file is specified
    print(f"Output file: {output_file}")
    if interleaved_abc_lines and output_file:
        with open(output_file, 'w', encoding='utf-8') as w:
            w.writelines(interleaved_abc_lines)

    return interleaved_abc_lines


def convert_abc2xml(input_file: str, output_file: Optional[str] = None) -> None:
    """
    Convert ABC file to XML format for the M3 model.
    """
    assert path.exists(input_file)
    input_file = path.abspath(input_file)
    if output_file is not None:
        output_dir = path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)
    try:
        cmd = f'python utils/abc_helper/abc2xml.py -o "{output_dir}" "{input_file}"'
        _ = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    except Exception as e:
        print(f'Error converting {input_file}: {e}')
        os.makedirs("logs", exist_ok=True)
        with open("logs/abc2xml_error_log.txt", "a", encoding="utf-8") as f:
            f.write(input_file + ' ' + str(e) + '\n')
    return None


def convert_midi2mtf(input_file: str, output_file: Optional[str] = None):
    """
    Convert MIDI file to MTF format for the M3 model.

    Args:
        input_file (str): Path to the MIDI file.
        output_file (Optional[str]): Path to save the MTF file (.mtf). If None, no file is saved.

    Returns:
        output: Output lines if successful, None if an error occurs.
        error: Error message if any. None if successful.
    """
    output, error = midi2mtf(input_file, output_file)
    if error is not None:
        print(error)
    return output


def convert_mtf2midi(input_file: str, output_file):
    return mtf2midi(input_file, output_file)
