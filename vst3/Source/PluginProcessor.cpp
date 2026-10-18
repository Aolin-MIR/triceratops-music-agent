#include "PluginProcessor.h"
#include "PluginEditor.h"

#if JucePlugin_Build_VST3
#include <pluginterfaces/base/funknown.h>
namespace triceratops_reaper
{
    using namespace Steinberg;
    #include "../vendor/JUCE/examples/Plugins/extern/reaper_vst3_interfaces.h"
    DEF_CLASS_IID(IReaperHostApplication)
}
#endif

juce::VST3ClientExtensions* TriceratopsAudioProcessor::getVST3ClientExtensions()
{
   #if JucePlugin_Build_VST3
    return this;
   #else
    return nullptr;
   #endif
}

void TriceratopsAudioProcessor::setIHostApplication(Steinberg::FUnknown* host)
{
   #if JucePlugin_Build_VST3
    ++reaperHostCallbacks;
    if (host == nullptr)
        return;
    void* result = nullptr;
    const auto query = host->queryInterface(triceratops_reaper::IReaperHostApplication::iid, &result);
    reaperHostQuery.store(query);
    if (query != Steinberg::kResultOk)
        return;
    auto* reaper = static_cast<triceratops_reaper::IReaperHostApplication*>(result);
    registerReaperScript.store(reinterpret_cast<RegisterScript>(reaper->getReaperApi("AddRemoveReaScript")));
    runReaperCommand.store(reinterpret_cast<RunCommand>(reaper->getReaperApi("Main_OnCommand")));
    enumReaperProjects.store(reinterpret_cast<EnumProjects>(reaper->getReaperApi("EnumProjects")));
    const juce::ScopedLock lock(reaperHostLock);
    if (reaperHostInterface != nullptr)
        static_cast<triceratops_reaper::IReaperHostApplication*>(reaperHostInterface)->release();
    reaperHostInterface = reaper; // queryInterface's reference is released at destruction.
   #else
    juce::ignoreUnused(host);
   #endif
}

void* TriceratopsAudioProcessor::currentReaperProject() const
{
   #if JucePlugin_Build_VST3
    const juce::ScopedLock lock(reaperHostLock);
    // REAPER assigns the parent after VST3 initialization. Resolve it when
    // needed on the UI thread, rather than caching a null during startup.
    if (reaperHostInterface != nullptr)
        return static_cast<triceratops_reaper::IReaperHostApplication*>(reaperHostInterface)->getReaperParent(3);
   #endif
    return nullptr;
}

void* TriceratopsAudioProcessor::reaperApi(const char* name) const
{
   #if JucePlugin_Build_VST3
    const juce::ScopedLock lock(reaperHostLock);
    if (reaperHostInterface != nullptr)
        return static_cast<triceratops_reaper::IReaperHostApplication*>(reaperHostInterface)->getReaperApi(name);
   #else
    juce::ignoreUnused(name);
   #endif
    return nullptr;
}

