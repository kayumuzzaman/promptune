# Render with:
#   vhs docs/assets/demo.tape

Output docs/assets/demo.gif

Require promptune

Set Shell "bash"
Set Width 1200
Set Height 720
Set FontSize 22
Set FontFamily "JetBrains Mono"
Set Theme "Catppuccin Mocha"
Set Padding 20
Set WindowBar Colorful
Set CursorBlink false
Set TypingSpeed 50ms

Type "promptune enhance --tier 0 --no-tui \"write tests for config loading\""
Sleep 500ms
Enter
Sleep 4s
