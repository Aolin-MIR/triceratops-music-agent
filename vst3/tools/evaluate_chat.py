"""Run real chat/tool tasks against the selected provider, with actual MIDI outputs.
Example: python vst3/tools/evaluate_chat.py --config /user/runtime.json --output /private/evaluation
No mocked clients or fake tool results are used. This is not a general model benchmark.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def evaluate(config: Path, output: Path, only: set[str] | None = None):
    from text2music.agent.runtime import configure
    configure(config)
    import mido
    from text2music.agent.llm_backend import check_chat_backend, create_chat_client, residency
    from text2music.agent.midi_tools import transform_midi_file
    from text2music.agent.symbolic_models import continue_midi_gpt, generate_midi_llm
    from text2music.agent.project_memory import ProjectMemory
    from text2music.agent.knowledge import KnowledgeBase
    from text2music.agent.tool_loop import run_tool_loop, DESCRIPTIONS
    output.mkdir(parents=True, exist_ok=True)
    source = output/'source.mid'
    memory = ProjectMemory(output/'memory', 'evaluation')
    project_notes = output/'project-notes.txt'
    project_notes.write_text('Project Silver Lantern: approved tempo is 87 BPM. Use F-sharp minor. The bridge starts at bar 17.', encoding='utf-8')
    knowledge = KnowledgeBase(output/'knowledge-index.json', [project_notes])
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack(); midi.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=500000))
    for pitch in [60, 64, 67, 65, 62, 60, 64, 69, 67, 65, 64, 60]:
        track.append(mido.Message('note_on', note=pitch, velocity=70, time=0))
        track.append(mido.Message('note_off', note=pitch, velocity=0, time=480))
    midi.save(source)
    quantize_source = output/'quantize-source.mid'
    quantized_input = mido.MidiFile(ticks_per_beat=480)
    quantize_track = mido.MidiTrack(); quantized_input.tracks.append(quantize_track)
    quantize_track.extend([mido.Message('note_on', note=60, velocity=67, time=40),
                           mido.Message('note_off', note=60, velocity=0, time=220),
                           mido.Message('note_on', note=64, velocity=81, time=200),
                           mido.Message('note_off', note=64, velocity=0, time=260)])
    quantized_input.save(quantize_source)
    def notes(path):
        events = []
        for tid, track in enumerate(mido.MidiFile(path).tracks):
            tick = 0
            for message in track:
                tick += message.time
                if message.type in {'note_on', 'note_off'}:
                    events.append((tid, tick, message.type, message.note, message.velocity))
        return events
    import numpy as np
    import soundfile as sf
    audio_path = output/'short-audio.wav'
    sample_rate = 22050
    time_axis = np.arange(sample_rate*8)/sample_rate
    audio = 0.18*np.sin(2*np.pi*440*time_axis)
    for start in np.arange(0.25, 8, 0.5):
        index = int(start*sample_rate)
        audio[index:index+600] += 0.35*np.hanning(600)
    sf.write(audio_path, np.clip(audio, -1, 1), sample_rate)

    def exercise(name, text, *, selection=source, previous=None, expected=None, edit=None,
                 reply_check=None, result_check=None, tool_check=None, context_extra=''):
        started = time.monotonic()
        client, _ = create_chat_client()
        actual = []
        def execute(tool, args):
            actual.append((tool, args))
            target = output/(name+'.mid')
            if tool == 'transform_midi':
                operations = dict(args['operations'])
                if 'protect_melody_track' in operations:
                    operations['preserve_melody'] = operations.pop('protect_melody_track')
                return transform_midi_file(selection, args['request'], target, operations=operations)
            if tool == 'continue_midi':
                return continue_midi_gpt(selection, target, bar_count=args.get('bar_count', 4))
            if tool == 'generate_draft':
                if args.get('max_tokens') != 96:
                    raise ValueError('The requested 96-token evaluation limit was not preserved')
                return generate_midi_llm(args['request'], output/name, max_tokens=args['max_tokens'])
            if tool == 'analyze_audio':
                from text2music.agent.audio_tools import analyze_audio, extract_audio_paths
                paths = extract_audio_paths(context_extra)
                if not paths: raise ValueError('No audio file is attached')
                return analyze_audio(paths[0])
            if tool == 'remember_fact': return memory.remember(args['fact'], args['category'])
            if tool == 'forget_fact': return memory.forget(args['text'])
            if tool == 'search_knowledge': return {'matches': knowledge.search(args['query'], limit=args.get('limit', 5))}
            if tool == 'list_capabilities': return {'capabilities': DESCRIPTIONS}
            raise RuntimeError('This real evaluation does not authorize the requested operation: '+tool)
        result = run_tool_loop(text, context='Tempo: 120 BPM; time signature 4/4. Reply in the user language.\n'+context_extra+'\n'+memory.context(),
                               selection=selection, conversation=previous, execute=execute, client=client, max_steps=12)
        tools = [entry['tool'] for entry in result.trace]
        errors = [entry for entry in result.trace if entry['state'] == 'failed']
        ok = not errors
        if expected == 'no_mutation': ok = ok and not actual
        elif expected == 'chat': ok = ok and not tools
        elif expected: ok = ok and expected in tools
        if expected == 'generate_draft':
            generated = [Path(entry['result']['midi']) for entry in result.trace if entry.get('result', {}).get('midi')]
            ok = ok and bool(generated) and all(path.is_file() and any(event[2]=='note_on' and event[4]>0 for event in notes(path)) for path in generated)
        if reply_check: ok = ok and reply_check(result.reply)
        if result_check:
            values = [entry.get('result') for entry in result.trace if entry.get('tool') == expected and entry.get('state') == 'completed']
            ok = ok and bool(values) and result_check(values[-1])
        if tool_check:
            ok = ok and tool_check(result.trace)
        if edit:
            target = output/(name+'.mid')
            ok = ok and target.is_file()
            if target.is_file(): ok = ok and edit(notes(selection), notes(target))
        return {'name': name, 'seconds': round(time.monotonic()-started, 3), 'passed': bool(ok),
                'tools': tools, 'reply': result.reply, 'trace': result.trace, 'actual_mutations': actual}
    report = {'compatibility': check_chat_backend(), 'tests': []}
    settings = create_chat_client()[1]
    if settings.provider in {'ollama', 'llama_cpp'}: report['resident_before'] = residency(settings)
    cases = [
        ('greeting_zh', '你好，我们先聊聊，不要生成或修改任何音乐。', dict(expected='chat', reply_check=lambda reply: any(word in reply for word in ('音乐', 'MIDI', 'REAPER', '创作')))),
        ('smalltalk_zh', '今天有点累，只想随便聊两句，暂时不做音乐。', dict(expected='chat', reply_check=lambda reply: len(reply) < 500 and any(word in reply for word in ('音乐', 'REAPER', 'MIDI', '创作')))),
        ('smalltalk_en', 'How are you? I just want a little chat for now, no music tasks yet.', dict(expected='chat', reply_check=lambda reply: len(reply) < 500 and any(word in reply.lower() for word in ('music', 'reaper', 'midi')))),
        ('capabilities_en', 'List the actual tools you can use in this plugin. Do not change files.', dict(expected='list_capabilities')),
        ('capabilities_natural_zh', '我第一次用这个插件，不想看复杂说明。你能在 REAPER 里直接替我做哪些事？该怎么开始？',
         dict(expected='list_capabilities')),
        ('ood_weather_zh', '今天北京天气怎么样？请不要编造实时天气，也不要假装能联网。',
         dict(expected='chat', reply_check=lambda reply: any(word in reply.lower() for word in ('reaper', 'midi', '音乐')) and any(word in reply for word in ('天气', '联网', '查询')))),
        ('ood_lyrics_en', 'Write a complete pop song lyric for me. I do not want MIDI or any music production help.',
         dict(expected='chat', reply_check=lambda reply: any(word in reply.lower() for word in ('lyric', 'lyrics', 'midi', 'reaper')))),
        ('ambiguous_midi_edit_zh', '把这段 MIDI 弄得更高级、更有感觉一点，其他你看着办。',
         dict(expected='no_mutation', reply_check=lambda reply: any(word in reply for word in ('移调', '力度', '量化', '和弦', '具体')))),
        ('unsupported_midi_edit_en', 'Humanize this MIDI with swing, articulation changes, and reharmonize the chords.',
         dict(expected='no_mutation', reply_check=lambda reply: any(word in reply.lower() for word in ('swing', 'humaniz', 'support', 'transpose', 'quantiz')))),
        ('mixed_in_scope_ood_zh', '把这段 MIDI 升高两个半音，然后顺便告诉我今天美元兑人民币汇率。',
         dict(expected='transform_midi', reply_check=lambda reply: any(word in reply.lower() for word in ('汇率', 'realtime', '实时', '无法', '不能')),
              edit=lambda before, after: len(before)==len(after) and all(a[:3]==b[:3] and a[3]+2==b[3] and a[4]==b[4] for a,b in zip(before,after)))),
        ('analysis_zh', '看看这段 MIDI，有多少个音符？别改它。', dict(expected='analyze_selected_midi')),
        ('transpose_zh', '把这段升高两个半音，力度和每个音符的起止时间保持原样。',
         dict(expected='transform_midi', edit=lambda before, after: len(before)==len(after) and all(a[:3]==b[:3] and a[3]+2==b[3] and a[4]==b[4] for a,b in zip(before,after)))),
        ('velocity_en', 'Increase every note velocity by 12. Keep pitches and all timing unchanged.',
         dict(expected='transform_midi', edit=lambda before, after: len(before)==len(after) and all(a[:4]==b[:4] and (b[4] == a[4]+12 if a[2]=='note_on' else b[4]==a[4]) for a,b in zip(before,after)))),
        ('continuation_zh', '接着这段再写四小节。保留现有音符和速度，不要改写原段。',
         dict(expected='continue_midi', edit=lambda before, after: len(after)>len(before) and all(event in after for event in before))),
        ('missing_input_en', 'Separate the attached recording into four stems.', dict(expected='no_mutation', selection=None)),
        ('question_zh', 'MIDI 为什么还要加载音源才有声音？只解释，不要操作。', dict(expected='chat')),
        ('conversation_context_zh', '按刚才说的做吧。', dict(expected='transform_midi', previous=[
            {'role':'user','content':'下一步把这段升高两个半音，其他都不要改。先别执行。'},
            {'role':'assistant','content':'好的，等你确认后再升高两个半音。'}],
            edit=lambda before, after: len(before)==len(after) and all(a[:3]==b[:3] and a[3]+2==b[3] and a[4]==b[4] for a,b in zip(before,after)))),
        ('memory_remember_zh', '请记住这个工程的固定标记是 Cedar-731，以后会用到。', dict(expected='remember_fact')),
        ('memory_recall_zh', '我让你记住的工程固定标记是什么？请从工程记忆回答，不要改音乐。',
         dict(expected='chat', reply_check=lambda reply: 'cedar-731' in reply.lower())),
        ('retrieval_en', 'Search the project notes for Silver Lantern. What is its approved tempo? Cite the source file.',
         dict(expected='search_knowledge', reply_check=lambda reply: '87' in reply and 'project-notes.txt' in reply)),
        ('generate_fragment_zh', '给我做一段像夜里走回家、雨刚停、路灯把影子拉很长的音乐。前半段很疏，后面稍微亮起来，但别太煽情；钢琴和大提琴就行，短一点。用 MIDI-LLM，最多生成 96 个新 token，不用问参数。',
         dict(expected='generate_draft', selection=None,
              tool_check=lambda trace: any(
                  all(term in str(entry.get('arguments', {}).get('request', '')).lower() for term in ('rain', 'piano', 'cello'))
                  and any(term in str(entry.get('arguments', {}).get('request', '')).lower() for term in ('shadow', 'streetlight', 'lamp'))
                  and any(term in str(entry.get('arguments', {}).get('request', '')).lower() for term in ('sparse', 'thin', 'open'))
                  and any(term in str(entry.get('arguments', {}).get('request', '')).lower() for term in ('night', 'evening', 'walking home'))
                  and any(term in str(entry.get('arguments', {}).get('request', '')).lower() for term in ('brighter', 'brightening', 'lighten', 'lift'))
                  and any(term in str(entry.get('arguments', {}).get('request', '')).lower() for term in ('not overly emotional', 'not too emotional', 'restrained', 'sentimental', 'melodramatic'))
                  and any(term in str(entry.get('arguments', {}).get('request', '')).lower() for term in ('brief', 'short', 'intimate'))
                  for entry in trace if entry.get('tool') == 'generate_draft'))),
        ('quantize_real_midi', '量化这段 MIDI 到十六分音符，音高和力度都不要动。',
         dict(expected='transform_midi', selection=quantize_source,
              edit=lambda before, after: len(before)==len(after) and all(a[0]==b[0] and a[2:]==b[2:] and b[1] % 120 == 0 for a,b in zip(before,after)))),
        ('transpose_without_midi', '把这段升高两个半音，其他不变。', dict(expected='no_mutation', selection=None)),
        ('audio_analysis_real', '分析这段音频的速度、调性和段落。',
         dict(expected='analyze_audio', selection=None, context_extra=f'Attached audio: {audio_path}',
              result_check=lambda result: result.get('duration_seconds', 0) >= 7 and result.get('onset_count', 0) > 0 and 40 <= result.get('tempo_bpm', 0) <= 240)),
        ('audio_analysis_missing', '分析音频的调性和速度。', dict(expected='no_mutation', selection=None)),
        ('audio_to_midi_missing', '把录音转换成 MIDI。', dict(expected='no_mutation', selection=None)),
        ('stems_missing', '把这首歌分成鼓、贝斯、人声和其他四轨。', dict(expected='no_mutation', selection=None)),
        ('memory_forget_zh', '忘掉工程记忆里的 Cedar-731。', dict(expected='forget_fact')),
        ('clarification_missing_audio', '把人声转成 MIDI 并保留原调。', dict(expected='no_mutation', selection=None)),
    ]
    for name, text, options in cases:
        if only and name not in only: continue
        try: entry = exercise(name, text, **options)
        except Exception as exc:
            detail = str(exc)
            secret = os.environ.get('QWEN_API_KEY', '')
            if secret: detail = detail.replace(secret, '[redacted]')
            entry = {'name':name, 'passed':False, 'error':detail}
        report['tests'].append(entry)
        (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        print(json.dumps({key:entry[key] for key in ('name','passed','seconds','tools','error') if key in entry}, ensure_ascii=False), flush=True)
    if settings.provider in {'ollama', 'llama_cpp'}: report['resident_after'] = residency(settings)
    report['passed'] = sum(case['passed'] for case in report['tests'])
    report['total'] = len(report['tests'])
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(f"Passed {report['passed']}/{report['total']} real task checks", flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', nargs='*')
    args = parser.parse_args()
    try:
        evaluate(args.config, args.output, set(args.only or []))
    except Exception as exc:
        detail = str(exc)
        secret = os.environ.get('QWEN_API_KEY', '')
        if secret: detail = detail.replace(secret, '[redacted]')
        raise SystemExit(detail)
