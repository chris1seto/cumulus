import time
import socket
import math
import os
import threading
import argparse
import collections
import queue
import frozendict
import datetime

from . import gdl90encoder
from . import adsb_target
from . import dump1090_provider
from . import nmea_gps_provider
from . import dump978_provider

# Default options for GDL90 output
DEF_SEND_ADDR = "192.168.8.255"
DEF_SEND_PORT = 4000

# Default for dump1090
HOST_1090 = "localhost"
PORT_1090 = 30003

MAX_MERGE_COUNT_PER_FRAME = 500
MAX_UAT_UPLINK_PER_FRAME = 5

MAX_TARGET_KEEP_TIMEOUT = 30
INS_TIMEOUT_S = .25
UPDATE_PERIOD_S = .25
DEFAULT_TARGET = {'lat': 0, 'lon': 0, 'altitude': 0, 'horizontal_speed': 0, 'vertical_rate': 0, 'track': 0, 'callsign': '---', 'last_seen': 0}

class Cumulus(threading.Thread):
  def __init__(self, config):
    super().__init__()

    self.config = config

  def run(self):
    # GDL90 output
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    target_update_queue = queue.Queue()
    uat_uplink_queue = queue.Queue()

    # Start the dump1090 provider
    dump1090_provider_ = dump1090_provider.Dump1090Provider(HOST_1090, PORT_1090, target_update_queue)
    dump1090_provider_.start()

    # Start the dump978 provider
    dump978_provider_ = dump978_provider.Dump978Provider(int(self.config['dump978']['device_sn']), uat_uplink_queue, target_update_queue)
    dump978_provider_.start()

    # Start nmea gps provider
    gps_situation = None
    nmea_gps = nmea_gps_provider.NmeaGpsProvider(self.config['gps']['device'], int(self.config['gps']['baud']))
    nmea_gps.start()

    packet_total = 0
    encoder = gdl90encoder.Encoder()

    ownship = adsb_target.AdsbTarget(0, 0, 0, 0, 0, 0, self.config['ownship']['callsign'], int(self.config['ownship']['mode_s_code'], base = 16))

    target_table = {}
    position_valid = False

    while True:
      timestamp_start = time.time()
      dt = datetime.datetime.fromtimestamp(timestamp_start)
      
      # Fetch GPS situation
      gps_situation = nmea_gps.get_situation()
      if (gps_situation == None):
        position_valid = False
        print('No GPS')
      else:
        position_valid = True
        ownship.lat = gps_situation.lat
        ownship.lon = gps_situation.lon
        ownship.altitude = gps_situation.alt
        ownship.horizontal_speed = int(gps_situation.h_speed)
        
        # Don't wander on heading if we have no speed
        if (ownship.horizontal_speed > 0):
          ownship.track = int(gps_situation.course)
      
      # Merge traffic data
      for x in range(0, MAX_MERGE_COUNT_PER_FRAME):
        try:
          target_update = target_update_queue.get_nowait()
          new_mode_s_code = list(target_update.keys())[0]

          if new_mode_s_code in target_table.keys():
            target_table[new_mode_s_code] = {**target_table[new_mode_s_code], **target_update[new_mode_s_code], 'updated': True}
          else:
            print(f'Adding {new_mode_s_code:x}')
            target_table.update({new_mode_s_code: DEFAULT_TARGET})
            target_table[new_mode_s_code] = {**target_table[new_mode_s_code], **target_update[new_mode_s_code], 'updated': True}
        except queue.Empty:
          break

      # Prune old targets
      purge_list = []
      for mode_s_code, target in target_table.items():
        if (timestamp_start - target['last_seen'] > MAX_TARGET_KEEP_TIMEOUT):
          print(f'Removing {mode_s_code:x}')
          purge_list.append(mode_s_code)

      for purge_mode_s_code in purge_list:
        del target_table[purge_mode_s_code]

      # Send UAT uplink messages
      for x in range(0, MAX_UAT_UPLINK_PER_FRAME):
        try:
          new_uplink_message = uat_uplink_queue.get_nowait()
        except queue.Empty:
          break

        buf = encoder.msgUatUplink(None, new_uplink_message)
        s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
        packet_total += 1

      # Heartbeat message
      buf = encoder.msgHeartbeat(ts = ((dt.hour * 3600) + (dt.minute * 60) + dt.second))
      s.sendto(buf, (DEF_SEND_ADDR, DEF_SEND_PORT))
      packet_total += 1

      # Ownership report
      if (position_valid):
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
        # Only send the target if it's an update
        if (not target['updated']):
          continue
        
        # Clear update flag
        target['updated'] = False
      
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
        quality = (2 if position_valid else 0),
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