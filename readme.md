# Triceratops Music Agent · 0.9

[中文](readme.md) | [English](README.en.md)

**把脑海里的几小节，留在 REAPER 的工程里。**

Triceratops 是 REAPER 中的音乐 Agent VST3。用自然语言描述想法，或点击操作按钮，让它调用本地模型生成、续写、编辑和分析 MIDI，再把可编辑结果导入真实轨道。

**v0.9 仅支持 REAPER。Windows 使用原生 Python 后端，不需要 WSL。** 聊天及意图改写通过你配置的 Qwen / OpenAI 兼容 API 完成；MIDI 生成、续写、分轨和转写在本机运行。

[![Triceratops 0.9 功能一览](docs/images/triceratops-0.9-overview.webp)](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Feature-Overview.png)

## 本次本地修复与验证（待合入 v1.0.1）

本轮基于 `main` 修复；先等待 Windows 1.0 更新，再合并、复测并统一发布 v1.0.1。当前发行附件仍为 v0.9.0，下面的本地实测不代表完整验收已通过。

- **跨平台共用修复**：失败的生成或编辑立即停止并显示真实错误；取消会终止任务的模型子进程，后端退出时清理所属进程树；MIDI-GPT 填充保留范围外的原始事件与控制信息；量化保留短音符并正确处理鼓轨的时值和力度；错误信息脱敏；固定并校验 HTDemucs、Basic Pitch 和解码器资源，国内镜像失败后明确重试同一固定版本的官方来源；修复 Basic Pitch 对 `pkg_resources` 的运行时依赖。新增显式的 MIDI-LLM 精度配置，保留原默认精度，不静默切换设备；按用户约束移除鼓事件和设置音色时保留原始 MIDI 与处理记录。原生工具调用调度避免只回复“将要执行”；音乐操作完成后按实际数据报告。续写裁剪新增音符的越界尾部并保留原始生成尾段；修正非整除 PPQ 的量化网格、末尾短音符边界和尾部休止长度；插件异步重连退出的后端；编辑器重开后保留录制状态与自动导入偏好；两分钟录音达到容量后仍可保存，不覆盖同秒录音文件；Undo 沿当前文件的来源逐级回退，避免按全局输出顺序恢复其他片段；记忆支持原子更新、从磁盘读取，空条件不删除，保存完成后不再擅自删除；知识查询检索成功后进入回答阶段，防止重复搜索到超限，并保留异常前的执行记录。
- **Mac 专属修复**：拒绝 Rosetta / x86 Python 混用；保留已有运行路径、设备及 API 设置，配置和备份权限为 `0600`；安装验证成功后才替换插件，并备份原插件；原生 Mac 不扫描或关闭 Linux 的旧模型 worker；录制文件统一保存到 `~/Library/Application Support/Triceratops/Captures`。
- **已做的真实宿主验证**：在 8 GB Apple A18 Pro、macOS 27.0.1、ARM64 Python 3.11.17、REAPER 7.82 上扫描、插入修复版 VST3，启动后端，切换中文 / English，通过 Qwen 原生工具调用执行 Basic Pitch ONNX 转写，手动和自动导入真实 MIDI 轨道，打开钢琴卷帘，并用 Apple DLSMusicDevice 渲染了 8 秒钢琴试听。还通过自然语言实际运行 MIDI-LLM（CPU/float16、512 token 上限，模型任务约 124 秒）：原始 170 音符含 45 个鼓音符，明确后处理后为 125 个钢琴音符、无鼓，保留原始非鼓事件。宿主 MIDI-GPT 续写新增 97 音符，保留原 125 音符事件流，裁剪 3 个越界尾部后为 8 小节 / 16 秒，并实际自动导入；宿主量化、力度、转调、连续四级 Undo 和指定小节填充也核对了真实事件，Undo 到起点后准确报错且不删除宿主轨道；HTDemucs 四声部实际导入、播放并渲染试听，宿主内部路由录到了 16 个 MIDI 音符和约 8 秒有效音频。音频设备由 REAPER 的用户设置决定，插件不固定声卡。
- **已做的模型 / 后端验证**：CPU MIDI-GPT 实际续写四小节和指定范围填充，并核对原始事件；HTDemucs 对 8 秒自有素材实际运行两次四分轨（约 8.02 / 6.60 秒）；Basic Pitch 实际使用 `CPUExecutionProvider`；量化、力度、转调、Undo、反馈、记忆和本地检索均核对真实文件或事件。真实宿主还验证了长任务取消后清理所属子进程、无效 API 的 401、网络失败、缺模型和缺 MIDI 的报错及恢复；测试配置已恢复为原字段，权限为 `0600`。生成钢琴另用 Apple DLSMusicDevice 实际播放、打开钢琴卷帘并渲染八秒试听。新增回归测试后，本机测试集为 91 项通过；这些后端测试不等同于全部宿主操作已通过，也不代表 Windows 已复测。
- **仍需完成**：声卡与系统默认输入路径、任意选中片段上下文及其余异常场景的端到端验证；录制状态、偏好保存及两分钟容量边界已在宿主复测；默认输出路径可播放，Studio 26c 单独输出仍在 CoreAudio 注册 I/O 回调处阻塞，不能宣称这张声卡已通过。已保存真实窗口采样录屏（约 0.7–1.5 fps，非连续全帧录屏），并实际重开宿主和验证后端退出后的自动恢复。宿主任意选中片段的上下文读取尚未跑通；目前续写 / 编辑验证使用插件已载入的 MIDI。VST3 的聊天上下文尚未传入真实工程路径，已验证的记忆 CRUD 使用本机 VST3 记忆文件，不能当作工程间隔离通过；该上下文需与 Windows 1.0 功能更新一起合并验证。MIDI-LLM 默认 CPU/float32 在本机以 96 token 上限运行 300 秒超时；显式 CPU/float16 两次约 30 秒可生成有效 MIDI，但原始输出出现错误乐器或鼓，未通过“钢琴、不要鼓”的音乐要求。后处理可修正明确的乐器 / 鼓限制，不能据此宣称情绪、留白等音乐质量达标。MPS 只验证了 MIDI-GPT 的实际推理，不能据此宣称所有模型支持 GPU。