bool TriceratopsAudioProcessor::saveSelectedReaperMidi(const juce::File& output, juce::String& error) const
{
    if (!juce::MessageManager::getInstance()->isThisTheMessageThread())
        return false;
    const auto project = currentReaperProject();
    const auto enumerate = enumReaperProjects.load();
    if (project == nullptr || enumerate == nullptr || enumerate(-1, nullptr, 0) != project)
    {
        error = "Activate this REAPER project before reading its selection.";
        return false;
    }
    const auto count = reinterpret_cast<int (*)(void*)>(reaperApi("CountSelectedMediaItems"));
    const auto selected = reinterpret_cast<void* (*)(void*, int)>(reaperApi("GetSelectedMediaItem"));
    const auto activeTake = reinterpret_cast<void* (*)(void*)>(reaperApi("GetActiveTake"));
    const auto isMidi = reinterpret_cast<bool (*)(void*)>(reaperApi("TakeIsMIDI"));
    const auto getAll = reinterpret_cast<bool (*)(void*, char*, int*)>(reaperApi("MIDI_GetAllEvts"));
    const auto ppqToQn = reinterpret_cast<double (*)(void*, double)>(reaperApi("MIDI_GetProjQNFromPPQPos"));
    const auto timeToQn = reinterpret_cast<double (*)(void*, double)>(reaperApi("TimeMap2_timeToQN"));
    const auto itemValue = reinterpret_cast<double (*)(void*, const char*)>(reaperApi("GetMediaItemInfo_Value"));
    const auto takeValue = reinterpret_cast<double (*)(void*, const char*)>(reaperApi("GetMediaItemTakeInfo_Value"));
    const auto getSource = reinterpret_cast<void* (*)(void*)>(reaperApi("GetMediaItemTake_Source"));
    const auto sourceLength = reinterpret_cast<double (*)(void*, bool*)>(reaperApi("GetMediaSourceLength"));
    const auto itemString = reinterpret_cast<bool (*)(void*, const char*, char*, bool)>(reaperApi("GetSetMediaItemInfo_String"));
    if (!count || !selected || !activeTake || !isMidi || !getAll || !ppqToQn || !timeToQn || !itemValue || !takeValue || !getSource || !sourceLength || !itemString)
    {
        error = "REAPER selection APIs are unavailable.";
        return false;
    }
    if (count(project) != 1)
    {
        error = "Select exactly one MIDI item in this REAPER project.";
        return false;
    }
    const auto item = selected(project, 0);
    const auto take = activeTake(item);
    if (take == nullptr || !isMidi(take))
    {
        error = "The selected item's active take is not MIDI.";
        return false;
    }
    const auto startSeconds = itemValue(item, "D_POSITION");
    const auto lengthSeconds = itemValue(item, "D_LENGTH");
    const auto startQn = timeToQn(project, startSeconds);
    const auto endQn = timeToQn(project, startSeconds + lengthSeconds);
    const bool looped = itemValue(item, "B_LOOPSRC") != 0.0;
    bool sourceIsQn = false;
    const auto length = sourceLength(getSource(take), &sourceIsQn);
    const auto rate = takeValue(take, "D_PLAYRATE");
    const auto period = sourceIsQn && rate > 0.0 ? length / rate : 0.0;
    if (endQn <= startQn || (looped && period <= 0.0))
    {
        error = "The selected MIDI item has an invalid length or loop source.";
        return false;
    }
    int bytes = 1024 * 1024;
    std::vector<char> raw(static_cast<size_t>(bytes));
    bool read = getAll(take, raw.data(), &bytes);
    if (!read && bytes > static_cast<int>(raw.size()) && bytes <= 64 * 1024 * 1024)
    {
        raw.resize(static_cast<size_t>(bytes));
        read = getAll(take, raw.data(), &bytes);
    }
    if (!read || bytes < 0 || bytes > static_cast<int>(raw.size()))
    {
        error = "Could not read the complete selected MIDI item.";
        return false;
    }
    juce::MidiMessageSequence expanded;
    juce::int64 ppq = 0;
    int position = 0;
    while (position + 9 <= bytes)
    {
        const auto offset = static_cast<juce::int32>(juce::ByteOrder::littleEndianInt(raw.data() + position));
        const auto flags = static_cast<unsigned char>(raw[static_cast<size_t>(position + 4)]);
        const auto size = juce::ByteOrder::littleEndianInt(raw.data() + position + 5);
        position += 9;
        if (size > static_cast<juce::uint32>(bytes - position))
        {
            error = "The selected MIDI event buffer is incomplete.";
            return false;
        }
        ppq += offset;
        if (size > 0 && !(flags & 2))
        {
            const auto qn = ppqToQn(take, static_cast<double>(ppq));
            const int first = looped ? static_cast<int>(std::floor((startQn - qn) / period)) - 1 : 0;
            const int last = looped ? static_cast<int>(std::ceil((endQn - qn) / period)) + 1 : 0;
            if (last - first > 100000)
            {
                error = "The selected MIDI loop is too large to export safely.";
                return false;
            }
            for (int cycle = first; cycle <= last; ++cycle)
            {
                juce::MidiMessage message(raw.data() + position, static_cast<int>(size),
                    (qn + cycle * period - startQn) * 960.0);
                expanded.addEvent(message);
            }
        }
        position += static_cast<int>(size);
    }
    if (position != bytes)
    {
        error = "The selected MIDI event buffer has trailing incomplete data.";
        return false;
    }
    expanded.updateMatchedPairs();
    juce::MidiMessageSequence clip;
    clip.addEvent(juce::MidiMessage::tempoMetaEvent(static_cast<int>(60000000.0 / currentTempo.load())));
    clip.addEvent(juce::MidiMessage::timeSignatureMetaEvent(numerator.load(), denominator.load()));
    const auto endTick = (endQn - startQn) * 960.0;
    int notes = 0;
    for (int index = 0; index < expanded.getNumEvents(); ++index)
    {
        const auto* event = expanded.getEventPointer(index);
        const auto& message = event->message;
        if (message.isNoteOn())
        {
            const auto* off = event->noteOffObject;
            if (off == nullptr || off->message.getTimeStamp() <= 0 || message.getTimeStamp() >= endTick)
                continue;
            auto onMessage = message;
            auto offMessage = off->message;
            onMessage.setTimeStamp(juce::jmax(0.0, message.getTimeStamp()));
            offMessage.setTimeStamp(juce::jmin(endTick, offMessage.getTimeStamp()));
            clip.addEvent(onMessage);
            clip.addEvent(offMessage);
            ++notes;
        }
        else if (!message.isNoteOff() && !message.isEndOfTrackMetaEvent() && message.getTimeStamp() >= 0 && message.getTimeStamp() <= endTick)
            clip.addEvent(message);
    }
    if (notes == 0)
    {
        error = "The selected MIDI item has no audible notes in its visible range.";
        return false;
    }
    auto endMarker = juce::MidiMessage::endOfTrack();
    endMarker.setTimeStamp(endTick);
    clip.addEvent(endMarker);
    juce::MidiFile file;
    file.setTicksPerQuarterNote(960);
    file.addTrack(clip);
    output.getParentDirectory().createDirectory();
    juce::FileOutputStream stream(output);
    if (!stream.openedOk() || !file.writeTo(stream))
    {
        error = "Could not write the selected MIDI file.";
        return false;
    }
    stream.flush();
    char guid[256] {};
    itemString(item, "GUID", guid, false);
    auto audit = new juce::DynamicObject();
    audit->setProperty("host", hostSnapshot());
    audit->setProperty("item_guid", juce::String::fromUTF8(guid));
    audit->setProperty("item_position_seconds", startSeconds);
    audit->setProperty("item_length_seconds", lengthSeconds);
    audit->setProperty("looped", looped);
    audit->setProperty("exported_notes", notes);
    audit->setProperty("midi", output.getFullPathName());
    output.withFileExtension(".source.json").replaceWithText(juce::JSON::toString(juce::var(audit)));
    return true;
}

