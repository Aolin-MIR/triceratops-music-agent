"""
Inject %%MIDI program directives into ABC files based on V: header nm= values.

This ensures that abc2xml produces MusicXML with <midi-instrument><midi-program>
elements, so that MuseScore (MS Basic) and MIDI-based DAWs select the correct
General MIDI instrument instead of defaulting to piano.

Output is written to abc_injected/ folders (originals are not modified).

Usage:
    python inject_midi_program.py --data_dir /path/to/data [--dry_run] [--verbose]
"""

import re
import os
import argparse
from pathlib import Path
from tqdm import tqdm

# GM Program Number mapping (0-based, abc2xml adds +1 for MusicXML)
# Reference: https://www.midi.org/specifications-old/item/gm-level-1-sound-set
GM_MAP = {
    # Piano (0-7)
    'piano': 0,
    'acoustic grand piano': 0,
    'grand piano': 0,
    # Chromatic Percussion (8-15)
    'celesta': 8,
    'glockenspiel': 9,
    'vibraphone': 11,
    'marimba': 12,
    'xylophone': 13,
    'chimes': 14,
    # Organ (16-23)
    'organ': 19,
    'pipe organ': 19,
    # Guitar (24-31)
    'acoustic guitar': 25,
    'classical guitar': 24,
    'guitar': 25,
    'electric guitar': 27,
    # Strings (40-47)
    'violin': 40,
    'viola': 41,
    'cello': 42,
    'violoncello': 42,
    'contrabass': 43,
    'double bass': 43,
    # Ensemble (48-55)
    'string ensemble': 48,
    'strings': 48,
    'choir': 52,
    'choir aahs': 52,
    # Voice — all mapped to GM 52 (0-based) = 53 (1-based), Choir Aahs
    'soprano': 52,
    'alto': 52,
    'tenor': 52,
    'baritone': 52,
    'bass': 52,
    'bass voice': 52,
    'mezzo-soprano': 52,
    'mezzo soprano': 52,
    'solo vocal': 52,
    'vocal': 52,
    'voice': 52,
    'singing': 52,
    'singer': 52,
    # Brass (56-63)
    'trumpet': 56,
    'trombone': 57,
    'tuba': 58,
    'french horn': 60,
    'horn': 60,
    'horn in f': 60,
    'horn in eb': 60,
    'cornet': 56,
    'c tuba': 58,
    # Reed (64-71)
    'soprano saxophone': 64,
    'soprano sax': 64,
    'alto saxophone': 65,
    'tenor saxophone': 66,
    'baritone saxophone': 67,
    'oboe': 68,
    'english horn': 69,
    'bassoon': 70,
    'contrabassoon': 70,
    'double bassoon': 70,
    'clarinet': 71,
    'clarinet in bb': 71,
    'bass clarinet': 71,
    'bb clarinet': 71,
    'c clarinet': 71,
    'eb clarinet': 71,
    'bass oboe': 68,
    # Pipe (72-79)
    'piccolo': 72,
    'flute': 73,
    'recorder': 74,
    'ocarina': 79,
    # Synth (80-87)
    'string synthesizer': 50,
    'brass synthesizer': 62,
    # Other
    'harpsichord': 6,
    'cembalo': 6,
    'cimbalo': 6,
    'clavecin': 6,
    'cravo': 6,       # Portuguese for harpsichord
    'clavinet': 7,
    'harp': 46,
    'harpe': 46,
    'timpani': 47,
    'mandolin': 25,
    'keyboard': 0,
    'duduk': 68,  # closest GM: oboe
    'winds': 73,  # generic woodwind -> flute
    'basses': 43, # orchestral basses -> double bass
    'women': 52,  # women's choir
    'canto': 52,  # voice
    'sopranos': 52,
    'contraltos': 52,
    'campane': 14, # bells -> tubular bells
    'left hand': 0,   # piano LH
    'right hand': 0,   # piano RH
    # Percussion (channel 10) - special handling
    'bass drum': ('perc', 35),
    'concert bass drum': ('perc', 35),
    'snare drum': ('perc', 38),
    'triangle': ('perc', 81),
    'crash cymbal': ('perc', 49),
    'tam-tam': ('perc', 59),
    'mallets': 12,  # marimba
    'claves': ('perc', 75),
}

