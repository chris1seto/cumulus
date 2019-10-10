#### file: dump978_provider.py
 
import socket
import threading
import time
import subprocess
import enum

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

DUMP978_PATH = './dump978'

class Dump978Provider(threading.Thread):
  def __init__(self):
    super().__init__()

  def run(self):
    # Get the index of the target sdr
  
    process_rtl_sdr = subprocess.Popen(['rtl_sdr', f'-d{device_index:d}', '-f978000000', '-s2083334', '-g48', '-'],
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      shell=False)

    process_dump978 = subprocess.Popen([f'{DUMP978_PATH}/dump978'],
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

      process_uat_frame(new_frame)
