import sys
import os
from functools import partial

import sublime
import sublime_plugin

sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), "serial"))

import serial_monitor_thread

# Check if test mode is enabled
TEST_MODE = False
settings = sublime.load_settings("serial_monitor.sublime-settings")
if settings.get("test_mode"):
    print("Serial Monitor: Test Mode enabled")
    TEST_MODE = True
del settings

# Load the correct serial implementation based on TEST_MODE
if not TEST_MODE:
    import serial
    from serial.tools import list_ports
else:
    from mock_serial.tools import list_ports
    import mock_serial as serial

# List of baud rates to choose from when opening a serial port
BAUD_RATES = ["9600", "19200", "38400", "57600", "115200"]


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


class CommandArgs(object):
    """
    Class for storing information during serial port selection, creation, deletion, etc.
    """
    def __init__(self, comport="", baud=0, text="", function_callback=None, port_list=None, override_selection=False):
        self.comport = comport
        self.baud = baud
        self.text = text
        self.port_list = port_list
        self.callback = function_callback
        self.override_selection = override_selection


class SerialMonitorCommand(sublime_plugin.ApplicationCommand):
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
        "override_selection": true - use this to indicate that whenever writing a file,
                                     always write the whole file and not just the selection
    """

    class PortListType(object):
        """
        Enum for selecting the port list to use when selecting a COM port
        """
        AVAILABLE = 0
        OPEN = 1

    def __init__(self):
        super(SerialMonitorCommand, self).__init__()
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

    def run(self, serial_command, comport="", baud=0, text="", override_selection=False, **args):
        self.settings = sublime.load_settings(self.settings_name)

        # Get a list of the available ports that aren't currently open
        self.available_ports = [c[0] for c in list_ports.comports() if c[0] not in self.open_ports]

        try:
            func = self.arg_map[serial_command]
        except KeyError:
            print("Unknown serial command: {0}".format(serial_command))
            return

        # Create a CommandArgs object to pass around the args
        command_args = CommandArgs(comport=str(comport), baud=int(baud), text=str(text),
                                   function_callback=func, override_selection=bool(override_selection))

        func(command_args)
        sublime.save_settings(self.settings_name)

    def connect(self, command_args):
        """
        Handler for the "connect" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to connect to
        :type command_args: CommandArgs
        """
        # If baud is already set, continue to port creation
        if command_args.baud != 0:
            self._create_port(command_args)
            return

        baud = self.settings.get("baud")
        index = -1
        if baud in BAUD_RATES:
            index = BAUD_RATES.index(str(baud))

        # Callback function for the baud selection quick panel
        def _baud_selected(p_info, selected_index):
            if selected_index == -1:
                return
            p_info.baud = BAUD_RATES[selected_index]
            self.settings.set("baud", BAUD_RATES[selected_index])
            self._create_port(p_info)

        sublime.active_window().show_quick_panel(BAUD_RATES, partial(_baud_selected, command_args),
                                                 selected_index=index)

    def disconnect(self, command_args):
        """
        Handler for the "disconnect" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to disconnect from
        :type command_args: CommandArgs
        """
        self.open_ports[command_args.comport].disconnect()

    def disconnected(self, command_args):
        """
        Handler for the "_port_closed" command.  This function should only be called by the SerialMonitorThread class
        to inform that the port has been closed

        :param command_args: The info of the port that was disconnected
        :type command_args: CommandArgs
        """
        sublime.status_message("Disconnected from {0}".format(command_args.comport))
        if command_args.comport in self.open_ports:
            self.open_ports.pop(command_args.comport)

    def write_line(self, command_args):
        """
        Handler for the "write_line" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to write to
        :type command_args: CommandArgs
        """

        # Callback to send the text to the SerialMonitorThread that handles the read/write for the port
        def _text_entered(p_info, text):
            sublime.active_window().run_command("serial_monitor_scroll",
                                                {"view_id": self.open_ports[p_info.comport].view.id()})

            self.open_ports[p_info.comport].write_line(text + "\n")
            self.write_line(p_info)

        # Text was already specified from the command args, skip the user input
        if command_args.text:
            _text_entered(command_args, command_args.text)
        else:
            sublime.active_window().show_input_panel("Enter Text:", "", partial(_text_entered, command_args),
                                                     None, None)

    def write_file(self, command_args):
        """
        Handler for the "write_file" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to write to
        :type command_args: CommandArgs
        """
        view = sublime.active_window().active_view()
        if view in [sm.view for sm in self.open_ports.values()]:
            sublime.message_dialog("Cannot write output view to serial port")
            return

        selection = view.sel()
        # if there's only one selection and is empty (or user wants to override selection regions),
        # set the list to the whole file
        if (len(selection) == 1 and selection[0].empty()) or command_args.override_selection:
            regions = [sublime.Region(0, view.size())]
        else:
            regions = [r for r in selection if not r.empty()]  # disregard any empty regions
        # if we still ended up with an empty list (i.e. all regions in selection were empty), send the whole file
        if not regions:
            regions.append(sublime.Region(0, view.size()))

        sublime.active_window().run_command("serial_monitor_scroll",
                                            {"view_id": self.open_ports[command_args.comport].view.id()})
        self.open_ports[command_args.comport].write_file(view, regions)

    def _select_port_wrapper(self, func, list_type):
        """
        Wrapper function to select the comport based on the user input

        :param func: The function to wrap
        :param list_type: The type of list to use for selecting the comport
        :type list_type: SerialMonitorCommand.PortListType or int
        """
        def f(command_args):
            open_port_names = sorted(self.open_ports)

            if list_type == self.PortListType.AVAILABLE:
                port_list = self.available_ports
            else:
                port_list = open_port_names

            if not port_list:
                sublime.message_dialog("No ports available")
                return

            command_args.callback = func
            command_args.port_list = port_list

            # If the comport is alredy specified, skip the selection process
            if command_args.comport:
                command_args.callback(command_args)
                return
            # If there's only one port in the list, skip the selection process
            if len(command_args.port_list) == 1:
                command_args.comport = command_args.port_list[0]
                command_args.callback(command_args)
                return

            index = -1
            comport = self.settings.get("comport")
            if comport in command_args.port_list:
                index = command_args.port_list.index(comport)

            # Callback function for the port selection quick panel
            def _port_selected(p_info, selected_index):
                if selected_index == -1:
                    return
                p_info.comport = p_info.port_list[selected_index]
                self.settings.set("comport", p_info.comport)
                p_info.callback(p_info)
            sublime.active_window().show_quick_panel(command_args.port_list, partial(_port_selected, command_args),
                                                     selected_index=index)
        return f

    def _create_port(self, command_args):
        """
        Creates and starts a SerialMonitorThread with the port info given

        :param command_args: The port info in order to open the serial port
        """
        window = sublime.active_window()
        last_focused = window.active_view()
        if window.num_groups() > 1:
            window.focus_group(1)
        view = window.new_file()
        view.set_name("{0}_output.txt".format(command_args.comport))
        view.set_read_only(True)
        window.focus_view(last_focused)

        serial_port = serial.Serial(None, command_args.baud, timeout=0.1)
        sm_thread = serial_monitor_thread.SerialMonitor(command_args.comport, serial_port, view, window)
        self.open_ports[command_args.comport] = sm_thread
        sm_thread.start()

        sublime.status_message("Starting serial monitor on {0}".format(command_args.comport))
