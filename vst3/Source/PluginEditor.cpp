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
const juce::Colour warmupBg       { 0xff2a2318 };
const juce::Colour warmupText     { 0xffe0af68 };
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
    g.drawText("SCORE STAVE VISUALIZER", bounds.reduced(12, 8).removeFromTop(18).toNearestInt(), juce::Justification::centredLeft);

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
        g.drawText("No musical score generated yet.", staveArea.toNearestInt(), juce::Justification::centred);
        return;
    }

    // Draw notes on stave
    float noteStartX = staveArea.getX() + 45.0f;
    float availableW = staveArea.getWidth() - 60.0f;
    size_t maxNotes = std::min(notes.size(), size_t(24));
    float stepX = availableW / std::max(1.0f, float(maxNotes));

    g.setColour(accentCyan);
    for (size_t i = 0; i < maxNotes; ++i)
    {
        int pitch = notes[i].pitch;
        float pitchOffset = (pitch - 64) * (lineSpacing * 0.5f);
        float noteY = (startY + 4 * lineSpacing) - pitchOffset;
        float noteX = noteStartX + i * stepX;

        // Notehead
        g.fillEllipse(noteX - 4.0f, noteY - 3.0f, 8.0f, 6.0f);

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
    amount += (target - amount) * 0.22f;
    if (isSpinning)
        spinnerAngle += 0.18f;
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
        g.drawText("Thinking...", bounds.withTrimmedRight(32).toNearestInt(), juce::Justification::centred, true);
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
    if (getButtonText().contains("Stop") || getButtonText().contains("Clear"))
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
    setSize(1180, 780);
    setResizable(true, true);
    setResizeLimits(900, 650, 1920, 1200);

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
    chatDisplay.setReadOnly(true);
    prompt.setTextToShowWhenEmpty("Say anything: sad piano, continue this, more energy, analyze it...", textSub.withAlpha(0.6f));
    arrangement.setReadOnly(true);
    arrangement.setText("Score Arrangement Plan will appear here.");
    history.setReadOnly(true);
    history.setText("Version history in this project session will appear here.");

    // Setup Labels & Components
    for (auto* label : { &statusLabel, &progressLabel, &warmupBanner, &midiLabel, &audioLabel })
    {
        label->setColour(juce::Label::textColourId, textMain);
        label->setFont(juce::FontOptions(13.0f, juce::Font::bold));
        addAndMakeVisible(label);
    }
    statusLabel.setText("WARMING UP MODEL", juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId, accentBlue);
    progressLabel.setText("Local GPU Model Service", juce::dontSendNotification);

    warmupBanner.setText("AI Model Warmup / Caching... Please wait (Model Caching... Generation Paused)", juce::dontSendNotification);
    warmupBanner.setColour(juce::Label::backgroundColourId, warmupBg);
    warmupBanner.setColour(juce::Label::textColourId, warmupText);
    warmupBanner.setColour(juce::Label::outlineColourId, warmupText.withAlpha(0.4f));
    warmupBanner.setJustificationType(juce::Justification::centred);

    midiLabel.setText("MIDI: None", juce::dontSendNotification);
    audioLabel.setText("AUDIO: None", juce::dontSendNotification);
    midiLabel.setColour(juce::Label::textColourId, textSub);
    audioLabel.setColour(juce::Label::textColourId, textSub);

    addAndMakeVisible(progressBar);
    addAndMakeVisible(scoreStave);

    // Setup Buttons
    for (auto* button : { &send, &cancel, &clearChatBtn, &autoImportBtn, &importReaperBtn, &sidebarToggleBtn,
                          &newMusic, &editMidi, &analyze, &continueFour, &moreEnergy, &tightenTiming,
                          &undoBtn, &keepBtn, &rejectBtn, &stems, &audioMidi,
                          &loadMidi, &loadAudio, &clearMidiBtn, &clearAudioBtn,
                          &playMidi, &dragMidi, &capture, &captureAudio })
        addAndMakeVisible(button);

    send.onClick          = [this] { sendMessage(); };
    cancel.onClick        = [this] { cancelCurrentTask(); };
    clearChatBtn.onClick  = [this] { clearChatHistory(); };
    autoImportBtn.onClick = [this] {
        autoImportToReaper = !autoImportToReaper;
        autoImportBtn.setButtonText(autoImportToReaper ? "Auto-Import: ON" : "Auto-Import: OFF");
        autoImportBtn.setPrimary(autoImportToReaper);
    };
    importReaperBtn.onClick = [this] { importToReaper(); };
    sidebarToggleBtn.onClick = [this] { showSidebar = !showSidebar; resized(); };

    newMusic.onClick      = [this] { setStarter("Create music: "); };
    editMidi.onClick      = [this] { setStarter("Change this MIDI: "); };
    analyze.onClick       = [this] { runQuickAction("Analyze what I loaded and explain the most useful musical details."); };
    continueFour.onClick  = [this] { runQuickAction("Continue the loaded MIDI for four bars, keeping its musical identity."); };
    moreEnergy.onClick    = [this] { runQuickAction("Make the loaded MIDI more energetic while keeping the main melody."); };
    tightenTiming.onClick = [this] { runQuickAction("Tighten the timing of the loaded MIDI without changing its notes."); };
    undoBtn.onClick       = [this] { runQuickAction("Undo the last MIDI change."); };
    keepBtn.onClick       = [this] { runQuickAction("Keep this version. I like it."); };
    rejectBtn.onClick     = [this] { runQuickAction("Reject this version and remember that I do not like it."); };
    stems.onClick         = [this] { runQuickAction("Split the loaded audio into stems."); };
    audioMidi.onClick     = [this] { runQuickAction("Convert the loaded audio to MIDI."); };

    continueFour.setTooltip("Generate a four-bar continuation from the loaded MIDI");
    moreEnergy.setTooltip("Increase musical energy while preserving the melody");
    tightenTiming.setTooltip("Quantize the loaded MIDI to a tighter grid");
    keepBtn.setTooltip("Accept this result and remember the preference");
    rejectBtn.setTooltip("Reject this result and remember the feedback");

    loadMidi.onClick  = [this] { chooseMidi(); };
    loadAudio.onClick = [this] { chooseAudio(); };
    clearMidiBtn.onClick  = [this] { clearMidi(); };
    clearAudioBtn.onClick = [this] { clearAudio(); };

    playMidi.onClick  = [this] { ownerProcessor.armGeneratedClip(); };
    dragMidi.onClick  = [this] { dragLatestMidi(); };
    capture.onClick   = [this] { toggleMidiCapture(); };
    captureAudio.onClick = [this] { toggleAudioCapture(); };

    // Initial button state during warmup
    send.setEnabled(false);
    prompt.setEnabled(false);

    // Initial welcoming chat message
    warmupStartMs = juce::Time::currentTimeMillis();
    chatTurns.push_back({
        "assistant",
        "Welcome to Triceratops Music Agent!\n"
        "Opening plugin session... Continuing saved conversation.\n"
        "Model worker is warming up GPU cache. Please wait...",
        juce::Time::getCurrentTime().formatted("%H:%M:%S"),
        "",
        {}
    });
    updateChatDisplay();

    startTimer(100);
    pending = std::async(std::launch::async, [this] { return ownerProcessor.backend().openSession(); });
    requestKind = RequestKind::open;
}

