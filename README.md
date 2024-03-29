# cumulus
A stratus/stratux x86_64 remake on crack

# Dependencies
* https://git.osmocom.org/rtl-sdr/

# Setup/Run

```
cd ~
mkdir opt && cd opt
git clone git://git.osmocom.org/rtl-sdr.git
git clone https://github.com/chris1seto/cumulus.git

# Build rtl-sdr drivers
cd cd ~/opt/rtl-sdr
mkdir build
cd build
cmake ../ -DINSTALL_UDEV_RULES=ON
make
sudo make install
sudo ldconfig

# Build dump1090
cd ~/opt/cumulus/dump1090
make

# Build dump978
cd ~/opt/cumulus/dump978
make

# Plug in ONLY your 1090 SDR:
sudo rtl_eeprom -s 00000001

# Plug in ONLY your 978 SDR:
sudo rtl_eeprom -s 00000002

# Run cumulus
cd ~/opt/cumulus
./cumulus_system_runner.py -c <path to your config file>
```

# hostapd Notes
* Need to disable Ubuntu's network manager on the wireless interface before hostapd will work
* hostapd config: /etc/hostapd/hostapd.conf
```
auth_algs=1
#beacon_int=50
hw_mode=g
channel=8
country_code=US
#disassoc_low_ack=1
driver=nl80211
wme_enabled=1
#ieee80211d=1
ieee80211n=1
#ieee80211ac=1
interface=wlp2s0
rsn_pairwise=CCMP
ssid=cumulus
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_passphrase=inthesky
ht_capab=[HT40+]

```
* To get hostapd to start automatically as a service, edit /etc/default/hostapd, add the line:
```
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

# dnsmasq notes
* Config:
```
interface=wlp2s0
dhcp-range=192.168.8.2,192.168.8.20,255.255.255.0,12h
no-hosts
addn-hosts=/etc/hosts.dnsmasq
bind-interfaces
port=0
```

# network interfaces notes
* /etc/network/interfaces
```
auto wlp2s0
iface wlp2s0 inet static
address 192.168.8.1
netmask 255.255.255.0
```

# rtl-sdr notes
* To change the serial number reported in the USB dscriptor of an rtl-sdr use `rtl_eeprom -s 00000xxx`

# Startup notes
* Full system startup:
```
[Unit]
Description=cumulus
After=multi-user.target

[Service]
Type=simple
WorkingDirectory=/home/user/opt/cumulus/
ExecStart=/home/user/opt/cumulus/cumulus_system_runner.py -c /home/user/opt/cumulus/cumulus_config.ini
StandardInput=tty-force

[Install]
WantedBy=multi-user.target
```
