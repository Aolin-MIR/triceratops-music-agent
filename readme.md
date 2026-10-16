# Triceratops Music Agent · 0.9

[中文](readme.md) | [English](README.en.md)

**把脑海里的几小节，留在 REAPER 的工程里。**

Triceratops 是 REAPER 中的音乐 Agent VST3。用自然语言描述想法，或点击操作按钮，让它调用本地模型生成、续写、编辑和分析 MIDI，再把可编辑结果导入真实轨道。

**v0.9 仅支持 REAPER。Windows 使用原生 Python 后端，不需要 WSL。** 聊天及意图改写通过你配置的 Qwen / OpenAI 兼容 API 完成；MIDI 生成、续写、分轨和转写在本机运行。

[![Triceratops 0.9 功能一览](docs/images/triceratops-0.9-overview.webp)](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Feature-Overview.png)

## 下载与安装

- [Windows x64 安装程序（EXE）](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Windows-x64-Setup.exe)
- [发布说明、校验文件与可用附件](https://github.com/Aolin-MIR/triceratops-music-agent/releases/tag/v0.9.0)
- [macOS Apple Silicon 下载（ZIP）](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-macOS-AppleSilicon.zip)：需要 **Apple Silicon、macOS 14+、原生 ARM64 Python 3.10 / 3.11**。解压后保留目录，在终端执行 `bash setup-macos.sh`。VST3 universal 构建已通过。Intel Mac 模型后端不受支持。

1. 保存工程并关闭 REAPER，运行 EXE。VST3 安装到 `C:\Program Files\Common Files\VST3\Triceratops.vst3`。
2. 安装结束打开 **Configure runtime and download models**。选择 REAPER 路径、模型目录、计算设备，输入自己的 API key。Windows 原生 Python 随包提供，不修改系统 Python。
3. 首次配置联网安装依赖并下载模型。默认使用清华 PyPI 镜像和 `hf-mirror.com`；下载失败会明确报错，可重新运行配置继续下载。不会换用其他模型冒充成功。
4. 校验通过后，在 REAPER 的 **Preferences → Plug-ins → VST → Re-scan** 中扫描，插入 **Triceratops**。
5. 更新配置或补下模型：从开始菜单再次打开配置程序。卸载插件保留用户模型、API 配置和生成结果，便于自行备份或清理。

安装包包含插件、配置程序和 Python 基础运行环境；**大模型文件由配置程序另行下载，不内嵌到 EXE**。首次安装需要网络和约 15 GB 可用空间，模型约 4 GB。CPU 为默认选项，建议至少 16 GB 内存、32 GB 更舒适；生成速度随硬件变化。选择 CUDA 需要 NVIDIA GPU、兼容驱动和 CUDA 版 PyTorch，配置程序会检查，无法使用时明确失败。GPU 不可用时不会自动切换到 CPU。

插件顶部提供 **中文 / English** 切换，按钮、状态、提示和操作结果支持双语，并记住语言选择。聊天默认跟随当前界面语言。

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

下载器核对 MIDI-LLM 与 MIDI-GPT 的 SHA-256。模型来源、版本和校验值见 [`download_models.py`](text2music/agent/download_models.py)。代码开源不代表所有模型权重具有同一许可；尤其 MIDI-GPT 权重有非商业限制。完整第三方说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 数据与配置

Windows 配置：`%APPDATA%\Triceratops\runtime.json`；模型与专用 Python：`%LOCALAPPDATA%\Triceratops\`；结果和记忆：`%APPDATA%\Triceratops\runs\`。密钥只保存在本机用户配置中，不随插件、发布包或生成结果上传。调用聊天 API 时会发送对话和必要的工程/分析上下文，API 提供方可能按用量收费。服务只监听 `127.0.0.1:49327`。

## 试用反馈

请到 [Issues](https://github.com/Aolin-MIR/triceratops-music-agent/issues) 提交系统版本、REAPER 版本、CPU/GPU、操作步骤、预期与实际结果。不要上传 API key 或含私密素材的完整配置。欢迎分享一小段可复现 MIDI 或音频。

## 致谢

项目起源于 [Keshav Bhandari 的 Text2Score](https://github.com/keshavbhandari/text2score)。Triceratops 的 Agent、REAPER 集成及桌面发行工作在此仓库维护。上游研究代码与第三方组件的权利归原作者所有，见 [NOTICE](NOTICE)。
