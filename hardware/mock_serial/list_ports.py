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
