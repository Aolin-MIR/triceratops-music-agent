-- @description Triceratops: Import generated media from agent
-- @version 0.9
-- One-shot consumer for reaper-command.txt written by the Triceratops backend.
-- Run inside the owning REAPER instance; receipt includes this request and project.
local ROOT = nil -- injected by vst_service
assert(ROOT, "Run this importer through Triceratops, which supplies the configured data folder")
local cmd_path = ROOT .. "/reaper-command.txt"

local function value(s, k) return (s or ""):match(k .. ": ([^\r\n]+)") or "" end

-- Claim the command file atomically so concurrent consumers (the Triceratops
-- agent panel, if it happens to be open) cannot double-import the payload.
local taken = cmd_path .. ".taken"
if os.rename(cmd_path, taken) ~= true then return end

local f = io.open(taken, "r")
local payload = f and f:read("*a") or ""
if f then f:close() end
os.remove(taken)

local request_id = value(payload, "REQUEST_ID")
local command = value(payload, "COMMAND")
if command ~= "import_midi_file" and command ~= "import_audio_stems" then return end
local files = value(payload, "FILES")
if files == "" then return end

local imported = 0
reaper.Undo_BeginBlock()
local ok, failure = xpcall(function()
for file in files:gmatch("[^|]+") do
  local source = reaper.PCM_Source_CreateFromFile(file)
  if not source then error("Cannot load generated media: " .. file) end
  local index = reaper.CountTracks(0)
  reaper.InsertTrackAtIndex(index, true)
  local track = reaper.GetTrack(0, index)
  local name = file:match("([^/\\]+)%.%w+$") or "Triceratops Import"
  reaper.GetSetMediaTrackInfo_String(track, "P_NAME", name, true)
  reaper.SetOnlyTrackSelected(track)
  -- InsertMedia's 512 flag is a track-index flag, not a dialog bypass.
  -- Attach the real source directly to avoid blocking unattended imports.
  local item = reaper.AddMediaItemToTrack(track)
  local take = reaper.AddTakeToMediaItem(item)
  reaper.SetMediaItemTake_Source(take, source)
  reaper.GetSetMediaItemTakeInfo_String(take, "P_NAME", name, true)
  local length, isQN = reaper.GetMediaSourceLength(source)
  local position = reaper.GetCursorPosition()
  if isQN then
    local startQN = reaper.TimeMap2_timeToQN(0, position)
    length = reaper.TimeMap2_QNToTime(0, startQN + length) - position
  end
  reaper.SetMediaItemInfo_Value(item, "D_POSITION", position)
  reaper.SetMediaItemInfo_Value(item, "D_LENGTH", length)
  imported = imported + 1
end
end, debug.traceback)
reaper.TrackList_AdjustWindows(false)
reaper.Undo_EndBlock("Triceratops import generated media", -1)
reaper.UpdateArrange()
local _, project_path = reaper.EnumProjects(-1, "")
local result_path = ROOT .. "/reaper-import-result.txt"
local temporary = result_path .. "." .. request_id .. ".tmp"
local result = io.open(temporary, "w")
if result then
  result:write("REQUEST_ID: " .. request_id .. "\nPROJECT: " .. (project_path or "") .. "\nERROR: " .. (ok and "" or tostring(failure):gsub("[\r\n]", " ")) .. "\nCOMMAND: " .. command .. "\nIMPORTED: " .. imported .. "\nFILES: " .. files .. "\n")
  result:close()
  os.remove(result_path) -- Windows rename does not replace an existing file.
  assert(os.rename(temporary, result_path), "Cannot publish import receipt")
end
