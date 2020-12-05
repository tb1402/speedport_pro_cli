from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
import time
import classes
import argparse
import os


# classes needed to have multiple formatter classes in argparse
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
    lightRed = '\33[91m'
    lightGreen = '\33[92m'
    white = '\33[97m'

    class Background:
        default = '\33[49m'
        red = '\33[41m'
        green = '\33[42m'
        yellow = '\33[43m'
        blue = '\33[44m'
        magenta = '\33[45m'
        cyan = '\33[46m'
        lightGrey = '\33[47m'
        darkGrey = '\33[100m'
        lightGreen = '\33[102m'
        lightYellow = '\33[103m'
        lightMagenta = '\33[105m'
        lightCyan = '\33[106m'
        white = '\33[107m'


def login(password):
    """
    login and start session

    :param str password: the password for the web interface
    """
    global loggedIn, webInterfaceVersion, ipAddress, browser

    browser.get("http://" + ipAddress + "/" + webInterfaceVersion + "/gui/login/")
    time.sleep(0.3)

    input_field = browser.find_element_by_id("device-pass")
    time.sleep(0.1)
    input_field.send_keys(password)
    browser.execute_script("arguments[0].click()", browser.find_element_by_id("login-button"))

    # increase sleep time until url is the one of the start page
    factor = 1
    while browser.current_url != "http://" + ipAddress + "/" + webInterfaceVersion + "/gui/":
        if factor > 10:
            exit_with_message(1, "[-] Login failed...")
        time.sleep(0.1 * factor)
        factor += 0.2

    loggedIn = True


# determine the current version of the web interface
def get_web_interface_version():
    global ipAddress, webInterfaceVersion, browser
    browser.get("http://" + ipAddress)

    # increase sleep time until url has changed
    factor = 1
    while browser.current_url == "http://" + ipAddress:
        time.sleep(0.1 * factor)
        factor += 0.2

    # split url and get version part
    url = str(browser.current_url).split("/")
    webInterfaceVersion = url[3]


def get_wifi_interface_info(interface_frequency):
    """
    get information about the wifi interfaces (state, connected devices etc.)
    :param str interface_frequency: the interface that should be used (24 for 2.4GHz and 5 for 5GHz)
    :return WifiInterface object containing all information
    """
    global loggedIn, webInterfaceVersion, ipAddress, browser

    # navigate to engineer page for wifi interfaces
    browser.get("http://" + ipAddress + "/" + webInterfaceVersion + "/gui/engineer/html/wlan.html/")
    time.sleep(0.8)

    # instantiate interface
    interface = classes.WifiInterface(interface_frequency == "5")
    interface.clients = []

    # filter for elements which contain needed information
    bindings = browser.find_elements_by_class_name("ng-binding")
    for binding in bindings:
        ng_bind = binding.get_attribute("ng-bind")
        if ng_bind == "fieldsTable.wifi24Status === 'UP' ? 'engineer_up' : 'engineer_down' | translate" and interface_frequency == "24":
            interface.up = binding.text == 'Up'
        elif ng_bind == "fieldsTable.wifi5Status === 'UP' ? 'Up' : 'Down'" and interface_frequency == "5":
            interface.up = binding.text == 'Up'
        elif ng_bind == "fieldsTable.wifi" + interface_frequency + "BSSID":
            interface.macAddress = binding.text
        elif ng_bind == "fieldsTable.channel" + interface_frequency + "g":
            interface.channel = int(binding.text)
        elif ng_bind == "fieldsTable.encryptionType" + interface_frequency:
            interface.encryption = str(binding.text).lower()
        elif ng_bind == "fieldsTable.wifi" + interface_frequency + "ssid":
            interface.ssid = binding.text
        elif ng_bind == "fieldsTable.transmitPower" + interface_frequency + "g":
            interface.power = int(binding.text)
        elif ng_bind == "fieldsTable.speed" + interface_frequency + "g":
            interface.dataRate = int(binding.text)

    # get connected clients
    clients = browser.find_elements_by_xpath('//div[@ng-repeat="device in fieldsTable.wifiDevices.wifi' + interface_frequency + '"]')
    for client in clients:
        raw = str(client.text).replace("\r", "").split("\n")
        interface.clients.append(classes.WifiClient(raw[1], raw[2], int(raw[3]), raw[4]))
    return interface


