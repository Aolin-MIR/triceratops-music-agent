# Triceratops Music Agent

[中文](readme.md) | [English](README.en.md)

**把脑海里的几小节，留在 REAPER 的工程里。**

Triceratops 是 REAPER 中的音乐 Agent VST3。用自然语言描述想法，或点击操作按钮，让它调用本地模型生成、续写、编辑和分析 MIDI，再把可编辑结果导入真实轨道。

**仅支持 REAPER。Windows 使用原生 Python 后端，不需要 WSL。** 聊天及意图改写可选择兼容的云端工具调用 API，或在 Windows 上用 llama.cpp 以 GPU 运行本地模型；本地聊天不回退到 CPU。分析、量化、力度、续写、分轨、转写等明确按钮直接调用本地工具，无需聊天 API。

[![Triceratops 0.9 功能一览](docs/images/triceratops-0.9-overview.webp)](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Feature-Overview.png)

## 本次更新 · 1.0 整合

当前检查：本地 Qwen3.5 4B 在 Windows 原生 llama.cpp/Vulkan 后端完成 21 项真实聊天与工具流程测试，21/21 通过；验证了原生工具调用、工具结果回传，以及测试前后模型都驻留在 RTX 3080 Laptop GPU 上。启动日志确认 33/33 层卸载至 GPU。另有 51 项针对配置、聊天与 MIDI 工具的单元测试通过。该结果验证当前本地模型测试范围，不代表所有 API、电脑或音乐模型组合均已验证。

本次源码更新面向 **1.0 整合**；下方下载链接仍指向现有 **v0.9 安装包**，不包含尚未重新打包的 1.0 改动。Mac 实机验证仍待完成，1.0 安装包尚未发布。

- **本地聊天接入**：Windows 使用 llama.cpp Vulkan GPU 推理，支持原生工具调用与工具结果回传；云端 API 可单独选择。所选模型必须通过兼容性检查，并非所有 API 或本地模型都兼容。
- **操作按钮直接执行**：分析、续写四小节、增加力度、收紧节奏、分轨、音频转 MIDI、撤销和反馈不经过聊天模型；关闭聊天也能运行这些操作。
- **固定计算设备**：本地 LLM 明确选择 CPU / GPU 并常驻，拒绝 GPU 模式自动分担到 CPU；MIDI-LLM、MIDI-GPT 和 HTDemucs 可分别设置设备，不在任务之间自动迁移。
- **模型来源分流**：下载器以公网出口 IP 的国家码选择源。中国大陆优先检查 `hf-mirror.com` 的固定版本；只有镜像确实提供该版本且未重定向到海外时才使用。镜像不可用会说明原因并选择官方源，其他地区使用官方源；支持手选 `official` / `china`。定位失败会显示原因并使用官方源，不能定位时不按系统语言猜测。版本固定，音乐模型权重核对 SHA-256。本地聊天模型通过 Ollama registry 下载，推理由 llama.cpp GPU 后端执行。分流只影响模型，不修改 API 地址或软件依赖来源。
- **资源规划器**：按可用内存、显存与模型预算计算设备建议；轻量音乐功能优先 CPU。设备规划与插件内设置页均已接入，已实际检查检测、验证保存与取消保留原设置。设置面板复用现有界面的配色和字体。云端基线和本地 GPU 聊天均通过真实工具流程检查；模型在其它硬件上的质量、速度与 API 替代程度仍需单独评估。

Windows 原生 CPU 实测（Ryzen 9 5900HX，当前可见内存 27.9 GiB）：

| 任务 | 测试条件 | 耗时 |
| --- | --- | --- |
| MIDI-GPT 续写 | 12 音符输入，新增 4 小节 | 首次约 11.2 秒；重复约 3.7 秒 |
| HTDemucs 四分轨 | 12 秒音频 | 约 19.9 秒 |
| Basic Pitch 转写 | 短小号素材 | 约 13.2 秒 |
| 音频分析 | 12 秒音频，含首次导入 | 约 19.2 秒 |
| MIDI-LLM 生成 | 默认上限 768 新 token，含加载 | 约 247 秒 |

这些是指定素材和电脑上的离线测试，不是所有用户的速度保证；CPU 完整生成较慢，设备规划会优先考虑把 MIDI-LLM 放到有足够预算的 GPU。Mac 实机结果由 Mac 端合并后补充。

## 下载与安装

