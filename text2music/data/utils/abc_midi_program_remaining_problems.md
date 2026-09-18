# Remaining Problems

Known issues not yet resolved by the MIDI program injection pipeline.

---

## 1. #55 XML generation failure (tablature parsing)

**Error:** `abc2xml.py:801` — `IndexError: list index out of range` in `strAlloc.bezet()`

**Cause:** Mismatch between `stafflines` and `strings` in the tablature voice definition.

```
V:3 tab stafflines=6 strings=D3,A3,D4 nostems
V:4 tab stafflines=6 strings=D3,A3,D4
```

- `stafflines=6` initializes the internal array (`snaarVrij`) with 6 slots
- `strings=D3,A3,D4` defines only **3** strings
- ABC notes reference string 4+ (e.g. `!4!`) but `tunTup`/`tunmid` only has 3 entries -> index out of range

This is a model-generated ABC inconsistency in TAB notation, unrelated to MIDI injection. The file also failed XML generation before the injection was applied.

---

## 2. Malformed instrument names in `nm=` values

Many `nm=` values in the ABC files contain unnecessary qualifiers, parenthetical junk, or outright hallucinated text from the generation model. These names propagate into `<part-name>` and `<instrument-name>` in MusicXML, and ultimately appear as displayed part names in MuseScore and DAWs.

A survey of all 238 ABC files identified three categories of problematic names:

### Case 1: Composite names (53 occurrences) — rule-based fix possible

Names with commas where only the first token is the actual instrument.

| # | Original | Should be |
|---|----------|-----------|
| 1 | "Piano, Concerto" | "Piano" |
| 100 | "Grand Piano,  " | "Grand Piano" |
| 100 | "Horn, in F" | "Horn" |
| 100 | "Trombone, Accompani " | "Trombone" |
| 100 | "Violoncello, Cellos" | "Violoncello" |
| 100 | "Alto Saxophone, Alto Saxophone in Solo/ A (only)" | "Alto Saxophone" |
| 115 | "Piano, Saxophone" | "Piano" |
| 116 | "Bass Choir I, Alod Choir" | "Bass Choir I" |
| 116 | "Cello, Bass" | "Cello" |
| 119 | "Piano, Violin" | "Piano" |
| 119 | "Violin, Violin 1" | "Violin" |
| 119 | "Viola, Cello" | "Viola" |
| 120 | "Organ, Right Hand" | "Organ" |
| 125 | "Cello,  " | "Cello" |
| 137 | "Violins, Violins" | "Violins" |
| 154 | "Piano, Double Bass" | "Piano" |
| 156 | "Piano, Right Hand" | "Piano" |
| 158 | "Piano, Harp" | "Piano" |
| 158 | "Harp, 2" | "Harp" |
| 161 | "Piano, Viola" | "Piano" |
| 161 | "Piano, Violin 2" | "Piano" |
| 161 | "Violin, Violin Solo" | "Violin" |
| 168 | "Piano, Clarinettion" | "Piano" |
| 17 | "Piano, Celesta" | "Piano" |
| 188 | "Piano, Violin" (x2) | "Piano" |
| 188 | "Viola, Cello" | "Viola" |
| 189 | "Organ, Organ 1" | "Organ" |
| 189 | "Organ, Organ 1 Round Hand" | "Organ" |
| 19 | "Piano, Bass Double" | "Piano" |
| 198 | "Choir in Cornies, Challen" | "Choir" |
| 221 | "Piano, Viola" | "Piano" |
| 221 | "Violin, Violin 2" | "Violin" |
| 221 | "Viola, Viola" | "Viola" |
| 221 | "Clarinet, Clarinet" (x2) | "Clarinet" |
| 224 | "Clarinet, Clarinet" | "Clarinet" |
| 225 | "Right Piano, Right Hand" | "Piano" |
| 227 | "Piano, Harp" | "Piano" |
| 227 | "Harp, 2" | "Harp" |
| 227 | "Viola, Viola" | "Viola" |
| 227 | "Flute, 1" | "Flute" |
| 227 | "Flute, 2" | "Flute" |
| 237 | "Piano, Violin (Piano)" | "Piano" |
| 28 | "Piano, Left Hand #2" | "Piano" |
| 38 | "Viola,  Stana" | "Viola" |
| 38 | "Cello, Canto" | "Cello" |
| 48 | "Piano, (Lower) #2" | "Piano" |
| 63 | "Organ, Organ (Orgee)" | "Organ" |
| 66 | "Choir Pad, Chord" | "Choir" |
| 83 | "Piano, Harp" | "Piano" |
| 97 | "Alto Choir I, Tenor I" | "Alto" |
| 97 | "Bass I, Choir III" | "Bass" |

