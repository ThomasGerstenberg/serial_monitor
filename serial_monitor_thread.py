import sublime
import functools
import threading

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
        self.text_to_write = []
        self.file_to_write = []
        self.text_lock = threading.Lock()
        self.file_lock = threading.Lock()

    def write_line(self, text):
        with self.text_lock:
            self.text_to_write.append(text)

    def write_file(self, view, region):
        with self.file_lock:
            self.file_to_write.append({"view": view, "region": region})

    def disconnect(self):
        self.running = False

    def _write_text_to_file(self, text):
        main_thread(self.view.run_command, "serial_monitor_write", {"text": text})

    def _read_serial(self):
        serial_input = self.serial.read(100)
        if serial_input:
            self._write_text_to_file(serial_input.decode(encoding="ascii"))

    def run(self):
        self.serial.port = self.comport
        self.serial.open()
        while self.running and self.view.is_valid():
            # Update the window if the view moved at all
            self.window = self.view.window()

            self._read_serial()
            with self.text_lock:
                # Write any text in the queue to the serial port
                while self.text_to_write:
                    text = self.text_to_write.pop(0)
                    # self._write_text_to_file(text)
                    self.serial.write(bytes(text, encoding="ascii"))
                    self._read_serial()

            with self.file_lock:
                # Write any files in the queue to the serial port
                while self.file_to_write:
                    output_file = self.file_to_write.pop(0)
                    view = output_file["view"]
                    region = output_file["region"]

                    # main_thread(self.view.run_command, "serial_monitor_write", {"view_id": view.id(),
                    #                                                             "region_begin": region.begin(),
                    #                                                             "region_end": region.end()})
                    text = view.substr(region)
                    if text[-1] not in ["\r", "\n"]:
                        text += "\n"
                    self.serial.write(bytes(text, encoding="ascii"))
                    self._read_serial()

        # Thread terminated, write to buffer if still valid and close the serial port
        if self.view.is_valid():
            self._write_text_to_file("\nDisconnected from {0}".format(self.comport))
        self.serial.close()
        main_thread(self.window.run_command, "serial_monitor", {"serial_command": "_port_closed",
                                                                "comport": self.comport})
