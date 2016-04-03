import sublime
import functools
import threading
import time

def main_thread(callback, *args, **kwargs):
    """
    Sends the callback to the sublime main thread by using the sublime.set_timeout function.
    Most of the sublime functions need to be called from the main thread

    :param callback: The callback function
    :param args: positional args to send to the callback function
    :param kwargs: keyword args to send to the callback function
    """
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)

class _WriteFileArgs(object):
    def __init__(self, view, regions):
        self.view = view
        self.regions = regions


class _FilterArgs(object):
    def __init__(self, filter_file, view):
        """
        :type filter_file: serial_filter.FilterFile
        :type view: sublime.View
        """
        self.filter_file = filter_file
        self.view = view

    def apply(self, text, timestamp=""):
        if self.filter_file.check_filters(text):
            self.write(text, timestamp)

    def write(self, text, timestamp=""):
        main_thread(self.view.run_command, "serial_monitor_write", {"text": timestamp + text})


class _FilterManager(object):
    def __init__(self):
        super(_FilterManager, self).__init__()
        self._filters = []
        self.filter_lock = threading.Lock()
        self._incomplete_line = ""

    def add_filter(self, new_filter, output_view):
        """
        :type new_filter: serial_filter.FilterFile
        """
        filter_args = _FilterArgs(new_filter, output_view)
        with self.filter_lock:
            self._filters.append(filter_args)

    def remove_filter(self, filter_to_remove):
        """
        :type filter_to_remove: serial_filter.FilterFile
        """
        filter_files = [f.filter_file for f in self._filters]
        if filter_to_remove in filter_files:
            with self.filter_lock:
                i = filter_files.index(filter_to_remove)
                filter_args = self._filters[i]
                filter_args.write("Filter Disabled")
                self._filters.remove(filter_args)

    def port_closed(self, port_name):
        with self.filter_lock:
            for f in self._filters:
                f.write("Disconnected from {}".format(port_name))

    def filters(self):
        return [f.filter_file for f in self._filters]

    def apply_filters(self, text, timestamp=""):
        if len(self._filters) == 0:
            return
        lines = self._split_text(text)
        if len(lines) == 0:
            return

        filters_to_remove = []
        # Loop through all lines and all filters for matches
        for line in lines:
            with self.filter_lock:
                for f in self._filters:
                    if not f.view or not f.filter_file:
                        continue

                    if not f.view.is_valid():
                        filters_to_remove.append(f)
                    else:
                        f.apply(line, timestamp)

        # If any filters have invalid views, remove from the list
        with self.filter_lock:
            for f in filters_to_remove:
                self._filters.remove(f)

    def _split_text(self, text):
        lines = text.splitlines(True)
        if len(lines) == 0:
            return lines

        # Append the last incomplete line to the beginning of this text
        lines[0] = self._incomplete_line + lines[0]
        self._incomplete_line = ""

        # Check if the last line is complete.  If not, pop it from the end of the list and save it as an incomplete line
        if not lines[-1].endswith("\n"):
            self._incomplete_line = lines.pop()
        return lines


