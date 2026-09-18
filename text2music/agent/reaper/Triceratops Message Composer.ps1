# Triceratops native message composer.
param(
    [ValidateSet('Chat', 'Compose', 'Revise')]
    [string] $Mode = 'Chat',
    [Parameter(Mandatory = $true)]
    [string] $Output
)

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

$ink = [Windows.Media.BrushConverter]::new().ConvertFromString('#15130F')
$mutedInk = $ink
$surface = [Windows.Media.BrushConverter]::new().ConvertFromString('#F5E6AE')
$card = [Windows.Media.BrushConverter]::new().ConvertFromString('#FFF8DC')
$soft = [Windows.Media.BrushConverter]::new().ConvertFromString('#E9D38A')
$accent = [Windows.Media.BrushConverter]::new().ConvertFromString('#D4A928')
$conversationPath = 'E:\text2score\text2music\artifacts\agent_runs\conversation-latest.txt'
$latest = if (Test-Path -LiteralPath $conversationPath) {
    ([IO.File]::ReadAllText($conversationPath, [Text.Encoding]::UTF8)).Trim()
} else { '' }
if ([string]::IsNullOrWhiteSpace($latest)) {
    $latest = 'I can compose, edit selected MIDI, analyze project audio, split stems, or report progress.'
}

$window = New-Object System.Windows.Window
$window.Title = 'Triceratops'
$window.Width = 1060
$window.Height = 760
$window.MinWidth = 820
$window.MinHeight = 620
$window.WindowStartupLocation = 'CenterScreen'
$window.ResizeMode = 'CanResize'
$window.Background = $surface
$window.FontFamily = 'Segoe UI'
$window.FontWeight = 'Bold'

function Enable-ButtonMotion(
    [System.Windows.Controls.Button] $button,
    [System.Windows.Media.Brush] $restBrush,
    [System.Windows.Media.Brush] $hoverBrush
) {
    $button.RenderTransformOrigin = '0.5,0.5'
    $button.RenderTransform = New-Object System.Windows.Media.ScaleTransform 1, 1
    $rest = $restBrush
    $hover = $hoverBrush
    $button.Add_MouseEnter({
        $this.Background = $hover
        $animation = New-Object Windows.Media.Animation.DoubleAnimation 1.0, 1.035, ([TimeSpan]::FromMilliseconds(110))
        $animation.EasingFunction = New-Object Windows.Media.Animation.QuadraticEase
        $this.RenderTransform.BeginAnimation([Windows.Media.ScaleTransform]::ScaleXProperty, $animation)
        $this.RenderTransform.BeginAnimation([Windows.Media.ScaleTransform]::ScaleYProperty, $animation)
        $this.Cursor = [Windows.Input.Cursors]::Hand
    }.GetNewClosure())
    $button.Add_MouseLeave({
        $this.Background = $rest
        $animation = New-Object Windows.Media.Animation.DoubleAnimation 1.035, 1.0, ([TimeSpan]::FromMilliseconds(130))
        $animation.EasingFunction = New-Object Windows.Media.Animation.QuadraticEase
        $this.RenderTransform.BeginAnimation([Windows.Media.ScaleTransform]::ScaleXProperty, $animation)
        $this.RenderTransform.BeginAnimation([Windows.Media.ScaleTransform]::ScaleYProperty, $animation)
    }.GetNewClosure())
    $button.Add_PreviewMouseDown({
        $animation = New-Object Windows.Media.Animation.DoubleAnimation 1.035, 0.965, ([TimeSpan]::FromMilliseconds(65))
        $animation.EasingFunction = New-Object Windows.Media.Animation.QuadraticEase
        $this.RenderTransform.BeginAnimation([Windows.Media.ScaleTransform]::ScaleXProperty, $animation)
        $this.RenderTransform.BeginAnimation([Windows.Media.ScaleTransform]::ScaleYProperty, $animation)
    })
    $button.Add_PreviewMouseUp({
        $animation = New-Object Windows.Media.Animation.DoubleAnimation 0.965, 1.035, ([TimeSpan]::FromMilliseconds(90))
        $animation.EasingFunction = New-Object Windows.Media.Animation.QuadraticEase
        $this.RenderTransform.BeginAnimation([Windows.Media.ScaleTransform]::ScaleXProperty, $animation)
        $this.RenderTransform.BeginAnimation([Windows.Media.ScaleTransform]::ScaleYProperty, $animation)
    })
}

$root = New-Object System.Windows.Controls.Grid
$root.Margin = '38,30,38,30'
foreach ($height in @('Auto', 'Auto', '*', 'Auto')) {
    $row = New-Object System.Windows.Controls.RowDefinition
    $row.Height = $height
    [void]$root.RowDefinitions.Add($row)
}