juce::String TriceratopsAudioProcessor::reaperImportDiagnostics() const
{
    return "callbacks=" + juce::String(reaperHostCallbacks.load())
        + ", query=" + juce::String(reaperHostQuery.load())
        + ", register=" + juce::String(static_cast<int>(registerReaperScript.load() != nullptr))
        + ", run=" + juce::String(static_cast<int>(runReaperCommand.load() != nullptr))
        + ", projects=" + juce::String(static_cast<int>(enumReaperProjects.load() != nullptr))
        + ", parent=" + juce::String(static_cast<int>(currentReaperProject() != nullptr));
}

bool TriceratopsAudioProcessor::canRunReaperScript() const
{
    return registerReaperScript.load() != nullptr && runReaperCommand.load() != nullptr
        && enumReaperProjects.load() != nullptr && currentReaperProject() != nullptr;
}

bool TriceratopsAudioProcessor::runReaperScript(const juce::String& path)
{
    if (!canRunReaperScript() || !juce::MessageManager::getInstance()->isThisTheMessageThread())
        return false;
    if (enumReaperProjects.load()(-1, nullptr, 0) != currentReaperProject())
        return false;
    const auto action = registerReaperScript.load()(true, 0, path.toRawUTF8(), true);
    if (action == 0)
        return false;
    runReaperCommand.load()(action, 0);
    registerReaperScript.load()(false, 0, path.toRawUTF8(), true);
    return true;
}

