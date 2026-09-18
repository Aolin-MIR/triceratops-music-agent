# ABC MIDI Program Injection Pipeline

Injects GM MIDI program numbers into ABC files so that downstream tools (MuseScore, DAWs) select the correct instruments instead of defaulting to piano.

## Usage

### CLI

```bash
# Dry run — preview mappings without modifying files
python text2music/data/utils/inject_midi_program.py --data_dir /path/to/data --dry_run --verbose

# Apply — writes to abc_injected/ folders (originals are not modified)
python text2music/data/utils/inject_midi_program.py --data_dir /path/to/data
```

**Options:**
- `--data_dir` (required): Data directory path (contains numbered subdirs with `abc/` folders)
- `--dry_run`: Report mappings without writing files
- `--verbose`: Print per-file mapping details

**Directory structure:**
```
data_dir/
├── 1/abc/*.abc          # input (not modified)
│   └── abc_injected/    # output (created automatically)
├── 2/abc/*.abc
│   └── abc_injected/
└── ...
```

All `.abc` files in each `abc/` folder are processed (no filename pattern constraint).

### Python API

```python
from text2music.data.utils.inject_midi_program import (
    inject_midi_into_abc,
    get_gm_program,
    process_directory,
)

# 1. Inject %%MIDI program into an ABC string
abc_text = open('sample.abc').read()
modified_abc, changes, unresolved = inject_midi_into_abc(abc_text)
# changes: [(raw_name, matched_name, program_number), ...]

# 2. Look up GM program number for an instrument name
prog, matched = get_gm_program("Cello")          # (42, 'cello')
prog, matched = get_gm_program("Piano, Concerto") # (0, 'piano')
prog, matched = get_gm_program("Violin 1")        # (40, 'violin')

# 3. Batch-process a directory
stats = process_directory('/path/to/data', dry_run=False, verbose=True)
print(f"Modified: {stats['modified_files']}/{stats['total_files']}")
```

### Converting modified ABC to MusicXML (abc2xml)

```python
from text2music.data.utils.abc_helper.abc2xml import getXmlDocs, fixDoctype

with open('sample.abc') as f:
    abc_str = f.read()

docs = getXmlDocs(abc_str)
xml_str = fixDoctype(docs[0])

with open('output.xml', 'w') as f:
    f.write(xml_str)
```

### Converting MusicXML to MIDI — xml2mid.py

**CLI (batch):**

```bash
# Convert all XML files in the data directory to MIDI
python text2music/data/utils/xml2mid.py --data_dir /path/to/data --verbose

# Use default path
python text2music/data/utils/xml2mid.py
```

Output: `{data_dir}/{num}/mid/{num}_output.mid`

**Python API (single file):**

```python
from text2music.data.utils.xml2mid import convert_xml_to_mid

status = convert_xml_to_mid('input.xml', 'output.mid')
# Returns 'ok' or 'ok (repeats stripped)' if repeat expansion failed
```

**Python API (batch):**

```python
from text2music.data.utils.xml2mid import process_directory

stats = process_directory('/path/to/data', verbose=True)
print(f"Success: {stats['success']}/{stats['total']}")
```

**Notes:**
- If music21 cannot expand malformed repeats, the script automatically strips repeat marks and retries (single pass, no repeats)
- 12 out of 237 files required repeat stripping; all 237 converted successfully

### File Reference

| File | Description |
|------|-------------|
| `inject_midi_program.py` | Injects `%%MIDI program` directives into ABC files |
| `xml2mid.py` | Batch MusicXML -> MIDI converter (music21, with repeat fallback) |
| `abc_helper/abc2xml.py` | ABC -> MusicXML converter (v245, built-in `%%MIDI` support) |
| `abc_helper/abc2abc_interleaved.py` | Interleaved ABC converter (strips `%%MIDI` — training only, no impact) |

### GM Program Number Reference

| Instrument | GM Program (0-based) | MusicXML (1-based) |
|------------|---------------------|-------------------|
| Piano | 0 | 1 |
| Harpsichord | 6 | 7 |
| Celesta | 8 | 9 |
| Organ | 19 | 20 |
| Acoustic Guitar | 25 | 26 |
| Violin | 40 | 41 |
| Viola | 41 | 42 |
| Cello | 42 | 43 |
| Double Bass | 43 | 44 |
| Harp | 46 | 47 |
| Timpani | 47 | 48 |
| Choir Aahs (all voices: soprano, alto, tenor, bass, etc.) | 52 | 53 |
| Trumpet | 56 | 57 |
| Trombone | 57 | 58 |
| Tuba | 58 | 59 |
| French Horn | 60 | 61 |
| Alto Sax | 65 | 66 |
| Oboe | 68 | 69 |
| Bassoon | 70 | 71 |
| Clarinet | 71 | 72 |
| Piccolo | 72 | 73 |
| Flute | 73 | 74 |

