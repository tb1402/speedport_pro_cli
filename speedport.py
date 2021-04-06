from classes import wifi
import time
import argparse
import os
import requests
import urllib3
import hashlib
import xmltodict
from tabulate import tabulate


# these classes are needed in order to use multiple argparse formatters
class Formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


class FormatterHelp(Formatter, argparse.RawTextHelpFormatter):
    pass


# class holding bash color codes for colored output
class BashColors:
    default = '\33[39m'
    reset = '\33[0m'
    bold = '\33[1m'
    black = '\33[30m'
    blue = '\33[34m'
    magenta = '\33[35m'
    cyan = '\33[36m'
    light_red = '\33[91m'
    light_green = '\33[92m'
    white = '\33[97m'

    class Background:
        default = '\33[49m'
        red = '\33[41m'
        green = '\33[42m'
        yellow = '\33[43m'
        blue = '\33[44m'
        magenta = '\33[45m'
        cyan = '\33[46m'
        light_grey = '\33[47m'
        dark_grey = '\33[100m'
        light_green = '\33[102m'
        light_yellow = '\33[103m'
        light_magenta = '\33[105m'
        light_cyan = '\33[106m'
        white = '\33[107m'


def get_request(parameter_list):
    """
    Method to get soap data for given parameters
    :param parameter_list: list of string parameters, to specify data to get
    :return: dictionary which contains parsed XML response
    """
    global ipAddress, headers, password
    if len(parameter_list) == 0:
        return None

    # convert given parameters to correct xml syntax
    parameter_string = ""
    for parameter in parameter_list:
        parameter_string += f"<xsd:string>{parameter}</xsd:string>\n"

    # data string for SOAP request todo: maybe use xml parser
    data = f"<soap-env:Envelope xmlns:soap-env=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\"" \
           f"xmlns:cwmp=\"urn:telekom-de.totr64-2-n\"><soap-env:Body><cwmp:GetParameterValues xmlns:cwmp=\"urn:dslforum-org:cwmp-1-0\"><cwmp:ParameterNames length=\"{len(parameter_list)}\">" \
           f"{parameter_string}</cwmp:ParameterNames></cwmp:GetParameterValues></soap-env:Body></soap-env:Envelope>"

    # send request with data
    request = requests.post(url=f"https://{ipAddress}:49443/", headers=headers, data=data, verify=False)

    # if header is set, authentication is needed; calculate hash, set authorization header and resend the request
    if "WWW-Authenticate" in request.headers:
        if password is None:
            exit_with_error_message(1, "[-] Request needs authentication, but no password was set.")
        wwa = request.headers["WWW-Authenticate"]

        # basic SOAP digest auth
        nonce = wwa[wwa.index("nonce") + 7:][:-1]
        hash1 = hashlib.md5(f"dslf-config:BT:{password}".encode()).hexdigest()
        hash2 = hashlib.md5("POST:/".encode()).hexdigest()
        response = hashlib.md5(f"{hash1}:{nonce}:{hash2}".encode())

        auth_headers = headers  # use global header and add auth header
        auth_headers["Authorization"] = f"Digest username=\"dslf-config\", realm=\"BT\", nonce=\"{nonce}\", uri=\"/\", response=\"{response.hexdigest()}\", algorithm=MD5"
        request = requests.post(url=f"https://{ipAddress}:49443/", headers=auth_headers, data=data, verify=False)

    # print(request.text)
    return xmltodict.parse(request.text)