def get_external_ip():
    """
    get external ip for the router
    :return str: ip address or Error
    """
    global webInterfaceVersion, ipAddress, browser

    browser.get("http://" + ipAddress + "/" + webInterfaceVersion + "/gui/internet/ip-address-information/")
    time.sleep(0.2)

    bindings = browser.find_elements_by_class_name("ng-binding")
    for binding in bindings:
        if binding.get_attribute("ng-bind") == "fields.ipv4.publicWanIp":
            return str(binding.text)
    return "Error"


def print_syslog(verbosity, exclude_string, include):
    """
    print colored syslog
    :param int verbosity: determines how many times older data should be loaded (be repeatedly scrolling down in syslog table in web interface)
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

    # get syslog page
    browser.get("http://192.168.2.1/3.5/gui/system-information/")
    time.sleep(0.5)

    # open section
    ngs = browser.find_elements_by_class_name("config_syslog")
    for a in ngs:
        if a.get_attribute("ng-click") == "expanded = !expanded; changeExpandedOpen(expanded);":
            browser.execute_script("arguments[0].click()", a)
            break
    time.sleep(0.1)

    # get message table
    table = browser.find_element_by_tag_name("system-messages-split")
    time.sleep(2)
    # scroll down, according to given verbosity
    for x in range(0, verbosity):
        browser.execute_script("document.getElementsByClassName('systemMessagesTable')[0].scrollTop=document.getElementsByClassName('systemMessagesTable')[0].scrollTop +25000;")
        time.sleep(0.8)

    # color code and print messages
    sp = str(table.text).split("\n")
    # exit if len%2 is not 0, meaning that data is incomplete
    if not len(sp) % 2 == 0:
        exit_with_message(1, "[-] Data is incomplete")
    for x in range(int(len(sp) / 2) - 1, 0, -1):
        first_digit = sp[x * 2 + 1][1:2]
        second_digit = sp[x * 2 + 1][2:3]
        print_line = True
        if first_digit == "W":  # Wifi
            color_beg = BashColors.Background.cyan
            color_end = BashColors.Background.default
            if ex_wifi:
                print_line = False
        elif first_digit == "I" and second_digit == "G":  # IGMP
            color_beg = BashColors.Background.darkGrey
            color_end = BashColors.Background.default
            if ex_igmp:
                print_line = False
        elif first_digit == "V" and second_digit == "P":  # VPN
            color_beg = BashColors.Background.lightGrey + BashColors.black
            color_end = BashColors.Background.default + BashColors.default
            if ex_vpn:
                print_line = False
        elif (first_digit == "R" and not second_digit == "E") or (first_digit == "A" and not second_digit == "S") or first_digit == "P":  # DSL Line, configuration service
            color_beg = BashColors.Background.magenta + BashColors.black
            color_end = BashColors.Background.default + BashColors.default
            if ex_dsl:
                print_line = False
            if sp[x * 2 + 1][4:5] == "9" or sp[x * 2 + 1][3:5] == "13" or sp[x * 2 + 1][3:5] == "20" or sp[x * 2 + 1][2:5] == "004":
                color_beg = BashColors.Background.red + BashColors.black
        elif (first_digit == "H" and (second_digit == "A" or second_digit == "Y")) or (first_digit == "L" and second_digit == "T") or (first_digit == "S" and second_digit == "I"):  # LTE, SIM Card
            color_beg = BashColors.Background.lightMagenta + BashColors.black
            color_end = BashColors.Background.default + BashColors.default
            if ex_lte:
                print_line = False
            if sp[x * 2 + 1][4:5] == "2" or sp[x * 2 + 1][2:5] == "213" or sp[x * 2 + 1][2:5] == "001" or sp[x * 2 + 1][2:5] == "210":
                color_beg = BashColors.Background.red + BashColors.black
        elif first_digit == "D" and second_digit == "0":  # dynamic dns
            color_beg = BashColors.Background.lightGreen + BashColors.black
            color_end = BashColors.Background.default + BashColors.default
            if ex_ddns:
                print_line = False
            if sp[x * 2 + 1][4:5] == "1":
                color_beg = BashColors.Background.red + BashColors.black
        elif first_digit == "V":  # voice
            color_beg = BashColors.Background.blue
            color_end = BashColors.Background.default
            if ex_voice:
                print_line = False
            if sp[x * 2 + 1][2:5] == "006":
                color_beg = BashColors.Background.red + BashColors.black
        elif first_digit == "T" or (first_digit == "N" and second_digit == "T"):  # time
            color_beg = BashColors.Background.green + BashColors.black
            color_end = BashColors.Background.default + BashColors.default
            if ex_time:
                print_line = False
            if sp[x * 2 + 1][3:6] == "102":
                color_beg = BashColors.Background.red + BashColors.black
        elif first_digit == "E" and second_digit == "P":  # email notifications
            color_beg = BashColors.Background.yellow + BashColors.black
            color_end = BashColors.Background.default + BashColors.default
            if ex_mails:
                print_line = False
        elif first_digit == "G" and not second_digit == "W":  # web interface sessions
            color_beg = BashColors.Background.lightYellow + BashColors.black
            color_end = BashColors.Background.default + BashColors.default
            if ex_web_sessions:
                print_line = False
        elif first_digit == "D" and second_digit == "H":  # web interface sessions
            color_beg = BashColors.Background.lightCyan + BashColors.black
            color_end = BashColors.Background.default + BashColors.default
            if ex_dhcp:
                print_line = False
        else:  # unclassified
            color_beg = BashColors.Background.white + BashColors.black
            color_end = BashColors.Background.default + BashColors.default
            if ex_unclassified:
                print_line = False

        if print_line:
            print(color_beg + "{}\t{}".format(sp[x * 2], sp[x * 2 + 1]) + color_end)


def main():
    global browser

    # argparser
    parser = argparse.ArgumentParser(description="Selenium based CLI for Speedport Pro - Tobias Bittner (2020)\n" + BashColors.lightRed +
                                                 "\nIf you use this tool, every session in the webinterface will be terminated!" + BashColors.reset, formatter_class=FormatterHelp)
    parser.add_argument("-v", "--version", action="version", version="0.0.1 pre-alpha")
    parser.add_argument("-p", "--password", default=argparse.SUPPRESS, help="Your Speedport Web-Ui password", metavar="password", nargs=1, required=True)
    parser.add_argument("-m", "--mode",
                        help="Set the mode (s -> static, print information once and exit / d -> dynamic, refresh information after given time (-t)", nargs=1, metavar="mode", default=["s"])
    parser.add_argument("-t", "--time", help="Time to wait until data is refreshed. (dynamic mode only)", metavar="refreshTime", nargs=1, default=[2])
    parser.add_argument("-w", "--wifi", help="Information about the wifi interface with given frequency (2.4 or 5) and connected clients.", metavar="frequency", nargs=1, default=argparse.SUPPRESS)
    parser.add_argument("-ip", "--ipAddress", help="Print ip address information (e for external)", metavar="addressType", nargs=1, default=argparse.SUPPRESS)
    parser.add_argument("-sl", "--syslog",
                        help="Print syslog of speedport. You must specify the verbosity, e.g. 0. The higher the number, the more old messages will be loaded. (You can ex- or include message types with -slf)",
                        metavar="printSyslog", nargs=1, default=argparse.SUPPRESS)
    parser.add_argument("-slf", "--syslog_filter", help="ARGUMENT DOES NOTHING WHEN -sl IS NOT SET!!\nEx - or include entries in the syslog. Use in, to include and ex, to exclude, followed by one or more option"
                                                        "\nFollowing options are possible:\ne -> E-Mail Notifications\nwui -> Login attempts to Web Interface\nt -> Entries related to time settings"
                                                        "\nv -> Voice, telephony\ndd -> Dynamic DNS\nl -> LTE, SIM Card\nd -> DSL, configurator service\ni -> IGMP\nw -> wifi\nvpn -> vpn\ndh -> DHCP"
                                                        "\nu -> unclassified\nYou can choose multiple options, they must be separated with a comma. E.g. -slf in w (show only entries related to wifi) or -slf ex "
                                                        "\"dh,wui\" to exclude entries related to DHCP and webui login attempts.", metavar="syslogFilter", nargs=2, default=argparse.SUPPRESS)
    # try to parse args, if failed quit browser
    args = None
    try:
        args = parser.parse_args()
    except SystemExit:
        browser.quit()
        exit_with_message(2, "[-] Could not parse args")

    dynamic_mode = args.mode[0] == "d"

    # limit refresh interval in dynamic mode to min. 2 seconds
    if int(args.time[0]) < 2:
        args.time[0] = 2

    # get version and log in
    get_web_interface_version()
    login(args.password[0])
    time.sleep(1)

    if not loggedIn:
        exit_with_message(1, "[-] Not logged in...")

    if hasattr(args, "wifi"):
        once = True
        while dynamic_mode or once:
            if once:
                once = False
            i24 = get_wifi_interface_info("5" if args.wifi[0] == "5" else "24")
            if dynamic_mode:
                os.system('cls' if os.name == 'nt' else 'clear')
            print("-- Wifi Information --")
            print(BashColors.lightGreen + "{} GHz:\tSSID: {}\tState: {}\tChannel: {}\tPower: {}%\tInterface mac: {}".format(("5" if i24.is5G else "2.4"), i24.ssid,
                                                                                                                            ("Up" if i24.up else BashColors.lightRed + "Down" + BashColors.lightGreen), i24.channel,
                                                                                                                            i24.power, i24.macAddress) + BashColors.reset)
            print(BashColors.cyan + "Clients {}".format(str(len(i24.clients))) + BashColors.reset)
            if len(i24.clients) > 0:
                print(BashColors.cyan + "Mac\t\t\tIp\t\tSignal-strength\t\tHostname" + BashColors.reset)
                for client in i24.clients:
                    print("{}\t{}\t{}\t\t\t{}".format(client.macAddress, client.ipAddress,
                                                      (BashColors.lightRed if client.signalStrength < -70 else BashColors.lightGreen) + str(client.signalStrength) + BashColors.reset, client.hostName))

            if dynamic_mode:
                time.sleep(float(args.time[0]) - 0.8)
    elif hasattr(args, "ipAddress"):
        if dynamic_mode:
            print("----[i] Dynamic mode not supported by this operation, static will be used.----")
        if args.ipAddress[0] == "e":
            print(get_external_ip())
    elif hasattr(args, "syslog"):
        if dynamic_mode:
            print("----[i] Dynamic mode not supported by this operation, static will be used.----")
        include = False
        if hasattr(args, "syslog_filter"):
            if args.syslog_filter[0] == "in":
                include = True
            print_syslog(int(args.syslog[0]), args.syslog_filter[1], include)
        else:
            print(BashColors.lightRed + "[-] Argument -slf missing..." + BashColors.reset)
            exit(1)
    browser.quit()
    exit(0)


def exit_with_message(exit_code, error_message):
    global browser
    browser.quit()
    print(BashColors.lightRed + error_message + BashColors.reset)
    exit(exit_code)


if __name__ == '__main__':
    loggedIn = False  # true if login was successful
    webInterfaceVersion = ""  # web interface version, determined at startup
    ipAddress = "192.168.2.1"  # todo argument for ip address

    o = Options()
    o.headless = True
    browser = webdriver.Firefox(options=o, service_log_path=os.path.devnull)  # run headless and don't write logs

    try:
        main()
    except KeyboardInterrupt:
        browser.quit()
        os.system('cls' if os.name == 'nt' else 'clear')
        time.sleep(1)
        print(BashColors.blue + "[] Aborted by user..." + BashColors.reset)
        exit(0)
