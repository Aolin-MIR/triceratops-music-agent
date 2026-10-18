param(
    [string]$InstallRoot = $PSScriptRoot,
    [switch]$NonInteractive,
    [ValidateSet('cpu','cuda')][string]$Device = 'cpu',
    [string]$ReaperPath = 'C:\Program Files\REAPER (x64)\reaper.exe',
    [string]$ModelHome = "$env:LOCALAPPDATA\Triceratops\models",
    [string]$Endpoint = 'auto',
    [string]$RuntimeRoot = "$env:LOCALAPPDATA\Triceratops\runtime-0.9",
    [switch]$SkipDependencies,
    [switch]$SkipModels
)
$ErrorActionPreference = 'Stop'
$dataRoot = Join-Path $env:APPDATA 'Triceratops'
$runtimeRoot = $RuntimeRoot
$configPath = Join-Path $dataRoot 'runtime.json'
$apiKey = ''
$baseUrl = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
$chatModel = 'qwen-plus'
$llmProvider = 'remote'
$localModel = 'qwen3.5:4b-q4_K_M'
$llmDevice = 'gpu'
$llamaCppUrl = 'http://127.0.0.1:1234/v1'
$midiGptDevice = 'cpu'
$stemDevice = 'cpu'
if (Test-Path -LiteralPath $configPath) {
    $previous = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $apiKey = $previous.api_key
    $baseUrl = $previous.base_url
    $chatModel = $previous.chat_model
    if ($previous.llm_provider) { $llmProvider = $previous.llm_provider }
    if ($previous.local_model) { $localModel = $previous.local_model }
    if ($previous.llm_device) { $llmDevice = $previous.llm_device }
    if ($previous.midi_gpt_device) { $midiGptDevice = $previous.midi_gpt_device }
    if ($previous.stem_device) { $stemDevice = $previous.stem_device }
    if ($previous.llama_cpp_url) { $llamaCppUrl = $previous.llama_cpp_url }
}
if (-not $NonInteractive) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $form = New-Object Windows.Forms.Form
    $form.Text = 'Triceratops 0.9 - Runtime and models'
    $form.Size = New-Object Drawing.Size(690, 770)
    $form.StartPosition = 'CenterScreen'
    $form.Font = New-Object Drawing.Font('Segoe UI', 10)
    $labels = @('REAPER executable', 'Model directory (~4 GB)', 'MIDI-LLM generation device', 'API key (Qwen / compatible API)', 'API base URL', 'Chat model', 'Models: auto / official / china / URL', 'Chat: remote / local GPU / disabled', 'Local chat model', 'Local LLM fixed device', 'Local server URL (loopback only)', 'MIDI-GPT fixed device', 'HTDemucs fixed device')
    $values = @($ReaperPath, $ModelHome, $Device, $apiKey, $baseUrl, $chatModel, $Endpoint, $llmProvider, $localModel, $llmDevice, $llamaCppUrl, $midiGptDevice, $stemDevice)
    $fields = @()
    for ($index=0; $index -lt $labels.Count; $index++) {
        $label = New-Object Windows.Forms.Label
        $label.Text = $labels[$index]
        $label.SetBounds(20, (24+$index*44), 240, 25)
        $form.Controls.Add($label)
        if ($index -in @(2, 7, 9, 11, 12)) {
            $field = New-Object Windows.Forms.ComboBox
            $field.DropDownStyle = 'DropDownList'
            $options = if ($index -in @(2, 11, 12)) { @('cpu','cuda') } elseif ($index -eq 7) { @('remote','llama_cpp','disabled') } elseif ($index -eq 9) { @('gpu') } else { @('cpu','gpu') }
            [void]$field.Items.AddRange($options)
            $field.SelectedItem = $values[$index]
        } else {
            $field = New-Object Windows.Forms.TextBox
            $field.Text = $values[$index]
        }
        if ($index -eq 3) { $field.UseSystemPasswordChar = $true }
        $field.SetBounds(270, (20+$index*44), 380, 29)
        $form.Controls.Add($field)
        $fields += $field
    }
    $note = New-Object Windows.Forms.Label
    $note.Text = 'Direct buttons need no API. Local chat downloads the model and runs llama.cpp with all model layers on the selected GPU. If GPU execution cannot be verified, setup stops without using CPU.'
    $note.SetBounds(20, 600, 630, 65)
    $form.Controls.Add($note)
    $button = New-Object Windows.Forms.Button
    $button.Text = 'Install / verify runtime and models'
    $button.SetBounds(270, 675, 380, 36)
    $button.DialogResult = [Windows.Forms.DialogResult]::OK
    $form.Controls.Add($button)
    $form.AcceptButton = $button
    if ($form.ShowDialog() -ne 'OK') { exit 1 }
    $ReaperPath=$fields[0].Text; $ModelHome=$fields[1].Text; $Device=$fields[2].Text
    $apiKey=$fields[3].Text; $baseUrl=$fields[4].Text; $chatModel=$fields[5].Text; $Endpoint=$fields[6].Text
    $llmProvider=$fields[7].Text; $localModel=$fields[8].Text; $llmDevice=$fields[9].Text; $llamaCppUrl=$fields[10].Text
    $midiGptDevice=$fields[11].Text; $stemDevice=$fields[12].Text
}
if (-not (Test-Path -LiteralPath $ReaperPath -PathType Leaf)) { throw "REAPER not found: $ReaperPath" }
if ($llmProvider -eq 'remote' -and -not $apiKey) { throw 'Cloud chat needs an API key. Choose llama_cpp for local GPU chat or disabled for direct buttons only.' }
$backendRoot = Join-Path $InstallRoot 'backend'
$entry = Join-Path $backendRoot 'text2music\agent\runtime.py'
if (-not (Test-Path -LiteralPath $entry)) { throw "Backend payload is missing: $entry" }
New-Item -ItemType Directory -Force -Path $dataRoot, $runtimeRoot, $ModelHome | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $runtimeRoot 'python.exe'))) {
    Copy-Item -LiteralPath (Join-Path $InstallRoot 'python') -Destination (Join-Path $runtimeRoot 'seed') -Recurse
    Get-ChildItem -LiteralPath (Join-Path $runtimeRoot 'seed') -Force | Move-Item -Destination $runtimeRoot
    Remove-Item -LiteralPath (Join-Path $runtimeRoot 'seed')
}
$python = Join-Path $runtimeRoot 'python.exe'
$utf8 = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $runtimeRoot 'python311._pth'), "python311.zip`n.`nLib\site-packages`n$backendRoot`nimport site`n", $utf8)
if (-not $SkipDependencies) {
    & $python -m pip install -r (Join-Path $InstallRoot 'requirements-runtime.txt') --index-url https://pypi.tuna.tsinghua.edu.cn/simple --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Rerun setup to resume; no alternate runtime was selected.' }
    & $python -m pip install --no-deps 'https://codeload.github.com/jthickstun/anticipation/tar.gz/af37397922665a0fb8d474d7988b0f3755a38d45'
    if ($LASTEXITCODE -ne 0) { throw 'MIDI decoder dependency installation failed.' }
    if ($Device -eq 'cuda' -or $midiGptDevice -eq 'cuda' -or $stemDevice -eq 'cuda') {
        & $python -m pip install --upgrade --force-reinstall --no-deps torch==2.13.0 --index-url https://download.pytorch.org/whl/cu130
        if ($LASTEXITCODE -ne 0) { throw 'CUDA Torch installation failed. No CPU substitution was made.' }
    }
}
$env:HF_ENDPOINT = $Endpoint
if (-not $SkipModels) {
    & $python -m text2music.agent.download_models --home $ModelHome --endpoint $Endpoint
    if ($LASTEXITCODE -ne 0) { throw 'Model installation failed. Rerun setup to resume.' }
}
$settings = @{
    python=$python; runs_dir=(Join-Path $dataRoot 'runs'); model_home=$ModelHome
    reaper=$ReaperPath; device=$Device; api_key=$apiKey; base_url=$baseUrl
    chat_model=$chatModel; model_source=$Endpoint
    midi_llm_device=$Device; midi_gpt_device=$midiGptDevice; stem_device=$stemDevice
    llm_provider=$llmProvider; local_model=$localModel; llm_device=$llmDevice; llama_cpp_url=$llamaCppUrl
}
# The plug-in sees only launcher paths. Credentials stay in the user-owned config.
[IO.File]::WriteAllText($configPath, ($settings | ConvertTo-Json), $utf8)
& icacls.exe $configPath /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict access to the API configuration.' }
if ($llmProvider -eq 'llama_cpp') {
    & $python -m text2music.agent.local_runtime --config $configPath
    if ($LASTEXITCODE -ne 0) { throw 'Local model GPU setup failed. Check llama-cpp-gpu-server.log; no CPU fallback was used.' }
}
& $python -m text2music.agent.doctor --config $configPath
if ($LASTEXITCODE -ne 0) { throw 'Runtime verification failed; the plug-in has not been configured as ready.' }
$launch = @{python=$python; entry=$entry; config=$configPath}
[IO.File]::WriteAllText((Join-Path $dataRoot 'backend.json'), ($launch | ConvertTo-Json), $utf8)
Write-Host 'Triceratops 0.9 ready. In REAPER, rescan VST3 and insert Triceratops.' -ForegroundColor Green
if (-not $NonInteractive) { [void](Read-Host 'Press Enter to close') }
