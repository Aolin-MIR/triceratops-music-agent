"""Filesystem and real child-process regression tests; these do not certify model inference."""
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
import pytest
from text2music.agent.model_job import run_command, TaskCancelled


def test_continuation_bounds_only_generated_tail_and_keeps_original_streams():
    from mido import Message, MetaMessage, MidiFile, MidiTrack
    from text2music.agent.midi_merge import append_bounded_continuation
    source = MidiFile(ticks_per_beat=480)
    source.tracks.append(MidiTrack([MetaMessage('marker', text='original'),
        Message('control_change', control=1, value=33),
        Message('note_on', note=60), Message('note_off', note=60, time=480)]))
    tail = MidiFile(ticks_per_beat=240)
    tail.tracks.append(MidiTrack([Message('note_on', note=62),
        Message('note_off', note=62, time=250),
        Message('note_on', note=64), Message('note_off', note=64, time=20)]))
    output, audit = append_bounded_continuation(source, tail, boundary_tick=480, end_tick=960)
    assert output.tracks[0] == source.tracks[0]
    assert audit['added_notes'] == 1
    assert audit['clipped_note_offs'] == 1
    assert audit['discarded_late_note_ons'] == 1
    assert sum(event.time for event in output.tracks[1]) == 960
    assert [(event.type, event.note) for event in output.tracks[1]
            if event.type in {'note_on', 'note_off'}] == [('note_on', 62), ('note_off', 62)]


@pytest.mark.skipif(os.name == 'nt', reason='POSIX process group regression')
def test_cancellation_terminates_owned_process_and_grandchild(tmp_path):
    child_pid_file = tmp_path/'child.pid'
    parent_pid_file = tmp_path/'parent.pid'
    code = ('import subprocess,sys,time,os,pathlib; '
            f'pathlib.Path({str(parent_pid_file)!r}).write_text(str(os.getpid())); '
            'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"]); '
            f'pathlib.Path({str(child_pid_file)!r}).write_text(str(child.pid)); '
            'time.sleep(60)')
    cancelled = threading.Event()
    def cancel_when_started():
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if child_pid_file.exists():cancelled.set();return
            time.sleep(.01)
        cancelled.set()
    watcher=threading.Thread(target=cancel_when_started);watcher.start()
    start=time.monotonic()
    with pytest.raises(TaskCancelled):
        run_command([sys.executable,'-c',code],cancelled=cancelled.is_set)
    watcher.join()
    assert time.monotonic()-start<6
    parent=int(parent_pid_file.read_text())
    with pytest.raises(ProcessLookupError):os.kill(parent,0)
    child=int(child_pid_file.read_text())
    # Reaping an orphan is up to launchd; a zombie cannot execute model work.
    import subprocess
    state=subprocess.run(['ps','-o','stat=','-p',str(child)],capture_output=True,text=True).stdout.strip()
    assert not state or state.startswith('Z')


def test_timeout_also_reaps_owned_process(tmp_path):
    pidfile=tmp_path/'pid'
    code=f'import os,time,pathlib;pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()));time.sleep(60)'
    with pytest.raises(TimeoutError):
        run_command([sys.executable,'-c',code],cancelled=lambda:False,timeout=.2)
    import psutil
    assert not psutil.pid_exists(int(pidfile.read_text()))


def test_infill_merge_keeps_outside_events_and_expression(tmp_path):
    # A deterministic merge unit test, not a substitute for MIDI-GPT inference.
    import copy
    from mido import Message, MetaMessage, MidiFile, MidiTrack
    from midigpt import Score
    from text2music.agent.midi_merge import merge_infill
    source=tmp_path/'source.mid';output=tmp_path/'infill.mid'
    midi=MidiFile(ticks_per_beat=480)
    track=MidiTrack([MetaMessage('marker',text='keep'),Message('control_change',control=1,value=25),
                    Message('pitchwheel',pitch=321),Message('program_change',program=0)])
    midi.tracks.append(track)
    for bar,pitch in enumerate([60,62,64,65]):
        track.append(Message('note_on',note=pitch,velocity=80,time=0 if bar==0 else 1440))
        track.append(Message('note_off',note=pitch,time=480))
    track.append(MetaMessage('end_of_track',time=1440));midi.save(source)
    original=Score.from_midi(str(source));replacement=copy.deepcopy(original)
    replacement.tracks[0].bars[1].notes[0].pitch=70
    merge_infill(source,output,original,replacement,[0],[1])
    def events(path):
        rows=[]
        for i,tr in enumerate(MidiFile(path).tracks):
            tick=0
            for m in tr:
                tick+=m.time
                if m.type!='end_of_track':rows.append((i,tick,m.copy(time=0).dict()))
        return rows
    before,after=events(source),events(output)
    assert [r for r in before if not 1920<=r[1]<=3840] == [r for r in after if not 1920<=r[1]<=3840]
    assert all(r in after for r in before if r[2]['type'] in {'marker','pitchwheel','control_change','program_change'})
    assert any(r[2].get('note')==70 and r[2]['type']=='note_on' for r in after)


def test_error_redaction_removes_credentials(monkeypatch):
    from text2music.agent.errors import redact_error
    monkeypatch.setenv('QWEN_API_KEY','local-regression-secret')
    result=redact_error('Invalid local-regression-secret and sk-regression-example-key')
    assert 'local-regression-secret' not in result
    assert 'sk-regression-example-key' not in result


