#include "SettingsPanel.h"

namespace { const juce::Colour bg(0xff161724), ink(0xffc0caf5), muted(0xff7a88cf), line(0xff282a40), blue(0xff7aa2f7); }

juce::String SettingsPanel::tr(const char* en, const char* zh) const { return juce::String::fromUTF8(chinese ? zh : en); }

SettingsPanel::SettingsPanel(BackendClient& client) : backend(client)
{
    addAndMakeVisible(viewport);
    viewport.setViewedComponent(&form, false);
    viewport.setScrollBarsShown(true, false);
    for (auto* label : {&title, &note, &apiStatus})
    {
        addAndMakeVisible(label);
        label->setColour(juce::Label::textColourId, ink);
    }
    title.setFont(juce::FontOptions(21.0f, juce::Font::bold));
    note.setFont(juce::FontOptions(13.0f));
    note.setColour(juce::Label::textColourId, muted);
    addAndMakeVisible(status);
    status.setMultiLine(true);
    status.setReadOnly(true);
    status.setScrollbarsShown(true);
    status.setColour(juce::TextEditor::backgroundColourId, juce::Colour(0xff0f101a));
    status.setColour(juce::TextEditor::textColourId, ink);
    status.setColour(juce::TextEditor::outlineColourId, line);
    status.setFont(juce::FontOptions(13.0f));
    addField("chat_policy", "Conversation", juce::String::fromUTF8("对话方式"), {"auto", "local", "remote", "disabled"}, {"Recommended / hardware checked", "Local GPU", "Cloud service", "Direct buttons only"});
    addField("local_model", "Custom chat model ID", juce::String::fromUTF8("自定义聊天模型标识"));
    addField("llm_context", "Chat context (tokens)", juce::String::fromUTF8("聊天上下文（token）"), {"4096", "8192", "16384"}, {"4096", "8192", "16384"});
    addField("llm_choice", juce::String::fromUTF8("Local chat · 4B / 4-bit*"), juce::String::fromUTF8("本地对话 · 4B / 4-bit*"), {"auto", "gpu"}, {"Recommended / GPU required", "GPU"});
    const char* keys[] = {"midi_llm_choice", "midi_gpt_choice", "stem_choice"};
    const char* namesEn[] = {"Text composition · 3.2 GiB", "Continue / fill · 334 MiB", "Audio stems · 80 MiB"};
    const char* namesZh[] = {"文本作曲 · 3.2 GiB", "续写填充 · 334 MiB", "音频分轨 · 80 MiB"};
    for (int i = 0; i < 3; ++i)
    {
       #if JUCE_MAC
        addField(keys[i], juce::String::fromUTF8(namesEn[i]), juce::String::fromUTF8(namesZh[i]), {"auto", "cpu", "mps"}, {"Recommended / CPU", "CPU", "GPU / explicit test"});
       #else
        addField(keys[i], namesEn[i], juce::String::fromUTF8(namesZh[i]), {"auto", "cpu", "cuda"}, {"Recommended / hardware checked", "CPU", "GPU"});
       #endif
    }
    addField("midi_llm_dtype", "Composition precision", juce::String::fromUTF8("文本作曲精度"), {"auto", "default", "float32", "float16", "bfloat16"}, {"Auto", "Default", "Float32", "Float16", "BFloat16"});
    addField("model_source", "Model downloads", juce::String::fromUTF8("模型下载来源"), {"auto", "official", "china"}, {"Auto / IP country", "Official", "China mirror (if available)"});
    addField("base_url", "API base URL", juce::String::fromUTF8("API 地址"));
    addField("chat_model", "API model", juce::String::fromUTF8("API 模型"));
    addField("api_key", "API key", juce::String::fromUTF8("API 密钥"));
    fields.back()->text.setPasswordCharacter('*');
    addField("llama_cpp_url", "Custom local service URL", juce::String::fromUTF8("自定义本地服务地址"));
    for (auto* button : {&close, &advanced, &inspect, &prepare, &apply, &cancel})
    {
        addAndMakeVisible(button);
        button->setColour(juce::TextButton::buttonColourId, juce::Colour(0xff282a40));
        button->setColour(juce::TextButton::textColourOffId, ink);
    }
    prepare.setColour(juce::TextButton::buttonColourId, juce::Colour(0xff30456c));
    close.onClick = [this] { if (onClose) onClose(); };
    advanced.onClick = [this] { showAdvanced = !showAdvanced; setChinese(chinese); resized(); };
    inspect.onClick = [this] { request("inspect"); };
    prepare.onClick = [this] { request("prepare"); };
    apply.onClick = [this] { request("apply"); };
    cancel.onClick = [this] { request("cancel"); };
    setChinese(false);
    startTimer(150);
}