以上是这一台 Mac 的实测；不能外推为所有 Mac 的最低配置或速度保证。

Basic Pitch 现记录实际执行该次转写的 ONNX 会话、模型校验值、加载耗时和音符数。8 秒自有双声部加鼓素材在真实宿主中转写约 4.10 秒，使用 `CPUExecutionProvider`，生成并导入 26 个音符；按音高与起音误差不超过 0.15 秒核对，匹配已知 32 个音符起点中的 26 个，遗漏 6 个低音。该结果只说明这段素材的误差，不能把文件生成成功当作完整音乐转写正确。

### Logic Pro AU 本地适配（待合入 v1.0.1）

新增两个 macOS Audio Unit：`Triceratops MIDI`（`aumi/TrMi/Tric`）插在软件乐器轨道的 **MIDI FX** 中、音源之前，用于 MIDI 输入录制及生成音符播放；`Triceratops Audio`（`aufx/TrAu/Tric`）插在 **Audio FX** 中，用于音频输入录制及文件工具。二者使用同一后端和固定音乐模型。MIDI 版没有音频录制入口，音频版不输出 MIDI 到音源；界面会关闭对应的不适用按钮。

AU 安装至 `~/Library/Audio/Plug-Ins/Components`，仍包含 REAPER VST3。Logic 单独安装时不要求安装 REAPER：配置可指定 `logic` 可执行文件，doctor 会报告实际找到的宿主。音频设备由 Logic 的用户设置决定，插件不选择或固定声卡。Logic 中通过“文件 → 导入 → MIDI 文件”加入工程已实测；原生拖出按钮仍待完整落轨验证，不能视为通过；“显示结果文件”定位真实文件。自动导入桥接仍仅对 REAPER 启用，Logic 中不会误启动 REAPER。

