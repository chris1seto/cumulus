# cumulus
A stratus/stratux x86_64 remake on crack

# To run
* Clone, build, make install rtl-sdr drivers
* clone, and build dump1090
* cd into dump1090 root: `./dump1090 --interactive --net`
* cd into this repo root: `./cumulus.py`

# hostapd Notes
* Need to disable Ubuntu's network manager on the wireless interface before hostapd will work
* hostapd config: /etc/hostapd/hostapd.conf
```
auth_algs=1
beacon_int=50
channel=6
country_code=US
disassoc_low_ack=1
driver=nl80211
hw_mode=g
ieee80211d=1
ieee80211n=1
interface=wlp2s0
rsn_pairwise=CCMP
ssid=cumulus
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_passphrase=inthesky
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
* To change the serial number creported in the USB dscriptor of an rtl-sdr use `rtl_eeprom -s 00000xxx`
