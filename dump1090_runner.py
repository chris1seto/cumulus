#!/usr/bin/env python3

import time
import os
import threading
import argparse
import collections
import subprocess
import cumulus.rtl_sdr_tools

NO_DEVICE_SLEEP_TIMEOUT = 10

class Dump1090Runner(threading.Thread):
  def __init__(self, device_serial):
    super().__init__()
    
    self.device_serial = device_serial
    
  def run(self):
    while True:
      device_index = cumulus.rtl_sdr_tools.get_rtl_sdr_index_from_serial(self.device_serial)

      if (device_index == None):
        print('1090 SDR not found')
        time.sleep(NO_DEVICE_SLEEP_TIMEOUT)
        continue
        
      dump1090_process = subprocess.Popen(['./dump1090/dump1090', '--quiet', '--device-index', f'{device_index:d}', '--net'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
      dump1090_process.wait()
      print('Warning: dump1090 exited')