import time
from serial.serialutil import SerialBase

class Serial(SerialBase):
    """
    Mock serial class
    """
    def __init__(self, comport, baud, timeout=1, **kwargs):
        super(Serial, self).__init__(comport, baud, timeout=timeout, **kwargs)
        self.i = 0
        self.echo = ""

    def _reconfigurePort(self):
        pass

    def open(self):
        print("Comport opened: {0}, baud:{1}".format(self.port, self.baudrate))

    def close(self):
        print("Comport closed: {0}".format(self.port))

    def read(self, size):
        time.sleep(.2)
        self.i += 1
        text = "{0},\n".format(self.i)
        if self.echo:
            retval = self.echo
        else:
            retval = bytes(text, encoding="ascii")
        self.echo = ""
        return retval

    def write(self, text):
        self.echo = text
        print("Writing: \"{0}\"".format(text))
