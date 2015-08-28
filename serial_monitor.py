import sublime, sublime_plugin
import sys
import os
import functools
import threading
import time
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), "serial"))
import serial



comports = ["COM" + str(i) for i in range(1, 5)]
baud_rates = ["9600", "19200", "38400", "57600", "115200"]

def main_thread(callback, *args, **kwargs):
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)


class SerialMonitorWriteCommand(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        self.view.set_read_only(False)
        self.view.insert(edit, self.view.size(), args["text"])
        self.view.set_read_only(True)

class SerialMonitor(threading.Thread):
    def __init__(self, comport, baud, view):
        super(SerialMonitor, self).__init__()
        self.comport = comport
        self.baud = baud
        self.view = view
        self.lock = threading.Lock()
        self.running = True;
        self.text_to_write = ""
        self.file_to_write = {}

    def write_line(self, text):
        if self._write_waiting():
            return False
        self.text_to_write = text
        return True

    def write_file(self, view, region):
        if self._write_waiting():
            return False
        self.file_to_write = {"view": view, "region": region}
        return True

    def _write_waiting(self):
        return self.file_to_write or self.text_to_write

    def disconnect(self):
        main_thread(sublime.status_message, "Disconnecting from {0}".format(self.comport))
        self.running = False

    def run(self):
        i = 0
        while self.running and self.view.is_valid():
            main_thread(self.view.run_command, "serial_monitor_write", {"text": "{0}, ".format(i)})

            if self.text_to_write:
                main_thread(self.view.run_command, "serial_monitor_write", {"text": self.text_to_write})
                self.text_to_write = ""
            if self.file_to_write:
                main_thread(self.view.run_command, "serial_monitor_write", {"view": self.file_to_write["view"], "region": self.file_to_write["region"]})
                self.file_to_write = {}

            i += 1
            time.sleep(1)
        main_thread(sublime.status_message, "Disconnecting from {0}".format(self.comport))

class PortInfo(object):
    def __init__(self, comport="", function_callback=None, port_list=None):
        self.callback = function_callback
        self.port_list = port_list
        self.comport = comport
        self.baud = 0

class SerialMonitorLayoutCommand(sublime_plugin.WindowCommand):
    layouts = [
        {
            "cols": [0.0, 0.5, 1.0],
            "rows": [0.0, 1.0],
            "cells": [[0, 0, 1, 1], [1, 0, 2, 1]]
        }, 
        {
            "cols": [0.0, 1.0],
            "rows": [0.0, 0.5, 1.0],
            "cells": [[0, 0, 1, 1], [0, 1, 1, 2]]
        }
    ]
    layout_names = ["Left-Right", "Over-Under"]

    def run(self):
        self.window.show_quick_panel(self.layout_names, self.layout_selected)

    def layout_selected(self, index):
        if index == -1:
            return
        self.window.run_command("set_layout", self.layouts[index])

        for view in self.window.views():
            group = 0
            fname = view.file_name()
            if fname and fname.endswith(".py"):
                group = 1
            view.run_command("move_to_group", {"group":1})





class SerialMonitorCommand(sublime_plugin.WindowCommand):
    def __init__(self, args):
        super(SerialMonitorCommand, self).__init__(args)
        self.settings = None
        self.output_view = None
        self.comport = None
        self.settings_name = "serial_monitor.sublime-settings"
        self.arg_map = {
            "connect": self.connect, 
            "disconnect": self.disconnect,
            "write_line": self.write_line,
            "write_file": self.write_file
        }
        self.open_ports = {}
        self.available_ports = []
        self.port_info = None

    def run(self, **args):
        self.settings = sublime.load_settings(self.settings_name)

        open_portnames = [k for k, v in self.open_ports.items()]
        self.available_ports = [c for c in comports if c not in open_portnames]

        func = self.arg_map[args.pop("serial_command")]
        if func == self.connect:
            port_list = self.available_ports
        else:
            port_list = open_portnames;

        print(self.available_ports)
        print(open_portnames)

        if not port_list:
            sublime.status_message("No ports available")
            return
    
        self.port_info = PortInfo(function_callback=func, port_list=port_list)
        if "comport" in args:
            self.port_info.comport = args["comport"]
        if "baud_rate" in args:
            self.port_info.baud = args["baud_rate"]

        self._select_port(self.port_info)

    def connect(self, port_info):
        index = -1
        if port_info.baud != 0:
            baud = port_info.baud
        else:
            baud = self.settings.get("baud_rate")
        if baud in baud_rates:
            index = baud_rates.index(str(baud))

        self.window.show_quick_panel(baud_rates, self._baud_selected, selected_index=index)

    def disconnect(self, port_info):
        self.open_ports.pop(port_info.comport).disconnect()

    def write_line(self, port_info):
        self.open_ports[port_info.comport].write_line("abcdef\n")

    def write_file(self, port_info):
        view = self.window.active_view()
        region = sublime.Region(0, view.size())
        self.open_ports[port_info.comport].write_file(view, region)

    def _select_port(self, port_info):
        index = -1
        if port_info.comport:
            comport = port_info.comport
        else:
            comport = self.settings.get("comport");
        if comport in port_info.port_list:
            index = port_info.port_list.index(comport)
        self.window.show_quick_panel(port_info.port_list, self._port_selected, selected_index=index)

    def _port_selected(self, selected_index):
        if selected_index == -1:
            return
        self.port_info.comport = self.port_info.port_list[selected_index]
        self.settings.set("comport", comports[selected_index])
        self.port_info.callback(self.port_info)

    def _baud_selected(self, selected_index):
        if selected_index == -1:
            return
        self.port_info.baud = baud_rates[selected_index]
        self.settings.set("baud_rate", baud_rates[selected_index])
        self._open_port(self.port_info)

    def _open_port(self, port_info):
        view = None
        view = self.window.new_file()
        view.set_name("{0}_output.txt".format(port_info.comport))
        view.set_read_only(True)

        sm_thread = SerialMonitor(port_info.comport, port_info.baud, view)
        self.open_ports[port_info.comport] = sm_thread
        sm_thread.start()

        sublime.status_message("Starting serial monitor on {0}".format(self.comport))
        sublime.save_settings(self.settings_name)
