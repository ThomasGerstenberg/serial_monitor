from serial_settings import SerialSettings


class AbstractStream(object):
    def __init__(self, config, name):
        """
        :type name: str
        """
        self.config = config
        self.name = name

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def read(self, num_bytes=1):
        raise NotImplementedError

    def write(self, data):
        raise NotImplementedError

    def reconfigure(self, config):
        raise NotImplementedError