本机 Logic Pro 12.4 原生 ARM64 已实际扫描、加载两个 AU，二者通过 Apple `auval`。真实聊天和 MIDI-LLM 生成已执行：首次 96 token 输出仅含鼓，去鼓后明确失败并保留原文件；后续 192 token 生成有效文件。修复后一次生成由原始 64 音符（40 鼓）交付为 24 个无鼓钢琴音符，模型任务约 36 秒；经 MIDI AU 实际输出至 Logic 音源并录成 MIDI 片段，24 个音符的音高、力度、通道和起音核对通过，最大起音误差约 0.000625 秒。Audio AU 也实际录到了 Logic 电钢琴的内部音频输出并保存试听。Basic Pitch 经 Audio AU 真实转写得到 16 音符，再通过 Logic 导入并在钢琴卷帘核对；MIDI AU 输入捕获核对了真实轨道的 24 个音符。Logic MIDI FX 菜单的“在此处将 MIDI 录制到轨道”需放在插件上方以捕获已有片段回放，放在插件下方以录制插件新生成的输出。上述测试不能代替所有宿主功能、其他 Logic 版本或工程隔离的完整验收。

生成后整理还处理同一音轨、通道和音高的重复 / 重叠起音：合并同刻重复起音，裁剪下一次重触发前的尾音，修复零时值与未结束音符；不添加替代旋律，原始 MIDI、哈希及处理计数始终保留。该共用问题是在 Logic 输出录制中发现的，并非只对 Mac 文件生效；用户已载入的 MIDI 编辑不会自动套用此生成后整理。另已修复无音符捕获仍保存空文件的问题，并提示检查路由、录制点及目录权限；POSIX 后端启动会恢复 SIGTERM，避免继承宿主忽略终止信号的设置，实际终止及 AU 自动重连已复测。Mac AU 每次链接后会重新签完整 bundle 并执行严格签名校验，修复增量重建后旧资源封装与新二进制签名不一致的问题。

### REAPER 导入回归与修复范围（本地，待合入 v1.0.1）

**跨平台共用**：每次导入使用唯一请求编号；只有匹配编号的宿主回执、实际工程路径和有效导入数量才确认成功。回执经临时文件发布，旧回执不能冒充新操作完成；失败会显示原因。导入期间禁用按钮，防止重复点击。Windows 保留原有 `-nonewinst` 调用路径，尚未在 Windows 实机复测。

**Mac 专属**：旧命令行导入曾启动第二个 REAPER，文件没有出现在插件所在工程。现在通过 REAPER 的 VST3 宿主 API，在所属实例的主线程执行导入；接口引用保持到插件释放，工程父对象在使用时读取，避免初始化期间父对象尚未分配。若当前工程不属于该插件，明确报错，不额外启动宿主。

REAPER 7.82 实机回归使用先前真实 MIDI-LLM 的 24 音符文件，另在插件界面通过 Qwen 原生工具调用新做量化：24 音符的音高、力度及通道保留，17 个起音改变。50 PPQ 的文件在十六分网格上有最多 0.01 拍的存储舍入误差。手动导入、自动导入、快速重复点击只新增一条轨道、宿主 Undo 只撤销本次轨道、保存后正常退出和重开均通过；导入回执核对到独立测试工程，原 12 轨测试工程保留。Apple DLSMusicDevice 钢琴实际播放经插件录音得到有效音频，已保存约 6.82 秒试听及 53 帧、约 6.13 秒的真实窗口采样视频。此次回归没有冒充重新运行 MIDI-LLM。

导入请求现各自保存命令、脚本和回执，避免不同插件实例覆盖命令或被旧面板领取。尚未执行的请求在工程切换导致拒绝执行、或编辑器提前关闭时会丢弃；已经有执行回执的请求保留事实，不误报取消。12 个并发准备请求及单请求丢弃由单元测试核对；真实 REAPER 又分别导入此前模型的 24 音符与 16 音符文件，两个请求和实际轨道事件完全对应。通过真实历史先退到 15 轨、再恢复 14 轨，已有轨道 GUID 和 MIDI 源块均不变。Mac 临时导入动作执行后从动作列表移除，已实测无新增残留。GUI 中请求进行期间恰好切换工程或关闭编辑器的时序仍未复现，不将单元测试当作该宿主场景通过。

