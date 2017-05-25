from hardware import serial
from stream import AbstractStream, SerialSettings


class SerialTextStream(AbstractStream):
    def __init__(self, serial_config):
        """
        :type serial_config: SerialSettings
        """
        super(SerialTextStream, self).__init__(serial_config)
        self.comport = serial_config.comport
        kwargs = {}
        if serial_config.data_bits:
            kwargs["bytesize"] = serial_config.data_bits
        if serial_config.parity:
            kwargs["parity"] = serial_config.parity
        if serial_config.stop_bits:
            kwargs["stopbits"] = serial_config.stop_bits
        kwargs["timeout"] = 0.05
        self.serial = serial.Serial(None, serial_config.baud, **kwargs)

    def open(self):
        if not self.serial.isOpen():
            self.serial.port = self.comport
            self.serial.open()

    def close(self):
        if self.serial.isOpen():
            self.serial.close()

    def read(self, num_bytes=1):
        return self.serial.read(num_bytes)

    def write(self, data):
        self.serial.write(data)

    def reconfigure(self, serial_config):
        """
        :type serial_config: SerialSettings
        """
        self.close()
        self.serial.port = serial_config.comport
        self.serial.baudrate = serial_config.baud
        self.serial.bytesize = serial_config.data_bits
        self.serial.parity = serial_config.parity
        self.serial.stopbits = serial_config.stop_bits
        self.open()