# Keyword fallback: if the full name doesn't match, try extracting a keyword
KEYWORD_PRIORITY = [
    ('piano', 0),
    ('harpsichord', 6),
    ('cembalo', 6),
    ('clavecin', 6),
    ('clavinet', 7),
    ('celesta', 8),
    ('glockenspiel', 9),
    ('xylophone', 13),
    ('organ', 19),
    ('guitar', 25),
    ('harp', 46),      # must come after harpsichord
    ('violin', 40),
    ('viola', 41),
    ('cello', 42),
    ('violoncello', 42),
    ('contrabass', 43),
    ('double bass', 43),
    ('timpani', 47),
    ('string ensemble', 48),
    ('choir', 52),
    ('soprano', 52),
    ('alto', 52),
    ('tenor', 52),
    ('baritone', 52),
    ('vocal', 52),
    ('voice', 52),
    ('singing', 52),
    ('trumpet', 56),
    ('trombone', 57),
    ('tuba', 58),
    ('french horn', 60),
    ('horn', 60),
    ('cornet', 56),
    ('corn', 56),       # abbreviation for cornet
    ('saxophone', 65),
    ('sax', 65),
    ('oboe', 68),
    ('english horn', 69),
    ('bassoon', 70),
    ('clarinet', 71),
    ('piccolo', 72),
    ('flute', 73),
    ('recorder', 74),
    ('ocarina', 79),
    ('mandolin', 25),
    ('bass drum', ('perc', 35)),
    ('drum', ('perc', 38)),
]


def normalize_name(name):
    """Normalize instrument name for matching."""
    name = name.strip().lower()
    # Remove trailing numbers and punctuation for base matching
    name = re.sub(r'\s*#?\d+\s*$', '', name)
    # Remove trailing whitespace and commas
    name = name.strip().rstrip(',').strip()
    return name


def resolve_composite_name(name):
    """Handle composite names like 'Piano, Concerto' -> 'Piano'."""
    if ',' in name:
        # Take the first part before comma
        first = name.split(',')[0].strip()
        return first
    return name


def get_gm_program(raw_name):
    """
    Return GM program number for an instrument name.
    Returns: (program_number, matched_name) or (None, None) if unresolvable.
    For percussion: (('perc', midi_note), matched_name)
    """
    name = normalize_name(raw_name)

    # 1. Exact match
    if name in GM_MAP:
        return GM_MAP[name], name

    # 2. Try composite (first part before comma)
    base = resolve_composite_name(name)
    if base in GM_MAP:
        return GM_MAP[base], base

    # 3. Try removing parenthetical content
    no_paren = re.sub(r'\s*\([^)]*\)', '', name).strip()
    if no_paren in GM_MAP:
        return GM_MAP[no_paren], no_paren

    # Also try composite after removing parens
    base_no_paren = resolve_composite_name(no_paren)
    if base_no_paren in GM_MAP:
        return GM_MAP[base_no_paren], base_no_paren

    # 4. Keyword fallback - check if name contains known keywords
    # Process in priority order (more specific first)
    for keyword, prog in KEYWORD_PRIORITY:
        if keyword in name:
            return prog, keyword

    # 5. Fallback: unresolvable names (mostly hallucinated) default to Piano
    return 0, f'FALLBACK(piano) for "{raw_name}"'


