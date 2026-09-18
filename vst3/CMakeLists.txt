cmake_minimum_required(VERSION 3.22)
project(Triceratops VERSION 1.0.0 LANGUAGES C CXX)

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
    FORMATS VST3 Standalone
    PRODUCT_NAME "Triceratops"
    DESCRIPTION "DAW-neutral local music agent"
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
    Source/BackendClient.cpp
    Source/BackendClient.h
    Source/PluginEditor.cpp
    Source/PluginEditor.h
    Source/PluginProcessor.cpp
    Source/PluginProcessor.h
)

target_compile_definitions(Triceratops PUBLIC
    JUCE_USE_WINDOWS_MEDIA_FORMAT=0
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0
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