TriceratopsAudioProcessorEditor::~TriceratopsAudioProcessorEditor()
{
    stopTimer();
    if (pending.valid())
        pending.wait();
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

    // Title branding
    g.setColour(accentBlue);
    g.setFont(juce::FontOptions(18.0f, juce::Font::bold));
    g.drawText("TRICERATOPS", 16, 0, 140, 48, juce::Justification::centredLeft);

    // Equalizer spectrum bars
    float eqX = 155.0f;
    float eqY = 16.0f;
    float eqH = 16.0f;
    eqPhase += 0.08f;

    g.setColour(accentPurple.withAlpha(0.85f));
    for (int i = 0; i < 6; ++i)
    {
        float fi = static_cast<float>(i);
        float barH = (busyGenerating || modelIsWarmingUp)
            ? (5.0f + 9.0f * std::sin(eqPhase + fi * 0.9f) * std::sin(eqPhase * 0.5f + fi))
            : (4.0f + 2.0f * std::sin(fi * 1.2f));
        barH = juce::jlimit(3.0f, 16.0f, std::abs(barH));
        g.fillRoundedRectangle(eqX + fi * 4.5f, eqY + (eqH - barH) * 0.5f, 2.5f, barH, 1.2f);
    }

    g.setFont(juce::FontOptions(11.0f, juce::Font::bold));
    g.setColour(textSub);
    g.drawText("LOCAL AI AGENT", 190, 0, 110, 48, juce::Justification::centredLeft);
}

