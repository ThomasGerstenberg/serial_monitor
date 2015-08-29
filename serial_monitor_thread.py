import sublime, sublime_plugin
import sys
import os
import functools
import threading
import time

def main_thread(callback, *args, **kwargs):
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)


class SerialMonitor(threading.Thread):
    def __init__(self, comport, serial, view, window):
        super(SerialMonitor, self).__init__()
        self.comport = comport
        self.serial = serial
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

    def _write_text_to_file(self, text):
        main_thread(self.view.run_command, "serial_monitor_write", {"text": text})

    def run(self):
        self.serial.port = self.comport
        self.serial.open()
        while self.running and self.view.is_valid():

            # Read the input from the serial port
            serial_input = ""
            serial_input = self.serial.read(100)
            if serial_input:
                self._write_text_to_file(serial_input)

            if self.text_to_write:
                self.serial.write(self.text_to_write)
                self._write_text_to_file(self.text_to_write)
                self.text_to_write = ""
            if self.file_to_write:
                view = self.file_to_write["view"]
                region = self.file_to_write["region"]

                self.serial.write(self.view.substr(region))
                main_thread(self.view.run_command, "serial_monitor_write", {"view_id": view.id(), "region_begin": region.begin(), "region_end": region.end()})
                self.file_to_write = {}

        # Thread terminated, write to buffer if still valid and close the serial port
        if self.view.is_valid():
            self._write_text_to_file("\nDisconnected from {0}".format(self.comport))
        self.serial.close()
        main_thread(self.window.run_command, "serial_monitor", {"serial_command": "file_closed", "comport": self.comport})
