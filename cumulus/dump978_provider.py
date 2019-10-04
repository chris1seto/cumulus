#### file: dump978_provider.py
 
import socket
import threading
import time
import subprocess
import asyncio

DUMP978_PATH = '~/opt/dump978'

class Dump978Provider(threading.Thread):
  def __init__(self):
    super().__init__()

  async def run(self):
    rtl_sdr_args = ['rtl_sdr', '-f978000000', '-s2083334', '-g48', '-']
    dump978_args = [f'{DUMP978_PATH}/dump978']

    # Start rtl_sdr
    self.rtl_sdr = await asyncio.create_subprocess_exec(
      *rtl_sdr_args,
      stdout = asyncio.subprocess.PIPE,
      stderr = asyncio.subprocess.PIPE)
    
    # Start dump978
    self.dump978 = await asyncio.create_subprocess_exec(
      dump978_args,
      stdin = self.rtl_sdr.stdout,
      stdout = asyncio.subprocess.PIPE,
      stderr = asyncio.subprocess.PIPE)
  
    while (True):
      print(self.dump978.communicate())
      time.sleep(1)
      pass