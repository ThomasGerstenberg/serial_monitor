## Sublime 3 Serial Monitor

This plugin is built upon [pyserial](https://github.com/pyserial/pyserial)

To install, clone this repository into `C:\Users\${user}\AppData\Roaming\Sublime Text 3\Packages` and restart sublime

### Commands
Commands are accessed through `Menu->Tools->Serial Monitor` or the Command Palette (`ctrl+shift+p`).  
For all commands, if multiple ports are available a list will first be shown to choose the comport to run the command on

- `Connect`: Brings up dialogs to connect to a comport.  If more than one comport is available, brings up a list of available comports before choosing a baud rate

- `Disconnect`: Brings up a list of connected comports to disconnect from

- `Write Line`: Brings up an input box at the bottom of the window to write a line to a comport.
  - Command/Write history is saved.  In the input box, use `Page Up` and `Page Down` to cycle through past entries

- `Write File`: Writes the active file to a comport

- `Write Selection(s)`: Writes the selected text to the comport.  Supports multiple selection regions (each selection will be on its own line).  If no text is selected, writes the whole file.

- `New Buffer`: Opens up a new output buffer for the comport

- `Clear Buffer`: Clears the current output buffer for the comport

- `Timestamp Logging`: Brings up dialog to enable or disable adding timestamps to the beginning of each line.  Timestamps are formatted as `[yy-mm-dd hh:mm:ss.xxx]`

- `Local Echo`: Brings up dialog to enable/disable local echo.  Local echo will write all input to the output window

- `Filtering`: Brings up a menu to enable/disable filtering of the serial port using a filtering file (see next command).  Filtering will create another buffer alongside the main output window to display filtered lines of text based on the filter file of your choice

- `New Filter`: Creates a new filter template file for the above command.  Template contains more details on the filtering as well.  Right clicking a single-line highlighted selection in the output window will bring up an option to create a filter from the selected text

- `Line Endings`: Set the line endings type of the comport so the data is correctly displayed in the output.  Sublime only cares about Line Feeds, so the text will be edited based on the setting
 - `CR`: Line endings are carriage return characters only.  All `CR` characters (`\r`) will be converted to `LF` (`\n`)
 - `LF`: Line endings are line feed characters only.  No text manipulation occurs
 - `CRLF`: Line endings contain both `CR` and `LF`.  `CR` characters are removed (default)

- `Layout`: Switches the layout of the sublime window.  Left/Right puts all input files on the left and serial files on the right, Over/Under puts all input files on the top and output on the bottom


### Preferences
Global and port-specific preferences can be specified under `Preferences->Package Settings->Serial Monitor->Settings - User`.
All of the preference possibilities go into more detail in the `Settings - Default` option in the same menu; use that file as a template for your own preferences


#### Advanced Commands
For those who want to use these commands for keybindings, etc.

`"command": "serial_monitor", "args":{"serial_command":"", ...}`

Currently supported `serial_command` values and optional args for each:

- `"connect"`:
 - `"comport": str` - The comport to connect to
 - `"baud": int` - The baud rate to connect with
 - `"enable_timestamps": bool` - Enable or disable timestamped logging upon connection
 - `"line_endings": str` - The line ending settings to use.  Should be `CR`, `LF`, or `CRLF`

- `"disconnect"`:
 - `"comport": str` - The comport to disconnect from

- `timestamp_logging`:
 - `"comport": str` - The comport to enable/disable timestamp logging on
 - `"enable_timestamps": bool` - True to enable, False to Disable

- `local_echo`:
 - `"comport": str` - the comport to enable/disable local echo on
 
- `line_endings`:
 - `"line_endings": str` - THe line ending settings to use.  See above for valid values

- `new_buffer`:
 - `"comport": str` - The comport to create a new buffer for

- `clear_buffer`:
 - `"comport": str` - The comport to create a clear the buffer on

- `"write_line"`:
 - `"comport": str` - The comport to write a line to
 - `"text": str` - The text to write to the comport (newline appended to end automatically)

- `"write_file"`:
 - `"comport": str` - The comport to write the currently active file to
 - `"override_selection": bool` - set to true if you want to write the whole file regardless if a region is currently selected

- `filter`:
 - `"comport": str` - the comport to enable/disable filtering on
