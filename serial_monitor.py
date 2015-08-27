import sublime, sublime_plugin
import sys
import os
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), "serial"))
import serial


comports = ["COM" + str(i) for i in range(1, 5)]
baud_rates = ["9600", "19200", "38400", "57600", "115200"]


class SerialMonitorWriteOutput(sublime_plugin.TextCommand):
    def run(self, edit, text):
        self.view.set_read_only(False)
        self.view.insert(edit, 0, text)
        self.view.set_read_only(True)


class SerialMonitorCommand(sublime_plugin.WindowCommand):
    def __init__(self, args):
        super(SerialMonitorCommand, self).__init__(args)
        self.settings = None
        self.output_view = None
        self.comport = None
        self.settings_name = "serial_monitor.sublime-settings"

    def run(self):
        self.settings = sublime.load_settings(self.settings_name)

        index = -1
        comport = self.settings.get("comport")
        if comport in comports:
            index = comports.index(comport)
        self.window.show_quick_panel(comports, self.port_selected, selected_index=index)

    def port_selected(self, selected_index):
        if selected_index == -1:
            return
        self.comport = comports[selected_index]
        self.settings.set("comport", comports[selected_index])
        index = -1
        baud = self.settings.get("baud_rate")
        if baud in baud_rates:
            index = baud_rates.index(str(baud))

        self.window.show_quick_panel(baud_rates, self.baud_selected, selected_index=index)

    def baud_selected(self, selected_index):
        if selected_index == -1:
            return
        self.settings.set("baud_rate", baud_rates[selected_index])
        self.output_view = self.window.new_file()
        self.output_view.set_name("{0}_output.txt".format(self.comport))
        self.output_view.set_read_only(True)
        self.output_view.run_command("serial_monitor_write_output", {"text":"abcd"})
        sublime.status_message("Starting serial monitor on {0}".format(self.comport))
        sublime.save_settings(self.settings_name)