**Fix strategy:** Take the first token before the comma, then strip trailing whitespace and numbers. Implementable as a `--clean_names` option in `inject_midi_program.py` with minimal code changes.

### Case 2: Parenthetical junk (35 occurrences) — rule-based fix possible

Names with parenthetical qualifiers that should be stripped.

| # | Original | Should be |
|---|----------|-----------|
| 100 | "Trumpet (Bb)" | "Trumpet" |
| 100 | "Trombone (Bass Trombone)" | "Trombone" |
| 100 | "Choir (Trombone)" | "Choir" |
| 109 | "Piano (Harmony)" | "Piano" |
| 111 | "Cello (a) (Concert" | "Cello" |
| 135 | "Violin (or Violine)" | "Violin" |
| 135 | "Charle tuplet (pace contralto)" | garbage |
| 135 | "Cello (calso)" | "Cello" |
| 138 | "Piano (LH" | "Piano" |
| 148 | "Piano (triangel)" | "Piano" |
| 148 | "Piano (Continuo)" | "Piano" |
| 151 | "Bass (option)" | "Bass" |
| 16 | "Oboe (optional)" | "Oboe" |
| 170 | "Piano harmony (right hand...)" | "Piano" |
| 185 | "Violin (Violin)" | "Violin" |
| 198 | "Cello Chord-and Horns (Corn)" | garbage |
| 199 | "Classical Guitar (labelled )" | "Classical Guitar" |
| 203 | "Cello (Harp)" | "Cello" |
| 205 | "Tenor  (Alto)" | "Tenor" |
| 207 | "Piano Harmony (high)" | "Piano" |
| 210 | "Clarinet (B)" | "Clarinet" |
| 222 | "Violinen (Concerting)" | "Violin" |
| 27 | "Classical Guitar (or part contimes)" | "Classical Guitar" |
| 42 | "Orff Soprano  From Funt (Oboe)..." | garbage |
| 48 | "Piano (Hard)" | "Piano" |
| 48 | "Piano (Lower)" | "Piano" |
| 49 | "Soprano (the verse only)" | "Soprano" |
| 49 | "Choir (ad lessed on complete)" | "Choir" |
| 53 | "Trombone 4 (Contrambone)" | "Trombone" |
| 63 | "Organ (Organ)" | "Organ" |
| 71 | "Harpsichord (bass rhythm)" | "Harpsichord" |
| 93 | "Piano (for players)" | "Piano" |
| 93 | "Piano (bass not forsaken)" | "Piano" |
| 93 | "Piano at for examp into (string )" | garbage |
| 94 | "Flute (Orchestralstick)" | "Flute" |

**Fix strategy:** Strip all `(...)` content, then normalize the remaining text. Combinable with Case 1 in a single `--clean_names` pass. A few entries are garbage even after stripping (marked above) and would need Case 3 handling.

### Case 3: Hallucinated / garbage names (~30 occurrences) — requires LLM

Names that are completely unrecognizable as instruments. Examples:

- "Honky tongue", "Leved on the strings is have me ingless", "Head (String y)thmic Ragging"
- "Wundt", "Mallpins", "Keyna", "Fraten", "Chops", "Story", "There"
- "Ocomprano", "Flubos", "Clo Choes", "Cornstruments", "Contill"

These cannot be resolved by rules alone because the intended instrument is unknown. Possible approaches:

1. **External LLM refinement** — feed each problematic ABC file (or at least the V: header + a few measures of music) to an LLM and ask it to identify the intended instrument based on clef, range, and musical context
2. **Heuristic from musical content** — infer from clef (treble/bass/alto), note range, and `%%score` grouping what instrument family is likely, then assign a reasonable default
3. **Manual curation** — only ~30 files, feasible to inspect and fix by hand

Note: The current pipeline already assigns GM program 0 (Piano) as a fallback for these names, so MIDI playback works but uses the wrong instrument sound and displays a garbled part name.
