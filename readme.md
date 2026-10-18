# Triceratops Music Agent

[中文](readme.md) | [English](README.en.md)

**把脑海里的几小节，留在 REAPER 的工程里。**

Triceratops 是一款面向 REAPER 的音乐 Agent VST3。用日常语言描述音乐想法，或点击插件里的操作按钮，生成、续写、编辑和分析 MIDI，并把结果导入 REAPER 轨道。

它能理解宽泛的风格、情绪和画面描述，也支持具体的音乐要求。插件会尽量保留你的原意，再交给音乐模型生成 MIDI。你可以和 Agent 闲聊、询问功能，也可以随时从操作按钮开始工作。

[![Triceratops 功能一览](docs/images/triceratops-0.9-overview.webp)](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Feature-Overview.png)

## 插件能做什么

| 功能 | 用途 |
| --- | --- |
| 聊天与新建音乐 | 用中文或英文描述风格、情绪、乐器、节奏和结构，生成文本引导的多乐器 MIDI |
| MIDI 编辑 | 转调、调整力度、收紧节奏等；保留可编辑音符 |
| 续写与填充 | 延续已有 MIDI，或为指定小节生成新内容 |
| 分析 | 查看 MIDI 音符与节奏信息，分析音频速度、调性、起音和段落 |
| 音频分轨 | 分离人声、鼓、贝斯和其他声部 |
| 音频转 MIDI | 从音频提取音符并生成 MIDI |
| 录制与导入 | 录制送入插件的 MIDI / 音频，并将 MIDI 或分轨结果导入 REAPER 新轨道 |
| 反馈与记忆 | 保留项目偏好与对话摘要，检索项目笔记和本地知识；可保留、拒绝或撤销生成结果 |

例如，你可以说：“阴天傍晚的钢琴和大提琴，留一些空白”；“接着这段再写四小节”；“节奏收紧一点，旋律不要变”。不需要 JSON 或固定提示词格式。**功能**按钮也可以直接打开可用操作。

## 1.0 新功能

1.0 将聊天、模型和设备设置放进插件内。Windows 可在本地 GPU 上运行聊天模型，不需要 WSL；也可以选择兼容的云端工具调用 API。若只使用分析、分轨、转写、续写等明确操作，可以直接点击按钮，无需聊天 API。

模型下载会根据网络出口选择官方源或中国镜像，也可手动选择来源。聊天模型和音乐模型可以分别设置计算设备；插件会根据模型资源需求提供设备建议。

## 下载与安装

当前公开下载为 **v0.9.0**。下方入口提供 Windows 安装程序、macOS Apple Silicon 压缩包及发布说明。

- [Windows x64 安装程序（EXE）](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-Windows-x64-Setup.exe)
- [macOS Apple Silicon 下载（ZIP）](https://github.com/Aolin-MIR/triceratops-music-agent/releases/download/v0.9.0/Triceratops-0.9.0-macOS-AppleSilicon.zip)
- [v0.9.0 发布说明与全部附件](https://github.com/Aolin-MIR/triceratops-music-agent/releases/tag/v0.9.0)

Windows：运行 EXE，按配置程序提示选择 REAPER 路径、模型目录和计算设备，然后在 REAPER 中重新扫描 VST 并插入 Triceratops。插件使用随安装包提供的独立 Python 环境；模型权重由配置程序下载。

macOS：需要 Apple Silicon、macOS 14 或更新版本，以及原生 ARM64 Python 3.10 或 3.11。解压后保留文件夹，在终端运行 `bash setup-macos.sh`。

插件仅支持 REAPER。Windows 使用原生后端，无需 WSL。插件顶部的 **中文 / English** 按钮可切换界面语言；按钮、状态和操作结果均支持双语。

## 运行方式

- **云端聊天**：在插件中填写兼容工具调用的 API 地址、模型和密钥，用于闲聊、意图整理和开放式音乐描述。
- **Windows 本地聊天**：使用插件设置下载并运行本地模型，推理通过 llama.cpp GPU 后端完成，无需云端密钥。
- **直接操作**：分析、MIDI 编辑、续写、分轨和转写等按钮直接调用本地工具，不需要聊天 API。

本地聊天模型、MIDI-LLM、MIDI-GPT 和 HTDemucs 可分别配置计算设备。插件设置提供资源检测和设备建议；不需要在不同任务之间卸载或切换模型设备。

## 系统要求

| 平台 | 支持要求 |
| --- | --- |
| Windows | Windows 10 / 11 x64、REAPER x64；安装包提供独立 Python 环境。聊天模型使用本地 GPU 时需要兼容的 NVIDIA GPU；音乐功能可按模型设置使用 CPU 或 GPU。 |
| macOS | Apple Silicon、macOS 14 或更新版本、原生 Apple Silicon 版 REAPER、ARM64 Python 3.10 / 3.11。 |

首次设置需要联网下载运行依赖和模型。详细的平台配置与资源说明见[系统要求](docs/SYSTEM_REQUIREMENTS.md)。

## 使用的模型

| 模型 | 功能 | 许可 |
| --- | --- | --- |
| [MIDI-LLM](https://huggingface.co/slseanwu/MIDI-LLM_Llama-3.2-1B) | 文本生成多乐器 MIDI | Llama 3.2 Community License |
| [MIDI-GPT Yellow Medium](https://huggingface.co/Metacreation/MIDI-GPT) | MIDI 续写与填充 | CC BY-NC 4.0，非商业使用 |
| [HTDemucs](https://huggingface.co/adefossez/HTDemucs) | 音频四分轨 | 见模型及上游许可 |
| [Basic Pitch](https://github.com/spotify/basic-pitch) | 音频转 MIDI | Apache 2.0 |

模型版本和第三方许可见 [`download_models.py`](text2music/agent/download_models.py) 与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 数据与致谢

模型和生成结果保存在本机。选择云端聊天时，对话及完成任务所需的工程上下文会发送给你配置的 API 提供方。API 密钥保存在本机用户配置中。

感谢 [MIDI-LLM](https://github.com/slSeanWU/MIDI-LLM)、[MIDI-GPT](https://github.com/Metacreation/MIDI-GPT)、[Demucs](https://github.com/facebookresearch/demucs)、[Basic Pitch](https://github.com/spotify/basic-pitch)、[Anticipation](https://github.com/jthickstun/anticipation)、[JUCE](https://github.com/juce-framework/JUCE) 和 [librosa](https://github.com/librosa/librosa)。本仓库源自 [Text2Score](https://github.com/keshavbhandari/text2score)，完整归属与许可见 [NOTICE](NOTICE)。

反馈与问题请提交到 [GitHub Issues](https://github.com/Aolin-MIR/triceratops-music-agent/issues)。
