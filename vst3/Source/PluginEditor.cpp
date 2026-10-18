#include "PluginEditor.h"

namespace
{
const juce::Colour bgCanvas       { 0xff0f101a }; // Tokyo Night Deep Obsidian
const juce::Colour panelBg        { 0xff161724 }; // Slate Card Bg
const juce::Colour cardBorder     { 0xff282a40 }; // Glassmorphic Border
const juce::Colour textMain       { 0xffc0caf5 }; // Crisp Soft Blue-White
const juce::Colour textSub        { 0xff7a88cf }; // Soft Purple-Slate
const juce::Colour accentBlue     { 0xff7aa2f7 }; // Electric Indigo Blue
const juce::Colour accentPurple   { 0xffbb9af7 }; // Neon Purple
const juce::Colour accentCyan     { 0xff7dcfff }; // Wave Cyan
const juce::Colour accentGreen    { 0xff73daca }; // Emerald Green
const juce::Colour accentRed      { 0xfff7768e }; // Velvet Coral Red
const juce::Colour connectionBg       { 0xff2a2318 };
const juce::Colour connectionText     { 0xffe0af68 };
}

ScoreStaveComponent::ScoreStaveComponent()
{
    setOpaque(false);
}

void ScoreStaveComponent::loadMidiFile(const juce::File& file)
{
    notes.clear();
    if (!file.existsAsFile())
    {
        repaint();
        return;
    }

    juce::FileInputStream stream(file);
    if (stream.openedOk())
    {
        juce::MidiFile midiFile;
        if (midiFile.readFrom(stream))
        {
            midiFile.convertTimestampTicksToSeconds();
            for (int t = 0; t < midiFile.getNumTracks(); ++t)
            {
                auto* trackSeq = midiFile.getTrack(t);
                if (trackSeq != nullptr)
                {
                    for (int i = 0; i < trackSeq->getNumEvents(); ++i)
                    {
                        auto* holder = trackSeq->getEventPointer(i);
                        if (holder != nullptr && holder->message.isNoteOn())
                            notes.push_back({ holder->message.getNoteNumber(), holder->message.getTimeStamp() });
                    }
                }
            }
        }
    }
    repaint();
}

void ScoreStaveComponent::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat().reduced(2.0f);
    
    // Background Card
    g.setColour(panelBg);
    g.fillRoundedRectangle(bounds, 10.0f);
    g.setColour(cardBorder);
    g.drawRoundedRectangle(bounds, 10.0f, 1.0f);

    // Title Label
    g.setColour(accentCyan);
    g.setFont(juce::FontOptions(12.0f, juce::Font::bold));
    g.drawText(ui("SCORE STAVE VISUALIZER"), bounds.reduced(12, 8).removeFromTop(18).toNearestInt(), juce::Justification::centredLeft);

    auto staveArea = bounds.reduced(12, 28);
    float startY = staveArea.getCentreY() - 20.0f;
    float lineSpacing = 8.5f;

    // Draw 5 parallel stave lines
    g.setColour(accentBlue.withAlpha(0.45f));
    for (int i = 0; i < 5; ++i)
    {
        float y = startY + i * lineSpacing;
        g.drawHorizontalLine(static_cast<int>(y), staveArea.getX() + 35.0f, staveArea.getRight() - 10.0f);
    }

    // Clef mark G
    g.setColour(accentPurple);
    g.setFont(juce::FontOptions(18.0f, juce::Font::bold));
    g.drawText("G", staveArea.getX() + 8, static_cast<int>(startY - 2), 20, 38, juce::Justification::centred);

    if (notes.empty())
    {
        g.setColour(textSub.withAlpha(0.5f));
        g.setFont(juce::FontOptions(11.0f, juce::Font::plain));
        g.drawText(ui("No musical score generated yet."), staveArea.toNearestInt(), juce::Justification::centred);
        return;
    }

    // Draw notes on stave
    float noteStartX = staveArea.getX() + 45.0f;
    float availableW = staveArea.getWidth() - 60.0f;
    // Fit the complete note sequence into the overview.  The old fixed
    // 24-note cap silently dropped the rest of longer MIDI files, making the
    // preview look truncated even when the generated file was valid.
    const size_t visibleNotes = notes.size();
    const float stepX = availableW / std::max(1.0f, float(visibleNotes > 1 ? visibleNotes - 1 : 1));
    const float noteRadius = juce::jlimit(1.5f, 4.0f, stepX * 0.35f);

    int minPitch = 127, maxPitch = 0;
    for (const auto& note : notes)
    {
        minPitch = std::min(minPitch, note.pitch);
        maxPitch = std::max(maxPitch, note.pitch);
    }
    const float pitchCentre = (static_cast<float>(minPitch) + static_cast<float>(maxPitch)) * 0.5f;
    const float pitchScale = std::min(lineSpacing * 0.5f,
        std::max(1.0f, staveArea.getHeight() - 40.0f) / std::max(1.0f, static_cast<float>(maxPitch - minPitch)));
    g.setColour(accentCyan);
    for (size_t i = 0; i < visibleNotes; ++i)
    {
        int pitch = notes[i].pitch;
        float pitchOffset = (static_cast<float>(pitch) - pitchCentre) * pitchScale;
        float noteY = staveArea.getCentreY() - pitchOffset;
        float noteX = noteStartX + i * stepX;

        // Notehead
        g.fillEllipse(noteX - noteRadius, noteY - noteRadius * 0.75f,
                      noteRadius * 2.0f, noteRadius * 1.5f);

        // Stem
        g.setColour(accentCyan.withAlpha(0.85f));
        if (pitch < 71)
            g.drawLine(noteX + 3.5f, noteY, noteX + 3.5f, noteY - 18.0f, 1.2f);
        else
            g.drawLine(noteX - 3.5f, noteY, noteX - 3.5f, noteY + 18.0f, 1.2f);

        // Ledger lines
        if (noteY > startY + 4 * lineSpacing + 2.0f)
        {
            g.setColour(accentBlue.withAlpha(0.5f));
            g.drawHorizontalLine(static_cast<int>(startY + 5 * lineSpacing), noteX - 6.0f, noteX + 6.0f);
        }
        else if (noteY < startY - 2.0f)
        {
            g.setColour(accentBlue.withAlpha(0.5f));
            g.drawHorizontalLine(static_cast<int>(startY - lineSpacing), noteX - 6.0f, noteX + 6.0f);
        }
        g.setColour(accentCyan);
    }
}

AnimatedButton::AnimatedButton(const juce::String& text, bool primary)
    : TextButton(text), isPrimaryStyle(primary)
{
    setMouseCursor(juce::MouseCursor::PointingHandCursor);
    startTimerHz(60);
}

void AnimatedButton::mouseEnter(const juce::MouseEvent& event) { target = 1.0f; TextButton::mouseEnter(event); }
void AnimatedButton::mouseExit(const juce::MouseEvent& event)  { target = 0.0f; TextButton::mouseExit(event); }
void AnimatedButton::mouseDown(const juce::MouseEvent& event) { target = -0.55f; TextButton::mouseDown(event); }
void AnimatedButton::mouseUp(const juce::MouseEvent& event)   { target = isMouseOver() ? 1.0f : 0.0f; TextButton::mouseUp(event); }

void AnimatedButton::timerCallback()
{
    const auto previous = amount;
    amount += (target - amount) * 0.22f;
    if (isSpinning)
        spinnerAngle += 0.18f;
    if (isSpinning || std::abs(amount - previous) > 0.0001f)
        repaint();
}