SettingsPanel::~SettingsPanel() { stopTimer(); if (pending.valid()) pending.wait(); }

void SettingsPanel::addField(const juce::String& key, const juce::String& en, const juce::String& zh,
                             const juce::StringArray& values, const juce::StringArray& labels)
{
    auto field = std::make_unique<Field>();
    field->key = key; field->en = en; field->zh = zh; field->values = values;
    field->isChoice = !values.isEmpty();
    field->advancedOnly = key == "local_model" || key == "llm_context" || key == "midi_llm_dtype" || key == "base_url" || key == "chat_model" || key == "api_key" || key == "llama_cpp_url";
    form.addAndMakeVisible(field->label);
    field->label.setColour(juce::Label::textColourId, muted);
    field->label.setFont(juce::FontOptions(13.0f));
    if (field->isChoice)
    {
        form.addAndMakeVisible(field->choice);
        field->choice.addItemList(labels, 1);
        field->choice.setColour(juce::ComboBox::backgroundColourId, juce::Colour(0xff0f101a));
        field->choice.setColour(juce::ComboBox::textColourId, ink);
        field->choice.setColour(juce::ComboBox::outlineColourId, line);
    }
    else
    {
        form.addAndMakeVisible(field->text);
        field->text.setColour(juce::TextEditor::backgroundColourId, juce::Colour(0xff0f101a));
        field->text.setColour(juce::TextEditor::textColourId, ink);
        field->text.setColour(juce::TextEditor::outlineColourId, line);
        field->text.setColour(juce::TextEditor::focusedOutlineColourId, blue);
        field->text.setFont(juce::FontOptions(14.0f));
    }
    fields.push_back(std::move(field));
}

void SettingsPanel::setChinese(bool value)
{
    chinese = value;
    title.setText(tr("Models & conversation", "模型与对话"), juce::dontSendNotification);
    note.setText(tr("Sizes refer to weights. *Default local chat; custom sizes vary. Transcription: 225 KiB / CPU. Recommended devices are checked before saving.",
                    "大小为权重大小；*本地对话为默认规格，自定义以实际为准。音频转 MIDI：225 KiB / CPU。推荐部署须验证后保存。"), juce::dontSendNotification);
    advanced.setButtonText(showAdvanced ? tr("Hide advanced", "收起高级设置") : tr("Advanced / custom", "高级 / 自定义"));
    close.setButtonText(tr("Close", "关闭")); inspect.setButtonText(tr("Detect", "检测配置"));
    prepare.setButtonText(tr("Download & set up", "下载并配置")); apply.setButtonText(tr("Verify & apply", "验证并应用"));
    cancel.setButtonText(tr("Stop setup", "停止配置"));
    for (auto& field : fields)
    {
        field->label.setText(chinese ? field->zh : field->en, juce::dontSendNotification);
        if (field->key == "api_key") field->text.setTextToShowWhenEmpty(savedApiKey ? tr("Saved; leave blank to keep", "已保存；留空保留") : tr("Required if local chat is unavailable", "本地不可用时必填"), muted);
        if (field->isChoice)
        {
            const int id = field->choice.getSelectedId();
            juce::StringArray labels;
            if (field->key == "chat_policy") labels = chinese ? juce::StringArray{juce::String::fromUTF8("推荐 / 按硬件验证"), juce::String::fromUTF8("本地对话 / GPU"), juce::String::fromUTF8("云端对话"), juce::String::fromUTF8("仅操作按钮")} : juce::StringArray{"Recommended / hardware checked", "Local GPU", "Cloud service", "Direct buttons only"};
            else if (field->key == "model_source") labels = chinese ? juce::StringArray{juce::String::fromUTF8("自动 / 公网 IP"), juce::String::fromUTF8("官方源"), juce::String::fromUTF8("国内镜像（如有）")} : juce::StringArray{"Auto / IP country", "Official", "China mirror (if available)"};
           #if JUCE_MAC
            else if (field->key == "midi_llm_dtype") labels = chinese ? juce::StringArray{juce::String::fromUTF8("自动：原始优先 / 低内存 FP16"), juce::String::fromUTF8("原始精度（随设备）"), "FLOAT32", "FLOAT16", "BFLOAT16"} : juce::StringArray{"Auto: original / low-RAM FP16", "Original / device default", "FLOAT32", "FLOAT16", "BFLOAT16"};
           #endif
            else for (const auto& option : field->values)
            {
                if (option == "auto")
                {
                   #if JUCE_MAC
                    labels.add(field->key == "llm_choice" ? tr("Recommended / GPU required", "推荐 / 需 GPU") : field->key.endsWith("_choice") ? tr("Recommended / CPU", "推荐 / CPU") : tr("Recommended", "推荐"));
                   #else
                    labels.add(tr("Recommended / hardware checked", "推荐 / 按硬件验证"));
                   #endif
                }
                else labels.add(option == "mps" ? tr("GPU / explicit test", "GPU / 单独验证") : option == "cuda" ? "GPU" : option.toUpperCase());
            }
            field->choice.clear(juce::dontSendNotification);
            field->choice.addItemList(labels, 1);
            field->choice.setSelectedId(id, juce::dontSendNotification);
        }
    }
}

