#!/usr/bin/env python3

import time
import math
import os
import threading
import argparse
import collections
import queue
import frozendict
import datetime
import subprocess
import sys
import atexit
import re
import enum
import cumulus.rtl_sdr_tools

class UatFrameType(enum.Enum):
  UPLINK = 0
  DOWNLINK = 1

class UatFrame:
  def __init__(self, type, frame):
    self.type = type
    self.frame = frame

class UatHeader:
  def __init__(self):
    self.type = 0
    self.address_qualifier = 0
    self.address = 0

class UatSv:
  def __init__(self):
    self.latitude = 0
    self.longitude = 0
    self.altitude_type = 0
    self.altitude = 0
    self.nic = 0
    self.ag_state = 0
    self.horizontal_velocity = 0
    self.vertical_velocity = 0
    self.utc = 0

def decode_uat_header(frame):
  header = UatHeader()

  header.type = (frame[0] >> 3) & 0x1f;
  header.address_qualifier = (frame[0] & 0x07);
  header.address = (frame[1] << 16) | (frame[2] << 8) | frame[3];

  return header

def process_uat_frame(frame):
  pass

DUMP978_SDR_SERIAL_NUMBER = 2

def dump978_thread(device_index):
  process_rtl_sdr = subprocess.Popen(['rtl_sdr', f'-d{device_index:d}', '-f978000000', '-s2083334', '-g48', '-'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    shell=False)

  process_dump978 = subprocess.Popen(['./dump978/dump978'],
    stdin=process_rtl_sdr.stdout,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    shell=False)

  atexit.register(close_all, process_rtl_sdr, process_dump978)

  while True:
    line = process_dump978.stdout.readline()
    new_frame_type = None
    frame = bytearray()

    # Is this an uplink or downlink?
    if (line[0] == '+'):
      new_frame_type = UatFrameType.UPLINK
    elif (line[0] == '-'):
      new_frame_type = UatFrameType.DOWNLINK
    else:
      continue

    # Try to parse the frame
    try:
      # Get the end of the data (if there is one)
      data_end = line.index(ord(';'))

      # Get the binary content of the frame (if it is properly aligned)
      frame = bytearray.fromhex(line[1:1 + data_end])
    except:
      continue

    new_frame = UatFrame(new_frame_type, frame)

    print(line)
    process_uat_frame(new_frame)

def close_all(pa, pb):
  pa.kill()
  pb.kill()

if __name__ == '__main__':
  device_index = cumulus.rtl_sdr_tools.get_rtl_sdr_index_from_serial(DUMP978_SDR_SERIAL_NUMBER)

  if (device_index == None):
    print('978 SDR not found')
    sys.exit()

  print(f'Using {device_index:d}')

  dump978_thread(device_index)