$header = New-Object System.Windows.Controls.Grid
$header.Margin = '2,0,2,24'
$header.ColumnDefinitions.Add((New-Object System.Windows.Controls.ColumnDefinition))
$header.ColumnDefinitions.Add((New-Object System.Windows.Controls.ColumnDefinition -Property @{ Width = 'Auto' }))
$logo = New-Object System.Windows.Controls.Canvas
$logo.Width = 72
$logo.Height = 58
$logo.HorizontalAlignment = 'Left'
$logo.VerticalAlignment = 'Center'
$logoPath = New-Object System.Windows.Shapes.Path
$logoPath.Data = [Windows.Media.Geometry]::Parse('M 8,45 L 20,20 L 36,10 L 52,20 L 64,45 M 20,20 L 10,3 M 52,20 L 62,3 M 24,31 L 48,31 M 36,31 L 36,50')
$logoPath.Stroke = $ink
$logoPath.StrokeThickness = 3.5
$logoPath.StrokeStartLineCap = 'Round'
$logoPath.StrokeEndLineCap = 'Round'
$logoPath.StrokeLineJoin = 'Round'
$logoPath.Fill = [Windows.Media.Brushes]::Transparent
[void]$logo.Children.Add($logoPath)
[void]$header.Children.Add($logo)
$brand = New-Object System.Windows.Controls.StackPanel
$brand.Margin = '88,0,0,0'
$brandName = New-Object System.Windows.Controls.TextBlock
$brandName.Text = 'TRICERATOPS'
$brandName.FontSize = 30
$brandName.FontWeight = 'Bold'
$brandName.Foreground = $ink
$brandLine = New-Object System.Windows.Controls.TextBlock
$brandLine.Text = 'LOCAL MUSIC AGENT  /  REAPER'
$brandLine.FontSize = 15
$brandLine.FontWeight = 'Bold'
$brandLine.Foreground = $mutedInk
$brandLine.Margin = '1,5,0,0'
[void]$brand.Children.Add($brandName)
[void]$brand.Children.Add($brandLine)
[void]$header.Children.Add($brand)
$status = New-Object System.Windows.Controls.Border
$status.Background = $soft
$status.CornerRadius = '16'
$status.Padding = '17,8,17,8'
$statusText = New-Object System.Windows.Controls.TextBlock
$statusText.Text = 'READY'
$statusText.FontSize = 15
$statusText.FontWeight = 'Bold'
$statusText.Foreground = $ink
$status.Child = $statusText
[Windows.Controls.Grid]::SetColumn($status, 1)
[void]$header.Children.Add($status)
[Windows.Controls.Grid]::SetRow($header, 0)
[void]$root.Children.Add($header)

$replyBorder = New-Object System.Windows.Controls.Border
$replyBorder.Background = $soft
$replyBorder.BorderBrush = $ink
$replyBorder.BorderThickness = '1'
$replyBorder.CornerRadius = '18'
$replyBorder.Padding = '22,17,22,17'
$replyBorder.Margin = '0,0,0,18'
$replyStack = New-Object System.Windows.Controls.StackPanel
$replyLabel = New-Object System.Windows.Controls.TextBlock
$replyLabel.Text = 'TRICERATOPS'
$replyLabel.FontSize = 14
$replyLabel.FontWeight = 'Bold'
$replyLabel.Foreground = $mutedInk
$replyText = New-Object System.Windows.Controls.TextBlock
$replyText.Text = $latest
$replyText.FontSize = 19
$replyText.FontWeight = 'Bold'
$replyText.Foreground = $ink
$replyText.TextWrapping = 'Wrap'
$replyText.Margin = '0,7,0,0'
$replyText.MaxHeight = 92
[void]$replyStack.Children.Add($replyLabel)
[void]$replyStack.Children.Add($replyText)
$replyBorder.Child = $replyStack
[Windows.Controls.Grid]::SetRow($replyBorder, 1)
[void]$root.Children.Add($replyBorder)

$composer = New-Object System.Windows.Controls.Border
$composer.Background = $card
$composer.BorderBrush = $ink
$composer.BorderThickness = '2'
$composer.CornerRadius = '22'
$composer.Padding = '22'
$composerGrid = New-Object System.Windows.Controls.Grid
foreach ($height in @('Auto', '*', 'Auto')) {
    $row = New-Object System.Windows.Controls.RowDefinition
    $row.Height = $height
    [void]$composerGrid.RowDefinitions.Add($row)
}
$composerTitle = New-Object System.Windows.Controls.TextBlock
$composerTitle.Text = 'What would you like Triceratops to do?'
$composerTitle.FontSize = 23
$composerTitle.FontWeight = 'Bold'
$composerTitle.Foreground = $ink
$composerTitle.Margin = '2,0,0,13'
[Windows.Controls.Grid]::SetRow($composerTitle, 0)
[void]$composerGrid.Children.Add($composerTitle)

$prompt = New-Object System.Windows.Controls.TextBox
$prompt.Text = ''
$prompt.FontSize = 22
$prompt.FontFamily = 'Segoe UI'
$prompt.FontWeight = 'Bold'
$prompt.Foreground = $ink
$prompt.Background = $card
$prompt.BorderThickness = '0'
$prompt.Padding = '2'
$prompt.AcceptsReturn = $true
$prompt.AcceptsTab = $true
$prompt.TextWrapping = 'Wrap'
$prompt.VerticalScrollBarVisibility = 'Auto'
$prompt.HorizontalScrollBarVisibility = 'Disabled'
$prompt.VerticalContentAlignment = 'Top'
$prompt.MinHeight = 210
$prompt.ToolTip = 'Describe a new piece, edit selected MIDI, or ask about the current project.'
[Windows.Controls.Grid]::SetRow($prompt, 1)
[void]$composerGrid.Children.Add($prompt)

