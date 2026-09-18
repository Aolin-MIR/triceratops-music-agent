-- @description Triceratops: Open Music Agent
-- @version 1.1
-- @author Triceratops
-- @about
--   Native REAPER dialog for Triceratops. It starts a headless local job; no
--   browser is opened and REAPER's audio engine remains responsive.

local project_root_linux = "/mnt/e/text2score"
local project_root_windows = "E:\\text2score"
local brief_file_linux = project_root_linux .. "/text2music/artifacts/agent_runs/reaper_brief.txt"
local brief_file_windows = project_root_windows .. "\\text2music\\artifacts\\agent_runs\\reaper_brief.txt"
local launcher = project_root_linux .. "/text2music/agent/launch_reaper_job.sh"

local function shell_quote(value)
  return "'" .. value:gsub("'", "'\\\"'\\\"'") .. "'"
end

local accepted, brief = reaper.GetUserInputs(
  "Triceratops", 1, "Describe the music to generate:",
  "Energetic rock cue with a memorable guitar riff, bass, and drums")
if not accepted or brief == "" then return end

local output_dir = project_root_windows .. "\\text2music\\artifacts\\agent_runs"
os.execute('cmd.exe /c if not exist "' .. output_dir .. '" mkdir "' .. output_dir .. '"')
local file, error_message = io.open(brief_file_windows, "w")
if not file then
  reaper.ShowMessageBox("Could not write the Triceratops request:\n" .. tostring(error_message), "Triceratops", 0)
  return
end
file:write(brief)
file:close()

local command = "cd " .. shell_quote(project_root_linux)
  .. " && nohup bash " .. shell_quote(launcher)
  .. " --brief-file " .. shell_quote(brief_file_linux)
  .. " >/tmp/text2score-reaper-job.log 2>&1 &"
os.execute("cmd.exe /c start \"\" wsl.exe bash -lc " .. shell_quote(command))

reaper.ShowMessageBox(
  "Triceratops is generating the score in the background. REAPER remains usable.\n\n"
    .. "When it finishes, see:\n"
    .. project_root_windows .. "\\text2music\\artifacts\\agent_runs\\reaper-status.txt\n\n"
    .. "The generated ABC/ABCI files are listed in that status file.",
  "Triceratops", 0)
