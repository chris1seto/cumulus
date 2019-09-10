#!/usr/bin/env python3

import time
import socket
import gdl90encoder
import math
import os
import threading
import threading
import argparse
import collections
import adsb_target
import dump1090_provider
import vectornav_provider
import queue

# Default options for GDL90 output
DEF_SEND_ADDR = "192.168.8.255"
DEF_SEND_PORT = 4000

# Default for dump1090 
HOST_1090 = "localhost"
PORT_1090 = 30003

MAX_MERGE_COUNT = 500

MAX_TARGET_KEEP_TIMEOUT = 30

DEFAULT_TARGET = {'lat': 0, 'lon': 0, 'altitude': 0, 'horizontal_speed': 0, 'vertical_rate': 0, 'track': 0, 'callsign': '---', 'last_seen': 0}

def connector_thread():
  # GDL90 output
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
  
  target_updates_queue = queue.Queue()

  # Start the dump1090 provider
  dump1090_provider_ = dump1090_provider.Dump1090Provider(HOST_1090, PORT_1090, target_updates_queue)
  dump1090_provider_.start()
  
  # Start vectornav_provider
  situation_update_queue = queue.Queue()
  vectornav_provider_ = vectornav_provider.VectornavProvider('/dev/ttyUSB0', 230400, situation_update_queue)
  vectornav_provider_.start()

  packetTotal = 0
  encoder = gdl90encoder.Encoder()

  ownship = adsb_target.AdsbTarget(38.625263, -90.2001021, 2500, 0, 0, 360, "N610SH", 0xA7F056)

  target_table = {}

  while True:
    time_start = time.time()
    
    # Merge traffic data
    merge_count = 0
    while merge_count < MAX_MERGE_COUNT:
      try:
        target_update = target_updates_queue.get_nowait()
        new_mode_s_code = list(target_update.keys())[0]

        if new_mode_s_code in target_table.keys():
          print(f'Updating {new_mode_s_code:x}')
          target_table[new_mode_s_code] = {**target_table[new_mode_s_code], **target_update[new_mode_s_code]}
          print(target_table)
        else:
          print(f'Adding {new_mode_s_code:x}')
          target_table.update({new_mode_s_code: DEFAULT_TARGET})
          target_table[new_mode_s_code] = {**target_table[new_mode_s_code], **target_update[new_mode_s_code]}
          
        merge_count += 1
      except queue.Empty:
        break
        
    # Prune old targets
    purge_list = []
    for mode_s_code, target in target_table.items():
      if (time_start - target['last_seen'] > MAX_TARGET_KEEP_TIMEOUT):
        print(f'Removing {mode_s_code:x} {time_start}')
        purge_list.append(mode_s_code)
        
    for purge_mode_s_code in purge_list:
      del target_table[purge_mode_s_code]

    # Heartbeat message
    buf = encoder.msgHeartbeat()
    s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
    packetTotal += 1

    # Stratux heartbeat message
    buf = encoder.msgStratuxHeartbeat()
    s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
    packetTotal += 1

    # Ownership report
    buf = encoder.msgOwnershipReport(latitude=ownship.lat,
      longitude = ownship.lon,
      altitude = ownship.altitude,
      hVelocity = ownship.horizontal_speed,
      vVelocity = ownship.vertical_rate,
      trackHeading = ownship.track,
      callSign = ownship.callsign)
    s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
    packetTotal += 1
    
    # Ownership geometric altitude
    buf = encoder.msgOwnershipGeometricAltitude(altitude=ownship.altitude)
    s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
    packetTotal += 1
    
    # Traffic reports
    for mode_s_code, target in target_table.items():
      # Do not include targets which lack lat/lon
      if (target['lat'] == 0 or target['lon'] == 0):
        continue
        
      # Do not include ownship
      if (mode_s_code == ownship.mode_s_code):
        continue

      # Pack the message
      buf = encoder.msgTrafficReport(latitude=target['lat'],
        longitude=target['lon'],
        altitude=target['altitude'],
        hVelocity=target['horizontal_speed'],
        vVelocity=target['vertical_rate'],
        trackHeading=target['track'],
        callSign=target['callsign'],
        address=target['mode_s_code'])
        
      s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
      packetTotal += 1
    
    # GPS Time, Custom 101 Message
    buf = encoder.msgGpsTime(count=packetTotal)
    s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
    packetTotal += 1

    # Delay for the rest of this second
    time.sleep(.25 - (time.time() - time_start))

if __name__ == '__main__':
  connector_thread()