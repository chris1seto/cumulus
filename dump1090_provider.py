#### file: dump_1090_provider.py
 
import socket
import threading
from time import time, sleep
from functools import partial
 
BUFFER_SIZE_1090 = 100
 
# Dump1090 uses the SBS1 message format
# http://woodair.net/SBS/Article/Barebones42_Socket_Data.htm
# We only care about a subset of it
# Define an array of field names and parser functions
SBS1_MESSAGE_FORMAT = 22 * [(None, None)]
SBS1_MESSAGE_FORMAT[4] = ('mode_s_code', partial(int, base = 16))
SBS1_MESSAGE_FORMAT[14] = ('lat', float)
SBS1_MESSAGE_FORMAT[15] = ('lon', float)
SBS1_MESSAGE_FORMAT[11] = ('altitude', int)
SBS1_MESSAGE_FORMAT[12] = ('horizontal_speed', int)
SBS1_MESSAGE_FORMAT[16] = ('vertical_rate', int)
SBS1_MESSAGE_FORMAT[13] = ('track', int)
SBS1_MESSAGE_FORMAT[10] = ('callsign', str)
 
class SBS1ParseError(Exception):
  """Error parsing an SBS1 message """
 
class Dump1090Provider(threading.Thread):
  def __init__(self, host, port, target_update_queue):
    super().__init__()
     
    self.host = host
    self.port = port
    self.target_update_queue = target_update_queue
    self.socket = None
 
  def run(self):
    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.socket.connect((self.host, self.port))
    
    while True:
      try:
        # Fetch and parse sentence from the network
        sentence = self.read_sentence()
        target = self.parse_sentence(sentence)

        # Ignore a mode_s_code of 0, it's a heartbeat
        if (target['mode_s_code'] == 0):
          continue
        
        # Record time now
        target['last_seen'] = time()
        
        # Generate and enqueue the dict to emit
        target_update_data = {}
        target_update_data[target['mode_s_code']] = target
        self.target_update_queue.put(target_update_data)
        
      except SBS1ParseError as e:
        print(e)
 
  def read_sentence(self, startkey=b"MSG", stopkey=b"\r\n"):
    syncbuffer = bytearray()
    sentence = bytearray()
 
    # Wait for start key
    while startkey not in syncbuffer[0:len(startkey)]:
      syncbuffer += self._readbytes(1)
      del syncbuffer[0:-len(startkey)]
 
    # Accumulate until stop key
    while stopkey not in sentence:
      sentence += self._readbytes(1)
 
    return str(sentence)
 
  def _readbytes(self, nbytes, timeout=10):
    # This really is a shortcoming of the python standard library
    val = bytes()
    while not val:
      try:
        val = self.socket.recv(nbytes)
      except socket.error:
        print(f'dump1090 socket error. Waiting {timeout} sec to connect again')
        sleep(timeout)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        continue

    return val
 
  @classmethod
  def parse_sentence(self, sentence):
    message = {}
    fields = sentence.split(',')
    
    # Check correct length of the sentence
    if len(fields) != len(SBS1_MESSAGE_FORMAT):
      raise SBS1ParseError(f"MSG with incorrect number of fields received: {sentence}")
      
    # For each token, parse
    for value, (fieldname, parser) in zip(fields, SBS1_MESSAGE_FORMAT):
      if value != '' and parser != None:
        try:
          message[fieldname] = parser(value)
        except Exception as e:
          print(f"Parse warning on {fieldname} in MSG {sentence}: {str(e)}")
          
    if 'mode_s_code' not in message:
      raise SBS1ParseError(f"MSG with no S code received: {sentence}")

    return message