---

## Work Notes

### Background

- ABC `V:` headers specify instrument names via `nm="Cello"` etc., but without a `%%MIDI program` directive abc2xml does not emit `<midi-instrument>` elements in MusicXML
- As a result, MuseScore (MS Basic) must guess the instrument from `<part-name>` alone and often falls back to piano

### Step 1. Survey of nm= values

Dataset: `/Users/sungkyun/ML/text2score_ablated/` (238 subdirectories)

**Results:**
- 319 unique `nm=` values, 1,392 total occurrences
- Top 10: Cello(100), Viola(76), Harp(73), Violin(64), Flute(61), Double Bass(52), Piano(43), Oboe(43), Clarinet(40), Bassoon(36)

**Notable findings:**
- ~46 names are model hallucinations (e.g. "Leved on the strings is have me ingless")
- Multiple spellings per instrument: Violin / Violin 1 / Violin I / Violins / Vln.
- Composite names: "Piano, Concerto", "Piano, Violin", "Viola, Cello"

### Step 2. Injection script

Script: [`inject_midi_program.py`](inject_midi_program.py)

**Mapping strategy (priority order):**
1. Normalize (lowercase, strip trailing numbers) then exact-match against `GM_MAP`
2. Extract first token before comma (e.g. "Piano, Concerto" -> "Piano")
3. Remove parenthetical content (e.g. "Cello (a) (Concert" -> "Cello")
4. Keyword fallback — check if name contains a known instrument keyword
5. Final fallback — unresolvable (hallucinated) names default to Piano (program 0)

**Results:**
- All 238 files, 1,392 voices mapped (0 unresolved)
- ~46 hallucinated names handled by keyword matching or Piano fallback

**Idempotency:** Re-running the script strips existing `%%MIDI program` / `%%MIDI channel` lines before re-inserting.

**Example (before / after):**
```
# Before
V:4 treble nm="Cello" snm="Cello"

# After
V:4 treble nm="Cello" snm="Cello"
%%MIDI program 42
```

### Step 3. Pipeline 1 verification (ABC -> MusicXML -> MuseScore)

Converted with abc2xml v245 and checked for `<midi-instrument>` in the output.

**Sample #1 (Piano + Cello):**
```xml
<score-part id="P1">
  <part-name>Piano, Concerto</part-name>
  <score-instrument id="I1-1"><instrument-name>Piano, Concerto</instrument-name></score-instrument>
  <midi-instrument id="I1-1"><midi-program>1</midi-program></midi-instrument>
</score-part>
<score-part id="P4">
  <part-name>Cello</part-name>
  <score-instrument id="I4-4"><instrument-name>Cello</instrument-name></score-instrument>
  <midi-instrument id="I4-4"><midi-program>43</midi-program></midi-instrument>
</score-part>
```

**Sample #4 (8-part orchestra):**
- Trumpet(57), French Horn(61), Trombone(58), Tuba(59), Violin(41), Viola(42), Cello(43), Double Bass(44)
- All correct GM program numbers (1-based)

**Notes:**
- abc2xml automatically converts 0-based ABC programs to 1-based MusicXML (+1)
- `nm=` value is also copied to `<instrument-name>`

### Step 4. Pipeline 2 verification (MusicXML -> music21 -> MIDI)

Parsed MusicXML with music21 v9.1.0 and exported to MIDI to verify program change events.

**Sample #1:**
```
Part: Piano, Concerto  | MIDI program: 0
Part: Cello            | MIDI program: 42
```
MIDI file: Track 1 ch=1 program=0, Track 3 ch=2 program=42

**Sample #4 (8 parts):**
- All 8 parts have correct program change events
- Each part auto-assigned to a separate MIDI channel (ch1–ch8)

**Conclusion: Fixing ABC for Pipeline 1 automatically resolves Pipeline 2.**

### Step 5. Batch application

1. Ran `inject_midi_program.py` on all 238 ABC files
2. Re-generated all XML files with abc2xml

**Results:**
- ABC injection: 238/238 succeeded
- XML regeneration: 237/238 succeeded
- 1 failure: #55 (contains tablature — pre-existing abc2xml issue, see [remaining problems](abc_midi_program_remaining_problems.md))
- All 237 XML files contain `<midi-program>` elements