TriceratopsAudioProcessor::TriceratopsAudioProcessor()
    : AudioProcessor(BusesProperties()
                        #if !JucePlugin_IsMidiEffect
                         .withInput("Input", juce::AudioChannelSet::stereo(), true)
                         .withOutput("Output", juce::AudioChannelSet::stereo(), true)
                        #endif
                     )
{
}

TriceratopsAudioProcessor::~TriceratopsAudioProcessor()
{
   #if JucePlugin_Build_VST3
    const juce::ScopedLock lock(reaperHostLock);
    if (reaperHostInterface != nullptr)
        static_cast<triceratops_reaper::IReaperHostApplication*>(reaperHostInterface)->release();
   #endif
}

void TriceratopsAudioProcessor::prepareToPlay(double sampleRate, int)
{
    currentSampleRate.store(sampleRate);
}

void TriceratopsAudioProcessor::releaseResources() {}

bool TriceratopsAudioProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const
{
   #if JucePlugin_IsMidiEffect
    return layouts.inputBuses.isEmpty() && layouts.outputBuses.isEmpty();
   #else
    return layouts.getMainInputChannelSet() == layouts.getMainOutputChannelSet()
        && (layouts.getMainOutputChannelSet() == juce::AudioChannelSet::mono()
            || layouts.getMainOutputChannelSet() == juce::AudioChannelSet::stereo());
   #endif
}

void TriceratopsAudioProcessor::processBlock(juce::AudioBuffer<float>& buffer,
                                             juce::MidiBuffer& midi)
{
    juce::ScopedNoDenormals noDenormals;
    const auto position = getPlayHead() != nullptr ? getPlayHead()->getPosition() : std::nullopt;
    if (position)
    {
        currentTempo.store(position->getBpm().orFallback(120.0));
        currentPpq.store(position->getPpqPosition().orFallback(0.0));
        const auto signature = position->getTimeSignature().orFallback(
            juce::AudioPlayHead::TimeSignature { 4, 4 });
        numerator.store(signature.numerator);
        denominator.store(signature.denominator);
        playing.store(position->getIsPlaying());
        looping.store(position->getIsLooping());
    }

    const auto blockStart = currentPpq.load();
    const auto ppqPerSample = currentTempo.load() / (60.0 * currentSampleRate.load());
    const auto blockEnd = blockStart + ppqPerSample * buffer.getNumSamples();

    if (captureMidi.load())
    {
        // Record incoming MIDI regardless of transport state: live playing
        // often happens while the host transport is stopped. Timestamps use a
        // monotonically increasing beat counter so they stay valid whether or
        // not the playhead is moving (and never go backwards).
        const juce::ScopedLock lock(clipLock);
        for (const auto metadata : midi)
        {
            auto message = metadata.getMessage();
            message.setTimeStamp(captureElapsedBeats + ppqPerSample * metadata.samplePosition);
            capturedClip.addEvent(message);
        }
        captureElapsedBeats += ppqPerSample * buffer.getNumSamples();
    }

    if (captureAudio.load())
    {
        const juce::ScopedLock lock(clipLock);
        const auto writable = juce::jmin(buffer.getNumSamples(),
                                         capturedAudio.getNumSamples() - capturedAudioSamples);
        for (int channel = 0; channel < juce::jmin(buffer.getNumChannels(),
                                                   capturedAudio.getNumChannels()); ++channel)
            capturedAudio.copyFrom(channel, capturedAudioSamples, buffer, channel, 0, writable);
        capturedAudioSamples += writable;
        // At the two-minute capacity, retain the pending recording and its
        // Save state. Clearing the flag here made the next click start a new
        // capture and discard the full buffer instead of saving it.
    }

    if (clipArmed.load() && playing.load())
    {
        const juce::ScopedLock lock(clipLock);
        const auto anchor = clipAnchorPpq.load();
        auto lastEventPpq = anchor;
        for (int index = 0; index < generatedClip.getNumEvents(); ++index)
        {
            const auto* event = generatedClip.getEventPointer(index);
            const auto eventPpq = anchor + event->message.getTimeStamp();
            lastEventPpq = juce::jmax(lastEventPpq, eventPpq);
            if (eventPpq >= blockStart && eventPpq < blockEnd)
            {
                const auto sample = juce::jlimit(0, buffer.getNumSamples() - 1,
                                                juce::roundToInt((eventPpq - blockStart) / ppqPerSample));
                midi.addEvent(event->message, sample);
            }
        }
        // Disarm once the playhead has passed the clip entirely, so the clip
        // plays exactly once instead of retriggering on every transport pass.
        if (blockStart > lastEventPpq)
            clipArmed.store(false);
    }
}

