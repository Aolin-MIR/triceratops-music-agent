param(
    [string]$ProcessName = "Triceratops",
    [string]$OutputPath = "E:\text2score\vst3\window-test.png"
)

Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WindowCapture
{
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr handle, out Rect rect);
}
'@

$process = Get-Process -Name $ProcessName -ErrorAction Stop | Select-Object -First 1
$rect = New-Object WindowCapture+Rect
if (-not [WindowCapture]::GetWindowRect($process.MainWindowHandle, [ref]$rect)) { exit 1 }
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
$bitmap = New-Object Drawing.Bitmap $width, $height
$graphics = [Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
$bitmap.Save($OutputPath, [Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