void SettingsPanel::open(bool value)
{
    setChinese(value); setVisible(true); toFront(true);
    if (!pending.valid()) { loadNext = true; request("load"); }
}

juce::var SettingsPanel::draft() const
{
    auto* object = new juce::DynamicObject();
    for (auto& field : fields)
    {
        const auto value = field->isChoice ? field->values[juce::jlimit(0, field->values.size()-1, field->choice.getSelectedId()-1)] : field->text.getText().trim();
        object->setProperty(field->key, value);
    }
    return juce::var(object);
}

void SettingsPanel::request(const juce::String& action)
{
    if (pending.valid()) { if (action != "poll") queuedAction = action; return; }
    pendingAction = action;
    if (action != "poll") lastActionError.clear();
    if (action == "load" || action == "poll")
        pending = std::async(std::launch::async, [this] { return backend.settings(); });
    else if (action == "cancel")
        pending = std::async(std::launch::async, [this] { return backend.cancelConfiguration(); });
    else
    {
        auto* object = new juce::DynamicObject();
        object->setProperty("action", action); object->setProperty("revision", revision); object->setProperty("settings", draft());
        const juce::var payload(object);
        pending = std::async(std::launch::async, [this, payload] { return backend.configureSettings(payload); });
    }
    if (action != "poll") { inspect.setEnabled(false); prepare.setEnabled(false); apply.setEnabled(false); }
    if (action != "poll" && action != "load")
    {
        for (auto& field : fields) { field->text.setEnabled(false); field->choice.setEnabled(false); }
        cancel.setEnabled(true);
    }
}