void AnimatedButton::paintButton(juce::Graphics& g, bool, bool)
{
    if (isSpinning)
    {
        auto bounds = getLocalBounds().toFloat().reduced(1.5f);
        g.setColour(accentBlue.withMultipliedSaturation(0.9f));
        g.fillRoundedRectangle(bounds, 6.0f);
        g.setColour(bgCanvas);
        g.drawRoundedRectangle(bounds, 6.0f, 1.2f);

        float cx = bounds.getRight() - 20.0f;
        float cy = bounds.getCentreY();
        juce::Path spinnerPath;
        spinnerPath.addCentredArc(cx, cy, 7.0f, 7.0f, 0.0f, spinnerAngle, spinnerAngle + 4.5f, true);
        g.setColour(bgCanvas);
        g.strokePath(spinnerPath, juce::PathStrokeType(2.5f, juce::PathStrokeType::curved, juce::PathStrokeType::rounded));

        g.setFont(juce::FontOptions(13.0f, juce::Font::bold));
        g.drawText(ui("Thinking..."), bounds.withTrimmedRight(32).toNearestInt(), juce::Justification::centred, true);
        return;
    }

    if (!isEnabled())
    {
        auto bounds = getLocalBounds().toFloat().reduced(1.5f);
        g.setColour(panelBg.brighter(0.05f));
        g.fillRoundedRectangle(bounds, 6.0f);
        g.setColour(textSub.withAlpha(0.3f));
        g.drawRoundedRectangle(bounds, 6.0f, 1.0f);
        g.setFont(juce::FontOptions(13.0f, juce::Font::bold));
        g.drawFittedText(getButtonText(), bounds.toNearestInt(), juce::Justification::centred, 1);
        return;
    }

    const auto press = juce::jmax(0.0f, -amount);
    const auto hover = juce::jmax(0.0f, amount);
    auto bounds = getLocalBounds().toFloat().reduced(1.5f - hover * 1.0f + press * 1.5f);
    bounds.translate(0.0f, press * 1.5f - hover * 0.5f);

    juce::Colour fillCol = isPrimaryStyle ? accentBlue.withMultipliedSaturation(0.85f).brighter(hover * 0.1f)
                                          : cardBorder.brighter(hover * 0.15f);
    if (getButtonText().contains(ui("Stop")) || getButtonText().contains("Clear"))
        fillCol = isPrimaryStyle ? accentRed.withMultipliedSaturation(0.8f) : cardBorder;

    g.setColour(fillCol);
    g.fillRoundedRectangle(bounds, 6.0f);

    g.setColour(isPrimaryStyle ? bgCanvas : textMain);
    if (!isPrimaryStyle && hover > 0.01f)
        g.setColour(accentBlue);
    g.drawRoundedRectangle(bounds, 6.0f, 1.0f);

    g.setFont(juce::FontOptions(13.0f, juce::Font::bold));
    g.drawFittedText(getButtonText(), bounds.toNearestInt(), juce::Justification::centred, 1);
}

TriceratopsAudioProcessorEditor::TriceratopsAudioProcessorEditor(TriceratopsAudioProcessor& owner)
    : AudioProcessorEditor(&owner), ownerProcessor(owner), progressBar(progress)
{
    const auto stored = juce::JSON::parse(languageFile());
    if (auto* object = stored.getDynamicObject())
    {
        chinese = object->getProperty("language").toString() == "zh";
        if (object->hasProperty("auto_import"))
            autoImportToReaper = static_cast<bool>(object->getProperty("auto_import"));
    }
    setResizable(true, true);
   #if JucePlugin_Build_AU
    // Keep the AU editor compact enough that Logic's arrange area remains
    // visible as an external MIDI drag target on small displays.
    const auto* display = juce::Desktop::getInstance().getDisplays().getPrimaryDisplay();
    const auto width = display != nullptr ? juce::jlimit(720, 820, display->userArea.getWidth() - 220) : 820;
    const auto height = display != nullptr ? juce::jlimit(600, 620, display->userArea.getHeight() - 70) : 620;
    setResizeLimits(700, 580, 1920, 1200);
    setSize(width, height);
   #else
    setResizeLimits(900, 650, 1920, 1200);
    setSize(1180, 780);
   #endif

    settingsPanel = std::make_unique<SettingsPanel>(ownerProcessor.backend());
    addChildComponent(*settingsPanel);
    settingsPanel->onClose = [this] { settingsPanel->setVisible(false); };
    addAndMakeVisible(settingsBtn);
    settingsBtn.onClick = [this] { settingsPanel->open(chinese); };
    // Setup Text Editors
    for (auto* editor : { &chatDisplay, &prompt, &arrangement, &history })
    {
        editor->setColour(juce::TextEditor::backgroundColourId, panelBg);
        editor->setColour(juce::TextEditor::textColourId, textMain);
        editor->setColour(juce::TextEditor::outlineColourId, cardBorder);
        editor->setColour(juce::TextEditor::focusedOutlineColourId, accentBlue);
        editor->setFont(juce::FontOptions("Microsoft YaHei UI", 14.0f, juce::Font::plain));
        editor->setMultiLine(true);
        editor->setScrollbarsShown(true);
        addAndMakeVisible(editor);
    }
    chatBackendSelector.addItem("Default / 默认", 1);
    chatBackendSelector.addItem("API", 2);
    chatBackendSelector.addItem("Local GPU / 本地", 3);
    chatBackendSelector.setSelectedId(1, juce::dontSendNotification);
    chatBackendSelector.setTitle("Chat model / 聊天模型");
    addAndMakeVisible(chatBackendSelector);
    addAndMakeVisible(chatBackendStatus);
    chatBackendStatus.setText("Default / 默认", juce::dontSendNotification);
    chatBackendStatus.setColour(juce::Label::textColourId, textSub);
    chatBackendSelector.onChange = [this] {
        selectedChatBackend = chatBackendSelector.getSelectedId() == 2 ? "remote"
            : chatBackendSelector.getSelectedId() == 3 ? "local" : "";
        chatBackendReady = false;
        deferredChatVerify = true;
        chatSwitchPending = true;
        send.setEnabled(false);
        chatBackendStatus.setText(chinese ? "切换中：准备并验证…" : "Switching: preparing & verifying...", juce::dontSendNotification);
    };
    chatDisplay.setReadOnly(true);
    prompt.setTextToShowWhenEmpty(ui("Say anything: sad piano, continue this, more energy, analyze it..."), textSub.withAlpha(0.6f));
    arrangement.setReadOnly(true);
    arrangement.setText(ui("Score Arrangement Plan will appear here."));
    history.setReadOnly(true);
    history.setText(ui("Version history in this project session will appear here."));

    // Setup Labels & Components
    for (auto* label : { &statusLabel, &progressLabel, &connectionBanner, &midiLabel, &audioLabel })
    {
        label->setColour(juce::Label::textColourId, textMain);
        label->setFont(juce::FontOptions(13.0f, juce::Font::bold));
        addAndMakeVisible(label);
    }
    statusLabel.setText(ui("CONNECTING TO AGENT"), juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId, accentBlue);
    progressLabel.setText(chinese ? juce::String::fromUTF8("本地音乐工具") : "Local music tools", juce::dontSendNotification);

    connectionBanner.setText(chinese ? juce::String::fromUTF8("正在连接本地音乐助手...") : "Connecting to the local music agent...", juce::dontSendNotification);
    connectionBanner.setColour(juce::Label::backgroundColourId, connectionBg);
    connectionBanner.setColour(juce::Label::textColourId, connectionText);
    connectionBanner.setColour(juce::Label::outlineColourId, connectionText.withAlpha(0.4f));
    connectionBanner.setJustificationType(juce::Justification::centred);

    midiLabel.setText(ui("MIDI: None"), juce::dontSendNotification);
    audioLabel.setText(ui("AUDIO: None"), juce::dontSendNotification);
    midiLabel.setColour(juce::Label::textColourId, textSub);
    audioLabel.setColour(juce::Label::textColourId, textSub);

    addAndMakeVisible(progressBar);
    addAndMakeVisible(scoreStave);

    // Setup Buttons
    for (auto* button : { &languageBtn, &send, &cancel, &clearChatBtn, &autoImportBtn, &importReaperBtn, &sidebarToggleBtn,
                          &helpBtn, &newMusic, &editMidi, &analyze, &continueFour, &moreEnergy, &tightenTiming,
                          &undoBtn, &keepBtn, &rejectBtn, &stems, &audioMidi,
                          &loadMidi, &loadAudio, &clearMidiBtn, &clearAudioBtn,
                          &playMidi, static_cast<AnimatedButton*>(&dragMidi), &capture, &captureAudio })
        addAndMakeVisible(button);

    languageBtn.onClick = [this] {
        chinese = !chinese;
        saveUiSettings();
        applyLanguage();
    };
    send.onClick          = [this] { sendMessage(); };
    cancel.onClick        = [this] { cancelCurrentTask(); };
    clearChatBtn.onClick  = [this] { clearChatHistory(); };
    autoImportBtn.onClick = [this] {
        autoImportToReaper = !autoImportToReaper;
        autoImportBtn.setButtonText(autoImportToReaper ? ui("Auto-Import: ON") : ui("Auto-Import: OFF"));
        autoImportBtn.setPrimary(autoImportToReaper);
        saveUiSettings();
    };
    importReaperBtn.onClick = [this] { importToReaper(); };
    sidebarToggleBtn.onClick = [this] { showSidebar = !showSidebar; resized(); };

    helpBtn.onClick       = [this] { runQuickAction(ui("Show my available music features and examples."), "list_capabilities"); };
    helpBtn.setTooltip(ui("View available tools and examples"));
    newMusic.onClick      = [this] { setStarter(ui("Create music: ")); };
    editMidi.onClick      = [this] { setStarter(ui("Change this MIDI: ")); };
    analyze.onClick       = [this] { runQuickAction(ui("Analyze what I loaded and explain the most useful musical details."),
        midiPath.isNotEmpty() ? "analyze_selected_midi" : (audioPath.isNotEmpty() ? "analyze_audio" : "inspect_project")); };
    continueFour.onClick  = [this] { runQuickAction(ui("Continue the loaded MIDI for four bars, keeping its musical identity."), "continue_midi"); };
    moreEnergy.onClick    = [this] { runQuickAction(ui("Make the loaded MIDI more energetic while keeping the main melody."), "more_energy"); };
    tightenTiming.onClick = [this] { runQuickAction(ui("Tighten the timing of the loaded MIDI without changing its notes."), "tighten_timing"); };
    undoBtn.onClick       = [this] { runQuickAction(ui("Undo the last MIDI change."), "undo"); };
    keepBtn.onClick       = [this] { runQuickAction(ui("Keep this version. I like it."), "accept"); };
    rejectBtn.onClick     = [this] { runQuickAction(ui("Reject this version and remember that I do not like it."), "reject"); };
    stems.onClick         = [this] { runQuickAction(ui("Split the loaded audio into stems."), "separate_stems"); };
    audioMidi.onClick     = [this] { runQuickAction(ui("Convert the loaded audio to MIDI."), "audio_to_midi"); };

    continueFour.setTooltip(ui("Generate a four-bar continuation from the loaded MIDI"));
    moreEnergy.setTooltip(ui("Increase musical energy while preserving the melody"));
    tightenTiming.setTooltip(ui("Quantize the loaded MIDI to a tighter grid"));
    keepBtn.setTooltip(ui("Accept this result and remember the preference"));
    rejectBtn.setTooltip(ui("Reject this result and remember the feedback"));

    loadMidi.onClick  = [this] { chooseMidi(); };
    loadAudio.onClick = [this] { chooseAudio(); };
    clearMidiBtn.onClick  = [this] { clearMidi(); };
    clearAudioBtn.onClick = [this] { clearAudio(); };

    playMidi.onClick  = [this] { ownerProcessor.armGeneratedClip(); };
    dragMidi.onFileDrag = [this] { dragLatestMidi(); };
    capture.onClick   = [this] { toggleMidiCapture(); };
    captureAudio.onClick = [this] { toggleAudioCapture(); };

    // Wait for the backend connection before sending a request.
    send.setEnabled(false);
    // Keep the input accessible while connecting; only Send needs to wait.
    prompt.setEnabled(true);
    prompt.setTitle("Message");

    const auto savedMidi = juce::File(ownerProcessor.getLoadedMidiPath());
    if (savedMidi.existsAsFile())
    {
        midiPath = savedMidi.getFullPathName();
        midiLabel.setText("MIDI: " + savedMidi.getFileName(), juce::dontSendNotification);
        midiLabel.setColour(juce::Label::textColourId, accentBlue);
        scoreStave.loadMidiFile(savedMidi);
    }

    // Initial welcoming chat message
    chatTurns.push_back({
        "assistant",
        ui("Welcome to Triceratops Music Agent!\nDescribe a musical goal in your own words. Try: create a wistful piano phrase; transpose this MIDI by two semitones; continue it for four bars; analyze this audio; split it into stems. Load MIDI or audio before file-based actions. Use Features for the full list. Requests outside music and REAPER will be identified clearly."),
        juce::Time::getCurrentTime().formatted("%H:%M:%S"),
        "",
        {}
    });
    applyLanguage();
    updateChatDisplay();

    startTimer(100);
}

