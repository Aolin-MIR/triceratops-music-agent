#pragma once

#include <JuceHeader.h>
#include <future>
#include "PluginProcessor.h"

class AnimatedButton final : public juce::TextButton, private juce::Timer
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

private:
    void timerCallback() override;
    float amount = 0.0f, target = 0.0f;
    float spinnerAngle = 0.0f;
    bool isPrimaryStyle = false;
    bool isSpinning = false;
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

private:
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
    void runQuickAction(const juce::String&);
    void startChat(const juce::String& message);
    void toggleMidiCapture();
    void toggleAudioCapture();
    juce::File nextCaptureFile(const juce::String& extension) const;

    enum class RequestKind { none, open, status, chat, clear_chat, import_reaper };

    TriceratopsAudioProcessor& ownerProcessor;

    // Chat stream & sidebar controls
    juce::TextEditor chatDisplay, prompt, arrangement, history;
    juce::Label statusLabel, progressLabel, warmupBanner, midiLabel, audioLabel;
    juce::ProgressBar progressBar;
    ScoreStaveComponent scoreStave;

    double progress = 0.0;
    float eqPhase = 0.0f;

    AnimatedButton send { "Send", true }, cancel { "Stop", false },
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
                   playMidi { "Play VST" }, dragMidi { "Drag MIDI" },
                   capture { "Rec MIDI" }, captureAudio { "Rec audio" };

    juce::String midiPath, audioPath, latestResultMidi;
    juce::String queuedMessage;
    std::future<juce::var> pending;
    RequestKind requestKind = RequestKind::none;
    juce::int64 lastStatusPollMs = 0;
    juce::int64 warmupStartMs = 0;

    bool modelIsWarmingUp = true;
    bool autoImportToReaper = true;
    bool showSidebar = true;
    bool busyGenerating = false;
    bool deferredAutoImport = false;
    std::vector<ChatTurn> chatTurns;
    std::vector<juce::String> currentThinkingSteps;
    juce::String lastStateDetail;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TriceratopsAudioProcessorEditor)
};
