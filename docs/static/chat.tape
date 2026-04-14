# VHS tape file - https://github.com/charmbracelet/vhs
# Run: vhs docs/static/chat.tape

Output docs/static/chat.gif

Set Shell "zsh"
Set FontSize 16
Set Width 1000
Set Height 600
Set Theme "Catppuccin Mocha"
Set TypingSpeed 20ms

Env PROMPT "$ "
Env PS1 "$ "

# Start the TUI and enter a chat session with MCP tools
Type "uv run padwan-cli  /chat:send 'Are French TGV trains on time?' -m magistral-medium-latest"
Enter
Sleep 30s

# Exit chat
Ctrl+C
Sleep 500ms

# Exit TUI
Ctrl+C
Sleep 300ms
Ctrl+C
Sleep 500ms
