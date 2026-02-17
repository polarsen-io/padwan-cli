# VHS tape file - https://github.com/charmbracelet/vhs
# Run: vhs docs/static/chat.tape

Output docs/static/chat.gif

Set Shell "zsh"
Set FontSize 14
Set Width 800
Set Height 500
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms

Env PROMPT "$ "
Env PS1 "$ "

# Start the TUI and enter a chat session
Type "uv run padwan-cli /chat:send 'Hello! What can you help me with?' -m gpt-4o-mini"
Enter
Sleep 5s

# Follow-up message
Type "Can you give me an example in Python?"
Sleep 300ms
Enter
Sleep 5s

# Exit chat
Ctrl+C
Sleep 500ms

# Exit TUI
Ctrl+C
Sleep 300ms
Ctrl+C
Sleep 500ms
