#pragma once

#include <JuceHeader.h>
#include "BackendClient.h"

class TriceratopsAudioProcessor final : public juce::AudioProcessor
{
public:
    TriceratopsAudioProcessor();
    ~TriceratopsAudioProcessor() override;

    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    bool isBusesLayoutSupported(const BusesLayout& layouts) const override;
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }
    const juce::String getName() const override { return "Triceratops"; }
    bool acceptsMidi() const override { return true; }
    bool producesMidi() const override { return true; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }
    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}
    void getStateInformation(juce::MemoryBlock&) override;
    void setStateInformation(const void*, int) override;

    juce::var hostSnapshot() const;
    bool loadMidiClip(const juce::File&);
    bool saveCapturedMidi(const juce::File&);
    void startAudioCapture();
    bool stopAudioCapture(const juce::File&);
    void armGeneratedClip();
    void setCaptureMidi(bool shouldCapture);
    bool isCapturingMidi() const noexcept { return captureMidi.load(); }
    bool isCapturingAudio() const noexcept { return captureAudio.load(); }
    juce::String getLoadedMidiPath() const;
    BackendClient& backend() noexcept { return backendClient; }

private:
    mutable juce::CriticalSection clipLock;
    juce::MidiMessageSequence generatedClip;
    juce::MidiMessageSequence capturedClip;
    juce::AudioBuffer<float> capturedAudio;
    int capturedAudioSamples = 0;
    juce::String loadedMidiPath;
    std::atomic<bool> clipArmed { false };
    std::atomic<bool> captureMidi { false };
    std::atomic<bool> captureAudio { false };
    std::atomic<double> clipAnchorPpq { 0.0 };
    std::atomic<double> captureAnchorPpq { 0.0 };
    double captureElapsedBeats = 0.0; // guarded by clipLock; used when transport is stopped
    std::atomic<double> currentTempo { 120.0 };
    std::atomic<double> currentPpq { 0.0 };
    std::atomic<double> currentSampleRate { 44100.0 };
    std::atomic<int> numerator { 4 }, denominator { 4 };
    std::atomic<bool> playing { false }, looping { false };
    BackendClient backendClient;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TriceratopsAudioProcessor)
};
