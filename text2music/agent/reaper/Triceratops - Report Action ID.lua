-- @description Triceratops: Report Import Action ID
-- @version 1.0
-- Bootstrap helper: finds the numeric command id of the registered
-- "Triceratops: Import generated media from agent" action and writes it to a
-- file that the Triceratops backend reads. Run this action ONCE after
-- registering the import script (Action List > Add > Load script).
local ROOT = "E:\\text2score\\text2music\\artifacts\\agent_runs"

local kb_path = reaper.GetResourcePath() .. "\\reaper-kb.ini"
local f = io.open(kb_path, "r")
if not f then
  reaper.ShowMessageBox("Cannot open " .. kb_path, "Triceratops", 0)
  return
end
local content = f:read("*a")
f:close()

local rs = content:match('"(RS%x+)"[^"]*Triceratops/Triceratops %- Import from Agent%.lua"')
if not rs then
  reaper.ShowMessageBox(
    "The import action is not registered yet.\n\n" ..
    "Open the Action List, click 'Add...', choose 'Load script...' and select:\n" ..
    reaper.GetResourcePath() .. "\\Scripts\\Triceratops\\Triceratops - Import from Agent.lua\n\n" ..
    "Then run this reporter action again.", "Triceratops", 0)
  return
end

local command_id = reaper.NamedCommandLookup("_" .. rs)
if command_id == 0 then
  reaper.ShowMessageBox("Found " .. rs .. " but REAPER reports no live command id.\n" ..
                        "Restart REAPER once, then run this action again.", "Triceratops", 0)
  return
end

local dir_f = io.open(ROOT .. "\\triceratops-action-id.txt", "w")
if not dir_f then
  reaper.ShowMessageBox("Cannot write " .. ROOT .. "\\triceratops-action-id.txt", "Triceratops", 0)
  return
end
dir_f:write(tostring(command_id))
dir_f:close()
reaper.ShowMessageBox("Triceratops REAPER bridge ready (action id " .. command_id .. ").\n" ..
                      "The VST3 plug-in can now import generated MIDI into REAPER.", "Triceratops", 0)
