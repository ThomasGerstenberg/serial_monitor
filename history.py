class History(object):
    def __init__(self):
        self._entries = [""]
        self.index = 0

    def add_entry(self, entry):
        if not entry:
            return
        if entry in self._entries:
            self._entries.remove(entry)
        self._entries.insert(1, entry)
        if len(self._entries) > 20:
            self._entries.pop()

        self.index = 0

    def get_entries_with(self, text):
        return [e.rstrip("\r") for e in self._entries if text in e]

    def has_previous(self):
        return self.index > 0

    def get_previous(self):
        if self.has_previous():
            self.index -= 1
            return self._entries[self.index]

    def has_next(self):
        return self.index < (len(self._entries) - 1)

    def get_next(self):
        if self.has_next():
            self.index += 1
            return self._entries[self.index]

    