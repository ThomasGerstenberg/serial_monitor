class History(object):
    def __init__(self):
        self._entries = []
        self._last_entry_list = []

    def get_entries_start_with(self, prefix):
        self._last_entry_list = [entry for entry in self._entries if entry.startswith(prefix)]
        if self._last_entry_list and self._last_entry_list[0] == prefix and len(self._last_entry_list) == 1:
            self._last_entry_list = []
        return self._last_entry_list

    def last_popup_list(self):
        return self._last_entry_list

    def add_entry(self, entry):
        if entry in self._entries:
            self._entries.remove(entry)
        self._entries.insert(0, entry)
        if len(self._entries) > 20:
            self._entries.pop()