TriceratopsAudioProcessorEditor::~TriceratopsAudioProcessorEditor()
{
    stopTimer();
    if (pending.valid())
    {
        pending.wait();
        if (requestKind == RequestKind::import_reaper)
        {
            auto response = pending.get();
            if (auto* object = response.getDynamicObject(); object != nullptr && object->hasProperty("script_path"))
                ownerProcessor.backend().reaperImportReceipt(object->getProperty("request_id").toString(), true);
        }
    }
    if (sessionStartupRequested)
        ownerProcessor.backend().closeSession();
}

void TriceratopsAudioProcessorEditor::paint(juce::Graphics& g)
{
    g.fillAll(bgCanvas);

    // Header Background
    g.setColour(panelBg);
    g.fillRect(0, 0, getWidth(), 48);
    g.setColour(cardBorder);
    g.drawHorizontalLine(48, 0.0f, static_cast<float>(getWidth()));

    // Reuse the original abstract frill / horns / face-axis brand mark.
    juce::Path mark;
    mark.startNewSubPath(0.0f, 57.0f); mark.lineTo(14.0f, 24.0f);
    mark.lineTo(35.0f, 11.0f); mark.lineTo(56.0f, 24.0f); mark.lineTo(70.0f, 57.0f);
    mark.startNewSubPath(14.0f, 24.0f); mark.lineTo(2.0f, 0.0f);
    mark.startNewSubPath(56.0f, 24.0f); mark.lineTo(68.0f, 0.0f);
    mark.startNewSubPath(20.0f, 40.0f); mark.lineTo(50.0f, 40.0f);
    mark.startNewSubPath(35.0f, 40.0f); mark.lineTo(35.0f, 64.0f);
    g.setColour(accentBlue);
    g.strokePath(mark, juce::PathStrokeType(4.0f, juce::PathStrokeType::curved, juce::PathStrokeType::rounded),
                 juce::AffineTransform::scale(0.40f).translated(12.0f, 11.0f));
    // Title branding
    g.setColour(accentBlue);
    g.setFont(juce::FontOptions(16.0f, juce::Font::bold));
    g.drawText("TRICERATOPS", 46, 0, 124, 48, juce::Justification::centredLeft);

    // Equalizer spectrum bars
    float eqX = 174.0f;
    float eqY = 16.0f;
    float eqH = 16.0f;
    eqPhase += 0.08f;

    g.setColour(accentPurple.withAlpha(0.85f));
    for (int i = 0; i < 6; ++i)
    {
        float fi = static_cast<float>(i);
        float barH = (busyGenerating || backendConnecting)
            ? (5.0f + 9.0f * std::sin(eqPhase + fi * 0.9f) * std::sin(eqPhase * 0.5f + fi))
            : (4.0f + 2.0f * std::sin(fi * 1.2f));
        barH = juce::jlimit(3.0f, 16.0f, std::abs(barH));
        g.fillRoundedRectangle(eqX + fi * 4.5f, eqY + (eqH - barH) * 0.5f, 2.5f, barH, 1.2f);
    }

    g.setFont(juce::FontOptions(11.0f, juce::Font::bold));
    g.setColour(textSub);
    if (getWidth() >= 1100) g.drawText(ui("LOCAL AI AGENT"), 190, 0, 110, 48, juce::Justification::centredLeft);
}

