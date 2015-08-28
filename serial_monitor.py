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
        if "text" in args:
            self.view.insert(edit, self.view.size(), args["text"])
        else:
            view = sublime.View(args["view_id"])
            begin = args["region_begin"]
            end = args["region_end"]
            self.view.insert(edit, self.view.size(), view.substr(sublime.Region(begin, end)))
        self.view.set_read_only(True)


class SerialMonitor(threading.Thread):
    def __init__(self, comport, baud, view, window):
        super(SerialMonitor, self).__init__()
        self.comport = comport
        self.baud = baud
        self.view = view
        self.window = window
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
        self.running = False

    def run(self):
        i = 0
        while self.running and self.view.is_valid():
            main_thread(self.view.run_command, "serial_monitor_write", {"text": "{0}, ".format(i)})

            if self.text_to_write:
                main_thread(self.view.run_command, "serial_monitor_write", {"text": self.text_to_write})
                self.text_to_write = ""
            if self.file_to_write:
                view = self.file_to_write["view"]
                region = self.file_to_write["region"]
                main_thread(self.view.run_command, "serial_monitor_write", {"view_id": view.id(), "region_begin": region.begin(), "region_end": region.end()})
                self.file_to_write = {}

            i += 1
            time.sleep(1)

        if self.view.is_valid():
            main_thread(self.view.run_command, "serial_monitor_write", {"text": "\nDisconnected from {0}".format(self.comport)})
        main_thread(self.window.run_command, "serial_monitor", {"serial_command": "file_closed", "comport": self.comport})


class PortInfo(object):
    def __init__(self, comport="", function_callback=None, port_list=None):
        self.callback = function_callback
        self.port_list = port_list
        self.comport = comport
        self.baud = 0


class SerialMonitorCommand(sublime_plugin.WindowCommand):
    class PortListType(object):
        AVAILABLE = 1
        OPEN = 2

    def __init__(self, args):
        super(SerialMonitorCommand, self).__init__(args)
        self.settings = None
        self.output_view = None
        self.comport = None
        self.settings_name = "serial_monitor.sublime-settings"
        self.arg_map = {
            "connect":    self._select_port(self.connect, self.PortListType.AVAILABLE),
            "disconnect": self._select_port(self.disconnect, self.PortListType.OPEN),
            "write_line": self._select_port(self.write_line, self.PortListType.OPEN),
            "write_file": self._select_port(self.write_file, self.PortListType.OPEN),
            "file_closed": self.disconnected
        }
        self.open_ports = {}
        self.available_ports = []
        self.port_info = None

    def run(self, **args):
        self.settings = sublime.load_settings(self.settings_name)

        open_portnames = [k for k, v in self.open_ports.items()]
        self.available_ports = [c for c in comports if c not in open_portnames]

        func = self.arg_map[args.pop("serial_command")]

        port_info = PortInfo()

        if "comport" in args:
            port_info.comport = args["comport"]
        if "baud" in args:
            port_info.baud = args["baud"]

        func(port_info)


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
        self.open_ports[port_info.comport].disconnect()

    def disconnected(self, port_info):
        if port_info.comport in self.open_ports:
            self.open_ports.pop(port_info.comport)
            sublime.status_message("Disconnected from {0}".format(comport))

    def write_line(self, port_info):
        self.window.show_input_panel("Enter Text:", "", self._text_entered, None, self._text_entry_cancelled)

    def write_file(self, port_info):
        view = self.window.active_view()
        region = sublime.Region(0, view.size())
        self.open_ports[port_info.comport].write_file(view, region)

    def _select_port(self, func, list_type):
        def f(port_info):
            open_portnames = [k for k, v in self.open_ports.items()]

            if list_type == self.PortListType.AVAILABLE:
                port_list = self.available_ports
            else:
                port_list = open_portnames;

            if not port_list:
                sublime.status_message("No ports available")
                return

            port_info.callback = func
            port_info.port_list = port_list

            index = -1
            if len(port_info.port_list) == 1:
                port_info.comport = port_info.port_list[0]
                port_info.callback(port_info)
                return

            comport = self.settings.get("comport");
            if comport in port_info.port_list:
                index = port_info.port_list.index(comport)

            self.port_info = port_info
            self.window.show_quick_panel(port_info.port_list, self._port_selected, selected_index=index)

        return f

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

        sm_thread = SerialMonitor(port_info.comport, port_info.baud, view, self.window)
        self.open_ports[port_info.comport] = sm_thread
        sm_thread.start()

        sublime.status_message("Starting serial monitor on {0}".format(self.comport))
        sublime.save_settings(self.settings_name)

    def _text_entered(self, text):
        if text:
            self.open_ports[self.port_info.comport].write_line(text + "\n")

    def _text_entry_cancelled(self):
        pass