同一批构建的两个 AU 重新通过严格签名、`auval` 和 Logic 12.4 实际载入；MIDI AU 重新捕获 24 个真实轨道音符，Audio AU 实际录到电钢琴音频。测试集共 91 项通过。导入回执的工程校验不等于聊天上下文、记忆或历史已按工程隔离；这些项目及原生拖出落轨仍待验证，最终合并后还须复测。

**跨平台空闲状态修复**：CPU 配置也可能进入通用空闲分支，旧提示却声称 GPU 模型已释放。现仅报告“服务已就绪”，不以旧 shutdown 标记冒充设备和进程退出的证据。新增空闲状态及重开保护回归；在 Logic 的真实 AU 中使用不含密钥的独立 CPU 配置，将测试超时缩短为五秒，实际关闭/重开编辑器触发并验证该分支。正式配置未改动，原配置后端自动重启及重连通过。原生拖出 MIDI 再次尝试仍未确认落轨，继续列为未验证。

另修复空闲线程与新请求之间的状态竞争：空闲检查和状态发布现处于同一临界区，避免旧线程覆盖新请求的完成状态。并发回归先在旧实现复现失败，再验证修复；真实 Logic AU 另验证隔离 CPU 配置下的请求完成、关闭后进入空闲及重开后再次请求。精确线程竞争由单元测试控制，不将顺序 GUI 操作称为该竞争时序已在宿主复现。

## 下载与安装

