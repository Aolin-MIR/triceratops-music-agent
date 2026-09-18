param(
    [Parameter(Mandatory=$true)][string]$ReportPath,
    [Parameter(Mandatory=$true)][string]$PluginDirectory
)

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class NativeImportTest
{
    [DllImport("kernel32", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern IntPtr LoadLibrary(string path);
    [DllImport("kernel32", SetLastError=true, CharSet=CharSet.Ansi)]
    public static extern IntPtr GetProcAddress(IntPtr module, string name);
    [DllImport("kernel32", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern bool SetDllDirectory(string path);
}
'@

[NativeImportTest]::SetDllDirectory($PluginDirectory) | Out-Null
$module = [IntPtr]::Zero
$moduleName = ""
foreach ($line in Get-Content $ReportPath) {
    if ($line -match '^\s+Name:\s+(.+\.dll)$') {
        $moduleName = $Matches[1]
        $module = [NativeImportTest]::LoadLibrary($moduleName)
        if ($module -eq [IntPtr]::Zero) {
            Write-Output "MISSING DLL $moduleName ERROR=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
        }
    } elseif ($line -match '^\s+Symbol:\s+([^\s(]+)') {
        $symbol = $Matches[1]
        if ($module -ne [IntPtr]::Zero -and
            [NativeImportTest]::GetProcAddress($module, $symbol) -eq [IntPtr]::Zero) {
            Write-Output "MISSING PROC $moduleName!$symbol"
        }
    }
}
