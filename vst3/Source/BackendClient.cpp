#include "BackendClient.h"

namespace
{
// Converts a Windows path (e.g. E:\text2score\...) into the WSL mount
// equivalent (/mnt/e/text2score/...) so the backend launch script is found
// regardless of where the repository lives.
juce::String toWslPath(const juce::File& windowsFile)
{
    const auto full = windowsFile.getFullPathName();
    if (full.length() >= 2 && full[1] == ':')
    {
        juce::String drive = full.substring(0, 1).toLowerCase();
        juce::String rest = full.substring(2).replaceCharacter('\\', '/');
        return "/mnt/" + drive + rest;
    }
    return full.replaceCharacter('\\', '/');
}

juce::String launchScriptWslPath()
{
    // Prefer the location of the running plug-in module / standalone exe so a
    // relocated checkout still works; fall back to the documented default.
    for (auto location : { juce::File::getSpecialLocation(juce::File::currentExecutableFile),
                           juce::File::getSpecialLocation(juce::File::currentApplicationFile) })
    {
        auto script = location.getParentDirectory()
                              .getChildFile("text2music/agent/launch_vst_service.sh");
        if (!script.existsAsFile())
            script = location.getParentDirectory()
                             .getChildFile("../text2music/agent/launch_vst_service.sh");
        if (script.existsAsFile())
            return toWslPath(script);
    }
    return "/mnt/e/text2score/text2music/agent/launch_vst_service.sh";
}
}

BackendClient::BackendClient()
    : sessionId(juce::Uuid().toString())
{
}

BackendClient::~BackendClient() = default;

void BackendClient::ensureService()
{
    auto health = request("/health", "GET");
    if (!health.isVoid())
        return;

    serviceProcess = std::make_unique<juce::ChildProcess>();
    const auto command = juce::String("wsl.exe -e bash \"") + launchScriptWslPath() + "\"";
    serviceProcess->start(command,
                          juce::ChildProcess::wantStdOut | juce::ChildProcess::wantStdErr);

    for (int attempt = 0; attempt < 50; ++attempt)
    {
        juce::Thread::sleep(100);
        if (!request("/health", "GET").isVoid())
            break;
    }
}

juce::var BackendClient::openSession()
{
    ensureService();
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    for (int attempt = 0; attempt < 3; ++attempt)
    {
        auto result = request("/session/open", "POST", juce::var(payload));
        if (!result.isVoid())
            return result;
        juce::Thread::sleep(500);
        ensureService();
    }
    return {};
}

juce::var BackendClient::closeSession()
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    return request("/session/close", "POST", juce::var(payload));
}

juce::var BackendClient::status()
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    return request("/session/ping", "POST", juce::var(payload));
}

juce::var BackendClient::history()
{
    return request("/history", "GET");
}

juce::var BackendClient::clearChat()
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    return request("/chat/clear", "POST", juce::var(payload));
}

juce::var BackendClient::cancelTask()
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    return request("/cancel", "POST", juce::var(payload));
}

juce::var BackendClient::importReaperTrack(const juce::String& filePath)
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    payload->setProperty("file", filePath);
    return request("/import_reaper", "POST", juce::var(payload));
}

juce::var BackendClient::chat(const juce::String& message, const juce::var& host,
                              const juce::String& midiPath, const juce::String& audioPath)
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    payload->setProperty("message", message);
    payload->setProperty("host", host);
    payload->setProperty("midi_path", midiPath);
    payload->setProperty("audio_path", audioPath);
    return request("/chat", "POST", juce::var(payload));
}

juce::var BackendClient::request(const juce::String& path, const juce::String& method,
                                 const juce::var& body)
{
    try
    {
        juce::URL url(juce::String(baseUrl) + path);
        if (method == "POST")
            url = url.withPOSTData(juce::JSON::toString(body, false));

        const auto options = juce::URL::InputStreamOptions(juce::URL::ParameterHandling::inAddress)
                                 .withHttpRequestCmd(method)
                                 .withConnectionTimeoutMs(5000)
                                 .withNumRedirectsToFollow(0)
                                 .withExtraHeaders("Content-Type: application/json\r\n");
        auto stream = url.createInputStream(options);
        if (stream == nullptr)
            return {};
        return juce::JSON::parse(stream->readEntireStreamAsString());
    }
    catch (...)
    {
        return {};
    }
}