$tools = New-Object System.Windows.Controls.WrapPanel
$tools.Margin = '0,18,0,0'
$tools.VerticalAlignment = 'Center'
function Add-ToolButton([string] $label, [string] $starter) {
    $button = New-Object System.Windows.Controls.Button
    $button.Content = $label
    $button.FontSize = 15
    $button.FontWeight = 'Bold'
    $button.Padding = '15,8,15,8'
    $button.Margin = '0,0,10,8'
    $button.Background = $soft
    $button.Foreground = $ink
    $button.BorderBrush = $ink
    $button.BorderThickness = '1'
    Enable-ButtonMotion $button $soft $surface
    $text = $starter
    $button.Add_Click({
        if ([string]::IsNullOrWhiteSpace($prompt.Text)) { $prompt.Text = $text }
        else { $prompt.Text = $prompt.Text.TrimEnd() + "`r`n" + $text }
        $prompt.Focus()
        $prompt.CaretIndex = $prompt.Text.Length
    }.GetNewClosure())
    [void]$tools.Children.Add($button)
}
Add-ToolButton '+ New music' 'Create new music that fits the current REAPER project: '
Add-ToolButton 'Edit MIDI' 'Edit the selected MIDI while preserving: '
Add-ToolButton 'Analyze project' 'Analyze the current project and tell me: '
Add-ToolButton 'Split stems' 'Split the selected project audio into stems and import them.'
Add-ToolButton 'Audio to MIDI' 'Convert the selected project audio to MIDI and import it.'
[Windows.Controls.Grid]::SetRow($tools, 2)
[void]$composerGrid.Children.Add($tools)
$composer.Child = $composerGrid
[Windows.Controls.Grid]::SetRow($composer, 2)
[void]$root.Children.Add($composer)

$footer = New-Object System.Windows.Controls.Grid
$footer.Margin = '2,20,2,0'
$footer.ColumnDefinitions.Add((New-Object System.Windows.Controls.ColumnDefinition))
$footer.ColumnDefinitions.Add((New-Object System.Windows.Controls.ColumnDefinition -Property @{ Width = 'Auto' }))
$footer.ColumnDefinitions.Add((New-Object System.Windows.Controls.ColumnDefinition -Property @{ Width = 'Auto' }))
$note = New-Object System.Windows.Controls.TextBlock
$note.Text = 'Ctrl + Enter to send  /  Enter for a new line'
$note.FontSize = 15
$note.FontWeight = 'Bold'
$note.VerticalAlignment = 'Center'
$note.Foreground = $mutedInk
[void]$footer.Children.Add($note)

$cancel = New-Object System.Windows.Controls.Button
$cancel.Content = 'Cancel'
$cancel.FontSize = 18
$cancel.FontWeight = 'Bold'
$cancel.Padding = '22,11,22,11'
$cancel.Margin = '0,0,12,0'
$cancel.Background = $soft
$cancel.Foreground = $ink
$cancel.BorderBrush = $ink
$cancel.BorderThickness = '1'
Enable-ButtonMotion $cancel $soft $surface
$cancel.Add_Click({ $window.Close() })
[Windows.Controls.Grid]::SetColumn($cancel, 1)
[void]$footer.Children.Add($cancel)

$submit = New-Object System.Windows.Controls.Button
$submit.Content = 'Send'
$submit.FontSize = 18
$submit.FontWeight = 'Bold'
$submit.Padding = '25,11,25,11'
$submit.Background = $accent
$submit.Foreground = $ink
$submit.BorderThickness = '0'
Enable-ButtonMotion $submit $accent $soft
$send = {
    $answer = $prompt.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($answer)) { return }
    $dir = Split-Path -Parent $Output
    [IO.Directory]::CreateDirectory($dir) | Out-Null
    [IO.File]::WriteAllText($Output, $answer, [Text.UTF8Encoding]::new($false))
    $window.Close()
}
$submit.Add_Click($send)
[Windows.Controls.Grid]::SetColumn($submit, 2)
[void]$footer.Children.Add($submit)
[Windows.Controls.Grid]::SetRow($footer, 3)
[void]$root.Children.Add($footer)

$prompt.Add_PreviewKeyDown({
    if ($_.Key -eq [Windows.Input.Key]::Enter -and
        ([Windows.Input.Keyboard]::Modifiers -band [Windows.Input.ModifierKeys]::Control)) {
        $_.Handled = $true
        & $send
    }
})
$window.Content = $root
$window.Add_ContentRendered({ $prompt.Focus() })
[void]$window.ShowDialog()
if (-not (Test-Path -LiteralPath $Output)) {
    $dir = Split-Path -Parent $Output
    [IO.Directory]::CreateDirectory($dir) | Out-Null
    [IO.File]::WriteAllText($Output, '', [Text.UTF8Encoding]::new($false))
}