def test_memory_updates_are_atomic_and_ambiguous_or_empty_edits_do_not_delete(tmp_path):
    from text2music.agent.project_memory import ProjectMemory
    memory = ProjectMemory(tmp_path, 'test')
    memory.remember('marker one velocity 70', 'preference')
    memory.remember('marker two piano', 'constraint')
    before = memory.path.read_bytes()
    with pytest.raises(ValueError):memory.forget(' ')
    with pytest.raises(ValueError):memory.update('marker', 'replacement')
    with pytest.raises(ValueError):memory.update('missing', 'replacement')
    assert memory.path.read_bytes() == before
    memory.update('marker one', 'marker one velocity 64', 'preference')
    facts = memory.load()['facts']
    assert len(facts) == 2
    assert facts[0]['fact'] == 'marker one velocity 64'
    assert facts[1]['fact'] == 'marker two piano'
    reloaded = ProjectMemory(tmp_path, 'test')
    assert reloaded.recall('marker one')['facts'] == [facts[0]]
    assert reloaded.forget('marker one') == {'removed': 1}
    assert reloaded.recall('marker one')['facts'] == []


def test_quantize_keeps_short_notes_and_edits_drum_timing_and_velocity(tmp_path):
    from mido import MidiFile,MidiTrack,Message
    from text2music.agent.midi_tools import transform_midi_file
    source=tmp_path/'short.mid';output=tmp_path/'quantized.mid'
    midi=MidiFile(ticks_per_beat=480)
    for channel,note in [(0,60),(9,36)]:
        midi.tracks.append(MidiTrack([Message('note_on',channel=channel,note=note,velocity=80,time=7),
                                     Message('note_off',channel=channel,note=note,time=8)]))
    midi.save(source)
    transform_midi_file(source,'tighten',output,operations={'quantize':True,'velocity_delta':-10})
    for track in MidiFile(output).tracks:
        tick=0;events=[]
        for m in track:
            tick+=m.time
            if m.type in {'note_on','note_off'}:events.append((tick,m))
        assert events[0][0]==0
        assert events[1][0]>events[0][0]
        assert events[0][1].velocity==70


def test_fractional_sixteenth_grid_and_trailing_rest_are_preserved(tmp_path):
    from mido import MidiFile, MidiTrack, Message, MetaMessage
    from text2music.agent.midi_tools import transform_midi_file
    source, output = tmp_path/'low-ppq.mid', tmp_path/'edited.mid'
    midi = MidiFile(ticks_per_beat=50)
    track = MidiTrack(); midi.tracks.append(track)
    previous = 0
    for onset in [0, 13, 26, 39, 51]:
        track.append(Message('note_on', note=60, time=onset-previous))
        track.append(Message('note_off', note=60, time=1))
        previous = onset+1
    track.append(MetaMessage('end_of_track', time=200-previous)); midi.save(source)
    transform_midi_file(source, 'quantize', output, operations={'quantize': True})
    tick, onsets = 0, []
    for event in MidiFile(output).tracks[0]:
        tick += event.time
        if event.type == 'note_on' and event.velocity: onsets.append(tick)
    assert onsets == [0, 12, 25, 38, 50]
    assert tick == 200
    transform_midi_file(source, 'velocity only', output, operations={'velocity_delta': -12})
    before, after = MidiFile(source).tracks[0], MidiFile(output).tracks[0]
    assert [m.copy(velocity=m.velocity-12) if m.type=='note_on' and m.velocity else m for m in before] == list(after)


def test_quantize_final_short_note_does_not_extend_clip(tmp_path):
    from mido import MidiFile, MidiTrack, Message
    from text2music.agent.midi_tools import transform_midi_file
    source, output = tmp_path/'last.mid', tmp_path/'tight.mid'
    midi = MidiFile(ticks_per_beat=50)
    midi.tracks.append(MidiTrack([Message('note_on', note=60, time=1599),
                                Message('note_off', note=60, time=1)]))
    midi.save(source)
    transform_midi_file(source, 'tighten', output, operations={'quantize': True})
    track = MidiFile(output).tracks[0]
    assert sum(event.time for event in track) == 1600
    assert track[0].time == 1588 and track[1].time > 0


@pytest.mark.skipif(os.name == 'nt', reason='POSIX backend-exit lifecycle regression')
def test_backend_exit_terminates_detached_worker_tree(tmp_path):
    import subprocess
    pidfile=tmp_path/'worker.json'
    worker_code=('import os,sys,time,json,threading,subprocess,pathlib; '
                 'from text2music.agent.model_job import watch_parent; '
                 'threading.Thread(target=watch_parent,args=(os.getppid(),),daemon=True).start(); '
                 'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]); '
                 f'pathlib.Path({str(pidfile)!r}).write_text(json.dumps([os.getpid(),child.pid])); '
                 'time.sleep(60)')
    parent_code=('import subprocess,sys,time,pathlib; '
                 f'p=subprocess.Popen([sys.executable,"-c",{worker_code!r}],start_new_session=True); '
                 f'ready=pathlib.Path({str(pidfile)!r}); '
                 'deadline=time.monotonic()+5\n'
                 'while not ready.exists() and time.monotonic()<deadline:time.sleep(.01)\n')
    parent=subprocess.Popen([sys.executable,'-c',parent_code])
    assert parent.wait(timeout=8)==0
    assert pidfile.exists()
    pids=json.loads(pidfile.read_text());deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        alive=[]
        for pid in pids:
            state=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True).stdout.strip()
            if state and not state.startswith('Z'):alive.append(pid)
        if not alive:break
        time.sleep(.05)
    assert not alive
