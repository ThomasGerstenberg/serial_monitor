import threading
import time
from util import main_thread
from filter.manager import FilterManager


class _WriteFileArgs(object):
    def __init__(self, view, regions):
        self.view = view
        self.regions = regions


class SerialMonitor(threading.Thread):
    """
    Thread that controls a stream's read, write, open, close, etc. and outputs the serial info to a sublime view
    :type stream: stream.AbstractStream
    """
    def __init__(self, stream, view, window):
        super(SerialMonitor, self).__init__()
        self.stream = stream
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
        self._filter_manager = FilterManager()
        self._newline = True

        self._new_configuration = None

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
        """
        :rtype: stream.SerialConfig
        """
        return self.stream.config

    def reconfigure_port(self, config):
        self._new_configuration = config

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

    def _write_to_output(self, text):
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

    def _read_stream(self):
        serial_input = self.stream.read(1024)
        if serial_input:
            self._write_to_output(serial_input.decode(encoding="ascii", errors="replace"))

    def _write_text(self):
        text_list = []
        with self._text_lock:
            text_list = self._text_to_write[:]
            self._text_to_write = []

        # Write any text in the queue to the serial port
        while text_list:
            text = text_list.pop(0)

            if self.local_echo:
                self._write_to_output(text)

            text = self._sublime_line_endings_to_serial(text)
            self.stream.write(bytes(text, encoding="ascii"))
            self._read_stream()

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
                            self._write_to_output(line)

                        line = self._sublime_line_endings_to_serial(line)
                        self.stream.write(bytes(line, encoding="ascii"))
                        self._read_stream()

    def run(self):
        self.running = True
        try:
            self.stream.open()
            while self.running and self.view.is_valid():
                self._read_stream()
                self._write_text()
                self._write_file()

                if self._new_configuration:
                    self.stream.close()
                    self.stream.reconfigure(self._new_configuration)
                    self.stream.open()
                    self._new_configuration = None
        except Exception as e:
            self._write_to_output("\nError occurred on port {0}: {1}".format(self.stream.comport, str(e)))
        finally:
            # Thread terminated, write to buffer if still valid and close the serial port
            self._write_to_output("\nDisconnected from {0}".format(self.stream.comport))
            self._filter_manager.port_closed(self.stream.comport)
            self.stream.close()
            self.running = False
            main_thread(self.window.run_command, "serial_monitor", {"serial_command": "_port_closed",
                                                                    "comport": self.stream.comport})
