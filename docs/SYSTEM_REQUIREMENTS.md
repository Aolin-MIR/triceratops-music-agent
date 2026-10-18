# System requirements / 系统配置 · Triceratops 0.9

[中文](#中文) · [English](#english) · [README](../readme.md)

## 中文

本页描述 v0.9 的实际实现。软件条件来自安装脚本和固定依赖，资源数字用于规划安装与运行；**尚未通过多种内存 / 显存配置测定全功能最低值**。单次成功、插件编译成功或依赖导入成功，都不能证明全部功能可用。

### Windows

- 系统：Windows 10 / 11 x64；安装器允许 Windows 10 起安装，已完成的本机功能测试在 Windows 11 上。Windows 10 尚未单独验证。Windows ARM64 不列为支持平台。
- 宿主：REAPER x64，已验证版本 7.80；建议 7.80 或更新版本。未测出最早兼容的 REAPER 版本，其他 DAW 不在 v0.9 支持范围。
- 运行环境：EXE 自带独立 CPython 3.11.9 种子环境，再安装固定运行依赖；不要求 WSL、Conda 或系统 Python。安装系统 VST3 和 VC++ 运行库需要管理员权限，首次配置需要联网。
- CPU 路径：不要求独立显卡；建议现代 64 位多核 CPU，4 核或更多作为运行预算，并非测出的指令集 / 核数下限。完整组合使用的原生依赖也必须支持该 CPU。建议至少 16 GB RAM、32 GB 更宽裕；16 GB 是规划建议，尚未在 16 GB 机器上验证全功能峰值。8 GB 不列为全功能建议配置。
- CUDA 路径：当前 MIDI-LLM 加载器指定 BF16；推荐具备 BF16 支持的 NVIDIA Ampere 或更新架构（例如 RTX 30 / 40 / 50 系列），并预留 16 GB 显存作为保守预算。16 GB 是已用显卡的容量和上游建议，**不是已测得的最低显存**；尚未验证 6 / 8 / 12 GB 设备。不能把相同显存的旧架构显卡视为等价。AMD / Intel GPU 加速未接入。
- CUDA 安装器选择 `torch==2.13.0` 的 `cu130` wheel；驱动必须能实际运行该 wheel。无需为使用预编译 wheel 单独安装完整 CUDA Toolkit。`nvidia-smi` 的 CUDA 字样和 `torch.cuda.is_available()` 仅是初步条件；完整验证还必须进行 BF16 模型生成、续写、分轨并导入宿主。设备失败会报错，不静默改成 CPU。
- 可用空间：CPU 安装建议预留 20 GB、CUDA 安装建议预留 30 GB；这些是预算而非实测安装峰值。依赖、下载缓存、模型、生成文件可能位于不同磁盘，分别需要余量。模型约 4 GB 不包含 Python / Torch、临时文件、重复缓存和用户音源。长音频四分轨可快速增加占用。

### macOS

- 硬件 / 系统：Apple Silicon（M1 或更新），macOS 14+；当前固定 Torch 运行环境不支持 Intel Mac。VST3 的 universal 架构不代表 Intel Mac 模型后端可用。
- 宿主：原生 Apple Silicon REAPER，建议 7.80 或更新版本。Rosetta / x86 Python 混用不属于当前支持路径。
- Python：自行安装原生 ARM64 Python 3.10 / 3.11。`setup-macos.sh` 默认执行 `python3.11`；只有 3.10 时，先设置 `TRICERATOPS_PYTHON` 为对应解释器路径。脚本创建独立 venv，不修改系统 Python。
- 计算设备：发行版脚本写入 `device=cpu`。代码中存在 MPS 设备选项，不等于所有音乐模型和音频依赖已验证支持 MPS；v0.9 没有已验证的 MPS / MLX 加速承诺。
- 统一内存：建议 16 GB 起、32 GB 更宽裕。系统、REAPER、音源和模型共享这部分内存；尚未完成 Mac 实机内存峰值和速度测量，因此不发布“8 GB 可运行全部功能”或某款芯片的速度保证。
- 空间：安装建议预留 20 GB，再为缓存、音频和工程保留余量；不是实测峰值。保留解压目录，后端启动路径引用其中的源码。
- 分发：当前 ZIP 未签名 / 未公证；首次打开可能需要在系统“隐私与安全性”中允许经核对来源的组件。不要关闭全局 Gatekeeper，也不要对整块磁盘移除隔离属性。若被拦截，记录实际提示和目标文件再处理。
- 状态：已通过 universal VST3 构建；完整 Mac 安装、各模型和 REAPER 实机流程尚待测试，取得实测数据后再收紧配置范围。

### 每项功能的资源差异

| 功能 | 当前后端 / 设备行为 | 配置影响 |
| --- | --- | --- |
| 聊天、意图整理、工具选择 | 可选外部聊天 API；Windows 本地聊天用 llama.cpp Vulkan 固定在 GPU；明确按钮直接执行本地工具，无需聊天模型 | 云端模式需要网络、凭据、额度及工具调用支持；本地聊天模型固定常驻 GPU，不回退 CPU。Mac 本地聊天尚未验证 |
| 文本生成 MIDI | MIDI-LLM；CUDA BF16，CPU / 当前 MPS 加载分支为 FP32 | 实际权重约 17.24 亿参数，虽以 Llama 3.2 1B 为基座，音乐词表扩展后参数更多。BF16 权重约 3.45 GB（3.21 GiB），转为 FP32 仅权重约 6.90 GB（6.42 GiB），另需激活、KV cache、框架和加载空间；这些计算不是实测峰值 |
| 续写 / 填充 | MIDI-GPT Yellow Medium；使用选择的 Torch 设备 | 权重文件约 351 MB；运行时还需上下文、激活和框架内存，不能按文件大小推断最低内存 |
| 四分轨 | 固定 HTDemucs；使用选择的 Torch 设备 | 时长、声道、采样率和分段影响内存与耗时；当前没有全时长范围的峰值保证 |
| 音频转 MIDI | Basic Pitch ICASSP 2022 ONNX；使用 `onnxruntime` 依赖 | 当前未配置 CUDA / CoreML ONNX Execution Provider，不能声称随 Torch 的 GPU 选择而加速；以实际会话 provider 为准 |
| 音频分析 | librosa / NumPy 的速度、起音、色度与分段算法 | CPU 工作；不是额外的音乐生成模型。当前分析最多读取 900 秒单声道 22.05 kHz 音频 |
| MIDI 编辑、统计、记忆与检索 | 本地 MIDI 和文件 / 检索工具 | 本身不要求音乐生成 GPU；明确按钮无需聊天 API；自由对话由所选语言模型调度 |
| 播放 MIDI | REAPER 中的用户音源 | 生成 MIDI 不等于合成音频；声卡、采样库及音源的内存 / CPU 开销另计 |

Windows 本地聊天用 Ollama 工具从模型 registry 下载 Qwen3.5 GGUF，实际推理由 llama.cpp Vulkan 完成；安装包附带这两个运行程序，但不附带聊天权重。聊天权重约 3.32 GB，另需计算服务器进程和 KV cache；不能据此承诺它与所有音乐模型可同时常驻同一 GPU。

### 已有证据与边界

- 本机：Windows 11 x64、AMD Ryzen 9 5900HX、操作系统当前可见内存约 27.9 GiB、RTX 3080 **Laptop** GPU 16 GiB；REAPER 7.80 x64。这里写实际可见容量，不能当作 16 GB 机器通过测试的证据。
- Windows 原生 CPU / `torch 2.13.0+cpu` 的固定短素材测试：音频分析成功、Basic Pitch 得到 12 个音符、MIDI-GPT 追加 4 小节约 2.44 秒、MIDI-LLM 192 新 token 约 78.84 秒、HTDemucs 得到 4 个 12 秒声部。不同任务条件不一致，不能据此进行跨设备速度排名。
- Windows 原生 RTX 3080 Laptop GPU 上的本地 Qwen3.5 4B / llama.cpp Vulkan：真实聊天与工具流程 21/21 通过，含 MIDI 生成、编辑、续写、记忆、知识检索和音频分析；工具调用及工具结果回传检查通过，测试前后模型均报告 GPU 常驻。启动日志确认 33/33 层卸载至 GPU。该测试证明选定本地聊天路径可运行，不证明所有音乐模型与聊天模型可并发占用 GPU，也不是所有输入的质量保证。
- 同一 GPU 本地模型的补充检查：闲聊、能力发现、模糊编辑、越界请求、混合意图、记忆与知识检索等 13 项通过；一项真实中文文字引导 MIDI 生成保留了具体与抽象描述，并返回可解析且含音符的 MIDI。共 118 项 Python 单元测试通过。该格式检查不代表主观听感保证；生成输出仍需用户试听与判断。
- Windows REAPER 已检查实际 MIDI / 分轨导入与双语界面；完整 Mac 实机流程尚无结果。未测完整任务树的内存峰值、长音频上限、所有 API 提供方和所有驱动 / GPU 组合。
- 证据摘要核对日期：2026-10-18。本地测试报告保留在 `text2music/artifacts/agent_runs/release-0.9/` 和 `listening-2026-10-16/`，含私有运行材料，不作为可公开下载的测试附件。

### 判断依据

安装与运行实现：[Windows 安装器](../vst3/installer/Triceratops.iss)、[Windows 配置](../vst3/installer/Setup-Runtime.ps1)、[Mac 配置](../vst3/installer/setup-macos.sh)、[固定依赖](../vst3/installer/requirements-runtime.txt)、[MIDI-LLM 加载精度](../text2music/agent/midi_llm_runner.py)、[固定模型下载](../text2music/agent/download_models.py)、[音频工具](../text2music/agent/audio_tools.py)。[MIDI-LLM 官方](https://github.com/slSeanWU/MIDI-LLM)建议 16 GB+ 显存；该建议不是本项目的最低值测量。

## English

This page describes the v0.9 implementation. Installer constraints, planning budgets and tested configurations are reported separately. **A full-feature hardware minimum has not been established across memory capacities.** A successful import, build or single generation does not certify every feature.

### Windows requirements

- Windows 10 / 11 x64; the installer permits Windows 10+, while completed local functional testing used Windows 11. Windows 10 has not been separately verified. Windows ARM64 is outside support.
- REAPER x64; 7.80 tested and 7.80+ recommended. The earliest compatible host version has not been established. Other DAWs are outside v0.9 support.
- The EXE includes a dedicated CPython 3.11.9 seed, then installs pinned dependencies. WSL, Conda and a system Python installation are unnecessary. Installing the system VST3 / VC++ runtime requires administrator rights; initial setup requires internet access.
- CPU mode needs no discrete GPU. Budget for a modern multicore x64 CPU (4+ cores suggested) and 16 GB RAM, preferably 32 GB when running instruments or longer audio. These are planning recommendations, not measured CPU / memory minimums. Native wheels must also support the CPU. An 8 GB machine is not a recommended full-feature configuration.
- The CUDA MIDI-LLM path loads BF16. A BF16-capable NVIDIA Ampere or newer GPU (for example RTX 30 / 40 / 50 series) and a conservative 16 GB VRAM budget are recommended. This reflects upstream guidance and the tested GPU capacity, **not a measured minimum**. No 6 / 8 / 12 GB configuration has been validated; older GPUs with equal VRAM are not equivalent. AMD / Intel GPU acceleration is not integrated.
- Setup selects `torch==2.13.0` from the `cu130` wheel index. The installed NVIDIA driver must run that wheel; a separate full CUDA Toolkit is unnecessary for a prebuilt wheel. `nvidia-smi` and `torch.cuda.is_available()` alone do not certify BF16 generation, continuation, separation and host import. Device failures are explicit, without a silent CPU switch.
- Reserve 20 GB for CPU installation or 30 GB for CUDA, plus download caches, recordings, instruments and projects. These are conservative budgets, not measured installation peaks. Check free space on every drive containing runtime, temporary files or models. Approximately 4 GB of model weights excludes Python / Torch and duplicated caches.

### macOS requirements

- Apple Silicon (M1 or newer), macOS 14+. The pinned runtime does not support Intel Mac model execution, even though the VST3 binary is universal.
- Native Apple Silicon REAPER, 7.80+ recommended. Mixing Rosetta / x86 Python with ARM64 dependencies is outside the supported path.
- Install native ARM64 Python 3.10 / 3.11 yourself. Setup defaults to `python3.11`; set `TRICERATOPS_PYTHON` to the correct interpreter path when using 3.10. Setup creates a dedicated venv.
- The release script selects CPU. An MPS option in source is not proof of compatibility across the music models; MPS / MLX acceleration is not validated in v0.9.
- Budget for 16 GB unified memory, preferably 32 GB. macOS, REAPER, instruments and models share this memory. No physical Mac peak-memory or speed results are available, and 8 GB full-feature operation is not certified.
- Reserve 20 GB plus cache, audio and project space; this is not a measured peak. Keep the extracted directory because backend launch paths reference its source.
- The ZIP is unsigned / not notarized. If macOS blocks a verified component, inspect its actual warning and target before using the system's Privacy & Security approval flow. Do not disable Gatekeeper globally or remove quarantine recursively across a disk.
- The universal VST3 build passed; installation, models and complete REAPER operation still need a physical Mac test before tightening the stated requirements.

### Resource use by feature

| Feature | Actual backend | Resource implications |
| --- | --- | --- |
| Chat / intent rewriting / tool dispatch | User-selected cloud API or Windows local llama.cpp Vulkan on a fixed GPU; explicit buttons bypass the LLM | Cloud mode requires internet, credentials and native tool calling; local chat stays on GPU with no CPU fallback. Mac local chat is unverified |
| Text-to-MIDI | MIDI-LLM, BF16 on CUDA; FP32 on CPU / the current MPS loading branch | The checkpoint has about 1.724 billion parameters after vocabulary expansion, despite its Llama 3.2 1B base. Weight-only size is about 3.45 GB / 3.21 GiB in BF16 or 6.90 GB / 6.42 GiB in FP32, plus activations, KV cache, framework and loading overhead. These are calculations, not measured peaks |
| Continuation / infill | MIDI-GPT Yellow Medium on the selected Torch device | Approximately 351 MB weight file, plus runtime context, activations and framework overhead |
| Four-stem separation | Pinned HTDemucs on the selected Torch device | Duration, channels, sample rate and segmentation affect resources; no peak guarantee across all input lengths |
| Audio-to-MIDI | Basic Pitch ICASSP 2022 ONNX | No CUDA / CoreML ONNX Execution Provider is configured; Torch's GPU selection does not certify ONNX acceleration. Inspect the actual session providers |
| Audio analysis | librosa / NumPy algorithms | CPU work, not another generation model. Analysis currently reads at most 900 seconds at 22.05 kHz mono |
| MIDI edits / statistics / memory / retrieval | Local MIDI and file / retrieval tools | Do not intrinsically require a generation GPU; explicit buttons require no chat API; free-form requests use the selected LLM |
| MIDI playback | User instruments in REAPER | MIDI is not rendered audio; budget separately for instruments, samples and audio processing |

On Windows, the installer bundles Ollama only as a model-download utility and includes llama.cpp Vulkan for inference; the Qwen3.5 GGUF weights are not bundled. Budget about 3.32 GB for the chat weights plus server and KV cache. Simultaneous GPU residency with every music model is not certified.

### Evidence and limits

- Local hardware: Windows 11 x64, Ryzen 9 5900HX, approximately 27.9 GiB currently visible system memory, RTX 3080 **Laptop** GPU with 16 GiB VRAM, REAPER 7.80 x64. This is not evidence of full-feature success on a 16 GB RAM computer.
- Native Windows CPU / `torch 2.13.0+cpu`, short fixtures: audio analysis passed; Basic Pitch produced 12 notes; MIDI-GPT appended 4 bars in about 2.44 s; MIDI-LLM generated up to 192 new tokens in about 78.84 s; HTDemucs produced four 12-second stems.
- Native Windows RTX 3080 Laptop GPU, local Qwen3.5 4B through llama.cpp Vulkan: 21/21 real chat/tool scenarios passed, including MIDI generation, edits, continuation, memory, retrieval and audio analysis. Native tool calls and tool-result replay passed; GPU residency was confirmed before and after evaluation, with all 33/33 model layers offloaded in the startup log. This does not certify simultaneous execution with every music model or output quality for all prompts.
- Supplemental local-GPU checks passed for 13 small-talk, capability-discovery, ambiguous-edit, out-of-scope, mixed-intent, memory and retrieval cases. One real Chinese text-guided MIDI generation preserved concrete and abstract prompt details and returned a parseable MIDI containing notes. A total of 118 Python unit tests passed. Format validation does not guarantee subjective musical quality; users should audition generated output.
- Actual MIDI / stem import and bilingual UI were checked in Windows REAPER. Full Mac operation, complete peak-memory measurements, long-audio limits, every API provider and every driver / GPU combination remain unverified.
- Evidence reviewed on 2026-10-18. Local reports remain in `text2music/artifacts/agent_runs/release-0.9/` and `listening-2026-10-16/`; they contain private runtime material and are not advertised as public downloadable fixtures.

Implementation sources are linked in the Chinese section above. [MIDI-LLM upstream](https://github.com/slSeanWU/MIDI-LLM) recommends 16 GB+ VRAM; this is guidance, not this project's measured minimum.

本地 LLM 使用固定 CPU/GPU 和常驻策略，不在任务之间卸载或自动改变设备。音乐模型可分别指定 `midi_llm_device`、`midi_gpt_device` 和 `stem_device`，不存在资源不足时自动切换的逻辑。Local LLM residency is fixed to CPU/GPU; music devices are selected independently, without automatic fallback.


2026-10-18 本地 1.0 工作区补充 / local 1.0 working-tree update: Ryzen 9 5900HX 原生 CPU 的默认长度 MIDI-LLM（768 新 token 上限）约 247 秒；四小节 MIDI-GPT 续写首次约 11.2 秒、重复约 3.7 秒；12 秒音频的 HTDemucs 四分轨约 19.9 秒，分析约 19.2 秒，短小号转写约 13.2 秒。These figures include the stated loading/import conditions and are not a cross-device benchmark. 本地 Qwen3.5 4B 的常驻与音乐模型并行实测仍在进行，不能据设备规划器的预算推断已全部验证。Automatic device budgets are planning estimates, not measured peak-memory certification.

1.0 模型空间补充 / Model storage: 音乐模型约 4 GB，默认 Qwen3.5 4B 本地聊天模型另需约 3.32 GB；安装器中的 Ollama 下载工具、llama.cpp Vulkan、Python/Torch、缓存和用户素材另计。Music weights use about 4 GB; the default local-chat model adds about 3.32 GB, excluding the bundled Ollama download utility, llama.cpp Vulkan, Python/Torch, caches and user media. Windows 1.0 安装器不内嵌聊天模型权重；本地聊天和所有音乐模型同时运行仍待验证 / Simultaneous local chat and every music model remain unverified.
