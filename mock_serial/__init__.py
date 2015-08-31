import time


class Serial(object):
    """
    Mock serial class
    """
    def __init__(self, comport, baud, timeout=1, **kwargs):
        self.i = 0
        self.port = comport
        self.baud = baud
        self.timeout = timeout

    def open(self):
        print("Comport opened: {0}, baud:{1}".format(self.port, self.baud))

    def close(self):
        print("Comport closed: {0}".format(self.port))

    def read(self, bytes):
        time.sleep(1)
        self.i += 1
        return "{0}, ".format(self.i)

    def write(self, text):
        print("Writing: \"{0}\"".format(text))
