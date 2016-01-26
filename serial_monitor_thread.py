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

class SerialMonitorWriteFileArgs(object):
    def __init__(self, view, regions):
        self.view = view
        self.regions = regions


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
        self.running = True
        self.timestamp_logging = False
        self.line_endings = "CRLF"
        self.local_echo = False
        self._text_to_write = []
        self._file_to_write = []
        self._text_lock = threading.Lock()
        self._file_lock = threading.Lock()
        self._view_lock = threading.Lock()
        self._filter_view_lock = threading.Lock()
        self._newline = True
        self._filtering = False
        self._filtering_file = None
        self._filtering_view = None
        self._incomplete_line = ""

    def write_line(self, text):
        with self._text_lock:
            self._text_to_write.append(text)

    def write_file(self, view, selection):
        file_args = SerialMonitorWriteFileArgs(view, selection)
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

    def set_filtering(self, enabled, filtering_file=None, filtering_view=None):
        # If already enabled, throw message on old view stating it is stale
        with self._filter_view_lock:
            if filtering_file:
                self._filtering_file = filtering_file
            if filtering_view:
                self._filtering_view = filtering_view
            self._filtering = enabled

    def filtering(self):
        return self._filtering

    def _write_to_filtering_file(self, text, timestamp):
        if not self._filtering or not self._filtering_view or not self._filtering_file:
            self._filtering = False
            return
        if not self._filtering_view.is_valid():
            self._filtering = False
            return

        lines = text.splitlines(True)

        if len(lines) == 0:
            return

        # Append the last incomplete line to the beginning of this text
        lines[0] = self._incomplete_line + lines[0]
        self._incomplete_line = ""

        # Check if the last line is complete.  If not, pop it from the end of the list and save it as an incomplete line
        if not lines[-1].endswith("\n"):
            self._incomplete_line = lines.pop()

        for line in lines:
            if self._filtering_file.check_filters(line):
                with self._filter_view_lock:
                    main_thread(self._filtering_view.run_command, "serial_monitor_write", {"text": timestamp + line})

    def _write_text_to_file(self, text):
        if not self.view.is_valid() or not text:
            return

        if self.line_endings == "CR":
            text = text.replace("\r", "\n")
        elif self.line_endings == "CRLF":
            text = text.replace("\r", "")

        timestamp = ""
        if self.timestamp_logging:
            t = time.time()
            timestamp = time.strftime("[%m-%d-%y %H:%M:%S.", time.localtime(t)) + "%03d] " % (int(t * 1000) % 1000)

        self._write_to_filtering_file(text, timestamp)

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
        serial_input = self.serial.read(512)
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
                        self.serial.write(bytes(line, encoding="ascii"))
                        self._read_serial()

    def run(self):
        try:
            self.serial.port = self.comport
            self.serial.open()
            while self.running and self.view.is_valid():
                self._read_serial()
                self._write_text()
                self._write_file()
        except Exception as e:
            self._write_text_to_file("\nError occurred on port {0}: {1}".format(self.comport, str(e)))
        finally:
            # Thread terminated, write to buffer if still valid and close the serial port
            self._write_text_to_file("\nDisconnected from {0}".format(self.comport))
            self.serial.close()
            main_thread(self.window.run_command, "serial_monitor", {"serial_command": "_port_closed",
                                                                    "comport": self.comport})