def get_all_wifi_interfaces():
    """
    Get information about all available WiFi interfaces
    :return: list with interfaces
    """
    # first request: retrieve status for all interfaces
    parameter_list = []
    for x in range(1, 8):
        parameter_list.append(f"Device.WiFi.SSID.{x}.Status")
    raw_data = get_request(parameter_list)["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["u:GetParameterValuesResponse"]["ParameterList"]["ParameterValueStruct"]

    # second request: get bssid (mac) and ssid as well as additional info, if interface is up
    interfaces = []
    parameter_list = []
    for entry in raw_data:
        interface = wifi.WifiInterface(interface_id=int(entry["Name"].split(".")[3]))  # initialize interface object
        interface.up = entry["Value"]["#text"] == "Up"  # set state
        interfaces.append(interface)

        # add mac address (bssid) and ssid for current interface to parameter list
        parameter_list.append(f"Device.WiFi.SSID.{interface.id}.SSID")
        parameter_list.append(f"Device.WiFi.SSID.{interface.id}.BSSID")

        if interface.up:  # get more info, which is only available when interface is uo
            parameter_list.append(f"Device.WiFi.Radio.{interface.id}.SupportedFrequencyBands")  # frequency
            parameter_list.append(f"Device.WiFi.Radio.{interface.id}.Channel")  # channel
            parameter_list.append(f"Device.WiFi.Radio.{interface.id}.TransmitPower")  # transmit power
            parameter_list.append(f"Device.WiFi.Radio.{interface.id}.MaxBitRate")  # max bitrate
            parameter_list.append(f"Device.WiFi.AccessPoint.{interface.id}.Security.ModeEnabled")  # encryption method used

    raw_data = get_request(parameter_list)["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["u:GetParameterValuesResponse"]["ParameterList"]["ParameterValueStruct"]  # request for additional info

    # add missing information to the interface objects
    for entry in raw_data:
        id = int(entry["Name"].split(".")[3])  # speedport interface id

        # find list index for needed interface (with same id)
        index = -1
        for x in range(0, len(interfaces)):
            if interfaces[x].id == id:
                index = x
                break

        if index == -1:  # exit if index is -1, wat means that a interface with given number wasn't found in list
            exit_with_error_message(1, "Interface not in list")

        type: str = entry["Name"].split(".")[4]  # entry type
        if type == "SSID":
            interfaces[index].ssid = entry["Value"]["#text"]
        elif type == "BSSID":
            interfaces[index].mac_address = entry["Value"]["#text"] if "#text" in entry["Value"] else "NA"
        elif type == "SupportedFrequencyBands":
            interfaces[index].frequency = entry["Value"]["#text"]
        elif type == "Channel":
            interfaces[index].channel = entry["Value"]["#text"]
        elif type == "TransmitPower":
            interfaces[index].power = entry["Value"]["#text"]
        elif type == "MaxBitRate":
            interfaces[index].data_rate_max = entry["Value"]["#text"]
        elif type == "Security":
            interfaces[index].encryption = entry["Value"]["#text"]
    return interfaces


def get_clients_for_wifi_interface(interface):
    """
    Get all clients associated to a WiFi interface
    :param interface: the interface
    :return: the passed interface, but with completed client list
    """
    raw_data = \
        get_request([f"Device.WiFi.AccessPoint.{interface.id}.AssociatedDevice."])["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["u:GetParameterValuesResponse"]["ParameterList"]["ParameterValueStruct"]
    clients = []

    for entry in raw_data:
        id = int(entry["Name"].split(".")[5])  # device id
        entry_type = entry["Name"].split(".")[6]

        # check if client already in list, if not add id
        index = -1
        for x in range(0, len(clients)):
            if clients[x].id == id:
                index = x
                break

        if index == -1:
            clients.append(wifi.WifiClient(client_id=id))
            index = len(clients) - 1  # last index

        # add fields
        if entry_type == "MACAddress":
            clients[index].mac_address = entry["Value"]["#text"]
        elif entry_type == "LastDataDownlinkRate":
            clients[index].downstream_speed = int(entry["Value"]["#text"])
        elif entry_type == "LastDataUplinkRate":
            clients[index].upstream_speed = int(entry["Value"]["#text"])
        elif entry_type == "SignalStrength":
            clients[index].signal_strength = int(entry["Value"]["#text"])

    raw_data = get_request([f"Device.Hosts.Host."])["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["u:GetParameterValuesResponse"]["ParameterList"]["ParameterValueStruct"]  # get device data

    for entry in raw_data:
        id = int(entry["Name"].split(".")[3])
        entry_type = entry["Name"].split(".")[4]

        if entry_type == "PhysAddress":
            for client in clients:
                if client.mac_address == entry["Value"]["#text"] and client.host_list_number == -1:
                    client.host_list_number = id

        elif entry_type == "IPAddress":
            for client in clients:
                if client.host_list_number == id:
                    client.ipAddress = entry["Value"]["#text"] if "#text" in entry["Value"] else "NA"
        elif entry_type == "HostName":
            for client in clients:
                if client.host_list_number == id:
                    client.hostName = entry["Value"]["#text"] if "#text" in entry["Value"] else "NA"
        elif entry_type == "Active":
            for client in clients:
                if client.host_list_number == id:
                    client.active = entry["Value"]["#text"] == "true"

    interface.clients = clients
    return interface


def get_external_ips():
    """
    Get the speedport's external IPs
    :return str: ip address(es) or Error
    """

    parameter_list = []
    for x in range(2, 6):
        parameter_list.append(f"Device.IP.Interface.{x}.Alias")
        parameter_list.append(f"Device.IP.Interface.{x}.IPv4Address.1.IPAddress")
        # parameter_list.append(f"Device.IP.Interface.{x}.IPv6Address.1.IPAddress")
    raw_data = get_request(parameter_list)["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["u:GetParameterValuesResponse"]["ParameterList"]["ParameterValueStruct"]

    # merge ip data rows
    merged_data = []
    for x in range(0, int(len(raw_data))):
        if x % 2 == 0:
            merged_data.append([raw_data[x]["Value"]["#text"], raw_data[x + 1]["Value"]["#text"] if "#text" in raw_data[x + 1]["Value"] else "NA"])

    output = BashColors.reset + "==== External interfaces - IPv4 addresses ====\n"
    for entry in merged_data:
        if entry[1] == "NA":
            output += f"{BashColors.light_red}{entry[0]}:{BashColors.reset} {entry[1]}\n"
        else:
            if entry[0] == "BOND" and entry[1] != "NA":
                output += f"{entry[0]}: {entry[1]} (This is your external address websites will see)\n"
            else:
                output += f"{entry[0]}: {entry[1]}\n"

    output = output[:-1]
    return output


def print_syslog(entry_count, exclude_string, include):
    """
    print colored syslog
    :param int entry_count: number of entries that should be printed, if -1 all
    :param str exclude_string: string containing information on which messages should be excluded or -if include==True - should be included
    :param bool include: determines whether to include or exclude messages given in exclude_string
    """
    '''
    possible message groups:
    e: E-Mail Notifications,
    wui: Logins and session timeouts in web interface,
    t: time messages
    v: Voice (telephony)
    dd: Dynamic DNS
    l: LTE and SIM Card
    d: DSL and configurator service
    i: IGMP
    w: WiFi
    vpn: VPN
    dh: DHCP
    u: unclassified
    '''

    # if include is set, convert input to exclude all other groups
    possible_options = ["e", "wui", "t", "v", "dd", "l", "d", "i", "w", "vpn", "dh", "u"]
    if include:
        split = exclude_string.split(",")
        excluded_options = []
        for x in split:
            for y in possible_options:
                if not x == y:
                    excluded_options.append(y)
        exclude_string = ",".join(excluded_options)

    ex_mails = False
    ex_web_sessions = False
    ex_time = False
    ex_voice = False
    ex_ddns = False
    ex_lte = False
    ex_dsl = False
    ex_igmp = False
    ex_wifi = False
    ex_vpn = False
    ex_dhcp = False
    ex_unclassified = False

    # set booleans for excluded message groups
    split_exclude = exclude_string.split(",")
    for exclusion in split_exclude:
        if exclusion == "e":
            ex_mails = True
        elif exclusion == "wui":
            ex_web_sessions = True
        elif exclusion == "t":
            ex_time = True
        elif exclusion == "v":
            ex_voice = True
        elif exclusion == "dd":
            ex_ddns = True
        elif exclusion == "l":
            ex_lte = True
        elif exclusion == "d":
            ex_dsl = True
        elif exclusion == "i":
            ex_igmp = True
        elif exclusion == "w":
            ex_wifi = True
        elif exclusion == "vpn":
            ex_vpn = True
        elif exclusion == "dh":
            ex_dhcp = True
        elif exclusion == "u":
            ex_unclassified = True

    # get syslog data
    raw_data = get_request(["Device.DeviceInfo.X_T-ONLINE-DE_DeviceLog"])["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["u:GetParameterValuesResponse"]["ParameterList"]["ParameterValueStruct"]["Value"]["#text"]
    # print(raw_data)

    sp = raw_data.split("\n")  # split data

    # determine entry count
    if entry_count == -1 or entry_count > len(sp):
        entry_count = len(sp)

    # color code and print messages
    for x in range(entry_count - 1, 0, -1):

        # get raw message type
        raw_msg_type = sp[x][22:28]
        if raw_msg_type[-1] == ")":
            raw_msg_type = raw_msg_type[:-1]
        elif raw_msg_type[-2] == ")":
            raw_msg_type = raw_msg_type[:-2]

        # get actual message type
        msg_type = ""
        msg_number = -1
        if len(raw_msg_type) == 4:
            msg_type = raw_msg_type[0:1]
            msg_number = raw_msg_type[1:]
        elif len(raw_msg_type) == 5:
            msg_type = raw_msg_type[0:2]
            msg_number = raw_msg_type[2:]
        else:  # len >6
            msg_type = raw_msg_type[0:3]
            msg_number = raw_msg_type[3:]

        # default values
        print_line = True  # print every line, if not excluded
        color_start = BashColors.Background.white + BashColors.black  # default line color (white bg + black text)
        color_end = BashColors.Background.default + BashColors.default  # default color end (default colors)

        if msg_type == "W":  # WiFi
            color_start = BashColors.Background.cyan
            if ex_wifi:
                print_line = False
            if msg_number == "005":  # 005=failed wifi device auth
                color_start = BashColors.Background.red + BashColors.black
        elif msg_type == "IG":  # IGMP
            color_start = BashColors.Background.dark_grey
            if ex_igmp:
                print_line = False
        elif msg_type == "VPN":  # VPN
            color_start = BashColors.Background.light_grey + BashColors.black
            if ex_vpn:
                print_line = False
        elif msg_type == "R" or msg_type == "A" or msg_type == "P":  # DSL Line, configuration service
            color_start = BashColors.Background.magenta + BashColors.black
            if ex_dsl:
                print_line = False
            if msg_number == "009" or msg_number == "013" or msg_number == "020" or msg_number == "004":  # 004=no prefix, 020=pppoe timeout, 013=lost sync
                color_start = BashColors.Background.red + BashColors.black
        elif msg_type == "HA" or msg_type == "HYB" or msg_type == "LT" or msg_type == "SI":  # LTE, SIM Card
            color_start = BashColors.Background.light_magenta + BashColors.black
            if ex_lte:
                print_line = False
            if msg_number == "001" or msg_number == "002" or msg_number == "210" or msg_number == "213":  # 002=hybrid server not reachable via dsl, 213(no error)=time for lte ipv6 renewal, 001=sim not available
                color_start = BashColors.Background.red + BashColors.black
        elif msg_type == "D":  # dynamic dns
            color_start = BashColors.Background.light_green + BashColors.black
            if ex_ddns:
                print_line = False
            if msg_number == "001":
                color_start = BashColors.Background.red + BashColors.black
        elif msg_type == "V":  # voice
            color_start = BashColors.Background.blue
            if ex_voice:
                print_line = False
            if msg_number == "006":
                color_start = BashColors.Background.red + BashColors.black
        elif msg_type == "T" or msg_type == "NT":  # time
            color_start = BashColors.Background.green + BashColors.black
            if ex_time:
                print_line = False
            if msg_number == "102" or msg_number == "000":  # 102=time sync failed, 000=time not available
                color_start = BashColors.Background.red + BashColors.black
        elif msg_type == "EP":  # email notifications
            color_start = BashColors.Background.yellow + BashColors.black
            if ex_mails:
                print_line = False
        elif msg_type == "G":  # web interface sessions
            color_start = BashColors.Background.light_yellow + BashColors.black
            if ex_web_sessions:
                print_line = False
        elif msg_type == "DH":  # dhcp
            color_start = BashColors.Background.light_cyan + BashColors.black
            if ex_dhcp:
                print_line = False
        else:  # unclassified
            if ex_unclassified:
                print_line = False

        if print_line:
            print(f"{color_start}{sp[x]}{color_end}")


def get_uptime():
    global browser, ipAddress, webInterfaceVersion, timeFactor

    browser.get("http://" + ipAddress + "/" + webInterfaceVersion + "/gui/engineer/html/version.html/")
    time.sleep(0.5 * timeFactor)

    uptime_seconds = -1
    spans = browser.find_elements_by_tag_name("span")
    for span in spans:
        if span.get_attribute("ng-bind") == "fields.uptime":
            uptime_seconds = int(span.text)
            break

    if not uptime_seconds == -1:
        unix_time = int(time.time())
        uptime = unix_time - uptime_seconds
        return time.strftime("%Y-%m-%d %H-%M-%S", time.localtime(uptime))
    return "Error"


def main():
    global password

    # argparser
    parser = argparse.ArgumentParser(description=f"Comman Line Interface for Speedport Pro - Tobias Bittner ({time.strftime('%Y', time.localtime(time.time()))})" + BashColors.reset,
                                     formatter_class=FormatterHelp)
    parser.add_argument("-v", "--version", action="version", version="0.2.0 beta")
    parser.add_argument("-p", "--password", default=argparse.SUPPRESS, help="Your Speedport Web-Ui password", metavar="password", nargs=1, required=False)
    parser.add_argument("-m", "--mode",
                        help="Set the mode (s -> static, print information once and exit / d -> dynamic, refresh information after given time (-t)", nargs=1, metavar="mode", default=["s"])
    parser.add_argument("-t", "--time", help="Time (seconds) to wait until data is refreshed. (dynamic mode only)", metavar="refreshTime", nargs=1, default=[2])
    parser.add_argument("-w", "--wifi", help="Information about available wifi interfaces.", action="store_true", default=argparse.SUPPRESS)
    parser.add_argument("-wi", "--wifi-interface", help="Information about the selected wifi interface, such as connected clients. (run -w before to get number)", metavar="interface_number",
                        nargs=1, default=argparse.SUPPRESS)
    parser.add_argument("-ip", "--ipAddress", help="Print ip address information (e for external)", metavar="addressType", nargs=1, default=argparse.SUPPRESS)
    parser.add_argument("-l", "--log",
                        help="Print log of speedport. Given value is the number of entries to print (-1 for all available ones) You can ex- or include certain message categories with -lf)",
                        metavar="numberOfEntries", nargs=1, default=argparse.SUPPRESS)
    parser.add_argument("-lf", "--log_filter", help=BashColors.light_red + "ARGUMENT DOES NOTHING WHEN -l IS NOT SET!!\n" + BashColors.reset +
                                                    "Ex - or include entries in the log. Use in, to include and ex, to exclude, followed by one or more option, these are:\n"
                                                    "e -> E-Mail Notifications\nwui -> Login attempts to Web Interface\nt -> Entries related to time settings\nv -> Voice, telephony"
                                                    "\ndd -> Dynamic DNS\nl -> LTE, SIM Card\nd -> DSL, configurator service\ni -> IGMP\nw -> wifi\nvpn -> vpn\ndh -> DHCP\nu -> unclassified"
                                                    "\nYou can choose multiple options, they must be separated with a comma, e.g. -lf in w (show only entries related to wifi) or -lf ex "
                                                    "\"dh,wui\" to exclude entries related to DHCP and webui login attempts.", metavar="syslogFilter", nargs=2, default=argparse.SUPPRESS)
    # parser.add_argument("-u", "--uptime", help="Print uptime", default=argparse.SUPPRESS, action="store_true")

    args = parser.parse_args()

    dynamic_mode = args.mode[0] == "d"

    if hasattr(args, "password"):
        password = args.password[0]

    # limit refresh interval in dynamic mode to min. 2 seconds
    if float(args.time[0]) < 2:
        args.time[0] = 2

    if hasattr(args, "wifi"):  # wifi interface info
        if dynamic_mode:
            print("[i] Dynamic mode not supported by this operation, static will be used.")
        interfaces = get_all_wifi_interfaces()
        print(f"= = = = = WiFi interface Information = = = = = ({BashColors.light_green}UP{BashColors.reset}) ({BashColors.light_red}DOWN{BashColors.reset})")

        data = []
        for interface in interfaces:
            if interface.up:
                data.append([f"{BashColors.light_green}{interface.id}", interface.frequency, interface.mac_address, interface.ssid, interface.channel, interface.encryption, interface.power,
                             f"{interface.data_rate_max}{BashColors.reset}"])

            else:
                data.append([f"{BashColors.light_red}{interface.id}", interface.frequency, interface.mac_address, f"{interface.ssid}{BashColors.reset}"])

        print(tabulate(data, headers=["No.", "Frequency", "MAC", "SSID", "Channel", "Encryption", "Power (%)", "MaxDataRate (mbit/s)"]))
    elif hasattr(args, "wifi_interface"):
        interfaces = get_all_wifi_interfaces()

        # try to get index
        index = -1
        for x in range(0, len(interfaces)):
            if interfaces[x].id == int(args.wifi_interface[0]):
                index = x
                break

        if index == -1:
            exit_with_error_message(1, "Interface with specified number not found")

        if not interfaces[index].up:
            exit_with_error_message(1, "Specified interface is not up!")

        once = True
        while dynamic_mode or once:
            if once:
                once = False

            interface: wifi.WifiInterface = get_clients_for_wifi_interface(interfaces[index])

            if dynamic_mode:
                os.system('cls' if os.name == 'nt' else 'clear')

            print(f"= = = = = Information for interface {interface.id} = = = = =")
            print(f"{BashColors.light_green if interface.up else BashColors.light_red}Frequency: {interface.frequency}, SSID: {interface.ssid}, MAC: {interface.mac_address}\n"
                  f"Channel: {interface.channel}, Power: {interface.power}%, Encryption: {interface.encryption}")

            print(f"{BashColors.cyan}Clients {str(len(interface.clients))}{BashColors.reset}")
            if len(interface.clients) > 0:
                data = []
                for client in interface.clients:
                    if client.active:
                        data.append([client.mac_address, client.ip_address,
                                     f"{(BashColors.light_red if client.signal_strength < -70 else BashColors.light_green)}{str(client.signal_strength)}{BashColors.reset}", client.host_name,
                                     client.downstream_speed, client.upstream_speed])

                print(tabulate(data, headers=["MAC", "IP", "Signal strength", "Host-Name", "Downlink", "Uplink"]))

            if dynamic_mode:
                if not interface.up:
                    dynamic_mode = False

            if dynamic_mode:
                time.sleep(float(args.time[0]))
                interfaces = get_all_wifi_interfaces()

    elif hasattr(args, "ipAddress"):
        if dynamic_mode:
            print("[i] Dynamic mode not supported by this operation, static will be used.")
        if args.ipAddress[0] == "e":
            print(get_external_ips())
    elif hasattr(args, "log"):
        if dynamic_mode:
            print("[i] Dynamic mode not supported by this operation, static will be used.")
        include = False
        if hasattr(args, "log_filter"):
            if args.syslog_filter[0] == "in":
                include = True
            print_syslog(int(args.syslog[0]), args.syslog_filter[1], include)
        else:
            print_syslog(int(args.syslog[0]), "", False)
    elif hasattr(args, "uptime"):
        if dynamic_mode:
            print("[i] Dynamic mode not supported by this operation, static will be used.")
        print(get_uptime())
    exit(0)


def exit_with_error_message(exit_code, error_message):
    """
    Helper method zo exit with a message and a exit code, in case of an error
    :param exit_code: process return code as use in exit()
    :param error_message: exit message to print
    """
    print(f"{BashColors.light_red}[-] {error_message}{BashColors.reset}")
    exit(exit_code)


if __name__ == '__main__':
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    ipAddress = "192.168.2.1"  # todo argument for ip address
    password = None
    headers = {
        "User-Agent": "Speedport-Pro-CLI/0.2.0 (Python)",
        "Accept": "*/*",
        "SOAPAction": "urn:telekom-de:device:TO_InternetGatewayDevice:2#GetParameterValues",
        "Content-Type": "text/xml; charset=utf-8"
    }

    try:
        main()
    except KeyboardInterrupt:
        os.system('cls' if os.name == 'nt' else 'clear')
        time.sleep(1)
        print(BashColors.blue + "[~] Aborted by user..." + BashColors.reset)
        exit(0)
