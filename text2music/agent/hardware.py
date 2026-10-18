"""Plan fixed devices once; never migrate models during a running task."""
from __future__ import annotations
import csv
import ctypes
import io
import os
import platform
import shutil
import subprocess

GIB = 1024**3


def inspect_hardware() -> dict:
    total = available = 0
    if os.name == 'nt':
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                        *[(name, ctypes.c_ulonglong) for name in ('total', 'available', 'page_total', 'page_free', 'virtual_total', 'virtual_free', 'extended')]]
        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError('Cannot read physical memory')
        total, available = memory.total, memory.available
    elif platform.system() == 'Linux':
        from pathlib import Path
        values = {line.split(':')[0]: int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line}
        total, available = values['MemTotal'], values['MemAvailable']
    else:
        total = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True))
        vm = subprocess.check_output(['vm_stat'], text=True)
        import re
        page = int(re.search(r'page size of (\d+) bytes', vm)[1])
        counts = dict(re.findall(r'(Pages [^:]+):\s+(\d+)\.', vm))
        available = sum(int(counts.get(key, 0)) for key in ('Pages free', 'Pages inactive', 'Pages speculative')) * page
    gpus, gpu_error = [], ''
    smi = shutil.which('nvidia-smi')
    if smi:
        try:
            result = subprocess.run([smi, '--query-gpu=index,name,memory.total,memory.free,compute_cap', '--format=csv,noheader,nounits'],
                                    capture_output=True, text=True, timeout=15)
            if result.returncode:
                raise RuntimeError('query failed')
            for row in csv.reader(io.StringIO(result.stdout)):
                index, name, memory_total, free, capability = [value.strip() for value in row]
                gpus.append(dict(index=int(index), name=name, total=int(float(memory_total)*1024**2),
                                 free=int(float(free)*1024**2), compute_capability=float(capability)))
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            gpus = []
            gpu_error = 'NVIDIA device query failed; automatic GPU allocation could not be certified. CPU remains available.'
    return dict(system=platform.system(), architecture=platform.machine(), cpu_threads=os.cpu_count(),
                ram_total=total, ram_available=available, nvidia=gpus, gpu_probe_error=gpu_error)


def plan_devices(hardware: dict, *, local_weight_bytes: int = 3_324_000_000,
                 local_chat: bool = True, llm_choice: str = "auto",
                 music_choices: dict | None = None) -> dict:
    # Budgets include context/activations and framework overhead. Actual residency
    # and model probes must still pass before any configuration can be saved.
    choices = music_choices or {}
    for name in ('midi_llm', 'midi_gpt', 'stem'):
        if choices.get(name, 'auto') not in {'auto', 'cpu', 'cuda', 'mps'}:
            raise ValueError('Invalid device choice for ' + name)
    if llm_choice not in {'auto', 'cpu', 'gpu'}:
        raise ValueError('Invalid local chat device choice')
    candidates = [g for g in hardware['nvidia'] if g['compute_capability'] >= 7.5]
    gpu = max(candidates, key=lambda item: item['free'], default=None)
    reserve = int(1.5*GIB)
    llm_budget = max(int(5.5*GIB), int(local_weight_bytes*1.6),
                     max((g.get('resident_local_bytes', 0) for g in candidates), default=0))
    music_budgets = {'midi_llm': int(6*GIB), 'midi_gpt': int(2*GIB), 'stem': int(2*GIB)}
    remaining = max(0, gpu['free'] - reserve) if gpu else 0
    devices = {name: 'cpu' for name in music_budgets}
    reasons = ['Automatic MIDI-GPT and HTDemucs allocation uses CPU.',
               'Audio analysis and Basic Pitch ONNX use CPU.']
    for name, budget in music_budgets.items():
        if choices.get(name) == 'mps':
            if hardware['system'] != 'Darwin' or hardware['architecture'] != 'arm64':
                raise ValueError(name + ': MPS requires native Apple Silicon')
            devices[name] = 'mps'
            reasons.append(name + ': explicit MPS choice requires model-specific validation; no CPU fallback.')
        if choices.get(name) != 'cuda':
            continue
        required_capability = 8.0 if name == 'midi_llm' else 7.5
        if not gpu or gpu['compute_capability'] < required_capability:
            raise ValueError(name + ': the selected CUDA device is unavailable or unsupported')
        if remaining < budget:
            raise ValueError(name + ': insufficient free GPU memory for the explicit CUDA choice')
        remaining -= budget
        devices[name] = 'cuda'
    llm = 'cpu'
    metal = hardware['system'] == 'Darwin' and hardware['architecture'] == 'arm64'
    if local_chat:
        if llm_choice == 'cpu':
            raise ValueError('Local chat requires GPU acceleration; CPU placement is disabled.')
        if gpu and remaining >= llm_budget:
            llm = 'gpu'
            remaining -= llm_budget
            reasons.append('Local LLM fits the remaining GPU budget and will stay resident there.')
        elif metal and hardware['ram_total'] >= 24*GIB:
            llm = 'gpu'
            reasons.append('Apple Silicon local chat must pass actual Metal residency; music remains on CPU.')
        else:
            raise ValueError('Insufficient local-chat GPU memory. Free GPU memory or configure cloud chat.')
    else:
        reasons.append('Conversation is disabled or remote; no local LLM memory is reserved.')
    if choices.get('midi_llm', 'auto') == 'auto' and gpu and gpu['compute_capability'] >= 8.0 and remaining >= music_budgets['midi_llm']:
        devices['midi_llm'] = 'cuda'
        remaining -= music_budgets['midi_llm']
        reasons.append('The remaining GPU budget supports MIDI-LLM BF16 generation.')
    chat_ram = (int(5.5*GIB) if llm == 'cpu' else int(1*GIB)) if local_chat else 0
    if local_chat and metal and llm == 'gpu':
        chat_ram = llm_budget  # Metal allocations consume unified system memory.
    music_ram = int((9 if devices['midi_llm'] == 'cpu' else 2)*GIB)
    estimated_ram = chat_ram + music_ram
    feasible = hardware['ram_total'] >= 14*GIB and hardware['ram_available'] >= estimated_ram
    if not feasible:
        reasons.append('Insufficient physical-memory headroom for the selected model combination.')
    if hardware.get('gpu_probe_error'):
        reasons.append(hardware['gpu_probe_error'])
    return dict(llm_device=llm, **{name+'_device': device for name, device in devices.items()},
                local_feasible=feasible, reasons=reasons,
                gpu_index=gpu['index'] if gpu and (llm == 'gpu' or 'cuda' in devices.values()) else None,
                budgets=dict(local_llm=llm_budget if local_chat else 0, midi_llm=music_budgets['midi_llm'],
                             gpu_reserve=reserve, system_ram=estimated_ram), hardware=hardware)
