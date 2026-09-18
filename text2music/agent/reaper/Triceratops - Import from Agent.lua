-- @description Triceratops: Import generated media from agent
-- @version 1.0
-- One-shot consumer for reaper-command.txt written by the Triceratops backend.
-- Registered as a REAPER action so the backend can trigger it with
-- "reaper.exe <numeric command id>" (REAPER does NOT run .lua files passed
-- on the command line; it treats them as media to open).
local ROOT = "E:\\text2score\\text2music\\artifacts\\agent_runs"
local cmd_path = ROOT .. "\\reaper-command.txt"

local function value(s, k) return (s or ""):match(k .. ": ([^\r\n]+)") or "" end

-- Claim the command file atomically so concurrent consumers (the Triceratops
-- agent panel, if it happens to be open) cannot double-import the payload.
local taken = cmd_path .. ".taken"
if os.rename(cmd_path, taken) ~= true then return end

local f = io.open(taken, "r")
local payload = f and f:read("*a") or ""
if f then f:close() end
os.remove(taken)

local command = value(payload, "COMMAND")
if command ~= "import_midi_file" and command ~= "import_audio_stems" then return end
local files = value(payload, "FILES")
if files == "" then return end

reaper.Undo_BeginBlock()
for file in files:gmatch("[^|]+") do
  local index = reaper.CountTracks(0)
  reaper.InsertTrackAtIndex(index, true)
  local track = reaper.GetTrack(0, index)
  local name = file:match("([^/\\]+)%.%w+$") or "Triceratops Import"
  reaper.GetSetMediaTrackInfo_String(track, "P_NAME", name, true)
  reaper.SetOnlyTrackSelected(track)
  -- 512 = 0x200: bypass MIDI import option dialogs, insert straight away.
  reaper.InsertMedia(file, 512)
end
reaper.TrackList_AdjustWindows(false)
reaper.Undo_EndBlock("Triceratops import generated media", -1)
reaper.UpdateArrange()
