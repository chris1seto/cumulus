import time
import os
import threading
import argparse
import collections
import subprocess
import re

RTL_EEPROM_TIMEOUT = 90
def get_rtl_sdr_index_from_serial(serial):
  # Get the number of rtl_sdrs connected
  first_query = subprocess.run(['rtl_eeprom'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=RTL_EEPROM_TIMEOUT).stderr.decode('utf-8')
  device_count = int(re.match('Found [0-9][0-9]*', first_query)[0].split(' ')[1])

  # For each index, check if the serial number matches
  for x in range(0, device_count):
    device_query = subprocess.run(['rtl_eeprom', f'-d{x:d}'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=RTL_EEPROM_TIMEOUT).stderr.decode('utf-8')

    # Find "Serial number:          xxxxxxxx"
    serial_string_pattern = 'Serial number:\t\t' + '[0-9]'*8

    try:
      match = re.findall(serial_string_pattern, device_query)[0]
      device_serial = int(match.split('\t\t')[1])
    except:
      continue

    if (serial == device_serial):
      return x

  return None