void TriceratopsAudioProcessorEditor::resized()
{
    auto area = getLocalBounds();
    auto header = area.removeFromTop(48).reduced(12, 6);

    header.removeFromLeft(290);
    statusLabel.setBounds(header.removeFromLeft(170));

    sidebarToggleBtn.setBounds(header.removeFromRight(120).reduced(2, 0));
    autoImportBtn.setBounds(header.removeFromRight(140).reduced(2, 0));
    clearChatBtn.setBounds(header.removeFromRight(100).reduced(2, 0));

    if (modelIsWarmingUp)
        warmupBanner.setBounds(area.removeFromTop(32).reduced(12, 2));
    else
        warmupBanner.setBounds(0, 0, 0, 0);

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
    auto inputDock = mainArea.removeFromTop(82);
    auto bottomDock = mainArea.removeFromBottom(36);
    auto progressRow = mainArea.removeFromBottom(28);

    progressLabel.setBounds(progressRow.removeFromLeft(200));
    progressBar.setBounds(progressRow.reduced(4, 6));

    chatDisplay.setBounds(mainArea.reduced(0, 4));

    auto row2 = quickDock.removeFromTop(36);
    const int modeWidth = row2.getWidth() / 6;
    auto placePill = [&row2, modeWidth](juce::Component& btn) {
        btn.setBounds(row2.removeFromLeft(modeWidth).reduced(2, 4));
    };
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
    dragMidi.setBounds(row1.removeFromRight(85).reduced(2, 2));

    auto row4 = inputDock.reduced(0, 2);
    auto sendArea = row4.removeFromRight(140);
    send.setBounds(sendArea.removeFromTop(44).reduced(3, 2));
    cancel.setBounds(sendArea.reduced(3, 2));
    prompt.setBounds(row4.reduced(2, 2));
}