void SettingsPanel::consume(const juce::var& value, bool load)
{
    auto* object = value.getDynamicObject();
    if (!object) { status.setText(tr("Cannot reach the local service. Close and reopen Settings to retry.", "无法连接本地服务，请关闭后重开设置重试。")); return; }
    if (object->hasProperty("error")) { for (auto& field : fields) { field->text.setEnabled(!jobBusy); field->choice.setEnabled(!jobBusy); } lastActionError = object->getProperty("error").toString(); status.setText(lastActionError); return; }
    savedApiKey = static_cast<bool>(object->getProperty("api_key_configured"));
    if (load)
    {
        revision = object->getProperty("revision").toString();
        if (auto* settings = object->getProperty("settings").getDynamicObject())
            for (auto& field : fields)
            {
                if (field->key == "api_key")
                {
                    field->text.clear();
                    field->text.setTextToShowWhenEmpty(static_cast<bool>(object->getProperty("api_key_configured")) ? tr("Saved; leave blank to keep", "已保存；留空保留") : tr("Required if local chat is unavailable", "本地不可用时必填"), muted);
                }
                else if (field->isChoice) field->choice.setSelectedId(field->values.indexOf(settings->getProperty(field->key).toString())+1, juce::dontSendNotification);
                else field->text.setText(settings->getProperty(field->key).toString(), false);
            }
    }
    if (pendingAction != "load" && pendingAction != "poll" && pendingAction != "cancel") { submitted = true; submittedAction = pendingAction; }
    juce::String text = lastActionError;
    if (auto* job = object->getProperty("job").getDynamicObject())
    {
        const auto state = job->getProperty("state").toString();
        jobBusy = state == "running" || state == "cancelling";
        auto detail = job->getProperty("detail").toString();
        const std::pair<const char*, const char*> translations[] = {
            {"Checking configuration", "正在检查配置"},
            {"Detecting memory and available GPU capacity", "正在检测内存和可用显存"},
            {"Selecting model sources by public egress country", "正在根据公网出口选择模型来源"},
            {"Installing dedicated Python dependencies", "正在安装专用运行依赖"},
            {"Installing selected CUDA Torch runtime", "正在安装所选 GPU 运行环境"},
            {"Installing CUDA Torch for the final verified device selection", "正在为已确定的设备安装 GPU 运行环境"},
            {"Using the installed private CUDA Torch runtime", "正在使用已安装的专用 GPU 运行环境"},
            {"Checking local native tool calling, replay and fixed-device residency", "正在验证本地工具调用、结果回传和设备驻留"},
            {"Checking selected cloud API tool calling", "正在验证云端 API 的工具调用"},
            {"Checking direct-button mode", "正在检查直接操作模式"},
            {"Verifying dependencies, selected devices and actual music models", "正在校验依赖、设备和音乐模型"},
            {"Hardware detected. Apply to verify and save.", "检测完成。点击验证并应用来保存。"},
            {"Verified and applied. Devices stay fixed until the next configuration.", "验证通过并已保存；设备固定使用，直到下次配置。"},
            {"Configuration cancelled. Previous settings retained.", "已取消配置，保留原设置。"},
            {"Local chat is unavailable. Enter an API key and verify cloud chat, or select direct buttons only.", "本地聊天暂不可用。请填写 API 密钥并验证，或选择仅操作按钮。"}
        };
        if (chinese) for (const auto& entry : translations) if (detail == entry.first) { detail = juce::String::fromUTF8(entry.second); break; }
        if (state == "failed") detail = tr("Setup failed: ", "配置失败：") + detail;
        text += (text.isEmpty() ? "" : "\n") + detail;
        if (job->getProperty("local_error").toString().isNotEmpty()) text += "\n" + job->getProperty("local_error").toString();
        auto plan = job->getProperty("hardware_plan");
        auto route = job->getProperty("model_sources");
        if (auto* planned = plan.getDynamicObject())
            text += "\n" + tr("Suggested devices: ", "建议设备：") + tr("Chat=", "对话=") + planned->getProperty("llm_device").toString() + tr(", composition=", "，作曲=") + planned->getProperty("midi_llm_device").toString() + tr(", continue/fill=", "，续写填充=") + planned->getProperty("midi_gpt_device").toString() + tr(", stems=", "，分轨=") + planned->getProperty("stem_device").toString();
        if (auto* source = showAdvanced ? route.getDynamicObject() : nullptr)
            text += "\n" + tr("Detected model source: ", "检测到的模型来源：") + source->getProperty("hf_endpoint").toString();
        if (submitted && !jobBusy)
        {
            revision = object->getProperty("revision").toString(); submitted = false;
            if (state == "complete" && submittedAction != "inspect") for (auto& field : fields) if (field->key == "api_key") field->text.clear();
        }
    }
    apiStatus.setText({}, juce::dontSendNotification);
    apiStatus.setVisible(false);
    if (auto* devices = object->getProperty("devices").getDynamicObject())
        text += "\n" + tr("Saved devices: ", "已保存设备：") + tr("Chat=", "对话=") + devices->getProperty("llm_device").toString() + tr(", composition=", "，作曲=") + devices->getProperty("midi_llm_device").toString()
                + tr(", continue/fill=", "，续写填充=") + devices->getProperty("midi_gpt_device").toString() + tr(", stems=", "，分轨=") + devices->getProperty("stem_device").toString();
    if (auto* route = showAdvanced ? object->getProperty("model_sources").getDynamicObject() : nullptr)
        text += "\n" + tr("Model source: ", "模型来源：") + route->getProperty("hf_endpoint").toString();
   #if JUCE_MAC
    if (auto* precision = object->getProperty("composition_precision").getDynamicObject())
    {
        const auto reason = precision->getProperty("reason").toString();
        const auto dtype = precision->getProperty("resolved").toString();
        text += "\n" + tr("Composition precision: ", "作曲精度：")
            + (reason == "auto-low-memory" ? tr("FP16 (automatic 8 GB memory tier)", "FP16（8 GB 低内存档自动减精度）")
               : reason == "manual" ? tr("Manual / ", "手动 / ") + dtype.toUpperCase()
               : tr("Original / device default", "原始精度（随设备）"));
    }
   #endif
    if (text.isNotEmpty() && status.getText() != text) status.setText(text);
    for (auto& field : fields) { field->text.setEnabled(!jobBusy); field->choice.setEnabled(!jobBusy); }
    cancel.setEnabled(jobBusy);
}

