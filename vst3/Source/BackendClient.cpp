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

void BackendClient::setHostContext(const juce::var& value)
{
    const juce::ScopedLock lock(contextLock);
    hostContext = value;
}

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
    const juce::var requestPayload(payload);
    for (int attempt = 0; attempt < 3; ++attempt)
    {
        auto result = request("/session/open", "POST", requestPayload);
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
    auto result = request("/session/ping", "POST", juce::var(payload));
    // The editor can remain alive when its backend exits. Re-establish the
    // session on the existing asynchronous polling thread, never the audio thread.
    return result.isVoid() ? openSession() : result;
}

juce::var BackendClient::settings() { return request("/settings", "GET"); }
juce::var BackendClient::configureSettings(const juce::var& payload) { return request("/settings/task", "POST", payload); }
juce::var BackendClient::cancelConfiguration() { return request("/settings/cancel", "POST", juce::var(new juce::DynamicObject())); }

juce::var BackendClient::history()
{
    return request("/history?session=" + sessionId, "GET");
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

juce::var BackendClient::importReaperTrack(const juce::String& filePath, const juce::var& files, bool inHost)
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    payload->setProperty("file", filePath);
    if (files.isArray())
        payload->setProperty("files", files);
    {
        const juce::ScopedLock lock(contextLock);
        payload->setProperty("host", hostContext.clone());
    }
    const juce::var requestPayload(payload);
    auto result = request(inHost ? "/prepare_import_reaper" : "/import_reaper", "POST", requestPayload);
    if (auto* object = result.getDynamicObject(); object != nullptr && object->hasProperty("request_id"))
    {
        const juce::ScopedLock lock(contextLock);
        importContexts[object->getProperty("request_id").toString()] = payload->getProperty("host");
    }
    return result;
}

juce::var BackendClient::reaperImportReceipt(const juce::String& requestId, bool discard)
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("request_id", requestId);
    {
        const juce::ScopedLock lock(contextLock);
        const auto context = importContexts.find(requestId);
        if (context == importContexts.end())
        {
            delete payload;
            auto error = new juce::DynamicObject();
            error->setProperty("error", "The import request has no originating workspace.");
            return juce::var(error);
        }
        payload->setProperty("host", context->second);
    }
    auto result = request(discard ? "/discard_import_reaper" : "/import_reaper_receipt", "POST", juce::var(payload));
    if (!result.isVoid())
    {
        const juce::ScopedLock lock(contextLock);
        importContexts.erase(requestId);
    }
    return result;
}

juce::var BackendClient::chat(const juce::String& message, const juce::var& host,
                              const juce::String& midiPath, const juce::String& audioPath,
                              const juce::String& action, const juce::String& language, const juce::String& chatBackend)
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    payload->setProperty("message", message);
    payload->setProperty("host", host);
    payload->setProperty("midi_path", midiPath);
    payload->setProperty("audio_path", audioPath);
    payload->setProperty("action", action);
    payload->setProperty("language", language);
    payload->setProperty("chat_backend", chatBackend);
    return request("/chat", "POST", juce::var(payload));
}

juce::var BackendClient::verifyChat(const juce::String& chatBackend)
{
    auto payload = new juce::DynamicObject();
    payload->setProperty("session", sessionId);
    payload->setProperty("chat_backend", chatBackend);
    return request("/chat/verify", "POST", juce::var(payload));
}

juce::var BackendClient::request(const juce::String& path, const juce::String& method,
                                 const juce::var& body)
{
    try
    {
        if (path != "/health")
        {
            const auto health = request("/health", "GET");
            auto* service = health.getDynamicObject();
            if (service == nullptr)
                return {};
            if (static_cast<int>(service->getProperty("api_version")) != 3)
            {
                auto error = new juce::DynamicObject();
                error->setProperty("error", "The previous backend is still running. Close REAPER and run the updated installer to restart it safely.");
                return juce::var(error);
            }
        }
        juce::URL url(juce::String(baseUrl) + path);
        if (method == "POST")
        {
            auto payload = body.clone();
            if (auto* object = payload.getDynamicObject())
            {
                const juce::ScopedLock lock(contextLock);
                if (!object->hasProperty("host"))
                    object->setProperty("host", hostContext);
                if (!object->hasProperty("session"))
                    object->setProperty("session", sessionId);
            }
            url = url.withPOSTData(juce::JSON::toString(payload, false));
        }

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
