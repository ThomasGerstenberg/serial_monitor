import time

from hardware.serial.serialutil import SerialBase

NUM_PORTS = 5
port_list = ["/dev/ttyUSB" + str(i) for i in range(1, NUM_PORTS + 1)]


def list_ports(exclude=[]):
    """
    Gets the list of comports available on the computer in the same format as serial_utils.list_ports()

    :param exclude: The list of serial ports to exclude from the list

    :return: the list of available comports
    :rtype: list of strings
    """
    return [p for p in port_list if p not in exclude]


class Serial(SerialBase):
    """
    Mock serial class
    """
    def __init__(self, comport, baud, *args, **kwargs):
        super(Serial, self).__init__(comport, baud, *args, **kwargs)
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
        text = "{0},\r\n".format(self.i)
        if self.echo:
            retval = self.echo
        else:
            retval = bytes(text, encoding="ascii")
        self.echo = ""
        return retval

    def write(self, text):
        self.echo = text
        print("Writing: \"{0}\"".format(text))
