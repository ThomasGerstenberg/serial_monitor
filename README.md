## Sublime 3 Serial Monitor

To install, clone this repository into `C:\Users\${user}\AppData\Roaming\Sublime Text 3\Packages` and restart sublime

### Commands
Commands are accessed through `Tools->Serial Monitor` or the Command Palette (`ctrl+shift+p`)

- `Connect`: Brings up dialogs to connect to a comport.  If more than one comport is available, brings up a list of available comports before choosing a baud rate

- `Disconnect`: Brings up a list of connected comports to disconnect from.  If multiple comports are connected, brings up a list of the open comports to choose which to disconnect

- `Write Line`: Brings up an input box at the bottom of the window to write a line to a comport.  If multiple comports are connected, brings up a list of open comports to choose first
  - Command/Write history is saved.  In the input box, use `Page Up` and `Page Down` to cycle through past entries

- `Write File`: Writes the active file to a comport.  If one or more regions are highlighted on the file, the selected text will be sent instead of the whole file.  If multiple comports are connected, brings up a list of open comports to choose first

- `Layout`: Switches the layout of the sublime window.  Left/Right puts all input files on the left and serial files on the right, Over/Under puts all input files on the top and output on the bottom


#### Advanced Commands
For those who want to use these commands for keybindings, etc.

`"command": "serial_monitor", "args":{"serial_command":"", ...}`

Currently supported `serial_command` values and optional args for each:

- `"connect"`:
 - `"comport": str` - The comport to connect to
 - `"baud": int` - The baud rate to connect with
- `"disconnect"`:
 - `"comport": str` - The comport to disconnect from
- `"write_line"`:
 - `"comport": str` - The comport to write a line to
 - `"text": str` - The text to write to the comport (newline appended to end automatically)
- `"write_file"`:
 - `"comport": str` - The comport to write the currently active file to
 - `"override_selection": bool` - set to true if you want to write the whole file regardless if a region is currently selected