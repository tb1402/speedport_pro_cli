class WifiClient:
    macAddress=""
    ipAddress=""
    signalStrength=-1
    hostName=""

    def __init__(self,mac_address,ip_address,signal_strength,host_name):
        self.macAddress=mac_address
        self.ipAddress=ip_address
        self.signalStrength=signal_strength
        self.hostName=host_name
