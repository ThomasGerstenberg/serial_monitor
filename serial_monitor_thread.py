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
        self.text_to_write = []
        self.file_to_write = []
        self.text_lock = threading.Lock()
        self.file_lock = threading.Lock()

    def write_line(self, text):
        with self.text_lock:
            self.text_to_write.append(text)

    def write_file(self, view, selection):
        file_args = SerialMonitorWriteFileArgs(view, selection)
        with self.file_lock:
            self.file_to_write.append(file_args)

    def disconnect(self):
        self.running = False

    def enable_timestamps(self, enabled):
        self.timestamp_logging = enabled;

    def _write_text_to_file(self, text):
        if not self.view.is_valid():
            return

        text = text.replace("\r", "")

        # If timestamps are enabled, append a timestamp to the start of each line
        if self.timestamp_logging:
            t = time.time()
            timestamp = time.strftime("[%m-%d-%y %H:%M:%S.", time.localtime(t))
            timestamp += "%03d] " % (int(t * 1000) % 1000)

            lines = text.splitlines()
            text = ""
            # Append the timestamp in front of each line
            for line in lines:
                text += timestamp + line + "\n"

        main_thread(self.view.run_command, "serial_monitor_write",
                    {"text": text})

    def _read_serial(self):
        serial_input = self.serial.read(512)
        if serial_input:
            self._write_text_to_file(serial_input.decode(encoding="ascii", errors="replace"))

    def _write_text(self):
        text_list = []
        with self.text_lock:
            text_list = self.text_to_write[:]
            self.text_to_write = []
            # Write any text in the queue to the serial port
        while text_list:
            text = text_list.pop(0)
            # Commenting out local echo
            # self._write_text_to_file(text)
            self.serial.write(bytes(text, encoding="ascii"))
            self._read_serial()

    def _write_file(self):
        with self.file_lock:
            # Write any files in the queue to the serial port
            while self.file_to_write:
                output_file = self.file_to_write.pop(0)
                for region in output_file.regions:
                    # Commenting out local echo
                    # main_thread(self.view.run_command, "serial_monitor_write", {"view_id": view.id(),
                    #                                                             "region_begin": region.begin(),
                    #                                                             "region_end": region.end()})
                    text = output_file.view.substr(region)
                    lines = text.splitlines(1)
                    if not lines[-1].endswith("\n"):
                        lines[-1] += "\n"
                    for line in lines:
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
