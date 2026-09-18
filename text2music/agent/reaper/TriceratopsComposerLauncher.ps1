param(
    [string] $Mode = 'Chat',
    [Parameter(Mandatory = $true)]
    [string] $Output
)

$composer = Join-Path $PSScriptRoot 'Triceratops Message Composer.ps1'
& $composer -Mode $Mode -Output $Output
