import sys
import os
from functools import partial

import sublime
import sublime_plugin

sys.path.append(os.path.dirname(__file__))

import serial_monitor_thread

TEST_MODE = True

# Load the correct serial implementation based on TEST_MODE
if not TEST_MODE:
    sys.path.append(os.path.join(os.path.dirname(__file__), "serial"))
    import serial
    from serial.tools import list_ports
else:
    from mock_serial.tools import list_ports
    import mock_serial as serial

# List of baud rates to choose from when opening a serial port
baud_rates = ["9600", "19200", "38400", "57600", "115200"]


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
    """
    Class for storing information during serial port selection, creation, deletion, etc.
    """
    def __init__(self, comport="", function_callback=None, port_list=None):
        self.comport = comport
        self.baud = 0
        self.text = ""
        self.port_list = port_list
        self.callback = function_callback


class SerialMonitorCommand(sublime_plugin.WindowCommand):
    """
    Main class for running commands using the serial monitor.  Available commands
        "serial_command": "connect" - Brings up dialogs to connect to a serial port
        "serial_command": "disconnect" - Brings up dialogs to disconnect from a serial port
        "serial_command": "write_line" - Writes a line to the serial port (newline appended automatically)
        "serial_command": "write_file" - Writes the currently active/focused file to the serial port

    Optional args for the commands:
        "comport": "COM1" - Comport to connect, disconnect, write, etc.
        "baud": 57600 - Baud rate to use for the "connect" command
        "text": "string" - text to write for the "write_line" command (newline appended automatically)
    """

    class PortListType(object):
        """
        Enum for selecting the port list to use when selecting a COM port
        """
        AVAILABLE = 0
        OPEN = 1

    def __init__(self, args):
        super(SerialMonitorCommand, self).__init__(args)
        self.settings = None
        self.settings_name = "serial_monitor.sublime-settings"

        # Map for the run command args and the functions to handle the command
        self.arg_map = {
            "connect":    self._select_port_wrapper(self.connect, self.PortListType.AVAILABLE),
            "disconnect": self._select_port_wrapper(self.disconnect, self.PortListType.OPEN),
            "write_line": self._select_port_wrapper(self.write_line, self.PortListType.OPEN),
            "write_file": self._select_port_wrapper(self.write_file, self.PortListType.OPEN),
            "_port_closed": self.disconnected
        }
        self.open_ports = {}
        self.available_ports = []

    def run(self, **args):
        self.settings = sublime.load_settings(self.settings_name)

        # Get a list of the available ports that aren't currently open
        self.available_ports = [c[0] for c in list_ports.comports() if c[0] not in self.open_ports]

        # Get the command and function callback to run
        try:
            command = args.pop("serial_command") 
        except KeyError:
            print("Missing serial_command argument")
            return
        try:
            func = self.arg_map[command]
        except KeyError:
            print("Unknown serial command: {0}".format(command))
            return

        # Create a port info object to pass in the args
        port_info = PortInfo()
        # If the args specify the comport or baud, get that now
        if "comport" in args:
            port_info.comport = args["comport"]
        if "baud" in args:
            port_info.baud = int(args["baud"])
        if "text" in args:
            port_info.text = args["text"]

        func(port_info)    

    def connect(self, port_info):
        """
        Handler for the "connect" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param port_info: The info of the port to connect to
        :type port_info: PortInfo
        """
        # If baud is already set, continue to port creation
        if port_info.baud != 0:
            self._create_port(port_info)
            return

        baud = self.settings.get("baud")
        index = -1
        if baud in baud_rates:
            index = baud_rates.index(str(baud))

        # Callback function for the baud selection quick panel
        def _baud_selected(p_info, selected_index):
            if selected_index == -1:
                return
            p_info.baud = baud_rates[selected_index]
            self.settings.set("baud", baud_rates[selected_index])
            self._create_port(p_info)

        self.window.show_quick_panel(baud_rates, partial(_baud_selected, port_info), selected_index=index)

    def disconnect(self, port_info):
        """
        Handler for the "disconnect" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param port_info: The info of the port to disconnect from
        :type port_info: PortInfo
        """
        self.open_ports[port_info.comport].disconnect()

    def disconnected(self, port_info):
        """
        Handler for the "_port_closed" command.  This function should only be called by the SerialMonitorThread class
        to inform that the port has been closed

        :param port_info: The info of the port that was disconnected
        :type port_info: PortInfo
        """
        sublime.status_message("Disconnected from {0}".format(port_info.comport))
        if port_info.comport in self.open_ports:
            self.open_ports.pop(port_info.comport)

    def write_line(self, port_info):
        """
        Handler for the "write_line" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param port_info: The info of the port to write to
        :type port_info: PortInfo
        """

        # Callback to send the text to the SerialMonitorThread that handles the read/write for the port
        def _text_entered(p_info, text):
            self.open_ports[p_info.comport].write_line(text + "\n")
            self.write_line(p_info)

        # Text was already specified from the command args, skip the user input
        if port_info.text:
            _text_entered(port_info, port_info.text)
        else:
            self.window.show_input_panel("Enter Text:", "", partial(_text_entered, port_info), None, None)

    def write_file(self, port_info):
        """
        Handler for the "write_file" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param port_info: The info of the port to write to
        :type port_info: PortInfo
        """
        view = self.window.active_view()
        region = sublime.Region(0, view.size())
        self.open_ports[port_info.comport].write_file(view, region)

    def _select_port_wrapper(self, func, list_type):
        """
        Wrapper function to select the comport based on the user input

        :param func: The function to wrap
        :param list_type: The type of list to use for selecting the comport
        :type list_type: SerialMonitorCommand.PortListType or int
        """
        def f(port_info):
            open_port_names = sorted(self.open_ports)

            if list_type == self.PortListType.AVAILABLE:
                port_list = self.available_ports
            else:
                port_list = open_port_names

            if not port_list:
                sublime.message_dialog("No ports available")
                return

            port_info.callback = func
            port_info.port_list = port_list

            # If the comport is alredy specified, skip the selection process
            if port_info.comport:
                port_info.callback(port_info)
                return
            # If there's only one port in the list, skip the selection process
            if len(port_info.port_list) == 1:
                port_info.comport = port_info.port_list[0]
                port_info.callback(port_info)
                return

            index = -1
            comport = self.settings.get("comport")
            if comport in port_info.port_list:
                index = port_info.port_list.index(comport)

            # Callback function for the port selection quick panel
            def _port_selected(p_info, selected_index):
                if selected_index == -1:
                    return
                p_info.comport = p_info.port_list[selected_index]
                self.settings.set("comport", p_info.comport)
                p_info.callback(p_info)
            self.window.show_quick_panel(port_info.port_list, partial(_port_selected, port_info), selected_index=index)
        return f

    def _create_port(self, port_info):
        """
        Creates and starts a SerialMonitorThread with the port info given

        :param port_info: The port info in order to open the serial port
        """
        view = self.window.new_file()
        view.set_name("{0}_output.txt".format(port_info.comport))
        view.set_read_only(True)
        serial_port = serial.Serial(None, port_info.baud, timeout=0.1)

        sm_thread = serial_monitor_thread.SerialMonitor(port_info.comport, serial_port, view, self.window)
        self.open_ports[port_info.comport] = sm_thread
        sm_thread.start()

        sublime.status_message("Starting serial monitor on {0}".format(port_info.comport))