- [Windows x64 安装程序（EXE）](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Windows-x64-Setup.exe)
- [发布说明、校验文件与可用附件](https://github.com/Aolin-MIR/triceratops-music-agent/releases/tag/v0.9.0)
- [macOS Apple Silicon 下载（ZIP）](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-macOS-AppleSilicon.zip)：需要 **Apple Silicon、macOS 14+、原生 ARM64 Python 3.10 / 3.11**。解压后保留目录，在终端执行 `bash setup-macos.sh`。VST3 universal 构建已通过。Intel Mac 模型后端不受支持。

1. 保存工程并关闭 REAPER，运行 EXE。VST3 安装到 `C:\Program Files\Common Files\VST3\Triceratops.vst3`。
2. 安装结束打开 **Configure runtime and download models**。选择 REAPER 路径、模型目录、计算设备，输入自己的 API key。Windows 原生 Python 随包提供，不修改系统 Python。
3. 首次配置联网安装依赖并下载模型。默认使用清华 PyPI 镜像和 `hf-mirror.com`；下载失败会明确报错，可重新运行配置继续下载。不会换用其他模型冒充成功。
4. 校验通过后，在 REAPER 的 **Preferences → Plug-ins → VST → Re-scan** 中扫描，插入 **Triceratops**。
5. 更新配置或补下模型：从开始菜单再次打开配置程序。卸载插件保留用户模型、API 配置和生成结果，便于自行备份或清理。

安装包包含插件、配置程序和 Python 基础运行环境；**大模型文件由配置程序另行下载，不内嵌到 EXE**。CPU 为默认选项。所选计算设备不可用时明确报错，不会静默更换设备。

插件顶部提供 **中文 / English** 切换，按钮、状态、提示和操作结果支持双语，并记住语言选择。聊天默认跟随当前界面语言。

## 系统要求

### 按硬件选择模型部署

安装器会读取系统架构和统一内存，按每个模型的实测能力分别选择设备：8 GB Apple Silicon 默认使用 MIDI-LLM CPU/float16、MIDI-GPT CPU、HTDemucs/Basic Pitch CPU，并继续使用远程 Qwen；更大内存的 Apple Silicon 可为 MIDI-GPT 单独选择 MPS。MIDI-LLM 不会因为 MPS 可用就自动切换，避免把本机实测的超慢或失败路径当作 GPU 成功。Windows 1.0 若已验证本地 Qwen 4B 的 OpenAI 兼容服务，可在 `runtime.json` 设置 `local_chat_available: true`、`local_chat_base_url` 和 `local_chat_model`，由策略切换到本地聊天服务。

用户可以使用 `model_policy: "custom"`，分别设置 `midi_llm_device`、`midi_llm_dtype`、`midi_gpt_device`、`audio_device` 和 `chat_deployment`。显式设备不可用时 doctor 会报错，不会静默换成另一设备；本地 Qwen 服务必须由用户先启动并提供 OpenAI 兼容地址。

以下区分**软件限制、建议资源预算和实测环境**；尚未在不同内存容量的电脑上测出“全功能最低配置”。建议值不是已验证的最低门槛。

| 项目 | Windows | macOS |
| --- | --- | --- |
| 系统 / 架构 | Windows 10 / 11 x64；已实测 Windows 11，Windows 10 尚未单独验证 | Apple Silicon（M1 或更新）、macOS 14+；不支持 Intel Mac 模型运行 |
| 宿主 | REAPER x64；已实测 7.80，建议 7.80 或更新版本 | 原生 Apple Silicon REAPER，建议 7.80 或更新版本；完整实机测试待完成 |
| Python | 安装包自带独立 Python 3.11.9，无需 WSL | 自行安装原生 ARM64 Python 3.10 / 3.11；脚本默认查找 `python3.11` |
| 内存预算 | CPU 模式建议 16 GB 起，32 GB 更适合同时打开音源 / 较长音频；不是实测最低值 | 统一内存建议 16 GB 起、32 GB 更宽裕；8 GB A18 Pro 已开始实测，默认 CPU/float32 MIDI-LLM 发生严重资源压力和超时，未通过全功能验收 |
| 图形设备 | CPU 模式不要求独显；当前 CUDA 路径使用 BF16，建议支持 BF16 的 Ampere 或更新 NVIDIA GPU，16 GB 显存作为保守预算 | 自动策略按模型选择设备：本机 8 GB 默认 CPU；MIDI-GPT 的 MPS 已单独实测，更大内存的 Apple Silicon 可能启用它；其余模型加速仍待验证，未验证 MLX |
| 可用空间预算 | CPU 安装预留 20 GB；CUDA 安装预留 30 GB，并为下载缓存、音频和工程另留空间 | 预留 20 GB，并为下载缓存、音频和工程另留空间 |
| 网络 / API | 首次依赖和模型下载需要联网；当前聊天和按钮工具调度需要自配支持原生工具调用的 API | 同左；Mac 包不附带 Python，也不附带模型权重 |

空间和内存数字是保守的安装 / 运行建议，尚未测定所有功能的峰值。模型文件约 4 GB，不等于安装总大小或运行内存。CPU 生成属于离线任务，不能保证实时速度。CUDA 还需要能运行安装器所选 `cu130` PyTorch 的 NVIDIA 驱动；`nvidia-smi` 显示的 CUDA 版本不能单独证明兼容。AMD / Intel GPU、Windows ARM64、Intel Mac 不在当前支持范围内。

完整说明、已验证环境、各功能的资源差异和判断依据见 **[系统配置与支持范围（中英双语）](docs/SYSTEM_REQUIREMENTS.md)**。

## 可以做什么

| 操作 | 实际实现 |
| --- | --- |
| 自然语言聊天 / New score | 原生工具调用循环、意图整理，MIDI-LLM 文本生成多乐器 MIDI |
| Edit MIDI / More energy / Tighten timing | 转调、力度、量化等明确的 MIDI 修改，保留可编辑音符 |
| Continue 4 bars / 指定小节填充 | MIDI-GPT 生成新的内容；续写保留原文件事件后追加小节 |
| Analyze | MIDI 音符、节奏统计；音频速度、调性估计、起音与分段分析 |
| Stem split | Demucs HTDemucs 四分轨：人声、鼓、贝斯、其他 |
| Audio → MIDI | Basic Pitch ONNX 音频转 MIDI |
| Rec MIDI / Rec audio | 录制进入插件的 MIDI / 音频；从宿主路由输入 |
| Import to REAPER / Auto-Import | 导入 MIDI 或分轨音频到 REAPER 新轨道；可关闭自动导入 |
| Keep / Reject / Undo | 反馈偏好、恢复上一 MIDI 版本；不删除已经导入的宿主轨道 |
| 记忆 / RAG | 工程约束、偏好与对话摘要持久化；检索项目笔记及本地知识文件 |

例如：“阴天傍晚的钢琴和大提琴，别太满。”、“接着这段再写四小节。”、“节奏收紧一点，旋律不要变。” 不要求用户写 JSON 或严格模板。具体编辑能力以工具支持的操作为准。

MIDI 是演奏数据，需要在 REAPER 的后续轨道/插件中加载音源才能发声。分轨和转写有模型误差；音频调性为估计结果。

## 模型与许可

| 模型 | 下载来源 / 用途 | 许可 |
| --- | --- | --- |
| [MIDI-LLM](https://huggingface.co/slseanwu/MIDI-LLM_Llama-3.2-1B) | 约 3.45 GB，文本生成 MIDI；固定 revision | Llama 3.2 Community License；Built with Llama |
| [MIDI-GPT Yellow Medium](https://huggingface.co/Metacreation/MIDI-GPT) | 约 351 MB，续写 / 填充；固定 revision | 权重 CC BY-NC 4.0，非商业使用 |
| [HTDemucs](https://huggingface.co/adefossez/HTDemucs) | 音频四分轨 | 见模型及 Demucs 上游许可 |
| [Basic Pitch](https://github.com/spotify/basic-pitch) | ONNX 模型随依赖包安装 | Apache 2.0 |

下载器核对 MIDI-LLM、MIDI-GPT、HTDemucs 和解码器资源的 SHA-256；Basic Pitch ONNX 权重也会校验。模型来源、版本和校验值见 [`download_models.py`](text2music/agent/download_models.py)。代码开源不代表所有模型权重具有同一许可；尤其 MIDI-GPT 权重有非商业限制。完整第三方说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 数据与配置

Windows 配置：`%APPDATA%\Triceratops\runtime.json`；模型与专用 Python：`%LOCALAPPDATA%\Triceratops\`；结果和记忆：`%APPDATA%\Triceratops\runs\`。密钥只保存在本机用户配置中，不随插件、发布包或生成结果上传。调用聊天 API 时会发送对话和必要的工程/分析上下文，API 提供方可能按用量收费。服务只监听 `127.0.0.1:49327`。

## 试用反馈

请到 [Issues](https://github.com/Aolin-MIR/triceratops-music-agent/issues) 提交系统版本、REAPER 版本、CPU/GPU、操作步骤、预期与实际结果。不要上传 API key 或含私密素材的完整配置。欢迎分享一小段可复现 MIDI 或音频。

## 致谢

v0.9 实际调用的音乐模型与工具：

- [MIDI-LLM / Shih-Lun Wu 等](https://github.com/slSeanWU/MIDI-LLM)：自然语言生成多乐器 MIDI；基于 Llama 3.2 并扩展音乐词表，Built with Llama。
- [MIDI-GPT / Metacreation Lab](https://github.com/Metacreation/MIDI-GPT)：使用 **Yellow Medium** 权重进行续写与填充；保留 CC BY-NC 4.0 限制。
- [HTDemucs / Alexandre Défossez 等](https://github.com/facebookresearch/demucs)：人声、鼓、贝斯和其他声部的四分轨。
- [Basic Pitch / Spotify](https://github.com/spotify/basic-pitch)：使用 ICASSP 2022 ONNX 模型转写 MIDI。
- [Anticipation / John Thickstun 等](https://github.com/jthickstun/anticipation)：MIDI-LLM 使用的音乐事件转换 / 解码工具；[JUCE](https://github.com/juce-framework/JUCE) 提供 VST3 框架；[librosa](https://github.com/librosa/librosa) 提供音频分析算法。

聊天模型由用户的 API 配置决定，发行包不附带聊天模型权重。未接入的候选模型不列入上述使用致谢。

代码来源：本仓库起源于 [Keshav Bhandari 的 Text2Score](https://github.com/keshavbhandari/text2score)，因此保留源代码归属说明；**v0.9 发行版不安装、不下载、不调用 Text2Score 训练权重**。Triceratops 的 Agent、REAPER 集成及桌面发行工作在此仓库维护。完整归属及许可见 [NOTICE](NOTICE) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
