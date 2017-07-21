import threading
from util import main_thread


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



class FilterManager(object):
    def __init__(self):
        super(FilterManager, self).__init__()
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