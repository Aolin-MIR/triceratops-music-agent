Triceratops 1.0.1b for REAPER and Logic Pro on Apple Silicon

Requires macOS 14 or newer on Apple Silicon. Python is installed privately if needed.
The model backend does not support Intel Macs or Python running under Rosetta.

1. Keep this extracted directory in a permanent location.
2. Save and quit REAPER / Logic Pro, then double-click Install Triceratops.command.
   Downloads automatically retry verified alternate sources. The small ZIP does not
   contain large runtimes or weights. Python (~27 MB) and the private local-chat
   runtime (~174 MB) download once and are SHA-256 checked against pinned official
   releases before installation. No Homebrew or administrator password is needed.
   Failed sources retry through the selected public-file proxies; no API key is
   sent to a mirror. Verified downloads are cached for retry.
   Advanced: TRICERATOPS_PYTHON=/absolute/path/to/python3.11 bash setup-macos.sh
   Source override: TRICERATOPS_DOWNLOAD_SOURCE=china (auto / official also valid).
3. Open Settings in either host to detect hardware and prepare/verify models.
   Configure your API key in the masked Settings field, or choose direct buttons.
   On suitable Apple Silicon Macs, local chat uses native Ollama/Metal and must
   pass native tool calling and full GPU-residency checks. Custom model/device
   choices are available; a failure is reported without silent CPU offload.
4. Rescan VST3 plug-ins in REAPER and insert Triceratops.
   In Logic Pro, scan the included Audio Units in Plug-in Manager:
   - Triceratops MIDI: MIDI FX slot before a software instrument.
   - Triceratops Audio: Audio FX slot for input-audio capture and file tools.
   AU bundles install into ~/Library/Audio/Plug-Ins/Components.
   A Logic-only installation can set the "logic" executable path in runtime.json;
   REAPER is not required when doctor finds that configured Logic executable.
5. In Logic, drag the current MIDI into a track or use Logic's MIDI import command.
   "Show output file" reveals MIDI or separated audio files. Automatic timeline
   import is currently a REAPER integration; AU never sends an import to REAPER.
   To record generated MIDI directly, enable Logic's "Record MIDI to Track Here"
   after Triceratops MIDI, click Play MIDI, then start Logic's recording transport.
   For audio capture, route audio through Triceratops Audio, then use Rec audio.

Settings: ~/Library/Application Support/Triceratops/runtime.json
The installer preserves existing paths, device, API endpoint and chat model.
Configuration backups stay in the same folder with owner-only permissions.
Settings only applies a new configuration after dependencies, models and chat checks pass.
CPU is the default. Models are downloaded at pinned revisions and verified.
Do not delete the extracted backend directory while it is installed.

See the release verification record for actual test coverage and limitations.

Music models: official Hugging Face or HF-Mirror, pinned revisions and hashes.
Local chat weights: official Ollama registry; no verified domestic model mirror.
Network availability varies; download failures remain explicit and can be retried.

Composition precision defaults to the original device precision (FP32 on CPU).
Only the detected 8 GB low-memory tier automatically uses FP16. Explicit advanced
precision overrides are preserved. This rule does not certify untested Mac GPUs.
