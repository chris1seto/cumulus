#!/usr/bin/env python3

import time
import os
import threading
import argparse
import collections
import subprocess
import cumulus.rtl_sdr_tools

DUMP1090_SDR_SERIAL_NUMBER = 1
NO_DEVICE_SLEEP_TIMEOUT = 10

if __name__ == '__main__':
  while True:
    device_index = cumulus.rtl_sdr_tools.get_rtl_sdr_index_from_serial(DUMP1090_SDR_SERIAL_NUMBER)

    if (device_index == None):
      print('1090 SDR not found')
      time.sleep(NO_DEVICE_SLEEP_TIMEOUT)
      continue
      
    dump1090_process = subprocess.Popen(['./dump1090/dump1090', '--quiet', '--device-index', f'{device_index:d}', '--net'], stdout=None, stderr=None)
    dump1090_process.wait()
    print('Warning: dump1090 exited')