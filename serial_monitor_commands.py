import sys
import os
import time

import sublime
import sublime_plugin

sys.path.append(os.path.dirname(__file__))

import serial_monitor_thread
from serial_settings import SerialSettings
from filter.serial_filter import FilterFile, FilterException
from . import command_history_event_listener

from hardware import serial, list_ports
from stream.serial_text_stream import SerialTextStream

import serial_constants

# List of baud rates to choose from when opening a serial port
BAUD_RATES = ["9600", "19200", "38400", "57600", "115200"]


class SerialOptionSelector(object):
    """
    Class that helps select items from Sublime's drop-down menu
    """
    def __init__(self, items, header=None):
        """
        Creates the selector to show the items and header given

        :param items: the selectable items to show in the drop-down
        :type items: list or tuple of strings
        :param header: optional non-selectable item to be shown as the first entry in the list
        :type header: str
        """
        self.items = items.copy()
        self.header = header
        if header:
            self.items.insert(0, header)

    def show(self, callback, starting_index=0):
        """
        Shows the list for the user to choose from

        :param callback: function to call when the user has selected an item.
                         Should take 2 positional arguments: the string selected, the index selected
        :param starting_index: the index of the initial item to be highlighted when shown
        :type starting_index: int
        """
        starting_index = max(starting_index, 0)
        if self.header:
            starting_index += 1
        starting_index = min(starting_index, len(self.items))

        def item_selected(selected_index):
            if selected_index == -1:
                # User cancelled, do not call callback
                return
            if self.header and selected_index == 0:
                # User selected the header, show the dropdown again
                self.show(callback, -1)
                return

            item = self.items[selected_index]
            if self.header:
                selected_index -= 1

            callback(item, selected_index)

        sublime.active_window().show_quick_panel(self.items, item_selected, flags=sublime.KEEP_OPEN_ON_FOCUS_LOST, selected_index=starting_index)


