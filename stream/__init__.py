from serial_settings import SerialSettings


class AbstractStream(object):
    def __init__(self, serial_config):
        """
        :type serial_config: SerialSettings
        """
        self.config = serial_config
        self.comport = serial_config.comport

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def read(self, num_bytes=1):
        raise NotImplementedError

    def write(self, data):
        raise NotImplementedError

    def reconfigure(self, serial_config):
        raise NotImplementedError
