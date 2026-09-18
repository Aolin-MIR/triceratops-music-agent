import argparse
from os import path, makedirs, remove
from glob import glob
from multiprocessing import Pool
from functools import partial
from tqdm import tqdm
from utils.convert_formats import convert_abc2abc_interleaved, convert_abc2xml, convert_xml2abc_interleaved


def process_file(abc_file, data_root=None, output_dir=None, safe_convert=True):
    """Process a single ABC file to ABC interleaved format.
    Args:
        ...
        safe_convert (bool): If True, convert ABC to XML first, then to ABCI.
    """

    if safe_convert:
        print(f"Processing {abc_file} (safe_convert={safe_convert}, abc2xml2abci)")
        try:
            abc_file = path.abspath(abc_file)
            data_root = path.abspath(data_root)
            temp_xml_file = abc_file.rsplit(".", 1)[0] + ".xml"
            abci_file = abc_file.rsplit(".", 1)[0] + ".abci"
            if output_dir and data_root:
                rel_path = path.relpath(path.dirname(abc_file), data_root)
                temp_xml_file = path.normpath(path.join(output_dir, rel_path, path.basename(temp_xml_file)))
                abci_file = path.normpath(path.join(output_dir, rel_path, path.basename(abci_file)))
            makedirs(path.dirname(temp_xml_file), exist_ok=True)
            _ = convert_abc2xml(abc_file, temp_xml_file)

            abci_lines = convert_xml2abc_interleaved(temp_xml_file, abci_file)
            if abci_lines is None:
                return False, abc_file

            # remove temp xml file
            remove(temp_xml_file)
            return True, abc_file
        except Exception as e:
            return False, abc_file

    else:
        print(f"Processing {abc_file} (safe_convert={safe_convert}, direct abc2abci)")
        try:
            abci_file = abc_file.rsplit(".", 1)[0] + ".abci"
            if output_dir and data_root:
                # Get relative path from data_root to preserve subdirectory structure
                rel_path = path.relpath(path.dirname(abc_file), data_root)
                # Construct output path maintaining the subdirectory structure
                abci_file = path.join(output_dir, rel_path, path.basename(abci_file))
                # Ensure output directory exists
                makedirs(path.dirname(abci_file), exist_ok=True)

            abci_lines = convert_abc2abc_interleaved(abc_file, abci_file,
                                                     fix_abc=True)  # fix abc w/ missing voice field (e.g., V:1)
            if abci_lines is None:
                return False, abc_file
            return True, abc_file
        except Exception as e:
            return False, abc_file


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Convert ABC files to ABC interleaved format")
    parser.add_argument('--data_root',
                        type=str,
                        default="../../abrsm_data/abc",
                        help='Root directory containing ABC files')
    parser.add_argument('--output_dir', type=str, default=None, help='Output directory for ABCI files (optional)')
    parser.add_argument('--num_workers', type=int, default=8, help='Number of worker processes for parallel processing')
    parser.add_argument('--disable_safe_convert',
                        action='store_true',
                        default=False,
                        help='Disable safe conversion (convert ABC directly to ABCI)')
    args = parser.parse_args()

    # If output_dir is not specified, create one by appending "_abci" to data_root
    if args.output_dir is None:
        args.output_dir = args.data_root + "_abci"

    # Get list of ABC files (case-insensitive)
    abc_filelist = glob(path.join(args.data_root, "**/*.[aA][bB][cC]"), recursive=True)

    if not abc_filelist:
        print(f"No ABC files found in {args.data_root}")
        return

    # Initialize counters
    success, fail = 0, 0

    # Process files using multiprocessing
    with Pool(processes=args.num_workers) as pool:
        # Create partial function with data_root and output_dir
        process_func = partial(process_file,
                               data_root=args.data_root,
                               output_dir=args.output_dir,
                               safe_convert=not args.disable_safe_convert)

        # Process files with tqdm progress bar
        results = list(
            tqdm(pool.imap(process_func, abc_filelist), total=len(abc_filelist), desc="Converting ABC to ABCI"))

    # Count successes and failures
    for result, abc_file in results:
        if result:
            success += 1
        else:
            fail += 1
            print(f"Failed to convert {abc_file}")

    print(f"\nabc to abc_interleaved: success={success}, failure={fail}")


if __name__ == "__main__":
    main()
