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
import configparser
import frozendict
import datetime
import dump978_provider

# Default options for GDL90 output
DEF_SEND_ADDR = "192.168.8.255"
DEF_SEND_PORT = 4000

# Default for dump1090 
HOST_1090 = "localhost"
PORT_1090 = 30003

MAX_MERGE_COUNT = 500
MAX_TARGET_KEEP_TIMEOUT = 30
INS_TIMEOUT_S = .25
UPDATE_PERIOD_S = .25
DEFAULT_TARGET = {'lat': 0, 'lon': 0, 'altitude': 0, 'horizontal_speed': 0, 'vertical_rate': 0, 'track': 0, 'callsign': '---', 'last_seen': 0}
INS_OWNSHIP_FIELDS = ['TimeGps', 'NumSats', 'Fix', 'YawPitchRoll', 'YprU', 'InsPosLla', 'VelBody']

class VectornavMerger(threading.Thread):
  def __init__(self, vectornav_queue):
    super().__init__()
    
    self.vectornav_state = {}
    self.vectornav_queue = vectornav_queue

  def run(self):
    while True:
      # Get the latest INS update
      vn_update = self.vectornav_queue.get()     
      # Get the current time
      time_now = time.time()
      
      # Update the main representation
      for item_name, item in vn_update.items():
        self.vectornav_state.update({item_name: [item, time_now]})
        
  def get_vectornav_state(self):
    return frozendict.frozendict(self.vectornav_state)
    
class AhrsData:
  def __init__(self, pitch, roll, yaw):
    self.pitch = pitch
    self.roll = roll
    self.yaw = yaw
    
def EulerYawToHeading(euler):
  if (euler < 0):
    return euler + 360
  
  return euler
  
METERS_TO_FT = 3.28084
def meters_to_feet(meters):
  return (meters * METERS_TO_FT)
  
def magnitude(x, y):
  return math.sqrt(x**2 + y**2)
  
METERS_PER_SECOND_TO_KTS = 1.94384
def meters_per_second_to_kts(mps):
  # Compute the magnitude of the horizontal components (NE) of the xyz vector
  # Then, convert to kts
  return (mps * METERS_PER_SECOND_TO_KTS)