- [Windows x64 安装程序（EXE）](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Windows-x64-Setup.exe)
- [发布说明、校验文件与可用附件](https://github.com/Aolin-MIR/triceratops-music-agent/releases/tag/v0.9.0)
- [macOS Apple Silicon 下载（ZIP）](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-macOS-AppleSilicon.zip)：需要 **Apple Silicon、macOS 14+、原生 ARM64 Python 3.10 / 3.11**。解压后保留目录，在终端执行 `bash setup-macos.sh`。VST3 universal 构建已通过。Intel Mac 模型后端不受支持。

1. 保存工程并关闭 REAPER，运行 EXE。VST3 安装到 `C:\Program Files\Common Files\VST3\Triceratops.vst3`。
2. 安装结束打开 **Configure runtime and download models**。选择 REAPER 路径、模型目录、计算设备并填写云端 API。此步骤描述已发布的 v0.9 配置程序；新增的本地聊天和直接按钮模式在 1.0 中配置。Windows 原生 Python 随包提供，不修改系统 Python。
3. 首次配置联网安装依赖并下载模型。现有 v0.9 安装包默认使用清华 PyPI 镜像和 `hf-mirror.com`；主分支模型下载器已改为按公网 IP 分流；下载失败会明确报错，可重新运行配置继续下载。不会换用其他模型冒充成功。
4. 校验通过后，在 REAPER 的 **Preferences → Plug-ins → VST → Re-scan** 中扫描，插入 **Triceratops**。
5. 更新配置或补下模型：从开始菜单再次打开配置程序。卸载插件保留用户模型、API 配置和生成结果，便于自行备份或清理。

现有 v0.9 安装包包含插件、配置程序和 Python 基础运行环境；**大模型文件由配置程序另行下载，不内嵌到 EXE**。CPU 为默认选项。所选计算设备不可用时明确报错，不会静默更换设备。

1.0 的配置入口已移至插件右上角 **设置**：检测资源、选择聊天方式与模型来源、下载并配置、验证并应用、取消配置都在插件中完成。Windows 1.0 安装器会提供 Ollama 下载工具与 llama.cpp Vulkan 推理程序；聊天模型权重仍由设置页下载。1.0 安装包尚未正式发布。

插件顶部提供 **中文 / English** 切换，按钮、状态、提示和操作结果支持双语，并记住语言选择。聊天默认跟随当前界面语言。

## 系统要求

以下区分**软件限制、建议资源预算和实测环境**；尚未在不同内存容量的电脑上测出“全功能最低配置”。建议值不是已验证的最低门槛。

| 项目 | Windows | macOS |
| --- | --- | --- |
| 系统 / 架构 | Windows 10 / 11 x64；已实测 Windows 11，Windows 10 尚未单独验证 | Apple Silicon（M1 或更新）、macOS 14+；不支持 Intel Mac 模型运行 |
| 宿主 | REAPER x64；已实测 7.80，建议 7.80 或更新版本 | 原生 Apple Silicon REAPER，建议 7.80 或更新版本；完整实机测试待完成 |
| Python | 安装包自带独立 Python 3.11.9，无需 WSL | 自行安装原生 ARM64 Python 3.10 / 3.11；脚本默认查找 `python3.11` |
| 内存预算 | CPU 模式建议 16 GB 起，32 GB 更适合同时打开音源 / 较长音频；不是实测最低值 | 统一内存建议 16 GB 起、32 GB 更宽裕；8 GB 不列为全功能建议配置，尚无 Mac 实测数据 |
| 图形设备 | CPU 模式不要求独显；当前 CUDA 路径使用 BF16，建议支持 BF16 的 Ampere 或更新 NVIDIA GPU，16 GB 显存作为保守预算 | 当前安装脚本选择 CPU；不要求独显，也没有已验证的 MPS / MLX 加速支持 |
| 可用空间预算 | CPU 安装预留 20 GB；CUDA 安装预留 30 GB，并为下载缓存、音频和工程另留空间 | 预留 20 GB，并为下载缓存、音频和工程另留空间 |
| 网络 / API | 首次依赖和模型下载需要联网；自由聊天需选择已兼容的云端 API 或 Windows 本地 GPU 模型；明确按钮无需 API | 同左；Mac 包不附带 Python，也不附带模型权重，Mac 本地聊天后端待实测 |

空间和内存数字是保守的安装 / 运行建议，尚未测定所有功能的峰值。音乐模型文件约 4 GB；默认本地聊天模型另需约 3.32 GB。它们不等于安装总大小或运行内存。CPU 生成属于离线任务，不能保证实时速度。CUDA 还需要能运行安装器所选 `cu130` PyTorch 的 NVIDIA 驱动；`nvidia-smi` 显示的 CUDA 版本不能单独证明兼容。AMD / Intel GPU、Windows ARM64、Intel Mac 不在当前支持范围内。

完整说明、已验证环境、各功能的资源差异和判断依据见 **[系统配置与支持范围（中英双语）](docs/SYSTEM_REQUIREMENTS.md)**。

## 聊天模式与固定设备

- **remote**：使用用户配置的 API 地址、模型和密钥。配置时实际检查原生工具调用与工具结果回传，不承诺所有“兼容 API”都正常。
- **Windows 本地 GPU 聊天**：在插件设置里选择本地聊天和 `qwen3.5:4b-q4_K_M`。安装包中的 Ollama 工具负责下载模型，推理由 llama.cpp Vulkan 在 GPU 上运行；必须通过 GPU 驻留检查，CPU 推理不会作为回退。不需要云端密钥。
- **disabled**：关闭自由聊天，明确操作按钮照常使用。新建音乐和开放式编辑描述需要启用语言模型。

本地 LLM 明确选择 **CPU / GPU** 并保持常驻，不在任务之间卸载或自动换设备。GPU 模式会检查实际驻留，拒绝自动分担到 CPU。MIDI-LLM、MIDI-GPT、HTDemucs 分别设置固定设备；新配置优先把 MIDI-GPT 和分轨放在 CPU。Basic Pitch ONNX 和音频分析使用 CPU。GPU 显存或系统内存不足时明确报错，需要用户修改配置。

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

1.0 下载器核对 MIDI-LLM、MIDI-GPT 与 HTDemucs 权重的 SHA-256。模型来源、版本和校验值见 [`download_models.py`](text2music/agent/download_models.py)。代码开源不代表所有模型权重具有同一许可；尤其 MIDI-GPT 权重有非商业限制。完整第三方说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 数据与配置

Windows 配置：`%APPDATA%\Triceratops\runtime.json`；模型与专用 Python：`%LOCALAPPDATA%\Triceratops\`；结果和记忆：`%APPDATA%\Triceratops\runs\`。密钥只保存在本机用户配置中，不随插件、发布包或生成结果上传。选择云端模式时会发送对话和必要的工程/分析上下文，API 提供方可能按用量收费。模型自动选源会向 IP 地理位置服务发起请求，只保留国家码和查询时间，不保存公网 IP、城市或精确位置；使用代理/VPN 时观察到的是实际出口。可手选来源跳过查询。服务只监听 `127.0.0.1:49327`。

## 试用反馈

请到 [Issues](https://github.com/Aolin-MIR/triceratops-music-agent/issues) 提交系统版本、REAPER 版本、CPU/GPU、操作步骤、预期与实际结果。不要上传 API key 或含私密素材的完整配置。欢迎分享一小段可复现 MIDI 或音频。

## 致谢

v0.9 实际调用的音乐模型与工具：

- [MIDI-LLM / Shih-Lun Wu 等](https://github.com/slSeanWU/MIDI-LLM)：自然语言生成多乐器 MIDI；基于 Llama 3.2 并扩展音乐词表，Built with Llama。
- [MIDI-GPT / Metacreation Lab](https://github.com/Metacreation/MIDI-GPT)：使用 **Yellow Medium** 权重进行续写与填充；保留 CC BY-NC 4.0 限制。
- [HTDemucs / Alexandre Défossez 等](https://github.com/facebookresearch/demucs)：人声、鼓、贝斯和其他声部的四分轨。
- [Basic Pitch / Spotify](https://github.com/spotify/basic-pitch)：使用 ICASSP 2022 ONNX 模型转写 MIDI。
- [Anticipation / John Thickstun 等](https://github.com/jthickstun/anticipation)：MIDI-LLM 使用的音乐事件转换 / 解码工具；[JUCE](https://github.com/juce-framework/JUCE) 提供 VST3 框架；[librosa](https://github.com/librosa/librosa) 提供音频分析算法。

聊天可选用户配置的云端模型或经兼容性检查的本地 Qwen3.5 模型；Windows 本地推理由 llama.cpp Vulkan GPU 后端执行，发行包不附带聊天模型权重。未接入的候选模型不列入上述使用致谢。

代码来源：本仓库起源于 [Keshav Bhandari 的 Text2Score](https://github.com/keshavbhandari/text2score)，因此保留源代码归属说明；**v0.9 发行版不安装、不下载、不调用 Text2Score 训练权重**。Triceratops 的 Agent、REAPER 集成及桌面发行工作在此仓库维护。完整归属及许可见 [NOTICE](NOTICE) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
