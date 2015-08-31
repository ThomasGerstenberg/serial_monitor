NUM_PORTS = 5
port_list = [("COM" + str(i), "Desc" + str(i), "HW" + str(i)) for i in range(1, NUM_PORTS + 1)]

def comports():
    """
    Gets the list of comports available on the computer in the same format as serial.tools.list_ports.comports()
    Format:
        (COMPORT, COMPORT_DESC, HW_DESC)

    :return: the list of available comports
    :rtype: list of tuple (see format)
    """
    return port_list
