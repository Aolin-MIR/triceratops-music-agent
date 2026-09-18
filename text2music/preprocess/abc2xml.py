import os
import subprocess

def convert_abc_list_to_xml(file_list, abc2xml_script="text2music/data/utils/abc_helper/abc2xml.py"):
    """
    Convert a list of .abc files to .xml files using abc2xml.py.
    Saves .xml files in the same directory as the input.
    """

    os.makedirs("logs", exist_ok=True)

    for file_path in file_list:
        try:
            if not file_path.endswith(".abc"):
                continue

            # Output path: same folder, but with .xml extension
            output_path = os.path.splitext(file_path)[0] + ".xml"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Run abc2xml
            cmd = f'python "{abc2xml_script}" "{file_path}"'
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            stdout, _ = process.communicate()

            xml_data = stdout.decode("utf-8")

            # Handle empty output (error case)
            if not xml_data.strip():
                with open("logs/abc2xml_error_log.txt", "a", encoding="utf-8") as logf:
                    logf.write(file_path + "\n")
                continue

            # Write .xml output
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_data)

        except Exception as e:
            # Log exceptions
            with open("logs/abc2xml_error_log.txt", "a", encoding="utf-8") as logf:
                logf.write(file_path + " " + str(e) + "\n")
            continue

# Example usage:
# files = [
#     "/path/to/music1.abc",
#     "/path/to/music2.abc"
# ]
# convert_abc_list_to_xml(files)