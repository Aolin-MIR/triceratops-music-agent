import os
import re

def convert_abci_list_to_abc(file_list):
    """
    Convert a list of .abci files into .abc files in the same directory.
    The converted file overwrites the extension but keeps the same base path.
    """

    for file_path in file_list:
        try:
            if not file_path.endswith(".abci"):
                continue

            # Output path: same folder, but .abc extension
            output_path = os.path.splitext(file_path)[0] + ".abc"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Read input file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = f.read()

            # Step 1: Remove patterns like %5, %123
            data = re.sub(r'%\d+', '', data)

            # Step 2: Ensure each [V:x] starts on a new line
            data = re.sub(r'(?<!\n)(\[V:\d+\])', r'\n\1', data)

            # Step 3: Collapse multiple blank lines into a single newline
            data = re.sub(r'\n{2,}', '\n', data)

            # Step 4: Strip whitespace on each line
            lines = [line.strip() for line in data.splitlines()]
            data = "\n".join(lines)

            # Write output .abc file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(data)

        except Exception as e:
            # Optional logging
            os.makedirs("logs", exist_ok=True)
            with open("logs/abci_to_abc_errors.txt", "a", encoding="utf-8") as logf:
                logf.write(f"{file_path} :: {e}\n")
            continue

# Example usage:
#     files = [
#     "/path/to/song1.abci",
#     "/path/to/song2.abci",
#     "/another/path/music.abci"
# ]
# convert_abci_list_to_abc(files)