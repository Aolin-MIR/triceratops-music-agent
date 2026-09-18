#pragma once

#include <JuceHeader.h>

class BackendClient
{
public:
    static constexpr const char* baseUrl = "http://127.0.0.1:49327";

    BackendClient();
    ~BackendClient();

    void ensureService();
    juce::var openSession();
    juce::var closeSession();
    juce::var status();
    juce::var history();
    juce::var clearChat();
    juce::var cancelTask();
    juce::var importReaperTrack(const juce::String& filePath);
    juce::var chat(const juce::String& message, const juce::var& host,
                   const juce::String& midiPath, const juce::String& audioPath);

    const juce::String& getSessionId() const noexcept { return sessionId; }

private:
    juce::var request(const juce::String& path, const juce::String& method,
                      const juce::var& body = {});

    juce::String sessionId;
    std::unique_ptr<juce::ChildProcess> serviceProcess;
};
