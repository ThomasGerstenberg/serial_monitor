import sublime, sublime_plugin
import sys
import os
import functools
import threading
import time

sys.path.append(os.path.dirname(__file__))

import serial_monitor_thread

TEST_MODE = False

if not TEST_MODE:
    sys.path.append(os.path.join(os.path.dirname(__file__), "serial"))
    import serial
    from serial.tools import list_ports
else:
    class MockListPorts(object):
        NUM_PORTS = 5
        def __init__(self):
            self.port_list = [("COM" + str(i), "Desc" + str(i), "HW" + str(i)) for i in range(1, self.NUM_PORTS + 1)]

        def comports(self):
            return self.port_list

    class MockSerial(object):
        class Serial(object):
            def __init__(self, *args, **kwargs):
                pass

            def open(self):
                pass

            def write(self, text):
                pass

            def read(self, size):
                pass

    # from mock_serial import MockSerial, MockListPorts
    list_ports = MockListPorts()
    serial = MockSerial()


baud_rates = ["9600", "19200", "38400", "57600", "115200"]

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
        # print(list_ports.port_list)
        open_portnames = [k for k, v in self.open_ports.items()]
        self.available_ports = [c[0] for c in list_ports.comports() if c[0] not in open_portnames]

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
            sublime.status_message("Disconnected from {0}".format(port_info.comport))

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
                sublime.message_dialog("No ports available")
                return

            port_info.callback = func
            port_info.port_list = port_list
            self.port_info = port_info

            index = -1
            if len(port_info.port_list) == 1:
                port_info.comport = port_info.port_list[0]
                port_info.callback(port_info)
                return

            comport = self.settings.get("comport");
            if comport in port_info.port_list:
                index = port_info.port_list.index(comport)

            self.window.show_quick_panel(port_info.port_list, self._port_selected, selected_index=index)
        return f

    def _port_selected(self, selected_index):
        if selected_index == -1:
            return
        self.port_info.comport = self.port_info.port_list[selected_index]
        self.settings.set("comport", self.port_info.comport)
        self.port_info.callback(self.port_info)

    def _baud_selected(self, selected_index):
        if selected_index == -1:
            return
        self.port_info.baud = baud_rates[selected_index]
        self.settings.set("baud_rate", baud_rates[selected_index])
        self._create_port(self.port_info)

    def _create_port(self, port_info):
        view = None
        view = self.window.new_file()
        view.set_name("{0}_output.txt".format(port_info.comport))
        view.set_read_only(True)
        serial_port = serial.Serial(None, port_info.baud, timeout=0.1)

        sm_thread = serial_monitor_thread.SerialMonitor(port_info.comport, serial_port, view, self.window)
        self.open_ports[port_info.comport] = sm_thread
        sm_thread.start()

        sublime.status_message("Starting serial monitor on {0}".format(self.comport))

    def _text_entered(self, text):
        if text:
            self.open_ports[self.port_info.comport].write_line(text + "\n")

    def _text_entry_cancelled(self):
        pass