
import socket
import threading
import time
import serial
import struct
import pynmea2
from collections import namedtuple

RECONNECT_WAIT_TIME = 1
SERIAL_TIMEOUT = 10

GPS_TIMEOUT = 5

GPS_SITUATION_TUPLE = namedtuple('GosSituation', ['lat', 'lon', 'alt', 'course', 'h_speed'])

class NmeaGpsProvider(threading.Thread):
  def __init__(self, port, baud):
    super().__init__()

    try:
      self.serial_port = serial.Serial(port, baud, timeout=SERIAL_TIMEOUT)
    except:
      pass

    self.port = port
    self.baud = baud
    self.situation = {
      'gga': {'last_update': 0, 'fix': 0, 'lat': 0, 'lon': 0, 'alt': 0, 'h_dop': 0},
      'rmc': {'last_update': 0, 'h_speed': 0, 'course': 0}
    }
    
  def _process_gga(self, gga):
    self.situation['gga']['last_update'] = time.time()
    self.situation['gga']['fix'] = gga.gps_qual
    self.situation['gga']['lat'] = gga.latitude
    self.situation['gga']['lon'] = gga.longitude
    self.situation['gga']['alt'] = gga.altitude
    #self.situation['gga']['h_dop'] = float(gga.horizontal_dil)
  
  def _process_rmc(self, rmc):
    self.situation['rmc']['last_update'] = time.time()
    self.situation['rmc']['h_speed'] = rmc.spd_over_grnd
    self.situation['rmc']['course'] = rmc.true_course
    
  def get_situation(self):
    current_time = time.time()
    if (current_time - self.situation['gga']['last_update'] > GPS_TIMEOUT
      or current_time - self.situation['rmc']['last_update'] > GPS_TIMEOUT):
      return None
      
    if (self.situation['gga']['fix'] < 2):
      return None
  
    situation = GPS_SITUATION_TUPLE(self.situation['gga']['lat'],
      self.situation['gga']['lon'],
      self.situation['gga']['alt'],
      self.situation['rmc']['course'],
      self.situation['rmc']['h_speed'])
      
    return situation

  def run(self):
    while True:
      # Read a new byte
      try:
        new_line = self.serial_port.readline().decode('utf-8')
      except:
        try:
          self.serial_port = serial.Serial(self.port, self.baud, timeout=SERIAL_TIMEOUT)
        except:
          pass
        time.sleep(RECONNECT_WAIT_TIME)
        continue
        
      if (new_line[0] != '$'):
        continue

      new_msg = pynmea2.parse(new_line)
      
      if (isinstance(new_msg, pynmea2.GGA)):
        self._process_gga(new_msg)
      elif (isinstance(new_msg, pynmea2.RMC)):
        self._process_rmc(new_msg)
      