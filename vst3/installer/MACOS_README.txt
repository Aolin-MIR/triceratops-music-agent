Triceratops 1.0.1 for REAPER and Logic Pro on Apple Silicon

Requires macOS 14 or newer and native ARM64 Python 3.10 or 3.11.
The model backend does not support Intel Macs or Python running under Rosetta.

1. Keep this extracted directory in a permanent location.
2. Run bash setup-macos.sh in Terminal.
   By default it uses python3.11. To select an interpreter:
   TRICERATOPS_PYTHON=/absolute/path/to/python3.11 bash setup-macos.sh
3. Open Settings in either host to detect hardware and prepare/verify models.
   Configure your API key in the masked Settings field, or choose direct buttons.
   On suitable Apple Silicon Macs, local Qwen uses native Ollama/Metal and must
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
