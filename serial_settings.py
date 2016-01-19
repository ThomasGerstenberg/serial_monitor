import sublime


class SerialSettings(object):
    SETTINGS_FILE = "serial_monitor.sublime-settings"

    _SETTINGS_LIST = [
        "comport",
        "baud",
        "text",
        "override_selection",
        "enable_timestamps",
        "line_endings",
        "local_echo",
        "full_config_on_connect"
        "data_bits",
        "parity",
        "stop_bits",
    ]

    def __init__(self, callback, **args):
        self.callback = callback
        self.comport = None
        self.baud = None
        self.text = None
        self.override_selection = None
        self.enable_timestamps = None
        self.line_endings = None
        self.local_echo = None
        self.full_config_on_connect = None
        self.data_bits = None
        self.parity = None
        self.stop_bits = None

        for attr in self._SETTINGS_LIST:
            setattr(self, attr, args.get(attr))

    @staticmethod
    def load_defaults(comport):
        defaults = sublime.load_settings(SerialSettings.SETTINGS_FILE)
        settings = SerialSettings(None)

        for attr in SerialSettings._SETTINGS_LIST:
            v = defaults.get(attr, None)
            if v is not None:
                setattr(settings, attr, v)

        # Check if there's any port-specific settings
        if comport:
            comport_settings = defaults.get(comport, None)
            if comport_settings:
                for attr in SerialSettings._SETTINGS_LIST:
                    v = comport_settings.get(attr, None)
                    if v is not None:
                        setattr(settings, attr, v)

        return settings
