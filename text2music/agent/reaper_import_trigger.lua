-- Triceratops One-Shot Direct REAPER Track Importer
local root = "E:\\text2score\\text2music\\artifacts\\agent_runs"
local cmd_path = root .. "\\reaper-command.txt"

local function read_file(path)
    local f = io.open(path, "r")
    if not f then return "" end
    local content = f:read("*a")
    f:close()
    return content
end

local content = read_file(cmd_path)
if content == "" then return end

local midi_file = content:match("FILES:%s*([^\r\n]+)")
if midi_file and midi_file ~= "" then
    reaper.Undo_BeginBlock()
    local index = reaper.CountTracks(0)
    reaper.InsertTrackAtIndex(index, true)
    local track = reaper.GetTrack(0, index)
    local track_name = midi_file:match("([^/\\]+)%.%w+$") or "Triceratops MIDI"
    reaper.GetSetMediaTrackInfo_String(track, "P_NAME", track_name, true)
    reaper.SetOnlyTrackSelected(track)
    reaper.InsertMedia(midi_file, 0)
    reaper.TrackList_AdjustWindows(false)
    reaper.Undo_EndBlock("Triceratops Import MIDI Track", -1)
    reaper.UpdateArrange()
end
