import sublime

import serial_constants
from hardware import serial, serial_utils, mock_serial


def _is_test_mode():
    """
    Checks if test mode has been enabled in the settings

    :return: True if test mode, False if not
    """
    settings = sublime.load_settings(serial_constants.DEFAULT_SETTINGS)
    return bool(settings.get("test_mode"))


def create_serial(*args, **kwargs):
    """
    Creates a serial port with the args provided

    :return: The serial object
    :rtype: serial.SerialBase
    """
    if _is_test_mode():
        return mock_serial.Serial(*args, **kwargs)
    return serial.Serial(*args, **kwargs)

def list_serial_ports(exclude=[]):
    """
    Lists the available serial ports in the system,
    excluding the ones provided in the given list

    :param exclude: The list of serial ports not to search
    :type exclude: list or tuple
    :return: list of the serial port names available
    :rtype: list of str
    """
    if _is_test_mode():
        return mock_serial.list_ports(exclude=exclude)
    return serial_utils.list_ports(exclude=exclude)