class SerialMonitorCommand(sublime_plugin.ApplicationCommand):
    """
    Main class for running commands using the serial monitor
    """

    class PortListType(object):
        """
        Enum for selecting the port list to use when selecting a COM port
        """
        AVAILABLE = 0
        OPEN = 1

    def __init__(self):
        super(SerialMonitorCommand, self).__init__()
        self.default_settings = SerialSettings(None)

        try:
            self.last_settings = sublime.load_settings(serial_constants.LAST_USED_SETTINGS)
        except:
            self.last_settings = sublime.save_settings(serial_constants.LAST_USED_SETTINGS)

        # Map for the run command args and the functions to handle the command
        self.arg_map = {
            "connect":           self._select_port_wrapper(self.connect, self.PortListType.AVAILABLE),
            "disconnect":        self._select_port_wrapper(self.disconnect, self.PortListType.OPEN),
            "reconfigure_port":  self._select_port_wrapper(self.reconfigure_port, self.PortListType.OPEN),
            "write_line":        self._select_port_wrapper(self.write_line, self.PortListType.OPEN),
            "write_file":        self._select_port_wrapper(self.write_file, self.PortListType.OPEN),
            "new_buffer":        self._select_port_wrapper(self.new_buffer, self.PortListType.OPEN),
            "clear_buffer":      self._select_port_wrapper(self.clear_buffer, self.PortListType.OPEN),
            "timestamp_logging": self._select_port_wrapper(self.timestamp_logging, self.PortListType.OPEN),
            "line_endings":      self._select_port_wrapper(self.line_endings, self.PortListType.OPEN),
            "local_echo":        self._select_port_wrapper(self.local_echo, self.PortListType.OPEN),
            "filter":            self._select_port_wrapper(self.filter, self.PortListType.OPEN),
            "_port_closed":      self.disconnected
        }
        self.open_ports = {}

    def run(self, serial_command, **args):
        self.last_settings = sublime.load_settings(serial_constants.LAST_USED_SETTINGS)

        try:
            func = self.arg_map[serial_command]
        except KeyError:
            print("Unknown serial command: {0}".format(serial_command))
            return

        # Create a CommandArgs object to pass around the args
        command_args = SerialSettings(func, **args)
        func(command_args)
        sublime.save_settings(serial_constants.LAST_USED_SETTINGS)

    def connect(self, command_args):
        """
        Handler for the "connect" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to connect to
        :type command_args: SerialSettings
        """

        # Callback function for the baud selection quick panel
        def baud_selected(baud_rate, index):
            command_args.baud = baud_rate
            self.last_settings.set("baud", baud_rate)
            self._create_port(command_args)

        if self.default_settings.baud is not None:
            command_args.baud = self.default_settings.baud

        # If baud is already set, continue to port creation
        if command_args.baud is not None:
            self._create_port(command_args)
            return

        baud = self.last_settings.get("baud", 9600)
        index = -1
        if baud in BAUD_RATES:
            index = BAUD_RATES.index(str(baud))

        selector = SerialOptionSelector(BAUD_RATES, "Select Baud Rate:")
        selector.show(baud_selected, index)

    def disconnect(self, command_args):
        """
        Handler for the "disconnect" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to disconnect from
        :type command_args: SerialSettings
        """
        self.open_ports[command_args.comport].disconnect()

    def disconnected(self, command_args):
        """
        Handler for the "_port_closed" command.  This function should only be called by the SerialMonitorThread class
        to inform that the port has been closed

        :param command_args: The info of the port that was disconnected
        :type command_args: SerialSettings
        """
        sublime.status_message("Disconnected from {0}".format(command_args.comport))
        if command_args.comport in self.open_ports:
            self.open_ports.pop(command_args.comport)

    def write_line(self, command_args):
        """
        Handler for the "write_line" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to write to
        :type command_args: SerialSettings
        """
        # Callback to send the text to the SerialMonitorThread that handles the read/write for the port
        def _text_entered(text):
            output_view = self.open_ports[command_args.comport].view
            output_view.window().focus_view(output_view)
            output_view.window().run_command("serial_monitor_scroll", {"view_id": output_view.id()})
            self.open_ports[command_args.comport].write_line(text + "\n")
            self.write_line(command_args)
            command_history_event_listener.add_text_to_history(text)

        # Callback for when text was entered into the input panel.
        # If the user enters a newline (shift+enter), send it to the serial port since the entry is single lined
        def _text_changed(text):
            if text and text[-1] == '\n':
                _text_entered(text[:-1])  # Strip the newline from the end since it'll be appended by _text_entered

        # Text was already specified from the command args, skip the user input
        if command_args.text:
            _text_entered(command_args.text)
        else:
            input_view = sublime.active_window().show_input_panel("Enter Text (%s):" % command_args.comport, "",
                                                                  _text_entered, _text_changed, None)
            # Add setting to the view so it can be found by the event listener
            input_view.settings().set("serial_input", True)
            input_view.settings().set("gutter", False)
            input_view.assign_syntax("Packages/Python/Python.sublime-syntax")

    def write_file(self, command_args):
        """
        Handler for the "write_file" command.  Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to write to
        :type command_args: SerialSettings
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
        # if still ended up with an empty list (i.e. all regions in selection were empty), send the whole file
        if not regions:
            regions.append(sublime.Region(0, view.size()))

        output_view = self.open_ports[command_args.comport].view
        output_view.window().focus_view(output_view)
        output_view.window().run_command("serial_monitor_scroll", {"view_id": output_view.id()})
        self.open_ports[command_args.comport].write_file(view, regions)

    def clear_buffer(self, command_args):
        """
        Handler for the "clear_buffer" command.  Clears the current output for the serial port
        Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to configure
        :type command_args: SerialSettings
        """
        output_view = self.open_ports[command_args.comport].view
        output_view.run_command("serial_monitor_erase")

    def new_buffer(self, command_args):
        """
        Handler for the "new_buffer" command.  Creates a new output buffer for the serial port
        Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to configure
        :type command_args: SerialSettings
        """
        window = sublime.active_window()
        view = self._create_new_view(window, command_args.comport)
        self.open_ports[command_args.comport].set_output_view(view)

    def timestamp_logging(self, command_args):
        """
        Handler for the "timestamp_logging" command.
        Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to configure
        :type command_args: SerialSettings
        """
        # Choice list is arranged so that disable maps to 0 (False), enable maps to 1 (True)
        choice_list = ["Disable", "Enable"]

        def _logging_selected(item, selected_index):
            self.open_ports[command_args.comport].enable_timestamps(selected_index)

        if command_args.enable_timestamps is not None:
            self.open_ports[command_args.comport].enable_timestamps(command_args.enable_timestamps)
        else:
            selector = SerialOptionSelector(choice_list, "Timestamp Logging:")
            selector.show(_logging_selected)

    def line_endings(self, command_args):
        """
        Handler for the "line_endings" command.
        Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to configure
        :type command_args: SerialSettings
        """
        choice_list = ["CR", "LF", "CRLF"]

        def _line_endings_selected(line_ending, selected_index):
            self.open_ports[command_args.comport].set_line_endings(line_ending)

        if command_args.line_endings is not None:
            self.open_ports[command_args.comport].set_line_endings(command_args.line_endings)
        else:
            selector = SerialOptionSelector(choice_list, "Line Endings:")
            selector.show(_line_endings_selected)

    def reconfigure_port(self, command_args):
        """
        Handler for the "reconfigure_port" command.
        Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to configure
        :type command_args: SerialSettings
        """
        sm_thread = self.open_ports[command_args.comport]

        s = serial.SerialBase()
        baud_list = [b[0] for b in s.getSupportedBaudrates()]
        data_bits_list = [b[0] for b in s.getSupportedByteSizes()]
        stop_bits_list = [b[0] for b in s.getSupportedStopbits()]
        parity_list = s.getSupportedParities()

        config = sm_thread.get_config()

        def stop_bits_selected(bits, index):
            config.stop_bits = float(bits)
            if config.stop_bits == int(bits):
                config.stop_bits = int(bits)

            sm_thread.reconfigure_port(*config)

        def parity_selected(parity, index):
            config.parity = parity_list[index][1]
            index = self._get_index_or_default(stop_bits_list, str(config.stop_bits))
            selector = SerialOptionSelector(stop_bits_list, "Select Stop Bits:")
            selector.show(stop_bits_selected, index)

        def data_bits_selected(bits, index):
            config.data_bits = int(bits)
            index = self._get_index_or_default([p[1] for p in parity_list], str(config.parity))
            selector = SerialOptionSelector([p[0] for p in parity_list], "Select Parity:")
            selector.show(parity_selected, index)

        def baud_selected(baud, index):
            config.baud = int(baud)
            index = self._get_index_or_default(data_bits_list, str(config.data_bits))
            selector = SerialOptionSelector(data_bits_list, "Select Data Bits:")
            selector.show(data_bits_selected, index)

        index = self._get_index_or_default(baud_list, str(config.baud))
        selector = SerialOptionSelector(baud_list, "Select Baud Rate:")
        selector.show(baud_selected, index)

    def filter(self, command_args):
        """
        Handler for the "filter" command.
        Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to configure
        :type command_args: SerialSettings
        """
        choice_list = ["Add Filter", "Remove Filter"]

        filters = self.open_ports[command_args.comport].filters()

        def _enable_disable_selected(item, selected_index):
            if selected_index == 1:
                self._select_filtering_file(command_args, filters, False)
            elif selected_index == 0:
                self._select_filtering_file(command_args)

        if len(filters) != 0:
            selector = SerialOptionSelector(choice_list)
            selector.show(_enable_disable_selected)
        else:
            self._select_filtering_file(command_args)

    def local_echo(self, command_args):
        """
        Handler for the "local_echo" command.
        Is wrapped in the _select_port_wrapper to get the comport from the user

        :param command_args: The info of the port to configure
        :type command_args: SerialSettings
        """
        choice_list = ["Disable", "Enable"]

        def _echo_selected(item, selected_index):
            self.open_ports[command_args.comport].set_local_echo(selected_index)

        if command_args.local_echo is not None:
            self.open_ports[command_args.comport].set_local_echo(command_args.local_echo)
        else:
            selector = SerialOptionSelector(choice_list, "Local Echo:")
            selector.show(_echo_selected)

    def _get_index_or_default(self, items, item, default=0):
        """
        Helper function to get the index of an item in a list, or return a default index if it's not there
        :param items: the list to check in
        :param item: the item to find
        :param default: the default value to return if not found
        :return: the index of the item in items
        """
        if item in items:
            default = items.index(item)
        return default

    def _select_port_wrapper(self, func, list_type):
        """
        Wrapper function to select the comport based on the user input

        :param func: The function to wrap
        :param list_type: The type of list to use for selecting the comport
        :type list_type: SerialMonitorCommand.PortListType or int
        """
        def wrapper(command_args):
            def _port_assigned():
                self.default_settings = SerialSettings.load_defaults(command_args.comport)
                self.last_settings.set("comport", command_args.comport)
                command_args.callback(command_args)

            open_port_names = sorted(self.open_ports)

            if list_type == self.PortListType.AVAILABLE:
                # Get a list of the available ports that aren't currently open
                port_list = [c for c in list_ports() if c not in self.open_ports]
            else:
                port_list = open_port_names

            if not port_list:
                sublime.message_dialog("No serial ports {}".format("open" if list_type == self.PortListType.OPEN else "available"))
                return

            command_args.callback = func
            command_args.port_list = port_list

            # If the comport is already specified, skip the selection process
            if command_args.comport:
                _port_assigned()
                return

            # If there's only one port in the list, skip the selection process
            if len(command_args.port_list) == 1:
                command_args.comport = command_args.port_list[0]
                _port_assigned()
                return

            index = -1
            comport = self.last_settings.get("comport", "COM1")
            if comport in command_args.port_list:
                index = command_args.port_list.index(comport)

            # Callback function for the port selection quick panel
            def _port_selected(selected_comport, selected_index):
                command_args.comport = selected_comport
                _port_assigned()

            selector = SerialOptionSelector(command_args.port_list, "Select Port:")
            selector.show(_port_selected, index)

        return wrapper

    def _create_new_view(self, window, comport, suffix=""):
        """
        Creates a new view for the serial output buffer

        :param window: The parent window for the view
        :param comport: The name of the comport the view is for

        :return: The newly created view
        """
        filename = "{0}_{1}_{2}.txt".format(comport.replace("/dev/", "", 1), suffix, time.strftime("%m-%d-%y_%H-%M-%S", time.localtime()))
        if window.num_groups() > 1:
            window.focus_group(1)

        view = window.new_file()
        view.set_name(filename)
        view.set_read_only(True)
        view.set_syntax_file(serial_constants.SYNTAX_FILE)
        return view

    def _merge_args_with_defaults(self, command_args):
        for attr in SerialSettings.SETTINGS_LIST:
            if getattr(command_args, attr) is None:
                default_value = getattr(self.default_settings, attr)
                setattr(command_args, attr, default_value)

    def _create_port(self, command_args):
        """
        Creates and starts a SerialMonitorThread with the port info given

        :param command_args: The port info in order to open the serial port
        :type command_args: SerialSettings
        """
        # Create the serial port without specifying the comport so it does not automatically open
        stream = SerialTextStream(command_args)

        window = sublime.active_window()
        view = self._create_new_view(window, command_args.comport)

        sm_thread = serial_monitor_thread.SerialMonitor(stream, view, window)

        self._merge_args_with_defaults(command_args)
        sm_thread.enable_timestamps(command_args.enable_timestamps)
        sm_thread.set_line_endings(command_args.line_endings)
        sm_thread.set_local_echo(command_args.local_echo)

        self.open_ports[command_args.comport] = sm_thread
        sm_thread.start()

        sublime.status_message("Starting serial monitor on {0}".format(command_args.comport))

    def _select_filtering_file(self, command_args, remove_list=list(), add_filter=True):
        filter_files = []
        if add_filter:
            sm_views = [sm.view for sm in self.open_ports.values()]
            for window in sublime.windows():
                for view in window.views():
                    if view in sm_views:
                        continue

                    if "json" not in view.settings().get("syntax").lower():
                        continue

                    try:
                        f = FilterFile.parse_filter_file(view.substr(sublime.Region(0, view.size())), True)
                        if f:
                            filter_files.append(f)
                    except FilterException:
                        pass
        else:
            filter_files = remove_list

        if not filter_files:
            sublime.message_dialog("Unable to find any valid filters")
            return

        selection_header = "Select filter to {}:".format("add" if add_filter else "remove")
        selections = [f.name for f in filter_files]
        sm_thread = self.open_ports[command_args.comport]

        def _filter_selected(item, selected_index):
                filter_file = filter_files[selected_index]
                if add_filter:
                    filter_view = self._create_new_view(sublime.active_window(), command_args.comport, filter_file.name)
                    sm_thread.add_filter(filter_file, filter_view)
                else:
                    sm_thread.remove_filter(filter_file)

        selector = SerialOptionSelector(selections, selection_header)
        selector.show(_filter_selected)
