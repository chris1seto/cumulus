#!/usr/bin/env python3

import time
import os
import threading
import argparse
import collections
import subprocess
import configparser

import cumulus.rtl_sdr_tools
import cumulus.cumulus
import dump1090_runner

IDLE_TIMEOUT = 5

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('-c', help=' Config path', action='store', dest='config_path', default=None)
  args = parser.parse_args()
  
  # Open config
  config = configparser.ConfigParser()
  config.read(args.config_path)

  # Start dump1090
  dump_1090_runner = dump1090_runner.Dump1090Runner(int(config['dump1090']['device_sn']))
  dump_1090_runner.start()
  
  # Start cumulus
  cumulus = cumulus.cumulus.Cumulus(config)
  cumulus.start()
  
  # Idle loop
  while (True):
    time.sleep(IDLE_TIMEOUT)