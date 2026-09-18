local cmd_path = "E:\\text2score\\text2music\\artifacts\\agent_runs\\reaper-command.txt"
local f = io.open(cmd_path, "r")
if not f then return end
local content = f:read("*a")
f:close()

local midi_file = content:match("FILES:%s*([^\r\n]+)")
if midi_file and midi_file ~= "" then
    reaper.Undo_BeginBlock()
    -- 512 = 0x200 (Suppress import dialogs and insert directly onto new track)
    reaper.InsertMedia(midi_file, 512)
    reaper.Undo_EndBlock("Import Triceratops MIDI", -1)
    reaper.UpdateArrange()
end
