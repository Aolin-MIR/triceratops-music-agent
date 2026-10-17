#pragma once

#include <JuceHeader.h>
#include <future>
#include "PluginProcessor.h"
#include "UiStrings.h"

class AnimatedButton : public juce::TextButton, private juce::Timer
{
public:
    explicit AnimatedButton(const juce::String& text, bool primary = false);
    void paintButton(juce::Graphics&, bool highlighted, bool down) override;
    void mouseEnter(const juce::MouseEvent&) override;
    void mouseExit(const juce::MouseEvent&) override;
    void mouseDown(const juce::MouseEvent&) override;
    void mouseUp(const juce::MouseEvent&) override;
    void setPrimary(bool isPrimary) { isPrimaryStyle = isPrimary; repaint(); }
    void setSpinning(bool spinning) { isSpinning = spinning; repaint(); }
    bool getSpinning() const noexcept { return isSpinning; }
    void setChinese(bool value) { chinese = value; repaint(); }

private:
    juce::String ui(const juce::String& value) const { return triceratopsUi(value, chinese); }
    bool chinese = false;
    void timerCallback() override;
    float amount = 0.0f, target = 0.0f;
    float spinnerAngle = 0.0f;
    bool isPrimaryStyle = false;
    bool isSpinning = false;
};

class MidiDragButton final : public AnimatedButton
{
public:
    explicit MidiDragButton(const juce::String& text) : AnimatedButton(text) {}
    std::function<void()> onFileDrag;
    void mouseDown(const juce::MouseEvent& event) override
    {
        AnimatedButton::mouseDown(event);
        // Native drag sessions need the live down/drag event, never onClick's
        // mouse-up event. Starting while held also works in Logic's AU view bridge.
        if (event.mods.isLeftButtonDown() && onFileDrag)
            onFileDrag();
    }
};

struct ChatTurn
{
    juce::String role; // "user" or "assistant"
    juce::String message;
    juce::String timestamp;
    juce::String midiPath;
    std::vector<juce::String> thinkingTrace;
};

class ScoreStaveComponent final : public juce::Component
{
public:
    ScoreStaveComponent();
    void loadMidiFile(const juce::File& file);
    void paint(juce::Graphics& g) override;
    void setChinese(bool value) { chinese = value; repaint(); }

private:
    juce::String ui(const juce::String& value) const { return triceratopsUi(value, chinese); }
    bool chinese = false;
    struct SimpleNote { int pitch; double time; };
    std::vector<SimpleNote> notes;
};

class TriceratopsAudioProcessorEditor final : public juce::AudioProcessorEditor,
                                               public juce::FileDragAndDropTarget,
                                               private juce::Timer
{
public:
    explicit TriceratopsAudioProcessorEditor(TriceratopsAudioProcessor&);
    ~TriceratopsAudioProcessorEditor() override;
    void paint(juce::Graphics&) override;
    void resized() override;
    bool isInterestedInFileDrag(const juce::StringArray&) override;
    void filesDropped(const juce::StringArray&, int, int) override;

private:
    juce::String ui(const juce::String& value) const { return triceratopsUi(value, chinese); }
    juce::File languageFile() const;
    void saveUiSettings() const;
    void applyLanguage();
    void timerCallback() override;
    void sendMessage();
    void pollStatus();
    void handleStatus(const juce::var&);
    void chooseMidi();
    void chooseAudio();
    void clearMidi();
    void clearAudio();
    void dragLatestMidi();
    void importToReaper();
    void clearChatHistory();
    void cancelCurrentTask();
    void updateChatDisplay();
    void addThinkingStep(const juce::String& step);
    void setStarter(const juce::String&);
    void runQuickAction(const juce::String&, const juce::String& action = {});
    void startChat(const juce::String& message, const juce::String& action);
    void toggleMidiCapture();
    void toggleAudioCapture();
    juce::File nextCaptureFile(const juce::String& extension) const;

    enum class RequestKind { none, open, status, chat, clear_chat, import_reaper, import_receipt };

    TriceratopsAudioProcessor& ownerProcessor;

    // Chat stream & sidebar controls
    juce::TextEditor chatDisplay, prompt, arrangement, history;
    juce::Label statusLabel, progressLabel, warmupBanner, midiLabel, audioLabel;
    juce::ProgressBar progressBar;
    ScoreStaveComponent scoreStave;

    double progress = 0.0;
    float eqPhase = 0.0f;

    AnimatedButton languageBtn { "中文" }, send { "Send", true }, cancel { "Stop", false },
                   clearChatBtn { "Clear Chat" }, autoImportBtn { "Auto-Import: ON", true },
                   importReaperBtn { "Import to REAPER", true },
                   sidebarToggleBtn { "Plan / History" },
                   newMusic { "New score" }, editMidi { "Edit MIDI" },
                   analyze { "Analyze" }, continueFour { "Continue 4 bars" },
                   moreEnergy { "More energy" }, tightenTiming { "Tighten timing" },
                   undoBtn { "Undo" }, keepBtn { "Keep" }, rejectBtn { "Reject" },
                   stems { "Stem split" },
                   audioMidi { "Audio -> MIDI" }, loadMidi { "Load MIDI" },
                   loadAudio { "Load audio" }, clearMidiBtn { "x" }, clearAudioBtn { "x" },
                   playMidi { "Play VST" },
                   capture { "Rec MIDI" }, captureAudio { "Rec audio" };
    MidiDragButton dragMidi { "Drag MIDI" };

    juce::String midiPath, audioPath, latestResultMidi, latestStemResult;
    juce::Array<juce::var> latestStemFiles;
    juce::String queuedMessage;
    juce::String queuedAction;
    std::future<juce::var> pending;
    RequestKind requestKind = RequestKind::none;
    juce::int64 lastStatusPollMs = 0;
    juce::int64 warmupStartMs = 0;
    juce::int64 visibleSinceMs = 0;

    bool modelIsWarmingUp = true;
    bool chinese = juce::SystemStats::getUserLanguage().startsWithIgnoreCase("zh");
    bool sessionStartupRequested = false;
    bool sessionOpened = false;
    bool autoImportToReaper = true;
    bool showSidebar = true;
    bool busyGenerating = false;
    bool deferredAutoImport = false;
    bool deferredCancel = false;
    bool deferredClearChat = false;
    std::vector<ChatTurn> chatTurns;
    std::vector<juce::String> currentThinkingSteps;
    juce::String lastStateDetail;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TriceratopsAudioProcessorEditor)
};