juce::AudioProcessorEditor* TriceratopsAudioProcessor::createEditor()
{
    return new TriceratopsAudioProcessorEditor(*this);
}

juce::String TriceratopsAudioProcessor::getWorkspaceId() const
{
    const juce::ScopedLock lock(workspaceLock);
    return workspaceId;
}

void TriceratopsAudioProcessor::setWorkspaceId(const juce::String& value)
{
    if (value.trim().isEmpty() || value.length() > 160)
        return;
    const juce::ScopedLock lock(workspaceLock);
    workspaceId = value.trim();
}

juce::var TriceratopsAudioProcessor::hostSnapshot() const
{
    auto result = new juce::DynamicObject();
    result->setProperty("name", getWrapperTypeDescription(wrapperType));
    result->setProperty("host_application", juce::PluginHostType().getHostDescription());
    result->setProperty("workspace_id", getWorkspaceId());
    result->setProperty("workspace_source", "persistent plug-in workspace");
    if (juce::MessageManager::getInstance()->isThisTheMessageThread())
    {
        const auto enumerate = enumReaperProjects.load();
        const auto parent = currentReaperProject();
        if (enumerate != nullptr && parent != nullptr)
        {
            for (int index = 0; ; ++index)
            {
                char path[8192] {};
                const auto project = enumerate(index, path, sizeof(path));
                if (project == nullptr)
                    break;
                if (project == parent)
                {
                    if (path[0] != 0)
                    {
                        result->setProperty("project_path", juce::String::fromUTF8(path));
                        result->setProperty("workspace_source", "REAPER project path");
                    }
                    break;
                }
            }
        }
    }
    result->setProperty("tempo", currentTempo.load());
    result->setProperty("ppq", currentPpq.load());
    result->setProperty("playing", playing.load());
    result->setProperty("looping", looping.load());
    result->setProperty("sample_rate", currentSampleRate.load());
    juce::Array<juce::var> signature { numerator.load(), denominator.load() };
    result->setProperty("time_signature", signature);
    return juce::var(result);
}

bool TriceratopsAudioProcessor::loadMidiClip(const juce::File& file)
{
    juce::FileInputStream input(file);
    if (!input.openedOk())
        return false;
    juce::MidiFile midi;
    if (!midi.readFrom(input) || midi.getNumTracks() == 0)
        return false;
    juce::MidiMessageSequence merged;
    const auto divisor = juce::jmax(1, static_cast<int>(midi.getTimeFormat()));
    for (int track = 0; track < midi.getNumTracks(); ++track)
    {
        if (const auto* sequence = midi.getTrack(track))
            for (int event = 0; event < sequence->getNumEvents(); ++event)
            {
                auto message = sequence->getEventPointer(event)->message;
                message.setTimeStamp(message.getTimeStamp() / divisor);
                merged.addEvent(message);
            }
    }
    merged.updateMatchedPairs();
    const juce::ScopedLock lock(clipLock);
    generatedClip = merged;
    loadedMidiPath = file.getFullPathName();
    clipArmed.store(false);
    return true;
}

void TriceratopsAudioProcessor::armGeneratedClip()
{
    const auto beatsPerBar = numerator.load() * 4.0 / denominator.load();
    const auto now = currentPpq.load();
    clipAnchorPpq.store(std::ceil(now / beatsPerBar) * beatsPerBar);
    clipArmed.store(true);
}