void TriceratopsAudioProcessorEditor::resized()
{
    auto area = getLocalBounds();
    auto header = area.removeFromTop(48).reduced(12, 6);

    header.removeFromLeft(getWidth() >= 1100 ? 290 : (getWidth() < 900 ? 200 : 220));
    statusLabel.setBounds(header.removeFromLeft(getWidth() < 900 ? 80 : 100));
    settingsBtn.setBounds(header.removeFromRight(80).reduced(2, 0));
    if (settingsPanel) settingsPanel->setBounds(getLocalBounds().withTrimmedTop(49));

    sidebarToggleBtn.setBounds(header.removeFromRight(getWidth() < 900 ? 85 : 104).reduced(2, 0));
    autoImportBtn.setBounds(header.removeFromRight(getWidth() < 900 ? 95 : 130).reduced(2, 0));
    clearChatBtn.setBounds(header.removeFromRight(getWidth() < 900 ? 65 : 90).reduced(2, 0));
    languageBtn.setBounds(header.removeFromRight(70).reduced(2, 0));

    if (backendConnecting)
        connectionBanner.setBounds(area.removeFromTop(32).reduced(12, 2));
    else
        connectionBanner.setBounds(0, 0, 0, 0);

    auto fileTools = area.removeFromTop(30).reduced(12, 1);
    dragMidi.setBounds(fileTools.removeFromRight(120));
    area.reduce(12, 8);

    int sidebarWidth = showSidebar ? static_cast<int>(area.getWidth() * 0.34) : 0;
    auto mainArea = showSidebar ? area.removeFromLeft(area.getWidth() - sidebarWidth - 10) : area;

    if (showSidebar)
    {
        auto rightArea = area;
        int staveH = 140;
        scoreStave.setBounds(rightArea.removeFromTop(staveH).reduced(0, 2));
        
        int halfH = rightArea.getHeight() / 2;
        arrangement.setBounds(rightArea.removeFromTop(halfH).reduced(0, 4));
        history.setBounds(rightArea.reduced(0, 4));
    }
    else
    {
        scoreStave.setBounds(0, 0, 0, 0);
    }

    // Main Chat Agent Layout. Keep quick actions at the top so host window
    // scaling can never clip them below the editor viewport.
    auto quickDock = mainArea.removeFromTop(72);
    auto inputDock = mainArea.removeFromTop(110);
    auto bottomDock = mainArea.removeFromBottom(36);
    auto progressRow = mainArea.removeFromBottom(28);

    progressLabel.setBounds(progressRow.removeFromLeft(200));
    progressBar.setBounds(progressRow.reduced(4, 6));

    chatDisplay.setBounds(mainArea.reduced(0, 4));

    auto row2 = quickDock.removeFromTop(36);
    const int modeWidth = row2.getWidth() / 7;
    auto placePill = [&row2, modeWidth](juce::Component& btn) {
        btn.setBounds(row2.removeFromLeft(modeWidth).reduced(2, 4));
    };
    placePill(helpBtn);
    placePill(newMusic);
    placePill(editMidi);
    placePill(analyze);
    placePill(continueFour);
    placePill(moreEnergy);
    placePill(tightenTiming);

    auto row3 = quickDock;
    const int toolWidth = row3.getWidth() / 9;
    auto placeTool = [&row3, toolWidth](juce::Component& btn) {
        btn.setBounds(row3.removeFromLeft(toolWidth).reduced(2, 4));
    };
    placeTool(stems);
    placeTool(audioMidi);
    placeTool(loadMidi);
    placeTool(capture);
    placeTool(loadAudio);
    placeTool(captureAudio);
    placeTool(undoBtn);
    placeTool(keepBtn);
    placeTool(rejectBtn);

    // Bottom Dock
    auto row1 = bottomDock.removeFromTop(36);
    midiLabel.setBounds(row1.removeFromLeft(120).reduced(2, 4));
    clearMidiBtn.setBounds(row1.removeFromLeft(24).reduced(2, 4));
    audioLabel.setBounds(row1.removeFromLeft(120).reduced(2, 4));
    clearAudioBtn.setBounds(row1.removeFromLeft(24).reduced(2, 4));

    importReaperBtn.setBounds(row1.removeFromRight(160).reduced(3, 2));
    playMidi.setBounds(row1.removeFromRight(85).reduced(2, 2));
    // dragMidi is placed in the header so it remains visible in compact AU
    // windows; leave the bottom dock slot empty.

    auto modelRow = inputDock.removeFromTop(28);
    chatBackendSelector.setBounds(modelRow.removeFromLeft(160).reduced(2, 0));
    chatBackendStatus.setBounds(modelRow.reduced(4, 0));
    auto row4 = inputDock.reduced(0, 2);
    auto sendArea = row4.removeFromRight(140);
    send.setBounds(sendArea.removeFromTop(44).reduced(3, 2));
    cancel.setBounds(sendArea.reduced(3, 2));
    prompt.setBounds(row4.reduced(2, 2));
}

void TriceratopsAudioProcessorEditor::timerCallback()
{
    repaint();
    const auto midiCaptureText = ui(ownerProcessor.isCapturingMidi() ? "Save MIDI" : "Rec MIDI");
    const auto audioCaptureText = ui(ownerProcessor.isCapturingAudio() ? "Save audio" : "Rec audio");
    if (capture.getButtonText() != midiCaptureText)
        capture.setButtonText(midiCaptureText);
    if (captureAudio.getButtonText() != audioCaptureText)
        captureAudio.setButtonText(audioCaptureText);

    // Hosts may construct an editor during plug-in scanning merely to query
    // its size. Starting WSL, HTTP, or GPU work at that point can stall the
    // scanner. Only open the backend after the editor has actually remained
    // visible to the user for a short interval.
    if (!sessionStartupRequested)
    {
        if (!isShowing())
        {
            visibleSinceMs = 0;
            return;
        }

        const auto now = juce::Time::currentTimeMillis();
        if (visibleSinceMs == 0)
        {
            visibleSinceMs = now;
            return;
        }

        if (now - visibleSinceMs < 300)
            return;

        sessionStartupRequested = true;
        pending = std::async(std::launch::async, [this] { return ownerProcessor.backend().openSession(); });
        requestKind = RequestKind::open;
    }

    if (requestKind != RequestKind::none && pending.valid()
        && pending.wait_for(std::chrono::seconds(0)) == std::future_status::ready)
    {
        auto response = pending.get();
        if (requestKind == RequestKind::verify_chat)
        {
            if (!static_cast<bool>(response.getProperty("accepted", false)))
            {
                chatSwitchPending = false;
                const auto error = response.getProperty("error", "Backend connection failed").toString();
                chatBackendStatus.setText((chinese ? "切换失败：" : "Switch failed: ") + error, juce::dontSendNotification);
                chatBackendStatus.setTooltip(error);
            }
            requestKind = RequestKind::none;
            return;
        }
        if (requestKind == RequestKind::chat && !static_cast<bool>(response.getProperty("accepted", false)))
        {
            busyGenerating = false;
            send.setSpinning(false);
            if (prompt.getText().isEmpty())
                prompt.setText(submittedMessage);
            const auto error = response.getProperty("error", "Backend connection failed. Check the local service and retry.").toString();
            chatTurns.push_back({ "assistant", ui("Operation failed:\n") + error,
                juce::Time::getCurrentTime().formatted("%H:%M:%S"), "", {} });
            updateChatDisplay();
            send.setEnabled(chatBackendReady && !backendConnecting);
            requestKind = RequestKind::none;
            return;
        }
        if (requestKind == RequestKind::import_reaper)
        {
            if (auto* object = response.getDynamicObject(); object != nullptr && object->hasProperty("script_path"))
            {
                const auto requestId = object->getProperty("request_id").toString();
                const auto discard = !ownerProcessor.runReaperScript(object->getProperty("script_path").toString());
                pending = std::async(std::launch::async, [this, requestId, discard] {
                    return ownerProcessor.backend().reaperImportReceipt(requestId, discard);
                });
                requestKind = RequestKind::import_receipt;
                return;
            }
        }
        if (requestKind == RequestKind::import_reaper || requestKind == RequestKind::import_receipt)
        {
            importReaperBtn.setEnabled(true);
            auto* object = response.getDynamicObject();
            const auto error = object != nullptr ? object->getProperty("error").toString()
                : ui("Backend connection failed. Check the local service and retry.");
            juce::String message;
            if (error.isNotEmpty())
                message = ui("Operation failed:\n") + error;
            else if (object != nullptr && static_cast<bool>(object->getProperty("ok")))
                message = object->getProperty("reply").toString();
            else
                message = "REAPER import was not confirmed.";
            chatTurns.push_back({ "assistant", message,
                juce::Time::getCurrentTime().formatted("%H:%M:%S"), "", {} });
            updateChatDisplay();
        }
        handleStatus(response);
        if (requestKind == RequestKind::open)
            sessionOpened = true;
        requestKind = RequestKind::none;
    }

    chatBackendSelector.setEnabled(!busyGenerating && !chatSwitchPending);
    if (requestKind == RequestKind::none && deferredChatVerify)
    {
        deferredChatVerify = false;
        const auto backend = selectedChatBackend;
        pending = std::async(std::launch::async, [this, backend] { return ownerProcessor.backend().verifyChat(backend); });
        requestKind = RequestKind::verify_chat;
    }
    else if (requestKind == RequestKind::none && deferredCancel)
    {
        deferredCancel = false;
        cancelCurrentTask();
    }
    else if (requestKind == RequestKind::none && deferredClearChat)
    {
        deferredClearChat = false;
        clearChatHistory();
    }
    else if (requestKind == RequestKind::none && queuedMessage.isNotEmpty())
    {
        const auto message = queuedMessage;
        const auto action = queuedAction;
        queuedMessage.clear();
        queuedAction.clear();
        startChat(message, action);
    }
    else if (requestKind == RequestKind::none && deferredAutoImport)
    {
        deferredAutoImport = false;
        importToReaper();
    }
    else if (requestKind == RequestKind::none
             && juce::Time::currentTimeMillis() - lastStatusPollMs >= 1000)
    {
        pollStatus();
    }
}

