class WifiClient:
    """
    Class representing a client device connected to a WiFi interface on the speedport.
    """
    active = False
    downstream_speed = -1
    host_list_number = -1  # number in host list
    host_name = ""
    id = -1  # internal id for speedport
    ip_address = ""
    mac_address = ""
    signal_strength = -1  # signal strength to client, measured by the speedport
    upstream_speed = -1

    def __init__(self, client_id: int):
        self.id = client_id


class WifiInterface:
    """
    Class representing a WiFI interface on the speedport
    """
    channel = -1
    clients = []  # associated clients with this interface
    data_rate_max = -1  # max. data throughput rate
    encryption = ""  # encryption method use, may be WPA2 etc.
    frequency = ""
    id = -1  # internal speedport interface id
    mac_address = ""
    ssid = ""
    power = -1  # transmit power in percent
    up = False  # state of the interface up (true)/down

    def __init__(self, interface_id: int):
        self.id = interface_id