void SettingsPanel::timerCallback()
{
    if (pending.valid() && pending.wait_for(std::chrono::seconds(0)) == std::future_status::ready)
    {
        auto value = pending.get();
        consume(value, loadNext); loadNext = false;
        inspect.setEnabled(!jobBusy); prepare.setEnabled(!jobBusy); apply.setEnabled(!jobBusy);
        if (queuedAction.isNotEmpty()) { const auto action = queuedAction; queuedAction.clear(); request(action); }
    }
    const auto now = juce::Time::currentTimeMillis();
    if ((isVisible() || jobBusy) && !pending.valid() && now-lastPoll >= 1000)
    { lastPoll = now; request("poll"); }
}

void SettingsPanel::paint(juce::Graphics& graphics) { graphics.fillAll(bg); graphics.setColour(line); graphics.drawRect(getLocalBounds(), 1); }

void SettingsPanel::resized()
{
    auto bounds = getLocalBounds().reduced(22, 12);
    auto header = bounds.removeFromTop(34); close.setBounds(header.removeFromRight(75)); advanced.setBounds(header.removeFromRight(155).reduced(4, 0)); title.setBounds(header);
    note.setBounds(bounds.removeFromTop(42));
    auto buttons = bounds.removeFromBottom(38); const int width = buttons.getWidth()/4;
    inspect.setBounds(buttons.removeFromLeft(width).reduced(3, 0)); prepare.setBounds(buttons.removeFromLeft(width).reduced(3, 0));
    apply.setBounds(buttons.removeFromLeft(width).reduced(3, 0)); cancel.setBounds(buttons.reduced(3, 0));
    bounds.removeFromBottom(8);
    status.setBounds(bounds.removeFromBottom(100)); apiStatus.setBounds({});
    viewport.setBounds(bounds);
    int visibleRows = 0;
    for (const auto& field : fields) if (!field->advancedOnly || showAdvanced) ++visibleRows;
    form.setSize(juce::jmax(400, viewport.getWidth()-18), visibleRows*36);
    int y = 0;
    for (auto& field : fields)
    {
        const bool visible = !field->advancedOnly || showAdvanced;
        field->label.setVisible(visible);
        field->choice.setVisible(visible && field->isChoice);
        field->text.setVisible(visible && !field->isChoice);
        if (!visible) continue;
        auto row = juce::Rectangle<int>(0, y, form.getWidth(), 32); y += 36;
        field->label.setBounds(row.removeFromLeft(205));
        if (field->isChoice) field->choice.setBounds(row.reduced(3, 1)); else field->text.setBounds(row.reduced(3, 1));
    }
}