void TriceratopsAudioProcessorEditor::pollStatus()
{
    lastStatusPollMs = juce::Time::currentTimeMillis();
    pending = std::async(std::launch::async, [this] { return ownerProcessor.backend().status(); });
    requestKind = RequestKind::status;
}

void TriceratopsAudioProcessorEditor::sendMessage(bool directAction)
{
    if (busyGenerating || (!directAction && !chatBackendReady))
        return;

    const auto message = prompt.getText().trim();
    if (message.isEmpty())
        return;

    prompt.setText("");
    queuedMessage = message;
    queuedChatBackend = selectedChatBackend;
    queuedAction.clear();

    chatTurns.push_back({
        "user",
        message,
        juce::Time::getCurrentTime().formatted("%H:%M:%S"),
        "",
        {}
    });
    currentThinkingSteps.clear();
    lastStateDetail.clear();
    addThinkingStep(ui("Understanding request & observing DAW project context..."));

    busyGenerating = true;
    send.setSpinning(true);
    send.setEnabled(false);
    updateChatDisplay();
}

void TriceratopsAudioProcessorEditor::startChat(const juce::String& message, const juce::String& action)
{
    submittedMessage = message;
    const auto host = ownerProcessor.hostSnapshot();
    const auto selectedMidi = midiPath;
    const auto selectedAudio = audioPath;
    const auto language = chinese ? juce::String("zh") : juce::String("en");
    const auto backend = queuedChatBackend;
    pending = std::async(std::launch::async, [this, message, action, host, selectedMidi, selectedAudio, language, backend] {
        return ownerProcessor.backend().chat(message, host, selectedMidi, selectedAudio, action, language, backend);
    });
    requestKind = RequestKind::chat;
}

void TriceratopsAudioProcessorEditor::addThinkingStep(const juce::String& step)
{
    if (step.isEmpty())
        return;

    auto getBaseText = [](const juce::String& s) -> juce::String {
        int idx = s.lastIndexOf("(");
        if (idx > 0 && s.endsWith("s)"))
            return s.substring(0, idx).trim();
        return s.trim();
    };

    juce::String newBase = getBaseText(step);
    if (!currentThinkingSteps.empty())
    {
        juce::String lastBase = getBaseText(currentThinkingSteps.back());
        if (newBase == lastBase)
        {
            currentThinkingSteps.back() = step;
            updateChatDisplay();
            return;
        }
    }

    currentThinkingSteps.push_back(step);
    updateChatDisplay();
}

