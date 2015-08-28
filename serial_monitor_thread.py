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
    def __init__(self, comport, baud, view, window):
        super(SerialMonitor, self).__init__()
        self.comport = comport
        self.baud = baud
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

    def run(self):
        i = 0
        while self.running and self.view.is_valid():
            main_thread(self.view.run_command, "serial_monitor_write", {"text": "{0}, ".format(i)})

            if self.text_to_write:
                main_thread(self.view.run_command, "serial_monitor_write", {"text": self.text_to_write})
                self.text_to_write = ""
            if self.file_to_write:
                view = self.file_to_write["view"]
                region = self.file_to_write["region"]
                main_thread(self.view.run_command, "serial_monitor_write", {"view_id": view.id(), "region_begin": region.begin(), "region_end": region.end()})
                self.file_to_write = {}

            i += 1
            time.sleep(1)

        if self.view.is_valid():
            main_thread(self.view.run_command, "serial_monitor_write", {"text": "\nDisconnected from {0}".format(self.comport)})
        main_thread(self.window.run_command, "serial_monitor", {"serial_command": "file_closed", "comport": self.comport})
