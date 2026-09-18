"""
Convert MusicXML files to MIDI using music21.

Reads XML files from the data directory and writes MIDI files alongside them.
Directory structure:
    {data_dir}/{num}/xml/{num}_output.xml  ->  {data_dir}/{num}/mid/{num}_output.mid

Usage:
    python text2music/data/utils/xml2mid.py --data_dir /path/to/data
    python text2music/data/utils/xml2mid.py  # uses default path
"""

import os
import argparse
from pathlib import Path
import music21
from tqdm import tqdm


def convert_xml_to_mid(xml_path, mid_path):
    """Convert a single MusicXML file to MIDI.

    If music21 fails to expand repeats, strips repeat barlines/marks
    and retries (single pass through the score, no repeats).
    Returns 'ok' or 'ok (repeats stripped)'.
    """
    score = music21.converter.parse(str(xml_path))
    try:
        score.write('midi', fp=str(mid_path))
        return 'ok'
    except Exception:
        # Strip malformed repeat marks and retry
        for el in score.recurse():
            if isinstance(el, (music21.bar.Repeat,
                               music21.repeat.RepeatMark,
                               music21.repeat.RepeatExpression)):
                site = el.activeSite
                if site is not None:
                    site.remove(el)
        score.write('midi', fp=str(mid_path))
        return 'ok (repeats stripped)'


def process_directory(data_dir, verbose=False):
    """Convert all XML files in the data directory to MIDI."""
    data_dir = Path(data_dir)
    stats = {'total': 0, 'success': 0, 'errors': []}

    subdirs = sorted(
        [d for d in data_dir.iterdir() if d.is_dir() and d.name.isdigit()],
        key=lambda x: int(x.name)
    )

    # Collect all xml files first for progress bar
    # all_xml = []
    # for subdir in subdirs:
    #     xml_path = subdir / 'xml' / f'{subdir.name}_output.xml'
    #     if xml_path.exists():
    #         all_xml.append((subdir, xml_path))
    
    # Collect all xml files first for progress bar
    all_xml = []
    for subdir in subdirs:
        xml_dir = subdir / 'xml'
        if xml_dir.exists():
            xml_files = list(xml_dir.glob('*.xml'))
            if xml_files:
                # Use the first XML file found
                xml_path = xml_files[0]
                all_xml.append((subdir, xml_path))

    for subdir, xml_path in tqdm(all_xml, desc='Converting XML→MIDI'):
        stats['total'] += 1
        mid_dir = subdir / 'mid'
        mid_dir.mkdir(exist_ok=True)
        # mid_path = mid_dir / f'{subdir.name}_output.mid'
        mid_path = mid_dir / f'{xml_path.stem}_output.mid'

        try:
            status = convert_xml_to_mid(xml_path, mid_path)
            stats['success'] += 1
            if verbose:
                print(f"  [{subdir.name}] {status}")
        except Exception as e:
            stats['errors'].append((subdir.name, str(e)[:120]))
            if verbose:
                print(f"  [{subdir.name}] ERROR: {str(e)[:120]}")

    return stats


def main():
    parser = argparse.ArgumentParser(description='Convert MusicXML to MIDI')
    parser.add_argument('--data_dir', type=str,
                        default='/Users/sungkyun/ML/text2score_ablated',
                        help='Path to data directory')
    parser.add_argument('--verbose', action='store_true',
                        help='Print per-file details')
    args = parser.parse_args()

    stats = process_directory(args.data_dir, args.verbose)

    print(f"\n{'='*60}")
    print(f"DONE")
    print(f"Total XML files: {stats['total']}")
    print(f"Success: {stats['success']}")
    print(f"Errors: {len(stats['errors'])}")

    if stats['errors']:
        print(f"\n--- Errors ---")
        for d, e in stats['errors']:
            print(f"  [{d}] {e}")


if __name__ == '__main__':
    main()
