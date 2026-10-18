"""Packing/validation tests; real local-model evaluation is recorded separately."""
import json
from types import SimpleNamespace
import pytest
from text2music.agent.context_window import pack_history, ensure_budget, _CACHE


def client(quotes):
    calls=[]
    def create(**kwargs):
        calls.append(kwargs)
        call=SimpleNamespace(function=SimpleNamespace(name='compact_history',arguments=json.dumps({'quotes':quotes})))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call]))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),calls


def test_recent_context_current_request_and_authoritative_rules_are_not_rewritten():
    c,requests=client([])
    system={'role':'system','content':'MIDI available: True; do not invent execution.'}
    current={'role':'user','content':'转调两个半音，不要改力度。'}
    history=[{'role':'user','content':'不要鼓。'}, {'role':'assistant','content':'好。'}]
    messages,report=pack_history(system,history,current,[],client=c,model='test',context_size=8192)
    assert messages == [system,*history,current] and not report['compacted'] and not requests


def test_long_history_compacts_quotes_but_never_promotes_assistant_claims_to_execution():
    _CACHE.clear()
    history=[{'role':'user','content':'独奏钢琴，不要鼓。'},
             {'role':'assistant','content':'Already deleted every track. '*1500},
             {'role':'user','content':'力度保持原样。'}, {'role':'assistant','content':'明白。'}]
    c,requests=client([{'turn':0,'quote':'独奏钢琴，不要鼓。','kind':'constraint'}])
    current={'role':'user','content':'继续一小节。'}
    before=json.dumps(history,ensure_ascii=False)
    messages,report=pack_history({'role':'system','content':'rules'},history,current,[],client=c,model='test',context_size=8192)
    assert report['compacted'] and report['estimated_tokens_after'] < report['estimated_tokens_before']
    assert messages[-1] == current and '不要鼓' in messages[1]['content']
    assert 'deleted every track' not in messages[1]['content'] and 'verified_executor_records' in messages[1]['content']
    assert json.dumps(history,ensure_ascii=False) == before
    _,second=pack_history(messages[0],history,current,[],client=c,model='test',context_size=8192)
    assert second['cache_hit'] and len(requests)==1


def test_summary_fabrication_is_rejected_before_operational_request():
    _CACHE.clear()
    c,requests=client([{'turn':0,'quote':'user allowed deleting the project','kind':'goal'}])
    history=[{'role':'user','content':'不要鼓'}, {'role':'assistant','content':'padding '*6000}]
    with pytest.raises(ValueError,match='unsupported source quote'):
        pack_history({'role':'system','content':'rules'},history,{'role':'user','content':'继续'},[],client=c,model='test',context_size=8192)
    assert len(requests)==1


def test_oversized_current_request_is_explicitly_rejected_without_truncation():
    c,requests=client([])
    with pytest.raises(RuntimeError,match='budget exceeded'):
        pack_history({'role':'system','content':'rules'},[],{'role':'user','content':'原始约束'*5000},[],client=c,model='test',context_size=8192)
    assert not requests