void TriceratopsAudioProcessorEditor::handleStatus(const juce::var& value)
{
    if (chatSwitchPending && !deferredChatVerify)
    {
        auto switches = value.getProperty("chat_switches", {});
        auto state = switches.getProperty(ownerProcessor.backend().getSessionId(), {});
        const auto status = state.getProperty("state", "").toString();
        if ((status == "ready" || status == "failed") && state.getProperty("selection", "").toString() == selectedChatBackend)
        {
            chatSwitchPending = false;
            chatBackendReady = status == "ready";
            const auto name = selectedChatBackend == "remote" ? "API" : selectedChatBackend == "local" ? (chinese ? "本地 GPU" : "Local GPU") : (chinese ? "默认模型" : "Default model");
            const auto detail = chatBackendReady ? ((chinese ? "切换完成：" : "Ready: ") + juce::String(name))
                : ((chinese ? "切换失败，请检查设置：" : "Switch failed; check Settings: ") + state.getProperty("error", "").toString());
            chatBackendStatus.setText(detail, juce::dontSendNotification);
            chatBackendStatus.setTooltip(detail);
        }
    }

    auto* object = value.getDynamicObject();
    if (object == nullptr)
    {
        statusLabel.setText(ui("BACKEND OFFLINE"), juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, accentRed);
        if (busyGenerating)
        {
            busyGenerating = false;
            queuedMessage.clear();
            send.setSpinning(false);
            chatTurns.push_back({ "assistant", ui("Backend connection failed. Check the local service and retry."),
                juce::Time::getCurrentTime().formatted("%H:%M:%S"), "", currentThinkingSteps });
            currentThinkingSteps.clear();
            updateChatDisplay();
        }
        send.setEnabled(chatBackendReady);
        prompt.setEnabled(true);
        return;
    }

    if (static_cast<bool>(object->getProperty("setup_required")) && !setupPrompted)
    {
        setupPrompted = true;
        settingsPanel->open(chinese);
    }
    const auto state = object->getProperty("state").toString();
    const auto configJob = object->getProperty("configuration_job");
    const auto* configObject = configJob.getDynamicObject();
    const auto configState = configObject ? configObject->getProperty("state").toString() : juce::String();
    backendConfiguring = configState == "running" || configState == "cancelling";
    const auto busy = static_cast<bool>(object->getProperty("busy")) && !backendConfiguring;
    if (backendConnecting)
    {
        backendConnecting = false;
        connectionBanner.setVisible(false);
        resized();
    }
    statusLabel.setText(busy ? ui("GENERATING...") : ui("AGENT READY"), juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId, busy ? accentBlue : accentGreen);

    const auto detail = object->getProperty("detail").toString();
    progressLabel.setText(ui(detail), juce::dontSendNotification);
    const auto percent = object->getProperty("progress").toString().getDoubleValue();
    progress = juce::jlimit(0.0, 1.0, percent / 100.0);

    const auto response = object->getProperty("reply").toString();
    const auto error = object->getProperty("error").toString();

    if (busy)
    {
        busyGenerating = true;
        send.setSpinning(true);
        send.setEnabled(false);

        juce::String stepText;
        if (detail.isNotEmpty() && detail != lastStateDetail)
        {
            lastStateDetail = detail;
            if (state == "planning" || state == "analyzing_audio")
                stepText = ui("[Observe & Plan] ") + detail;
            else if (state == "loading_model" || state == "sampling")
                stepText = ui("[GPU Model Sampling] ") + detail;
            else if (state == "converting" || state == "verifying" || state == "correcting")
                stepText = ui("[Constraint Verification] ") + detail;
            else
                stepText = ui("[Processing] ") + detail;

            addThinkingStep(stepText);
        }
    }
    else if (busyGenerating && !busy && queuedMessage.isEmpty())
    {
        // The backend is the source of truth: once it reports idle, the
        // generation is finished regardless of any stale state file, so the
        // UI must always leave the "thinking" state here.
        busyGenerating = false;
        send.setSpinning(false);
        send.setEnabled(chatBackendReady && !backendConnecting);

        juce::String finalReply = error.isEmpty() ? response : ui("Operation failed:\n") + error;
        const auto* finalResult = object->getProperty("result").getDynamicObject();
        if (finalResult != nullptr)
        {
            const auto provenance = finalResult->getProperty("context_usage").getProperty("chat_backend", {});
            const auto provider = provenance.getProperty("provider", "").toString();
            if (provider.isNotEmpty())
                finalReply = "[" + juce::String(provider == "remote" ? "API" : "Local GPU") + "]\n" + finalReply;
        }
        const auto finalMidi = finalResult != nullptr
            ? finalResult->getProperty("midi_windows").toString() : juce::String();
        if (finalReply.isNotEmpty() && finalReply != "Ready." && finalReply != ui("Understanding your request..."))
            chatTurns.push_back({
            "assistant",
            finalReply,
            juce::Time::getCurrentTime().formatted("%H:%M:%S"),
            finalMidi,
            currentThinkingSteps
        });
        currentThinkingSteps.clear();
        lastStateDetail.clear();
        updateChatDisplay();
    }

    if (error.isNotEmpty() && busyGenerating)
    {
        busyGenerating = false;
        send.setSpinning(false);
        send.setEnabled(chatBackendReady && !backendConnecting);
        chatTurns.push_back({
            "assistant",
            ui("ERROR EXCEPTION DETAILS:\n----------------------------------------\n") + error + "\n----------------------------------------",
            juce::Time::getCurrentTime().formatted("%H:%M:%S"),
            "",
            currentThinkingSteps
        });
        currentThinkingSteps.clear();
        lastStateDetail.clear();
        updateChatDisplay();
    }

    if (backendConfiguring)
    {
        statusLabel.setText(chinese ? juce::String::fromUTF8("正在配置...") : "CONFIGURING...", juce::dontSendNotification);
        send.setEnabled(false);
        send.setSpinning(false);
        currentThinkingSteps.clear();
    }
    for (auto* button : { &newMusic, &editMidi, &analyze, &continueFour, &moreEnergy, &tightenTiming,
                          &undoBtn, &keepBtn, &rejectBtn, &stems, &audioMidi })
        button->setEnabled(!backendConfiguring && !busy);
    if (!backendConfiguring && !busyGenerating && !backendConnecting) send.setEnabled(chatBackendReady);

    // Process Result Object & Update Score Visualizer
    if (auto* result = object->getProperty("result").getDynamicObject();
        result != nullptr && !busy && queuedMessage.isEmpty())
    {
        if (!busy)
            if (auto* files = result->getProperty("files").getArray())
            {
                const auto stemKey = juce::JSON::toString(result->getProperty("files"), false);
                if (!files->isEmpty() && stemKey != latestStemResult)
                {
                    latestStemResult = stemKey;
                    latestStemFiles = *files;
                    latestResultMidi.clear();
                    if (ownerProcessor.supportsReaperImport() && autoImportToReaper && requestKind != RequestKind::open)
                        deferredAutoImport = true;
                }
            }
        const auto midi = result->getProperty("midi_windows").toString();
        if (midi.isNotEmpty())
        {
            if (midi != latestResultMidi)
            {
                latestResultMidi = midi;
                latestStemResult.clear();
                latestStemFiles.clear();
                midiPath = midi;
                ownerProcessor.loadMidiClip(juce::File(midi));
                midiLabel.setText("MIDI: " + juce::File(midi).getFileName(), juce::dontSendNotification);
                midiLabel.setColour(juce::Label::textColourId, accentGreen);

                // Load and paint score stave visualizer
                scoreStave.loadMidiFile(juce::File(midi));

                if (ownerProcessor.supportsReaperImport() && autoImportToReaper && requestKind != RequestKind::open)
                {
                    // Defer to the timer so the REAPER import request runs on a
                    // background future instead of blocking the message thread.
                    deferredAutoImport = true;
                }
            }
            else
            {
                latestResultMidi = midi;
            }

            // Attach the result file to the most recent assistant message so
            // the chat actually shows which MIDI was produced.
            for (auto turn = chatTurns.rbegin(); turn != chatTurns.rend(); ++turn)
            {
                if (turn->role == "assistant")
                {
                    if (turn->midiPath.isEmpty())
                    {
                        turn->midiPath = midi;
                        updateChatDisplay();
                    }
                    break;
                }
            }
        }
        const auto planPath = result->getProperty("plan_windows").toString();
        if (juce::File(planPath).existsAsFile())
            arrangement.setText(juce::File(planPath).loadFileAsString());
    }

    // Process History Array
    const auto versions = object->getProperty("history");
    if (auto* array = versions.getArray())
    {
        juce::String text;
        for (int index = array->size(); --index >= 0;)
            if (auto* item = array->getReference(index).getDynamicObject())
                text << item->getProperty("time").toString() << "  "
                     << juce::File(item->getProperty("midi_windows").toString()).getFileName() << "\n";
        if (text.isNotEmpty())
            history.setText(text);
    }
}

void TriceratopsAudioProcessorEditor::updateChatDisplay()
{
    chatDisplay.setText("");

    for (const auto& turn : chatTurns)
    {
        if (turn.role == "user")
        {
            chatDisplay.setCaretPosition(chatDisplay.getText().length());
            chatDisplay.insertTextAtCaret("--------------------------------------------------\n");
            chatDisplay.insertTextAtCaret(ui("USER [") + turn.timestamp + "]\n");
            chatDisplay.insertTextAtCaret(turn.message + "\n\n");
        }
        else
        {
            chatDisplay.setCaretPosition(chatDisplay.getText().length());
            chatDisplay.insertTextAtCaret("--------------------------------------------------\n");
            chatDisplay.insertTextAtCaret(ui("TRICERATOPS AGENT [") + turn.timestamp + "]\n");

            if (!turn.thinkingTrace.empty())
            {
                chatDisplay.insertTextAtCaret(ui("Reasoning & Execution Trace:\n"));
                for (size_t i = 0; i < turn.thinkingTrace.size(); ++i)
                {
                    juce::String prefix = (i == turn.thinkingTrace.size() - 1) ? "  \\_ " : "  |- ";
                    chatDisplay.insertTextAtCaret(prefix + ui(turn.thinkingTrace[i]) + "\n");
                }
                chatDisplay.insertTextAtCaret("\n");
            }

            chatDisplay.insertTextAtCaret(ui(turn.message) + "\n");
            if (turn.midiPath.isNotEmpty())
            {
                chatDisplay.insertTextAtCaret(ui("[MIDI Result: ") + juce::File(turn.midiPath).getFileName() + "]\n");
            }
            chatDisplay.insertTextAtCaret("\n");
        }
    }

    if (busyGenerating)
    {
        chatDisplay.setCaretPosition(chatDisplay.getText().length());
        chatDisplay.insertTextAtCaret("--------------------------------------------------\n");
        chatDisplay.insertTextAtCaret(ui("TRICERATOPS AGENT [THINKING & GENERATING...]\n"));
        chatDisplay.insertTextAtCaret(ui("Live Reasoning Stream:\n"));
        if (currentThinkingSteps.empty())
        {
            chatDisplay.insertTextAtCaret(ui("  \\_ [Observe & Plan] Formulating music arrangement strategy...\n"));
        }
        else
        {
            for (size_t i = 0; i < currentThinkingSteps.size(); ++i)
            {
                juce::String prefix = (i == currentThinkingSteps.size() - 1) ? "  \\_ " : "  |- ";
                chatDisplay.insertTextAtCaret(prefix + ui(currentThinkingSteps[i]) + "\n");
            }
        }
        chatDisplay.insertTextAtCaret("\n");
    }

    chatDisplay.moveCaretToEnd();
}

