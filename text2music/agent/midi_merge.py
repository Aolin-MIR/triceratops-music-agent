"""Replace requested MIDI-GPT bars while retaining original event streams."""
from collections import Counter, defaultdict, deque
from pathlib import Path
from mido import Message, MetaMessage, MidiFile, MidiTrack


def append_bounded_continuation(source: MidiFile, tail: MidiFile, *,
                                boundary_tick: int, end_tick: int) -> tuple[MidiFile, dict]:
    """Append actual generated events, bounding only the new material's duration."""
    if source.type == 2 or end_tick <= boundary_tick:
        raise ValueError("Continuation requires synchronous MIDI and a positive tail length")
    output = MidiFile(type=1, ticks_per_beat=source.ticks_per_beat)
    output.tracks.extend(MidiTrack(event.copy() for event in track) for track in source.tracks)
    audit = {"clipped_note_offs": 0, "discarded_late_note_ons": 0,
             "closed_unterminated_notes": 0, "added_notes": 0,
             "boundary_tick": boundary_tick, "end_tick": end_tick}
    for track in tail.tracks:
        result, active = MidiTrack(), defaultdict(deque)
        absolute, previous = 0, 0
        for event in track:
            absolute += event.time
            tick = boundary_tick + round(absolute * source.ticks_per_beat / tail.ticks_per_beat)
            if event.type in {"set_tempo", "end_of_track"}:
                continue
            if event.type == "note_on" and event.velocity > 0:
                keep = tick < end_tick
                active[event.channel, event.note].append(keep)
                if not keep:
                    audit["discarded_late_note_ons"] += 1
                    continue
                audit["added_notes"] += 1
            elif event.type in {"note_on", "note_off"}:
                queue = active[event.channel, event.note]
                if not queue or not queue.popleft():
                    continue
                if tick > end_tick:
                    audit["clipped_note_offs"] += 1
                    tick = end_tick
            elif tick > end_tick:
                continue
            result.append(event.copy(time=tick - previous))
            previous = tick
        for (channel, note), pending in active.items():
            for keep in pending:
                if keep:
                    result.append(Message("note_off", channel=channel, note=note,
                                          time=end_tick - previous))
                    previous = end_tick
                    audit["closed_unterminated_notes"] += 1
        result.append(MetaMessage("end_of_track", time=end_tick - previous))
        output.tracks.append(result)
    if not audit["added_notes"]:
        raise RuntimeError("MIDI-GPT returned no notes within the requested continuation bars")
    return output, audit


def merge_infill(source: Path, destination: Path, original, generated,
                 track_ids: list[int], bar_ids: list[int]) -> dict:
    midi = MidiFile(source)
    if midi.type == 2:
        raise ValueError("Infill requires synchronous MIDI tracks (type 0 or 1)")
    generated = generated.resample(original.resolution)
    if len(generated.tracks) != len(original.tracks):
        raise RuntimeError("MIDI-GPT infill changed the number of source tracks")
    ratio = midi.ticks_per_beat / original.resolution
    streams, groups = [], defaultdict(list)
    for index, track in enumerate(midi.tracks):
        tick, rows = 0, []
        for order, message in enumerate(track):
            tick += message.time
            rows.append((tick, order, message))
            if message.type == "note_on" and message.velocity > 0:
                groups[index, message.channel].append((message.note, tick))
        streams.append(rows)

    remove = defaultdict(set)
    additions = defaultdict(list)
    used = set()
    added_notes = 0
    for track_id in track_ids:
        reference, replacement = original.tracks[track_id], generated.tracks[track_id]
        offsets, cursor = [], 0
        signature = []
        for bar in reference.bars:
            offsets.append(cursor)
            signature.extend((note.pitch, round(cursor + note.onset_ticks)) for note in bar.notes)
            cursor += bar.beat_length * original.resolution
        candidates = [group for group, notes in groups.items()
                      if group not in used and Counter((pitch, round(tick / ratio)) for pitch, tick in notes) == Counter(signature)
                      and (group[1] == 9) == (reference.track_type == "drum")]
        if len(candidates) != 1:
            raise ValueError("Cannot unambiguously map MIDI-GPT track to source MIDI events; source was not changed")
        raw_track, channel = candidates[0]
        used.add(candidates[0])
        if max(bar_ids) >= len(reference.bars) or max(bar_ids) >= len(replacement.bars):
            raise ValueError("Infill bar id is outside the source MIDI")
        ranges = []
        for bar_id in bar_ids:
            start = round(offsets[bar_id] * ratio)
            end = round((offsets[bar_id] + reference.bars[bar_id].beat_length * original.resolution) * ratio)
            if ranges and ranges[-1][1] == start:
                ranges[-1] = (ranges[-1][0], end)
            else:
                ranges.append((start, end))
            for note in replacement.bars[bar_id].notes:
                onset = round((offsets[bar_id] + note.onset_ticks) * ratio)
                release = min(end, onset + max(1, round(note.duration_ticks * ratio)))
                if not start <= onset < end or release <= onset:
                    continue
                additions[raw_track].append((onset, 1, Message("note_on", channel=channel,
                    note=note.pitch, velocity=max(1, min(127, note.velocity)))))
                additions[raw_track].append((release, 0, Message("note_off", channel=channel,
                    note=note.pitch, velocity=0)))
                added_notes += 1
        active = defaultdict(deque)
        for tick, order, message in streams[raw_track]:
            if getattr(message, "channel", -1) != channel or message.type not in {"note_on", "note_off"}:
                continue
            if message.type == "note_on" and message.velocity > 0:
                active[message.note].append((tick, order))
            elif active[message.note]:
                onset, on_order = active[message.note].popleft()
                # Keep notes crossing a selection boundary, including their
                # release outside the range. All CCs, bends and metadata stay.
                if any(start <= onset < end and tick <= end for start, end in ranges):
                    remove[raw_track].update((on_order, order))
    if added_notes == 0:
        raise RuntimeError("MIDI-GPT returned no new notes in the requested infill bars")
    output = MidiFile(type=midi.type, ticks_per_beat=midi.ticks_per_beat)
    for index, rows in enumerate(streams):
        if index not in additions:
            output.tracks.append(MidiTrack(event.copy() for event in midi.tracks[index]))
            continue
        events = [(tick, 1, order, event) for tick, order, event in rows
                  if order not in remove[index] and event.type != "end_of_track"]
        events.extend((tick, priority, len(rows) + order, event)
                      for order, (tick, priority, event) in enumerate(additions[index]))
        events.sort(key=lambda event: event[:3])
        track, previous = MidiTrack(), 0
        for tick, _, _, event in events:
            track.append(event.copy(time=tick - previous))
            previous = tick
        # Preserve trailing rest as well as the unchanged absolute events.
        from mido import MetaMessage
        track.append(MetaMessage("end_of_track", time=max(0, rows[-1][0] - previous)))
        output.tracks.append(track)
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.save(destination)
    return {"infill_notes": added_notes, "preserved_outside_selection": True}
