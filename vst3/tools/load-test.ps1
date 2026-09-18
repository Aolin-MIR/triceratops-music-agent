param([Parameter(Mandatory=$true)][string]$PluginPath)

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class NativePluginTest
{
    [DllImport("kernel32", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern IntPtr LoadLibrary(string path);
    [DllImport("kernel32", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern bool SetDllDirectory(string path);
    [DllImport("kernel32", SetLastError=true)]
    public static extern bool FreeLibrary(IntPtr handle);
}
'@

[NativePluginTest]::SetDllDirectory((Split-Path -Parent $PluginPath)) | Out-Null
$handle = [NativePluginTest]::LoadLibrary($PluginPath)
$errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
Write-Output "HANDLE=$handle ERROR=$errorCode"
if ($handle -ne [IntPtr]::Zero) {
    [NativePluginTest]::FreeLibrary($handle) | Out-Null
    exit 0
}
exit 1
