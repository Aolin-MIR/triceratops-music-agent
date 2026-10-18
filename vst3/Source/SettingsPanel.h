#pragma once
#include <JuceHeader.h>
#include <future>
#include "BackendClient.h"

class SettingsPanel final : public juce::Component, private juce::Timer
{
public:
    explicit SettingsPanel(BackendClient&);
    ~SettingsPanel() override;
    void open(bool chinese);
    void setChinese(bool);
    void stopSetup() { request("cancel"); }
    void paint(juce::Graphics&) override;
    void resized() override;
    std::function<void()> onClose;
private:
    struct Field
    {
        juce::String key, en, zh;
        juce::Label label;
        juce::TextEditor text;
        juce::ComboBox choice;
        bool isChoice = false;
        juce::StringArray values;
    };
    void addField(const juce::String&, const juce::String&, const juce::String&, const juce::StringArray& values = {}, const juce::StringArray& labels = {});
    void timerCallback() override;
    void request(const juce::String& action);
    void consume(const juce::var&, bool load);
    juce::var draft() const;
    juce::String tr(const char* en, const char* zh) const;
    BackendClient& backend;
    juce::Viewport viewport;
    juce::Component form;
    juce::Label title, note, apiStatus;
    juce::TextEditor status;
    juce::TextButton close, inspect, prepare, apply, cancel;
    std::vector<std::unique_ptr<Field>> fields;
    std::future<juce::var> pending;
    juce::String revision, pendingAction, submittedAction, lastActionError, queuedAction;
    bool savedApiKey = false;
    bool chinese = false, loadNext = false, jobBusy = false, submitted = false;
    juce::int64 lastPoll = 0;
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(SettingsPanel)
};
