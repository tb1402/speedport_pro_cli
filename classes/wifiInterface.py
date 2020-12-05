class WifiInterface:
    is5G=False
    macAddress = ""
    up = False
    channel = -1
    encryption = ""
    ssid = ""
    power = -1
    dataRate = -1
    clients=[]

    def __init__(self, is_5g):
        self.is5G=is_5g

        '''def __init__(self, is_5g, is_up, mac_address, channel, encryption, ssid, power, data_rate):
        self.is5G=is_5g
        self.macAddress = mac_address
        self.up = is_up
        self.channel = channel
        self.encryption = encryption
        self.ssid = ssid
        self.power = power
        self.dataRate = data_rate'''
