#### file: dump978_provider.py
 
import socket
import threading
import time
import subprocess
import enum
import atexit

from . import rtl_sdr_tools

class UatFrameType(enum.Enum):
  UPLINK = 0
  DOWNLINK = 1

class UatFrame:
  def __init__(self, type, frame):
    self.type = type
    self.frame = frame

# Hack for now...
def close_sub_processes(processes):
  for process in processes:
    process.kill()

DUMP978_PATH = './dump978'
DEVICE_WAIT_TIMEOUT = 5

class Dump978Provider(threading.Thread):
  def __init__(self, device_sn, uat_uplink_frame_queue, traffic_update_queue):
    super().__init__()
    
    self.device_sn = device_sn
    self.uat_uplink_frame_queue = uat_uplink_frame_queue
    self.traffic_update_queue = traffic_update_queue
    
  def _process_uat_frame(self, new_frame):
    if (new_frame.type == UatFrameType.UPLINK):
      self.uat_uplink_frame_queue.put(new_frame.frame)

  def run(self):
    # Get the index of the target sdr
    device_index = None
    while (device_index == None):
      device_index = rtl_sdr_tools.get_rtl_sdr_index_from_serial(self.device_sn)

      if (device_index == None):
        time.sleep(DEVICE_WAIT_TIMEOUT)
        
    print(f'dump978: Using device {device_index:d}')

    # Start rtl_sdr
    process_rtl_sdr = subprocess.Popen(['rtl_sdr', f'-d{device_index:d}', '-f978000000', '-s2083334', '-g48', '-'],
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      shell=False)

    # Start dump978
    process_dump978 = subprocess.Popen([f'{DUMP978_PATH}/dump978'],
      stdin=process_rtl_sdr.stdout,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      shell=False)

    # Register our handler to close the subprocesses we started
    atexit.register(close_sub_processes, [process_rtl_sdr, process_dump978])
    
    while True:
      line = process_dump978.stdout.readline()
      new_frame_type = None
      frame = bytearray()
      
      if (len(line) == 0):
        continue

      # Is this an uplink or downlink?
      if (line[0] == ord('+')):
        new_frame_type = UatFrameType.UPLINK
      elif (line[0] == ord('-')):
        new_frame_type = UatFrameType.DOWNLINK
      else:
        continue
      
      # Try to parse the frame and extract binary contents
      try:
        # Get the end of the data (if there is one)
        data_end = line.index(ord(';')) - 1
        
        # Get the binary content of the frame (if it is properly aligned)
        frame = bytearray.fromhex(line[1:1 + data_end].decode('utf-8'))
      except:
        continue

      self._process_uat_frame(UatFrame(new_frame_type, frame))