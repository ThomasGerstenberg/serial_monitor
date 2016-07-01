import sublime
import sublime_plugin
from .command_history import CommandHistory

entry_history = CommandHistory()


class SerialMonitorUpdateEntryCommand(sublime_plugin.TextCommand):
    """
    Updates the serial monitor input view with the text provided
    """
    def run(self, edit, text):
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, 0, text)


class SerialMonitorEventListener(sublime_plugin.EventListener):
    def on_text_command(self, view, command, cmd_args):
        """
        Runs every time a text command is executed on a view.  If the view is the "serial input" view and
        the command is Page Up/Down, replace the command with the serial monitor update entry command
        """
        if not view.settings().get("serial_input"):
            return

        if command == "move" and cmd_args["by"] == "pages":
            # Page Up was pressed and there's more entries in the history
            if not cmd_args["forward"] and entry_history.has_next():
                return "serial_monitor_update_entry", {"text": entry_history.get_next()}
            # Page Down was pressed and there are more entries in the history
            elif cmd_args["forward"] and entry_history.has_previous():
                return "serial_monitor_update_entry", {"text": entry_history.get_previous()}

        if command == "reindent":
            sel = view.sel()
            return "serial_monitor_update_entry", {"text": str(sel)}

    def on_query_completions(self, view, prefix, locations):
        if not view.settings().get("serial_input"):
            return

        ret = []
        for i in range(1,12):
            ret.append(("t" * i,))
        return ret

def add_text_to_history(text):
    entry_history.add_entry(text)