void TriceratopsAudioProcessorEditor::clearChatHistory()
{
    if (busyGenerating)
        return;
    if (requestKind != RequestKind::none)
    {
        deferredClearChat = true;
        return;
    }
    chatTurns.clear();
    currentThinkingSteps.clear();
    chatTurns.push_back({
        "assistant",
        ui("Chat history cleared. Active session reset."),
        juce::Time::getCurrentTime().formatted("%H:%M:%S"),
        "",
        {}
    });
    updateChatDisplay();
    pending = std::async(std::launch::async, [this] { return ownerProcessor.backend().clearChat(); });
    requestKind = RequestKind::clear_chat;
}

void TriceratopsAudioProcessorEditor::cancelCurrentTask()
{
    if (backendConfiguring) { settingsPanel->stopSetup(); return; }
    queuedMessage.clear();
    queuedAction.clear();
    deferredAutoImport = false;
    if (requestKind != RequestKind::none)
    {
        deferredCancel = true;
        return;
    }
    if (busyGenerating)
    {
        pending = std::async(std::launch::async, [this] { return ownerProcessor.backend().cancelTask(); });
        requestKind = RequestKind::status;

        chatTurns.push_back({
            "assistant",
            ui("Stop requested. Waiting for the active tool to finish cancelling."),
            juce::Time::getCurrentTime().formatted("%H:%M:%S"),
            "",
            currentThinkingSteps
        });
        currentThinkingSteps.clear();
        lastStateDetail.clear();
        updateChatDisplay();
    }
    else
    {
        pending = std::async(std::launch::async, [this] { return ownerProcessor.backend().cancelTask(); });
        requestKind = RequestKind::status;
    }
}

void TriceratopsAudioProcessorEditor::importToReaper()
{
    if (requestKind == RequestKind::import_reaper || requestKind == RequestKind::import_receipt)
        return;
    const auto fileToImport = latestStemFiles.isEmpty() ? midiPath : juce::String();
    const juce::var filesToImport(latestStemFiles);
    if (fileToImport.isEmpty() && latestStemFiles.isEmpty())
    {
        chatTurns.push_back({ "assistant", ui("Load or generate MIDI or stems before importing."),
            juce::Time::getCurrentTime().formatted("%H:%M:%S"), "", {} });
        updateChatDisplay();
        return;
    }

    if (!ownerProcessor.supportsReaperImport())
    {
        // AU has no public API to insert a region in Logic's timeline. Reveal
        // the actual output for native drag/import instead of calling REAPER.
        const auto output = fileToImport.isNotEmpty() ? fileToImport
            : latestStemFiles.getFirst().toString();
        juce::File(output).revealToUser();
        return;
    }

    // Never destroy a future that is still running: if another request is in
    // flight, retry once it completes (the timer drives the deferred import).
    if (pending.valid()
        && pending.wait_for(std::chrono::seconds(0)) != std::future_status::ready)
    {
        deferredAutoImport = true;
        return;
    }

   #if JUCE_MAC
    if (!ownerProcessor.canRunReaperScript())
    {
        chatTurns.push_back({ "assistant", ui("REAPER host API is unavailable; no other instance was launched.")
            + "\n" + ownerProcessor.reaperImportDiagnostics(),
            juce::Time::getCurrentTime().formatted("%H:%M:%S"), "", {} });
        updateChatDisplay();
        return;
    }
   #endif
    const auto inHost = ownerProcessor.canRunReaperScript();
    pending = std::async(std::launch::async, [this, fileToImport, filesToImport, inHost] {
        return ownerProcessor.backend().importReaperTrack(fileToImport, filesToImport, inHost);
    });
    requestKind = RequestKind::import_reaper;
    importReaperBtn.setEnabled(false);

    juce::String msg = fileToImport.isNotEmpty()
        ? (ui("Importing ") + juce::File(fileToImport).getFileName() + ui(" into REAPER track..."))
        : ui("Importing separated audio stems into REAPER tracks...");

    chatTurns.push_back({
        "assistant",
        msg + ui("\n(Tip: You can also click and drag 'Drag MIDI' directly onto any track in REAPER!)"),
        juce::Time::getCurrentTime().formatted("%H:%M:%S"),
        fileToImport,
        {}
    });
    updateChatDisplay();
}

void TriceratopsAudioProcessorEditor::chooseMidi()
{
    auto chooser = std::make_shared<juce::FileChooser>(ui("Load MIDI"), juce::File(), "*.mid;*.midi",
                                                    !JucePlugin_Build_AU, false, this);
    const juce::Component::SafePointer<TriceratopsAudioProcessorEditor> safeThis(this);
    chooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles,
                         [safeThis, chooser](const juce::FileChooser& selected) {
        if (safeThis == nullptr)
            return;
        const auto file = selected.getResult();
        if (file.existsAsFile() && safeThis->ownerProcessor.loadMidiClip(file))
        {
            safeThis->midiPath = file.getFullPathName();
            safeThis->latestStemFiles.clear();
            safeThis->midiLabel.setText("MIDI: " + file.getFileName(), juce::dontSendNotification);
            safeThis->midiLabel.setColour(juce::Label::textColourId, accentBlue);
            safeThis->scoreStave.loadMidiFile(file);
        }
    });
}

void TriceratopsAudioProcessorEditor::chooseAudio()
{
    auto chooser = std::make_shared<juce::FileChooser>(ui("Load Audio"), juce::File(), "*.wav;*.flac;*.mp3;*.ogg",
                                                    !JucePlugin_Build_AU, false, this);
    const juce::Component::SafePointer<TriceratopsAudioProcessorEditor> safeThis(this);
    chooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles,
                         [safeThis, chooser](const juce::FileChooser& selected) {
        if (safeThis == nullptr)
            return;
        const auto file = selected.getResult();
        if (file.existsAsFile())
        {
            safeThis->audioPath = file.getFullPathName();
            safeThis->audioLabel.setText("AUDIO: " + file.getFileName(), juce::dontSendNotification);
            safeThis->audioLabel.setColour(juce::Label::textColourId, accentBlue);
        }
    });
}

void TriceratopsAudioProcessorEditor::clearMidi()
{
    ownerProcessor.clearMidiClip();
    midiPath.clear();
    midiLabel.setText(ui("MIDI: None"), juce::dontSendNotification);
    midiLabel.setColour(juce::Label::textColourId, textSub);
    scoreStave.loadMidiFile(juce::File());
}

void TriceratopsAudioProcessorEditor::clearAudio()
{
    audioPath.clear();
    audioLabel.setText(ui("AUDIO: None"), juce::dontSendNotification);
    audioLabel.setColour(juce::Label::textColourId, textSub);
}

void TriceratopsAudioProcessorEditor::dragLatestMidi()
{
    const auto file = juce::File(midiPath);
    if (!file.existsAsFile())
        return;
    const auto started = juce::DragAndDropContainer::performExternalDragDropOfFiles({ midiPath }, false, &dragMidi);
    chatTurns.push_back({ "assistant", started
        ? ui("MIDI file drag started: ") + file.getFileName()
        : ui("Could not start MIDI file drag."),
        juce::Time::getCurrentTime().formatted("%H:%M:%S"), "", {} });
    updateChatDisplay();
}