class SerialMonitor(threading.Thread):
    """
    Thread that controls a serial port's read, write, open, close, etc. and outputs the serial info to a sublime view
    """
    def __init__(self, comport, serial, view, window):
        super(SerialMonitor, self).__init__()
        self.comport = comport
        self.serial = serial
        self.view = view
        self.window = window
        self.lock = threading.Lock()
        self.running = False
        self.timestamp_logging = False
        self.line_endings = "CRLF"
        self.local_echo = False
        self._text_to_write = []
        self._file_to_write = []
        self._text_lock = threading.Lock()
        self._file_lock = threading.Lock()
        self._view_lock = threading.Lock()
        self._filter_manager = _FilterManager()
        self._newline = True

        self._new_configuration = False
        self._new_baud = None
        self._new_data_bits = None
        self._new_parity = None
        self._new_stop_bits = None

    def write_line(self, text):
        with self._text_lock:
            self._text_to_write.append(text)

    def write_file(self, view, selection):
        file_args = _WriteFileArgs(view, selection)
        with self._file_lock:
            self._file_to_write.append(file_args)

    def disconnect(self):
        self.running = False

    def enable_timestamps(self, enabled):
        self.timestamp_logging = enabled

    def set_output_view(self, view):
        with self._view_lock:
            self.view = view

    def set_line_endings(self, line_endings):
        if line_endings.upper() in ["CR", "LF", "CRLF"]:
            self.line_endings = line_endings.upper()
            return True

        print("Unknown line ending: %s" % line_endings)
        return False

    def set_local_echo(self, enabled):
        self.local_echo = enabled

    def add_filter(self, filtering_file, output_view):
        self._filter_manager.add_filter(filtering_file, output_view)

    def remove_filter(self, filtering_file):
        self._filter_manager.remove_filter(filtering_file)

    def filters(self):
        return self._filter_manager.filters()

    def get_config(self):
        return self.serial.baudrate, self.serial.bytesize, self.serial.parity, self.serial.stopbits

    def reconfigure_port(self, baud, data_bits, parity, stop_bits):
        self._new_baud = baud
        self._new_data_bits = data_bits
        self._new_parity = parity
        self._new_stop_bits = stop_bits
        self._new_configuration = True

    def _sublime_line_endings_to_serial(self, text):
        if self.line_endings == "CR":
            text.replace("\n", "\r")
        elif self.line_endings == "CRLF":
            text.replace("\n", "\r\n")
        return text

    def _serial_line_endings_to_sublime(self, text):
        if self.line_endings == "CR":
            text = text.replace("\r", "\n")
        elif self.line_endings == "CRLF":
            text = text.replace("\r", "")
        return text

    def _write_text_to_file(self, text):
        if not self.view.is_valid() or not text:
            return

        text = self._serial_line_endings_to_sublime(text)

        timestamp = ""
        if self.timestamp_logging:
            t = time.time()
            timestamp = time.strftime("[%m-%d-%y %H:%M:%S.", time.localtime(t)) + "%03d] " % (int(t * 1000) % 1000)

        filter_thread = threading.Thread(target=self._filter_manager.apply_filters, args=(text, timestamp))
        filter_thread.start()

        # If timestamps are enabled, append a timestamp to the start of each line
        if self.timestamp_logging:
            # Newline was stripped from the end of the last write, needs to be
            # added to the beginning of this write
            if self._newline:
                text = timestamp + text
                self._newline = False

            # Count the number of newlines in the text to add a timestamp to
            # if the text ends with a newline, do not add a timestamp to the next
            # line and instead add it with the next text received
            newlines = text.count("\n")
            if text[-1] == '\n':
                newlines -= 1
                self._newline = True

            text = text.replace("\n", "\n%s" % timestamp, newlines)

        with self._view_lock:
            main_thread(self.view.run_command, "serial_monitor_write", {"text": text})

    def _read_serial(self):
        serial_input = self.serial.read(1024)
        if serial_input:
            self._write_text_to_file(serial_input.decode(encoding="ascii", errors="replace"))

    def _write_text(self):
        text_list = []
        with self._text_lock:
            text_list = self._text_to_write[:]
            self._text_to_write = []

        # Write any text in the queue to the serial port
        while text_list:
            text = text_list.pop(0)

            if self.local_echo:
                self._write_text_to_file(text)

            text = self._sublime_line_endings_to_serial(text)
            self.serial.write(bytes(text, encoding="ascii"))
            self._read_serial()

    def _write_file(self):
        with self._file_lock:
            # Write any files in the queue to the serial port
            while self._file_to_write:
                output_file = self._file_to_write.pop(0)
                for region in output_file.regions:
                    text = output_file.view.substr(region)
                    lines = text.splitlines(True)
                    if not lines[-1].endswith("\n"):
                        lines[-1] += "\n"
                    for line in lines:
                        if self.local_echo:
                            self._write_text_to_file(line)

                        line = self._sublime_line_endings_to_serial(line)
                        self.serial.write(bytes(line, encoding="ascii"))
                        self._read_serial()

    def run(self):
        self.running = True
        try:
            self.serial.port = self.comport
            self.serial.open()
            while self.running and self.view.is_valid():
                self._read_serial()
                self._write_text()
                self._write_file()

                if self._new_configuration:
                    self.serial.close()
                    self.serial.baudrate = self._new_baud
                    self.serial.bytesize = self._new_data_bits
                    self.serial.parity = self._new_parity
                    self.serial.stopbits = self._new_stop_bits
                    self.serial.open()
                    self._new_configuration = False
        except Exception as e:
            self._write_text_to_file("\nError occurred on port {0}: {1}".format(self.comport, str(e)))
        finally:
            # Thread terminated, write to buffer if still valid and close the serial port
            self._write_text_to_file("\nDisconnected from {0}".format(self.comport))
            self._filter_manager.port_closed(self.comport)
            self.serial.close()
            self.running = False
            main_thread(self.window.run_command, "serial_monitor", {"serial_command": "_port_closed",
                                                                    "comport": self.comport})