void TriceratopsAudioProcessor::clearMidiClip()
{
    const juce::ScopedLock lock(clipLock);
    clipArmed.store(false);
    generatedClip.clear();
    loadedMidiPath.clear();
}

void TriceratopsAudioProcessor::setCaptureMidi(bool shouldCapture)
{
    const juce::ScopedLock lock(clipLock);
    if (shouldCapture)
    {
        capturedClip.clear();
        captureAnchorPpq.store(currentPpq.load());
        captureElapsedBeats = 0.0;
    }
    captureMidi.store(shouldCapture);
}

bool TriceratopsAudioProcessor::saveCapturedMidi(const juce::File& file)
{
    const juce::ScopedLock lock(clipLock);
    bool hasNotes = false;
    for (int index = 0; index < capturedClip.getNumEvents(); ++index)
        hasNotes = hasNotes || capturedClip.getEventPointer(index)->message.isNoteOn();
    if (!hasNotes)
        return false;
    juce::MidiFile midi;
    auto copy = capturedClip;
    for (int i = 0; i < copy.getNumEvents(); ++i)
        copy.getEventPointer(i)->message.setTimeStamp(
            juce::jmax(0.0, copy.getEventPointer(i)->message.getTimeStamp()) * 960.0);
    midi.setTicksPerQuarterNote(960);
    midi.addTrack(copy);
    juce::FileOutputStream output(file);
    return output.openedOk() && midi.writeTo(output);
}

void TriceratopsAudioProcessor::startAudioCapture()
{
    const juce::ScopedLock lock(clipLock);
    const auto channels = juce::jmax(1, getTotalNumInputChannels());
    const auto maximumSamples = juce::roundToInt(currentSampleRate.load() * 120.0);
    capturedAudio.setSize(channels, maximumSamples, false, true, false);
    capturedAudio.clear();
    capturedAudioSamples = 0;
    captureAudio.store(true);
}

bool TriceratopsAudioProcessor::stopAudioCapture(const juce::File& file)
{
    captureAudio.store(false);
    const juce::ScopedLock lock(clipLock);
    if (capturedAudioSamples <= 0)
        return false;

    file.getParentDirectory().createDirectory();
    file.deleteFile();
    auto stream = file.createOutputStream();
    if (stream == nullptr)
        return false;
    juce::WavAudioFormat wav;
    std::unique_ptr<juce::AudioFormatWriter> writer(
        wav.createWriterFor(stream.release(), currentSampleRate.load(),
                            static_cast<unsigned int>(capturedAudio.getNumChannels()),
                            24, {}, 0));
    return writer != nullptr
        && writer->writeFromAudioSampleBuffer(capturedAudio, 0, capturedAudioSamples);
}

juce::String TriceratopsAudioProcessor::getLoadedMidiPath() const
{
    const juce::ScopedLock lock(clipLock);
    return loadedMidiPath;
}

void TriceratopsAudioProcessor::getStateInformation(juce::MemoryBlock& destination)
{
    auto state = new juce::DynamicObject();
    state->setProperty("midi", getLoadedMidiPath());
    state->setProperty("workspace_id", getWorkspaceId());
    const auto json = juce::JSON::toString(juce::var(state));
    destination.append(json.toRawUTF8(), static_cast<size_t>(json.getNumBytesAsUTF8()));
}

void TriceratopsAudioProcessor::setStateInformation(const void* data, int size)
{
    const auto json = juce::String::fromUTF8(static_cast<const char*>(data), size);
    const auto state = juce::JSON::parse(json);
    if (auto* object = state.getDynamicObject())
    {
        const auto savedWorkspace = object->getProperty("workspace_id").toString();
        if (savedWorkspace.isNotEmpty())
            setWorkspaceId(savedWorkspace);
        const juce::File midi(object->getProperty("midi").toString());
        if (midi.existsAsFile())
            loadMidiClip(midi);
    }
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new TriceratopsAudioProcessor();
}
