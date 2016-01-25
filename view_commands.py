import sublime
import sublime_plugin


class SerialMonitorWriteCommand(sublime_plugin.TextCommand):
    """
    Writes text (or a file) to the serial output view the command is run on
    """
    def run(self, edit, **args):
        """
        Runs the command to write to a serial output view
        :param args: The args for writing to the view.  Needs to contain:
                    "text": string of text to write to the view
                    or
                    "view_id": The id of the input view
                    "region_begin": Starting index for the input view
                    "region_end": Ending index for the input view
        :type args: dict
        :return:
        """

        # Check if the end of the output file is visible.  If so, enable the auto-scroll
        should_autoscroll = self.view.visible_region().contains(self.view.size())

        self.view.set_read_only(False)
        if "text" in args:
            self.view.insert(edit, self.view.size(), args["text"])
        else:
            view = sublime.View(args["view_id"])
            begin = args["region_begin"]
            end = args["region_end"]
            self.view.insert(edit, self.view.size(), view.substr(sublime.Region(begin, end)))
        self.view.set_read_only(True)

        if should_autoscroll and not self.view.visible_region().contains(self.view.size()):
            self.view.window().run_command("serial_monitor_scroll", {"view_id": self.view.id()})


class SerialMonitorEraseCommand(sublime_plugin.TextCommand):
    """
    Clears the view
    """
    def run(self, edit, **args):
        self.view.set_read_only(False)
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.set_read_only(True)


class SerialMonitorScrollCommand(sublime_plugin.WindowCommand):
    """
    Scrolls to the end of a view
    """
    def run(self, view_id):
        last_focused = self.window.active_view()
        view = sublime.View(view_id)
        self.window.focus_view(view)
        view.show(view.size())
        self.window.focus_view(last_focused)


class SerialMonitorUpdateEntryCommand(sublime_plugin.TextCommand):
    """
    Updates the serial monitor input view with the text provided
    """
    def run(self, edit, text):
        self.view.erase(edit, sublime.Region(0, self.view.size()))
        self.view.insert(edit, 0, text)


class SerialMonitorNewFilterCommand(sublime_plugin.WindowCommand):
    def run(self):
        self.window.new_file()