void TriceratopsAudioProcessorEditor::timerCallback()
{
    repaint();

    if (requestKind != RequestKind::none && pending.valid()
        && pending.wait_for(std::chrono::seconds(0)) == std::future_status::ready)
    {
        handleStatus(pending.get());
        requestKind = RequestKind::none;
    }

    if (requestKind == RequestKind::none && queuedMessage.isNotEmpty())
    {
        const auto message = queuedMessage;
        queuedMessage.clear();
        startChat(message);
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

void TriceratopsAudioProcessorEditor::sendMessage()
{
    if (busyGenerating)
        return;

    const auto message = prompt.getText().trim();
    if (message.isEmpty())
        return;

    prompt.setText("");
    queuedMessage = message;

    chatTurns.push_back({
        "user",
        message,
        juce::Time::getCurrentTime().formatted("%H:%M:%S"),
        "",
        {}
    });
    currentThinkingSteps.clear();
    lastStateDetail.clear();
    latestResultMidi.clear();
    addThinkingStep("Understanding request & observing DAW project context...");

    busyGenerating = true;
    send.setSpinning(true);
    send.setEnabled(false);
    updateChatDisplay();
}

void TriceratopsAudioProcessorEditor::startChat(const juce::String& message)
{
    pending = std::async(std::launch::async, [this, message] {
        return ownerProcessor.backend().chat(message, ownerProcessor.hostSnapshot(), midiPath, audioPath);
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
    auto* object = value.getDynamicObject();
    if (object == nullptr)
    {
        statusLabel.setText("BACKEND OFFLINE", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, accentRed);
        return;
    }

    const auto state = object->getProperty("state").toString();
    const auto worker = object->getProperty("worker_state").toString();
    const auto busy = static_cast<bool>(object->getProperty("busy"));
    const auto workerIsLoading = (worker == "loading");
    const auto workerHasError   = (worker == "error");

    if (warmupStartMs == 0 && workerIsLoading)
        warmupStartMs = juce::Time::currentTimeMillis();

    if (!busy && workerIsLoading)
    {
        if (!modelIsWarmingUp)
        {
            modelIsWarmingUp = true;
            warmupBanner.setVisible(true);
            send.setEnabled(true);
            prompt.setEnabled(true);
            resized();
        }
        int elapsedSec = static_cast<int>((juce::Time::currentTimeMillis() - warmupStartMs) / 1000);
        statusLabel.setText("WARMING UP MODEL", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, warmupText);
        warmupBanner.setText("AI Model Warmup / Caching... Please wait (GPU Caching... " + juce::String(elapsedSec) + "s elapsed)", juce::dontSendNotification);
    }
    else if (workerHasError && modelIsWarmingUp)
    {
        modelIsWarmingUp = false;
        warmupBanner.setVisible(false);
        send.setSpinning(false);
        send.setEnabled(true);
        prompt.setEnabled(true);
        statusLabel.setText("WARMUP ERROR", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, accentRed);
        resized();

        juce::String errDetail = object->getProperty("worker_detail").toString();
        if (errDetail.isEmpty())
            errDetail = "Local GPU model service failed to initialize.";

        chatTurns.push_back({
            "assistant",
            "MODEL WARMUP ERROR EXCEPTION DETAILS:\n----------------------------------------\n" + errDetail + "\n----------------------------------------",
            juce::Time::getCurrentTime().formatted("%H:%M:%S"),
            "",
            {}
        });
        updateChatDisplay();
    }
    else if (modelIsWarmingUp && (worker == "ready" || (!workerIsLoading && !workerHasError)))
    {
        modelIsWarmingUp = false;
        warmupBanner.setVisible(false);
        send.setSpinning(false);
        send.setEnabled(!busyGenerating);
        prompt.setEnabled(true);
        statusLabel.setText("AGENT READY", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, accentGreen);
        resized();
    }
    else if (busy)
    {
        statusLabel.setText("GENERATING...", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, accentBlue);
    }
    else if (!workerHasError)
    {
        statusLabel.setText("AGENT READY", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, accentGreen);
    }

    auto detail = object->getProperty("detail").toString();
    const auto workerDetail = object->getProperty("worker_detail").toString();
    const auto workerProg = object->getProperty("worker_progress").toString().getDoubleValue();

    if (!busy && workerIsLoading)
    {
        int elapsedSec = static_cast<int>((juce::Time::currentTimeMillis() - warmupStartMs) / 1000);
        juce::String msg = workerDetail.isNotEmpty() ? workerDetail : "Warming local GPU notation model...";
        detail = msg + " (" + juce::String(elapsedSec) + "s elapsed)";
    }
    if (detail.isNotEmpty())
        progressLabel.setText(detail, juce::dontSendNotification);

    const auto percent = object->getProperty("progress").toString().getDoubleValue();
    if (!busy && workerIsLoading)
    {
        int elapsedSec = static_cast<int>((juce::Time::currentTimeMillis() - warmupStartMs) / 1000);
        if (workerProg > 0.0)
            progress = juce::jlimit(0.05, 0.95, workerProg / 100.0);
        else
            progress = juce::jlimit(0.05, 0.95, elapsedSec / 25.0);
    }
    else
    {
        progress = juce::jlimit(0.0, 1.0, percent / 100.0);
    }

    const auto response = object->getProperty("reply").toString();

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
                stepText = "[Observe & Plan] " + detail;
            else if (state == "loading_model" || state == "sampling")
                stepText = "[GPU Model Sampling] " + detail;
            else if (state == "converting" || state == "verifying" || state == "correcting")
                stepText = "[Constraint Verification] " + detail;
            else
                stepText = "[Processing] " + detail;

            addThinkingStep(stepText);
        }
    }
    else if (busyGenerating && !busy && response.isNotEmpty()
             && response != "Ready." && response != "Understanding your request...")
    {
        // The backend is the source of truth: once it reports idle, the
        // generation is finished regardless of any stale state file, so the
        // UI must always leave the "thinking" state here.
        busyGenerating = false;
        send.setSpinning(false);
        send.setEnabled(!modelIsWarmingUp);

        juce::String finalReply = response;
        chatTurns.push_back({
            "assistant",
            finalReply,
            juce::Time::getCurrentTime().formatted("%H:%M:%S"),
            latestResultMidi,
            currentThinkingSteps
        });
        currentThinkingSteps.clear();
        lastStateDetail.clear();
        updateChatDisplay();
    }

    const auto error = object->getProperty("error").toString();
    if (error.isNotEmpty() && busyGenerating)
    {
        busyGenerating = false;
        send.setSpinning(false);
        send.setEnabled(!modelIsWarmingUp);
        chatTurns.push_back({
            "assistant",
            "ERROR EXCEPTION DETAILS:\n----------------------------------------\n" + error + "\n----------------------------------------",
            juce::Time::getCurrentTime().formatted("%H:%M:%S"),
            "",
            currentThinkingSteps
        });
        currentThinkingSteps.clear();
        lastStateDetail.clear();
        updateChatDisplay();
    }

    // Process Result Object & Update Score Visualizer
    if (auto* result = object->getProperty("result").getDynamicObject())
    {
        const auto midi = result->getProperty("midi_windows").toString();
        if (midi.isNotEmpty())
        {
            if (midi != latestResultMidi)
            {
                latestResultMidi = midi;
                midiPath = midi;
                ownerProcessor.loadMidiClip(juce::File(midi));
                midiLabel.setText("MIDI: " + juce::File(midi).getFileName(), juce::dontSendNotification);
                midiLabel.setColour(juce::Label::textColourId, accentGreen);

                // Load and paint score stave visualizer
                scoreStave.loadMidiFile(juce::File(midi));

                if (autoImportToReaper)
                {
                    // Defer to the timer so the REAPER import request runs on a
                    // background future instead of blocking the message thread.
                    deferredAutoImport = true;
                }
            }
            else
            {
                latestResultMidi = midi;
                if (midiPath.isEmpty())
                    midiPath = midi;
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
            chatDisplay.insertTextAtCaret("USER [" + turn.timestamp + "]\n");
            chatDisplay.insertTextAtCaret(turn.message + "\n\n");
        }
        else
        {
            chatDisplay.setCaretPosition(chatDisplay.getText().length());
            chatDisplay.insertTextAtCaret("--------------------------------------------------\n");
            chatDisplay.insertTextAtCaret("TRICERATOPS AGENT [" + turn.timestamp + "]\n");

            if (!turn.thinkingTrace.empty())
            {
                chatDisplay.insertTextAtCaret("Reasoning & Execution Trace:\n");
                for (size_t i = 0; i < turn.thinkingTrace.size(); ++i)
                {
                    juce::String prefix = (i == turn.thinkingTrace.size() - 1) ? "  \\_ " : "  |- ";
                    chatDisplay.insertTextAtCaret(prefix + turn.thinkingTrace[i] + "\n");
                }
                chatDisplay.insertTextAtCaret("\n");
            }

            chatDisplay.insertTextAtCaret(turn.message + "\n");
            if (turn.midiPath.isNotEmpty())
            {
                chatDisplay.insertTextAtCaret("[MIDI Result: " + juce::File(turn.midiPath).getFileName() + "]\n");
            }
            chatDisplay.insertTextAtCaret("\n");
        }
    }

    if (busyGenerating)
    {
        chatDisplay.setCaretPosition(chatDisplay.getText().length());
        chatDisplay.insertTextAtCaret("--------------------------------------------------\n");
        chatDisplay.insertTextAtCaret("TRICERATOPS AGENT [THINKING & GENERATING...]\n");
        chatDisplay.insertTextAtCaret("Live Reasoning Stream:\n");
        if (currentThinkingSteps.empty())
        {
            chatDisplay.insertTextAtCaret("  \\_ [Observe & Plan] Formulating music arrangement strategy...\n");
        }
        else
        {
            for (size_t i = 0; i < currentThinkingSteps.size(); ++i)
            {
                juce::String prefix = (i == currentThinkingSteps.size() - 1) ? "  \\_ " : "  |- ";
                chatDisplay.insertTextAtCaret(prefix + currentThinkingSteps[i] + "\n");
            }
        }
        chatDisplay.insertTextAtCaret("\n");
    }

    chatDisplay.moveCaretToEnd();
}

void TriceratopsAudioProcessorEditor::clearChatHistory()
{
    chatTurns.clear();
    currentThinkingSteps.clear();
    chatTurns.push_back({
        "assistant",
        "Chat history cleared. Active session reset.",
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
    if (busyGenerating)
    {
        busyGenerating = false;
        send.setSpinning(false);
        send.setEnabled(!modelIsWarmingUp);
        pending = std::async(std::launch::async, [this] { return ownerProcessor.backend().cancelTask(); });
        requestKind = RequestKind::status;

        chatTurns.push_back({
            "assistant",
            "Stop requested. Active generation task cancelled.",
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
    juce::String fileToImport = latestResultMidi;
    if (fileToImport.isEmpty())
        fileToImport = midiPath;

    // Never destroy a future that is still running: if another request is in
    // flight, retry once it completes (the timer drives the deferred import).
    if (pending.valid()
        && pending.wait_for(std::chrono::seconds(0)) != std::future_status::ready)
    {
        deferredAutoImport = true;
        return;
    }

    pending = std::async(std::launch::async, [this, fileToImport] {
        return ownerProcessor.backend().importReaperTrack(fileToImport);
    });
    requestKind = RequestKind::import_reaper;

    juce::String msg = fileToImport.isNotEmpty()
        ? ("Importing " + juce::File(fileToImport).getFileName() + " into REAPER track...")
        : "Importing latest generated MIDI clip into REAPER track...";

    chatTurns.push_back({
        "assistant",
        msg + "\n(Tip: You can also click and drag 'Drag MIDI' directly onto any track in REAPER!)",
        juce::Time::getCurrentTime().formatted("%H:%M:%S"),
        fileToImport,
        {}
    });
    updateChatDisplay();
}

void TriceratopsAudioProcessorEditor::chooseMidi()
{
    auto chooser = std::make_shared<juce::FileChooser>("Load MIDI", juce::File(), "*.mid;*.midi");
    chooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles,
                         [this, chooser](const juce::FileChooser& selected) {
        const auto file = selected.getResult();
        if (file.existsAsFile() && ownerProcessor.loadMidiClip(file))
        {
            midiPath = file.getFullPathName();
            midiLabel.setText("MIDI: " + file.getFileName(), juce::dontSendNotification);
            midiLabel.setColour(juce::Label::textColourId, accentBlue);
            scoreStave.loadMidiFile(file);
        }
    });
}

void TriceratopsAudioProcessorEditor::chooseAudio()
{
    auto chooser = std::make_shared<juce::FileChooser>("Load Audio", juce::File(), "*.wav;*.flac;*.mp3;*.ogg");
    chooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles,
                         [this, chooser](const juce::FileChooser& selected) {
        const auto file = selected.getResult();
        if (file.existsAsFile())
        {
            audioPath = file.getFullPathName();
            audioLabel.setText("AUDIO: " + file.getFileName(), juce::dontSendNotification);
            audioLabel.setColour(juce::Label::textColourId, accentBlue);
        }
    });
}

void TriceratopsAudioProcessorEditor::clearMidi()
{
    midiPath.clear();
    midiLabel.setText("MIDI: None", juce::dontSendNotification);
    midiLabel.setColour(juce::Label::textColourId, textSub);
    scoreStave.loadMidiFile(juce::File());
}

void TriceratopsAudioProcessorEditor::clearAudio()
{
    audioPath.clear();
    audioLabel.setText("AUDIO: None", juce::dontSendNotification);
    audioLabel.setColour(juce::Label::textColourId, textSub);
}

void TriceratopsAudioProcessorEditor::dragLatestMidi()
{
    if (juce::File(latestResultMidi).existsAsFile())
        juce::DragAndDropContainer::performExternalDragDropOfFiles({ latestResultMidi }, false, this);
}

void TriceratopsAudioProcessorEditor::setStarter(const juce::String& text)
{
    prompt.setText(text);
    prompt.moveCaretToEnd();
    prompt.grabKeyboardFocus();
}

void TriceratopsAudioProcessorEditor::runQuickAction(const juce::String& text)
{
    if (busyGenerating)
        return;
    prompt.setText(text);
    sendMessage();
}

juce::File TriceratopsAudioProcessorEditor::nextCaptureFile(const juce::String& extension) const
{
    const auto folder = juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
                            .getChildFile("Triceratops")
                            .getChildFile("Captures");
    folder.createDirectory();
    return folder.getChildFile("capture-"
        + juce::Time::getCurrentTime().formatted("%Y%m%d-%H%M%S") + extension);
}

void TriceratopsAudioProcessorEditor::toggleMidiCapture()
{
    if (!ownerProcessor.isCapturingMidi())
    {
        ownerProcessor.setCaptureMidi(true);
        capture.setButtonText("Save MIDI");
        return;
    }

    ownerProcessor.setCaptureMidi(false);
    const auto file = nextCaptureFile(".mid");
    if (ownerProcessor.saveCapturedMidi(file))
    {
        midiPath = file.getFullPathName();
        midiLabel.setText("MIDI: " + file.getFileName(), juce::dontSendNotification);
        midiLabel.setColour(juce::Label::textColourId, accentBlue);
        scoreStave.loadMidiFile(file);
        capture.setButtonText("Capture MIDI");
    }
    else
    {
        capture.setButtonText("Capture MIDI");
    }
}

void TriceratopsAudioProcessorEditor::toggleAudioCapture()
{
    if (!ownerProcessor.isCapturingAudio())
    {
        ownerProcessor.startAudioCapture();
        captureAudio.setButtonText("Save audio");
        return;
    }

    const auto file = nextCaptureFile(".wav");
    if (ownerProcessor.stopAudioCapture(file))
    {
        audioPath = file.getFullPathName();
        audioLabel.setText("AUDIO: " + file.getFileName(), juce::dontSendNotification);
        audioLabel.setColour(juce::Label::textColourId, accentBlue);
    }
    captureAudio.setButtonText("Capture audio");
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
        midiPath = file.getFullPathName();
        ownerProcessor.loadMidiClip(file);
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
