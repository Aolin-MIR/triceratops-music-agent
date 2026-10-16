#include "BackendClient.h"

namespace
{
juce::File backendConfiguration()
{
   #if JUCE_MAC
    return juce::File::getSpecialLocation(juce::File::userHomeDirectory)
        .getChildFile("Library/Application Support/Triceratops/backend.json");
   #else
    return juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
        .getChildFile("Triceratops/backend.json");
   #endif
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

    const auto config = juce::JSON::parse(backendConfiguration());
    auto* settings = config.getDynamicObject();
    if (settings == nullptr)
        return;
    const auto launcher = settings->getProperty("entry").toString();
    const auto runtime = settings->getProperty("config").toString();
    const auto python = settings->getProperty("python").toString();
    if (launcher.isEmpty() || runtime.isEmpty() || python.isEmpty())
        return;
    juce::StringArray command;
    command.addArray({ python, "-X", "utf8", launcher, "--config", runtime });
    serviceProcess = std::make_unique<juce::ChildProcess>();
    if (!serviceProcess->start(command, juce::ChildProcess::wantStdOut | juce::ChildProcess::wantStdErr))
        return;

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

juce::var BackendClient::importReaperTrack(const juce::String& filePath, const juce::var& files)
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    payload->setProperty("file", filePath);
    if (files.isArray())
        payload->setProperty("files", files);
    return request("/import_reaper", "POST", juce::var(payload));
}

juce::var BackendClient::chat(const juce::String& message, const juce::var& host,
                              const juce::String& midiPath, const juce::String& audioPath,
                              const juce::String& action)
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    payload->setProperty("message", message);
    payload->setProperty("host", host);
    payload->setProperty("midi_path", midiPath);
    payload->setProperty("audio_path", audioPath);
    payload->setProperty("action", action);
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
