cmake_minimum_required(VERSION 3.22)
project(Triceratops VERSION 1.0.1 LANGUAGES C CXX)
# Public hotfix label: 1.0.1b. JUCE requires a numeric plug-in version.

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if (CMAKE_CROSSCOMPILING)
    set(JUCE_HOST_CXX_COMPILER "${CMAKE_CURRENT_SOURCE_DIR}/tools/native-g++")
    set(JUCE_HOST_PKG_CONFIG "${CMAKE_CURRENT_SOURCE_DIR}/tools/native-pkgconf")
    set(JUCE_HOST_PKG_CONFIG_PATH "/home/liaolin/.local/opt/native-dev/usr/lib/x86_64-linux-gnu/pkgconfig")
    set(JUCE_HOST_PKG_CONFIG_SYSROOT "/home/liaolin/.local/opt/native-dev")
endif()
add_subdirectory(vendor/JUCE)

juce_add_plugin(Triceratops
    COMPANY_NAME "Triceratops Audio"
    BUNDLE_ID "audio.triceratops.agent"
    PLUGIN_MANUFACTURER_CODE Tric
    PLUGIN_CODE Tria
    FORMATS VST3
    PRODUCT_NAME "Triceratops"
    DESCRIPTION "Music agent for REAPER"
    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT TRUE
    NEEDS_MIDI_OUTPUT TRUE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS TRUE
    COPY_PLUGIN_AFTER_BUILD FALSE
    VST3_AUTO_MANIFEST FALSE
    VST3_CATEGORIES "Fx" "Tools"
)

target_sources(Triceratops PRIVATE
    Source/SettingsPanel.h
    Source/SettingsPanel.cpp
    Source/UiStrings.h
    Source/BackendClient.cpp
    Source/BackendClient.h
    Source/PluginEditor.cpp
    Source/PluginEditor.h
    Source/PluginProcessor.cpp
    Source/PluginProcessor.h
)

if (MSVC)
    target_compile_options(Triceratops PRIVATE /utf-8)
endif()

target_compile_definitions(Triceratops PUBLIC
    JUCE_USE_WINDOWS_MEDIA_FORMAT=0
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0
    JUCE_VST3_EMULATE_MIDI_CC_WITH_PARAMETERS=0
)

if (MINGW)
    target_compile_definitions(Triceratops PUBLIC JUCE_ALLOW_UNSUPPORTED_MINGW=1)
endif()

target_link_libraries(Triceratops PRIVATE
    juce::juce_audio_utils
    juce::juce_gui_extra
    juce::juce_recommended_config_flags
    juce::juce_recommended_lto_flags
    juce::juce_recommended_warning_flags
)

if(WIN32)
    target_link_libraries(Triceratops PUBLIC
        version ws2_32 dbghelp winmm shlwapi wininet
        imm32 comctl32 dwmapi shell32 shcore vfw32
        dwrite d2d1 dxgi d3d11 dcomp dxguid sapi ksuser
    )
endif()

juce_generate_juce_header(Triceratops)
if(APPLE)
    target_include_directories(Triceratops PRIVATE
        vendor/JUCE/modules/juce_audio_processors_headless/format_types/VST3_SDK)
endif()

# Logic routes MIDI processors before an instrument, and audio effects after it.
# Separate AU identities let both paths use the same tested agent/backend.
if(APPLE)
    foreach(kind IN ITEMS Midi Audio)
        set(target Triceratops${kind}AU)
        if(kind STREQUAL "Midi")
            set(product "Triceratops MIDI")
            set(code TrMi)
            set(midi TRUE)
            set(au_type kAudioUnitType_MIDIProcessor)
        else()
            set(product "Triceratops Audio")
            set(code TrAu)
            set(midi FALSE)
            set(au_type kAudioUnitType_Effect)
        endif()
        juce_add_plugin(${target}
            COMPANY_NAME "Triceratops Audio"
            BUNDLE_ID "audio.triceratops.agent.${kind}"
            PLUGIN_MANUFACTURER_CODE Tric
            PLUGIN_CODE ${code}
            FORMATS AU
            PRODUCT_NAME "${product}"
            DESCRIPTION "Music agent for Logic Pro"
            IS_SYNTH FALSE
            NEEDS_MIDI_INPUT ${midi}
            NEEDS_MIDI_OUTPUT ${midi}
            IS_MIDI_EFFECT ${midi}
            AU_MAIN_TYPE ${au_type}
            EDITOR_WANTS_KEYBOARD_FOCUS TRUE
            COPY_PLUGIN_AFTER_BUILD FALSE)
        get_target_property(shared_sources Triceratops SOURCES)
        target_sources(${target} PRIVATE ${shared_sources})
        target_compile_definitions(${target} PUBLIC
            JUCE_USE_WINDOWS_MEDIA_FORMAT=0 JUCE_WEB_BROWSER=0 JUCE_USE_CURL=0)
        target_link_libraries(${target} PRIVATE
            juce::juce_audio_utils juce::juce_gui_extra
            juce::juce_recommended_config_flags juce::juce_recommended_lto_flags
            juce::juce_recommended_warning_flags)
        juce_generate_juce_header(${target})
        # Relinking replaces the Mach-O signature while an older bundle seal
        # may remain. Seal the complete AU after every link, then verify it.
        add_custom_command(TARGET ${target}_AU POST_BUILD
            COMMAND /usr/bin/codesign --force --sign - --timestamp=none
                    "$<TARGET_BUNDLE_DIR:${target}_AU>"
            COMMAND /usr/bin/codesign --verify --deep --strict
                    "$<TARGET_BUNDLE_DIR:${target}_AU>"
            VERBATIM)
    endforeach()
endif()
