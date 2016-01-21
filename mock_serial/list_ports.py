NUM_PORTS = 5
port_list = ["ttyUSB" + str(i) for i in range(1, NUM_PORTS + 1)]

def list_ports():
    """
    Gets the list of comports available on the computer in the same format as serial_utils.list_ports()

    :return: the list of available comports
    :rtype: list of strings
    """
    return port_list
