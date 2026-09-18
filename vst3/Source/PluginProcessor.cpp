#include "PluginProcessor.h"
#include "PluginEditor.h"

TriceratopsAudioProcessor::TriceratopsAudioProcessor()
    : AudioProcessor(BusesProperties()
                         .withInput("Input", juce::AudioChannelSet::stereo(), true)
                         .withOutput("Output", juce::AudioChannelSet::stereo(), true))
{
}

TriceratopsAudioProcessor::~TriceratopsAudioProcessor() = default;

void TriceratopsAudioProcessor::prepareToPlay(double sampleRate, int)
{
    currentSampleRate.store(sampleRate);
}

void TriceratopsAudioProcessor::releaseResources() {}

bool TriceratopsAudioProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const
{
    return layouts.getMainInputChannelSet() == layouts.getMainOutputChannelSet()
        && (layouts.getMainOutputChannelSet() == juce::AudioChannelSet::mono()
            || layouts.getMainOutputChannelSet() == juce::AudioChannelSet::stereo());
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
        if (writable < buffer.getNumSamples())
            captureAudio.store(false);
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

juce::var TriceratopsAudioProcessor::hostSnapshot() const
{
    auto result = new juce::DynamicObject();
    result->setProperty("name", getWrapperTypeDescription(wrapperType));
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
    if (capturedClip.getNumEvents() == 0)
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
    const auto json = juce::JSON::toString(juce::var(state));
    destination.append(json.toRawUTF8(), static_cast<size_t>(json.getNumBytesAsUTF8()));
}

void TriceratopsAudioProcessor::setStateInformation(const void* data, int size)
{
    const auto json = juce::String::fromUTF8(static_cast<const char*>(data), size);
    const auto state = juce::JSON::parse(json);
    if (auto* object = state.getDynamicObject())
    {
        const juce::File midi(object->getProperty("midi").toString());
        if (midi.existsAsFile())
            loadMidiClip(midi);
    }
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new TriceratopsAudioProcessor();
}
