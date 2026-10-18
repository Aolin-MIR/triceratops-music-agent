#pragma once

#include <JuceHeader.h>
#include <future>
#include "PluginProcessor.h"
#include "UiStrings.h"
#include "SettingsPanel.h"

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
        dragStarted = false;
    }
    void mouseDrag(const juce::MouseEvent& event) override
    {
        AnimatedButton::mouseDrag(event);
        // Logic's AU view bridge requires a real pointer movement before it
        // accepts an external file drag. Starting from mouseDown is treated as
        // an ordinary click and produces no timeline region.
        // JUCE only delivers mouseDrag while a button is held.  Some AU host
        // bridges omit the button modifier on the forwarded drag event, so
        // checking it here can silently prevent the native Cocoa session from
        // ever starting.  The distance threshold still excludes a click.
        if (!dragStarted && event.getDistanceFromDragStart() >= 6 && onFileDrag)
        {
            dragStarted = true;
            onFileDrag();
        }
    }
    void mouseUp(const juce::MouseEvent& event) override
    {
        AnimatedButton::mouseUp(event);
        dragStarted = false;
    }

private:
    bool dragStarted = false;
};

// Read/write accessibility value for selecting an existing model option.
// JUCE's default ComboBox value interface is read-only, which prevents
// assistive clients from selecting an option without a pointer popup.
class ChatModelSelector final : public juce::ComboBox
{
public:
    std::unique_ptr<juce::AccessibilityHandler> createAccessibilityHandler() override
    {
        class Value final : public juce::AccessibilityTextValueInterface
        {
        public:
            explicit Value(ChatModelSelector& owner) : box(owner) {}
            bool isReadOnly() const override { return false; }
            juce::String getCurrentValueAsString() const override { return box.getText(); }
            void setValueAsString(const juce::String& text) override
            {
                if (!box.isEnabled()) return;
                for (int i = 0; i < box.getNumItems(); ++i)
                    if (box.getItemText(i) == text)
                    {
                        box.setSelectedId(box.getItemId(i), juce::sendNotificationSync);
                        return;
                    }
            }
        private:
            ChatModelSelector& box;
        };
        return std::make_unique<juce::AccessibilityHandler>(*this, juce::AccessibilityRole::comboBox,
            juce::AccessibilityActions().addAction(juce::AccessibilityActionType::press, [this] { showPopup(); })
                .addAction(juce::AccessibilityActionType::showMenu, [this] { showPopup(); }),
            juce::AccessibilityHandler::Interfaces{std::make_unique<Value>(*this)});
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
    void sendMessage(bool directAction = false);
    void pollStatus();
    void handleStatus(const juce::var&);
    void startChatVerification();
    void failChatSwitch(const juce::String&);
    void chooseWorkspace();
    void loadReaperSelection();
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

    enum class RequestKind { none, open, status, chat, clear_chat, import_reaper, import_receipt, verify_chat };

    TriceratopsAudioProcessor& ownerProcessor;

    // Chat stream & sidebar controls
    juce::TextEditor chatDisplay, prompt, arrangement, history;
    ChatModelSelector chatBackendSelector;
    juce::Label chatBackendStatus;
    bool chatBackendReady = true, deferredChatVerify = false, chatSwitchPending = false;
    juce::String selectedChatBackend, queuedChatBackend, activeWorkspace;
    AnimatedButton workspaceBtn { "Workspace" }, selectionBtn { "Selected MIDI" }, retryChatBtn { "Retry" };
    juce::int64 chatVerifyStartedMs = 0;
    juce::Label statusLabel, progressLabel, connectionBanner, midiLabel, audioLabel;
    juce::ProgressBar progressBar;
    ScoreStaveComponent scoreStave;

    double progress = 0.0;
    float eqPhase = 0.0f;

    std::unique_ptr<SettingsPanel> settingsPanel;
    bool setupPrompted = false;
    bool backendConfiguring = false;
    AnimatedButton settingsBtn { "Settings" };
    AnimatedButton languageBtn { "中文" }, send { "Send", true }, cancel { "Stop", false },
                   clearChatBtn { "Clear Chat" }, autoImportBtn { "Auto-Import: ON", true },
                   importReaperBtn { "Import to REAPER", true },
                   sidebarToggleBtn { "Plan / History" },
                   helpBtn { "Features" }, newMusic { "New score" }, editMidi { "Edit MIDI" },
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
    juce::String queuedMessage, submittedMessage;
    juce::String queuedAction;
    std::future<juce::var> pending;
    RequestKind requestKind = RequestKind::none;
    juce::int64 lastStatusPollMs = 0;
    juce::int64 visibleSinceMs = 0;

    bool backendConnecting = true;
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