void TriceratopsAudioProcessorEditor::setStarter(const juce::String& text)
{
    prompt.setText(ui(text));
    prompt.moveCaretToEnd();
    prompt.grabKeyboardFocus();
}

void TriceratopsAudioProcessorEditor::runQuickAction(const juce::String& text, const juce::String& action)
{
    if (busyGenerating)
        return;
    prompt.setText(ui(text));
    sendMessage(action.isNotEmpty());
    queuedAction = action;
}

juce::File TriceratopsAudioProcessorEditor::nextCaptureFile(const juce::String& extension) const
{
   #if JUCE_MAC
    const auto folder = juce::File::getSpecialLocation(juce::File::userHomeDirectory)
                            .getChildFile("Library/Application Support/Triceratops/Captures");
   #else
    const auto folder = juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
                            .getChildFile("Triceratops")
                            .getChildFile("Captures");
   #endif
    folder.createDirectory();
    return folder.getNonexistentChildFile("capture-"
        + juce::Time::getCurrentTime().formatted("%Y%m%d-%H%M%S"), extension, false);
}

void TriceratopsAudioProcessorEditor::toggleMidiCapture()
{
    if (!ownerProcessor.isCapturingMidi())
    {
        ownerProcessor.setCaptureMidi(true);
        capture.setButtonText(ui("Save MIDI"));
        return;
    }

    ownerProcessor.setCaptureMidi(false);
    const auto file = nextCaptureFile(".mid");
    if (ownerProcessor.saveCapturedMidi(file))
    {
        ownerProcessor.loadMidiClip(file);
        latestStemFiles.clear();
        midiPath = file.getFullPathName();
        midiLabel.setText("MIDI: " + file.getFileName(), juce::dontSendNotification);
        midiLabel.setColour(juce::Label::textColourId, accentBlue);
        scoreStave.loadMidiFile(file);
        capture.setButtonText(ui("Capture MIDI"));
    }
    else
    {
        capture.setButtonText(ui("Capture MIDI"));
        chatTurns.push_back({ "assistant", ui("No MIDI notes saved. Check host MIDI routing, the recording point and capture-folder permissions."),
            juce::Time::getCurrentTime().formatted("%H:%M:%S"), "", {} });
        updateChatDisplay();
    }
}

void TriceratopsAudioProcessorEditor::toggleAudioCapture()
{
    if (!ownerProcessor.isCapturingAudio())
    {
        ownerProcessor.startAudioCapture();
        captureAudio.setButtonText(ui("Save audio"));
        return;
    }

    const auto file = nextCaptureFile(".wav");
    if (ownerProcessor.stopAudioCapture(file))
    {
        audioPath = file.getFullPathName();
        audioLabel.setText("AUDIO: " + file.getFileName(), juce::dontSendNotification);
        audioLabel.setColour(juce::Label::textColourId, accentBlue);
    }
    captureAudio.setButtonText(ui("Capture audio"));
}

bool TriceratopsAudioProcessorEditor::isInterestedInFileDrag(const juce::StringArray& files)
{
    for (const auto& path : files)
        if (juce::File(path).hasFileExtension("mid;midi;wav;flac;mp3;ogg"))
            return true;
    return false;
}

void TriceratopsAudioProcessorEditor::filesDropped(const juce::StringArray& files, int, int)
{
    if (files.isEmpty())
        return;
    const juce::File file(files[0]);
    if (file.hasFileExtension("mid;midi"))
    {
        if (!ownerProcessor.loadMidiClip(file))
            return;
        midiPath = file.getFullPathName();
        latestStemFiles.clear();
        midiLabel.setText("MIDI: " + file.getFileName(), juce::dontSendNotification);
        midiLabel.setColour(juce::Label::textColourId, accentBlue);
        scoreStave.loadMidiFile(file);
    }
    else
    {
        audioPath = file.getFullPathName();
        audioLabel.setText("AUDIO: " + file.getFileName(), juce::dontSendNotification);
        audioLabel.setColour(juce::Label::textColourId, accentBlue);
    }
}

juce::File TriceratopsAudioProcessorEditor::languageFile() const
{
   #if JUCE_MAC
    return juce::File::getSpecialLocation(juce::File::userHomeDirectory)
        .getChildFile("Library/Application Support/Triceratops/ui-settings.json");
   #else
    return juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
        .getChildFile("Triceratops/ui-settings.json");
   #endif
}

void TriceratopsAudioProcessorEditor::saveUiSettings() const
{
    auto settings = juce::JSON::parse(languageFile());
    if (settings.getDynamicObject() == nullptr)
        settings = juce::var(new juce::DynamicObject());
    settings.getDynamicObject()->setProperty("language", chinese ? "zh" : "en");
    settings.getDynamicObject()->setProperty("auto_import", autoImportToReaper);
    const auto file = languageFile();
    file.getParentDirectory().createDirectory();
    file.replaceWithText(juce::JSON::toString(settings));
}

void TriceratopsAudioProcessorEditor::applyLanguage()
{
    settingsBtn.setButtonText(chinese ? juce::String::fromUTF8("设置") : "Settings");
    if (settingsPanel) settingsPanel->setChinese(chinese);
    for (auto* button : { &send, &cancel, &clearChatBtn, &autoImportBtn, &importReaperBtn,
        &sidebarToggleBtn, &helpBtn, &newMusic, &editMidi, &analyze, &continueFour, &moreEnergy,
        &tightenTiming, &undoBtn, &keepBtn, &rejectBtn, &stems, &audioMidi, &loadMidi,
        &loadAudio, &playMidi, static_cast<AnimatedButton*>(&dragMidi), &capture, &captureAudio })
    {
        button->setChinese(chinese);
        button->setButtonText(ui(button->getButtonText()));
        button->setTooltip(ui(button->getTooltip()));
    }
    languageBtn.setButtonText(chinese ? "English" : juce::String::fromUTF8("中文"));
    const auto reaperImport = ownerProcessor.supportsReaperImport();
    importReaperBtn.setButtonText(reaperImport ? ui("Import to REAPER") : ui("Show output file"));
    autoImportBtn.setButtonText(reaperImport
        ? (autoImportToReaper ? ui("Auto-Import: ON") : ui("Auto-Import: OFF"))
        : ui("Drag / import into host"));
    autoImportBtn.setEnabled(reaperImport);
    autoImportBtn.setPrimary(reaperImport && autoImportToReaper);
    capture.setEnabled(ownerProcessor.acceptsMidi());
    playMidi.setEnabled(ownerProcessor.producesMidi());
    captureAudio.setEnabled(!ownerProcessor.isMidiEffect());
    captureAudio.setTooltip(ownerProcessor.isMidiEffect()
        ? ui("Record audio with Triceratops Audio in an Audio FX slot.") : juce::String());
    const auto midiHelp = ui("Use Triceratops MIDI in a MIDI FX slot before an instrument.");
    dragMidi.setTooltip(ui("Drag this button into a MIDI track to import the current file."));
    capture.setTooltip(ownerProcessor.acceptsMidi() ? juce::String() : midiHelp);
    playMidi.setTooltip(ownerProcessor.producesMidi() ? juce::String() : midiHelp);
    languageBtn.setTooltip(juce::String::fromUTF8("切换界面语言 / Switch interface language"));
    scoreStave.setChinese(chinese);
    for (auto* label : { &statusLabel, &progressLabel, &connectionBanner, &midiLabel, &audioLabel })
        label->setText(ui(label->getText()), juce::dontSendNotification);
    prompt.setTextToShowWhenEmpty(ui("Say anything: sad piano, continue this, more energy, analyze it..."), textSub.withAlpha(0.6f));
    arrangement.setText(ui(arrangement.getText()));
    history.setText(ui(history.getText()));
    updateChatDisplay();
    repaint();
}
