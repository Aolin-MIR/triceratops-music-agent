# Triceratops Music Agent

Triceratops 是一个面向 REAPER 的本地音乐 Agent 插件。你可以直接用自然语言描述音乐，也可以点击常用操作按钮；Agent 会理解意图、选择工具、调用本地模型，并把可继续编辑的 MIDI 送回 DAW。

它的目标不是导出一段无法修改的音频，而是让音乐生成参与真实工程：生成、修改、续写、分析、撤销和反馈都发生在 REAPER 的轨道和插件窗口里。

## 真实工作流

```text
宽泛描述 → 意图识别与改写 → Agent 工具循环 → 本地 MIDI 模型
       → 可编辑 MIDI 进入 REAPER → Keep / Reject / Undo → 记忆与偏好反馈
```

例如输入：

> 阴天傍晚的钢琴和大提琴，别太满，像一段没说完的话。

Agent 会将它整理成乐器、密度、情绪、调性、速度和结构约束，再调用 MIDI-LLM 生成 MIDI。实际演示中生成了 341 个音符，并成功出现在 REAPER 的 MIDI 轨道上。

## 已实现能力

- 自然语言聊天，支持宽泛输入和意图改写
- 新建乐段、编辑选中 MIDI、续写 4 小节
- 增强能量、收紧节奏、分析当前工程
- 音频转 MIDI、Stem 分离、MIDI/音频录制
- 工具调用循环与任务状态反馈
- 对话记忆、偏好反馈、版本记录和工程上下文检索（RAG）
- MIDI-LLM / MIDI-GPT 本地后端，可扩展更多符号音乐模型
- Keep / Reject / Undo，生成结果可回到宿主继续工作
- REAPER 轨道、选区、节拍、文件和 MIDI 桥接
- 原生 Windows MSVC VST3 构建；官方 VST3 Validator 47/47 通过

## 项目结构

```text
text2music/agent/       Agent、意图分类、工具循环、记忆和 REAPER bridge
text2music/             MIDI 生成、编辑、分析与数据处理
vst3/Source/             JUCE VST3 插件界面和音频/MIDI 处理
vst3/CMakeLists.txt      Windows / WSL 构建配置
tests/                   Agent、MIDI、工具和桥接测试
marketing/xiaohongshu/  真实 REAPER 演示、视频和发布素材
```

## 环境要求

- Windows 10/11
- REAPER 7.x
- WSL2（用于本地 Agent 和模型运行）
- Visual Studio 2022 + CMake（用于原生 Windows VST3）
- Python 3.10+
- 可选 NVIDIA GPU；没有 GPU 时仍可使用轻量后端和宿主桥接

## 安装 Agent

```bash
git clone https://github.com/Aolin-MIR/triceratops-music-agent.git
cd triceratops-music-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m text2music.agent.app
```

如果使用 Qwen 等远程规划器，把密钥放在 WSL 环境变量中，不要写入仓库：

```bash
export QWEN_API_KEY="your-key"
```

生成结果默认写入 `text2music/artifacts/agent_runs/`。Agent 的核心工具循环也可以由 REAPER bridge 直接调用，不需要浏览器。

## 构建 VST3 插件

在 Windows PowerShell 中：

```powershell
cmake -S vst3 -B vst3/build-msvc -G "Visual Studio 17 2022" -A x64
cmake --build vst3/build-msvc --config Release --target Triceratops_VST3
```

构建产物位于 `vst3/build-msvc/Triceratops_artefacts/Release/VST3/Triceratops.vst3`。把它复制到用户 VST3 目录后，在 REAPER 中执行 **Options → Preferences → Plug-ins → VST → Re-scan**。

## REAPER 使用方式

1. 在 REAPER 中加载 `Triceratops` VST3。
2. 直接输入自然语言，或点击 **New score / Edit MIDI / Continue 4 bars / Analyze / Audio → MIDI / Stem split** 等按钮。
3. 等待 Agent 完成工具调用和本地模型生成。
4. 生成的 MIDI 会进入当前工程，可继续编辑、换音色、续写或撤销。
5. 使用 **Keep / Reject / Undo** 记录反馈，后续任务会读取这些偏好。

## 测试与验证

```bash
pytest -q
```

VST3 使用 Steinberg 官方 validator 验证。当前原生 MSVC 构建已通过 47/47 项检查，包括总线、参数、程序列表、状态转换、MIDI 映射和处理线程测试。

## 演示素材

真实 REAPER 插件窗口、MIDI 轨道截图、36 秒竖屏演示视频和小红书文案位于 [`marketing/xiaohongshu/`](marketing/xiaohongshu/)。

## 当前边界

大模型权重、GPU 显存和生成速度取决于本机配置；部分音频分析能力需要额外安装对应模型。插件优先保证 MIDI 和工程上下文工作流，不替代完整 DAW 或最终混音工具。

## License

代码和第三方依赖的许可信息见 [`NOTICE`](NOTICE)。