def inject_midi_into_abc(abc_text, verbose=False):
    """
    Parse ABC text, find V: lines with nm=, and inject %%MIDI program directives.

    Returns: (modified_abc_text, list_of_changes)
    """
    lines = abc_text.split('\n')
    new_lines = []
    changes = []
    unresolved = []

    for i, line in enumerate(lines):
        # Skip existing %%MIDI lines (idempotency: remove old injections)
        stripped = line.strip()
        if stripped.startswith('%%MIDI program') or stripped.startswith('%%MIDI channel'):
            continue

        new_lines.append(line)

        if not stripped.startswith('V:'):
            continue

        # Extract nm= value
        m = re.search(r'(?:^|[ \t])nm="([^"]*)"', stripped)
        if not m:
            m = re.search(r'(?:^|[ \t])name="([^"]*)"', stripped)
        if not m:
            continue

        raw_name = m.group(1)
        prog, matched = get_gm_program(raw_name)

        if prog is None:
            unresolved.append((raw_name, stripped))
            continue

        if isinstance(prog, tuple) and prog[0] == 'perc':
            # Percussion: set channel 10
            midi_line = '%%MIDI channel 10'
            new_lines.append(midi_line)
            changes.append((raw_name, matched, 'channel 10'))
        else:
            midi_line = f'%%MIDI program {prog}'
            new_lines.append(midi_line)
            changes.append((raw_name, matched, prog))

    return '\n'.join(new_lines), changes, unresolved


def process_directory(data_dir, dry_run=False, verbose=False):
    """Process all ABC files in the data directory.

    For each {data_dir}/{subdir}/abc/*.abc, writes the injected version to
    {data_dir}/{subdir}/abc_injected/{filename}.abc (originals are not modified).
    """
    data_dir = Path(data_dir)
    stats = {
        'total_files': 0,
        'modified_files': 0,
        'total_voices_mapped': 0,
        'unresolved': [],
    }

    subdirs = sorted([d for d in data_dir.iterdir() if d.is_dir()],
                     key=lambda x: int(x.name) if x.name.isdigit() else 0)

    # Collect all abc files first for progress bar
    all_abc_files = []
    for subdir in subdirs:
        abc_dir = subdir / 'abc'
        if not abc_dir.is_dir():
            continue
        for abc_path in sorted(abc_dir.glob('*.abc')):
            all_abc_files.append((subdir, abc_path))

    for subdir, abc_path in tqdm(all_abc_files, desc='Injecting MIDI'):
            stats['total_files'] += 1
            abc_text = abc_path.read_text(encoding='utf-8')
            modified, changes, unresolved = inject_midi_into_abc(abc_text, verbose)

            if changes:
                stats['modified_files'] += 1
                stats['total_voices_mapped'] += len(changes)

            if unresolved:
                for raw_name, vline in unresolved:
                    stats['unresolved'].append((subdir.name, raw_name, vline))

            if not dry_run and changes:
                injected_dir = subdir / 'abc_injected'
                injected_dir.mkdir(exist_ok=True)
                out_path = injected_dir / abc_path.name
                out_path.write_text(modified, encoding='utf-8')

            if verbose and (changes or unresolved):
                print(f"\n--- {abc_path.relative_to(data_dir)} ---")
                for raw, matched, prog in changes:
                    print(f"  OK: '{raw}' -> {matched} (program {prog})")
                for raw, vline in unresolved:
                    print(f"  ??: '{raw}' -> UNRESOLVED")

    return stats


def main():
    parser = argparse.ArgumentParser(description='Inject %%MIDI program into ABC files')
    parser.add_argument('--data_dir', type=str, required=True,
                        help='Path to data directory (contains numbered subdirs with abc/ folders)')
    parser.add_argument('--dry_run', action='store_true',
                        help='Do not write files, just report')
    parser.add_argument('--verbose', action='store_true',
                        help='Print per-file details')
    args = parser.parse_args()

    stats = process_directory(args.data_dir, args.dry_run, args.verbose)

    print(f"\n{'='*60}")
    print(f"{'DRY RUN' if args.dry_run else 'DONE'}")
    print(f"Total files: {stats['total_files']}")
    print(f"Modified files: {stats['modified_files']}")
    print(f"Total voices mapped: {stats['total_voices_mapped']}")
    print(f"Unresolved names: {len(stats['unresolved'])}")

    if stats['unresolved']:
        print(f"\n--- Unresolved instrument names ---")
        for dir_name, raw_name, vline in stats['unresolved']:
            print(f"  [{dir_name}] '{raw_name}'")


if __name__ == '__main__':
    main()