def connector_thread(config_path):
  # Open config
  config = configparser.ConfigParser()
  config.read(config_path)

  # GDL90 output
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
  
  target_updates_queue = queue.Queue()

  # Start the dump1090 provider
  dump1090_provider_ = dump1090_provider.Dump1090Provider(HOST_1090, PORT_1090, target_updates_queue)
  dump1090_provider_.start()
  
  # Start the dump978 provider
  #dump978_provider_ = dump978_provider.Dump978Provider()
  #dump978_provider_.start()
  
  # Start vectornav_provider
  ins_update_queue = queue.Queue()
  vectornav_provider_ = vectornav_provider.VectornavProvider(config['ins']['device'], int(config['ins']['baud']), ins_update_queue)
  vectornav_provider_.start()
  
  # Start the vn merger
  vectornav_merger = VectornavMerger(ins_update_queue)
  vectornav_merger.start()

  packet_total = 0
  encoder = gdl90encoder.Encoder()

  ownship = adsb_target.AdsbTarget(0, 0, 0, 0, 0, 0, config['ownship']['callsign'], int(config['ownship']['mode_s_code'], base = 16))
  ahrs_data = None
  
  ins_data = {}
  target_table = {}
  ins_valid = False

  while True:
    timestamp_start = time.time()
    dt = datetime.datetime.fromtimestamp(timestamp_start)
    
    # Merge INS data
    # Verify we have fields
    current_ins_data = vectornav_merger.get_vectornav_state()
    if (set(INS_OWNSHIP_FIELDS).issubset(current_ins_data.keys())):
      # Use YawPitchRoll as our canary item
      if (timestamp_start - current_ins_data['YawPitchRoll'][1] > INS_TIMEOUT_S):
        print('INS timeout!')
        ownship.lat = 0
        ownship.lon = 0
        ownship.altitude = 0
        ownship.track = 360
        ownship.horizontal_speed = 0
        ownship.vertical_rate = 0
      else:
        # Ahrs data
        ahrs_data = AhrsData(current_ins_data['YawPitchRoll'][0].pitch, 
          current_ins_data['YawPitchRoll'][0].roll, 
          current_ins_data['YawPitchRoll'][0].yaw)

        # Write heading
        ownship.track = EulerYawToHeading(current_ins_data['YawPitchRoll'][0].yaw)
        
        ins_valid = ((current_ins_data['InsStatus'][0] & 0x03) > 0)

        # Write GPS data if INS is valid
        if (ins_valid):
          # Lat/lon
          ownship.lat = current_ins_data['InsPosLla'][0].latitude
          ownship.lon = current_ins_data['InsPosLla'][0].longitude
          
          # Altitude (ft)
          ownship.altitude = meters_to_feet(current_ins_data['InsPosLla'][0].altitude)
          
          # Horizontal speed
          horizontal_speed_kts = magnitude(current_ins_data['VelBody'][0].x, current_ins_data['VelBody'][0].y)
          ownship.horizontal_speed = int(meters_per_second_to_kts(horizontal_speed_kts))
          
          # Vertical velocity
          ownship.vertical_rate = int(meters_to_feet(current_ins_data['VelBody'][0].z))
      
    # Merge traffic data
    merge_count = 0
    while merge_count < MAX_MERGE_COUNT:
      try:
        target_update = target_updates_queue.get_nowait()
        new_mode_s_code = list(target_update.keys())[0]

        if new_mode_s_code in target_table.keys():
          print(f'Updating {new_mode_s_code:x}')
          target_table[new_mode_s_code] = {**target_table[new_mode_s_code], **target_update[new_mode_s_code]}
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
      if (timestamp_start - target['last_seen'] > MAX_TARGET_KEEP_TIMEOUT):
        print(f'Removing {mode_s_code:x} {timestamp_start}')
        purge_list.append(mode_s_code)
        
    for purge_mode_s_code in purge_list:
      del target_table[purge_mode_s_code]

    # Heartbeat message
    buf = encoder.msgHeartbeat(ts = ((dt.hour * 3600) + (dt.minute * 60) + dt.second))
    s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
    packet_total += 1

    # Ownership report
    buf = encoder.msgOwnershipReport(latitude = ownship.lat,
      longitude = ownship.lon,
      altitude = ownship.altitude,
      hVelocity = ownship.horizontal_speed,
      vVelocity = ownship.vertical_rate,
      trackHeading = ownship.track,
      callSign = ownship.callsign)
    s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
    packet_total += 1
    
    # Ownership geometric altitude
    buf = encoder.msgOwnershipGeometricAltitude(altitude = ownship.altitude)
    s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
    packet_total += 1
    
    # Traffic reports
    for mode_s_code, target in target_table.items():
      # Do not include targets which lack lat/lon
      if (target['lat'] == 0 or target['lon'] == 0):
        continue
        
      # Do not include ownship
      if (mode_s_code == ownship.mode_s_code):
        continue

      # Pack the message
      buf = encoder.msgTrafficReport(latitude = target['lat'],
        longitude = target['lon'],
        altitude = target['altitude'],
        hVelocity = target['horizontal_speed'],
        vVelocity = target['vertical_rate'],
        trackHeading = target['track'],
        callSign = target['callsign'],
        address = target['mode_s_code'])
        
      s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
      packet_total += 1
    
    # GPS Time, Custom 101 Message
    buf = encoder.msgGpsTime(count = packet_total,
      quality = (2 if ins_valid else 0),
      hour = dt.hour,
      minute = dt.minute)
      
    s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
    packet_total += 1

    # Delay for the rest of this second
    sleep_period = UPDATE_PERIOD_S - (time.time() - timestamp_start)
    
    # Should never happen, but have seen it in the field
    if (sleep_period < 0):
      sleep_period = UPDATE_PERIOD_S
      
    time.sleep(sleep_period)

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('-c', help=' Config path', action='store', dest='config_path', default=None)
  args = parser.parse_args()
  while True:
    time.sleep(5)
  connector_thread(args.config_path)