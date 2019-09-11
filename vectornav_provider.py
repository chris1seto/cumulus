#### file: vectornav_provider.py

import socket
import threading
from time import time, sleep
import serial
import struct
import cstruct

VECTORNAV_START = 0xfa

PARSER_STATE_HEADER = 0
PARSER_STATE_GROUPS = 1
PARSER_STATE_GROUP_FIELDS = 2
PARSER_STATE_PAYLOAD = 3
PARSER_STATE_CRC = 4

VN_HEADER_SIZE = 1
VN_GROUPS_SIZE = 1
VN_CRC_SIZE = 2

class VnType(cstruct.CStruct):
  __byte_order__ = cstruct.LITTLE_ENDIAN

class VnUint8(VnType):
  __struct__ = '''
  uint8 value
  '''

class VnUint16(VnType):
  __struct__ = '''
  uint16 value;
  '''

class VnUint32(VnType):
  __struct__ = '''
  uint32 value
  '''

class VnUint64(VnType):
  __struct__ = '''
  uint64 value
  '''

class VnFloat(VnType):
  __struct__ = '''
  float value;
  '''

class VnYawPitchRoll(VnType):
  __struct__ = '''
  float yaw;
  float pitch;
  float roll;
  '''

class VnQuaternion(VnType):
  __struct__ = '''
  float qtn_0;
  float qtn_1;
  float qtn_2;
  float qtn_3;
  '''

class VnXyz(VnType):
  __struct__ = '''
  float x;
  float y;
  float z;
  '''

class VnPosLla(VnType):
  __struct__ = '''
  double latitude;
  double longitude;
  double altitude;
  '''

class VnPosEcef(VnType):
  __struct__ = '''
  double pos_0;
  double pos_1;
  double pos_2;
  '''

class VnNed(VnType):
  __struct__ = '''
  float north;
  float east;
  float down;
  '''

class VnImu(VnType):
  __struct__ = '''
  float accel_x;
  float accel_y;
  float accel_z;
  float rate_x;
  float rate_y;
  float rate_z;
  '''

VN_TYPES = [
  # Common group
  [
    ('TimeStartup', VnUint64), ('TimeGps', VnUint64), ('TimeSyncIn', VnUint64), ('YawPitchRoll', VnYawPitchRoll),
    ('Quaternion', VnQuaternion), ('AngularRate', VnXyz), ('InsPosition', VnPosLla), ('Velocity', VnNed),
    ('Accel', VnXyz), ('Imu', VnImu), ('MagPres', None), ('DeltaThetaVel', None),
    ('InsStatus', VnUint16), ('SyncInCnt', VnUint32), ('TimeGpsPps', VnUint64)
  ],

  # Time
  [
    ('TimeStartup', VnUint64), ('TimeGps', VnUint64), ('GpsTow', VnUint64), ('GpsWeek', VnUint16), ('TimeSyncIn', VnUint64),
    ('TimeGpsPps', VnUint64), ('TimeUtc', None), ('SyncInCnt', VnUint32), ('SyncOutCnt', VnUint32), ('TimeStatus', VnUint8)
  ],

  # IMU
  [
    ('ImuStatus', VnUint16), ('UncompMag', VnXyz), ('UncompAccel', VnXyz), ('UncompGyro', VnXyz), ('Temp', VnFloat),
    ('Pres', VnFloat), ('DeltaTheta', None), ('DeltaV', VnXyz), ('Mag', VnXyz), ('Accel', VnXyz), ('AngularRate', VnXyz)
  ],

  # GPS1
  [
    ('UTC', None),  ('Tow', VnUint64),  ('Week', VnUint16),  ('NumSats', VnUint8),  ('Fix', VnUint8),  ('GpsPosLla', VnPosLla),
    ('PosEcef', VnPosEcef), ('VelNed', VnNed), ('VelEcef', None), ('PosU', VnNed), ('VelU', VnFloat), ('TimeU', VnFloat), ('TimeInfo', None),
    ('DOP', None), ('SatInfo', None)
  ],

  # Attitude
  [
    ('ImuStatus', VnUint16), ('YawPitchRoll', VnYawPitchRoll), ('Quaternion', VnQuaternion), ('DCM', None), ('MagNed', VnNed), ('AccelNed', VnNed),
    ('LinearAccelBody', VnXyz), ('LinearAccelNed', VnNed),  ('YprU', VnYawPitchRoll)
  ],

  # INS
  [
    ('InsStatus', VnUint16),  ('InsPosLla', VnPosLla), ('PosEcef', VnPosEcef), ('VelBody', VnXyz), ('VelNed', VnNed),
    ('VelEcef', None), ('MagEcef', None), ('AccelEcef', None),('LinearAccelEcef', None), ('PosU', VnFloat), ('VelU', VnFloat)
  ]
]

class VectorNavPacketDecoder:
  def __init__(self):
    self.groups = 0x00
    self.group_fields = []
    self.data_items = []
    self.group_count = 0
    self.payload_size = 0

  # Set groups present word
  def set_groups(self, groups):
    count = 0

    # Upper 2 bits not used. If these are set, the packet is bad
    if (groups & (0x03 << 6)):
      return False

    # Scan the groups word
    for x in range(0, 6):
      if (groups & (1 << x)):
        count += 1

    self.groups = groups
    self.group_count = count
    return True

  # Set group fields
  def set_group_fields(self, group_fields_bin):
    # Group fields binary content needs to be 16bit word aligned
    if ((len(group_fields_bin) % 2) != 0):
      return False

    # Unpack the group fields
    self.group_fields = struct.unpack('<' + 'H'*self.get_group_count(), group_fields_bin)

    # Build list of items
    group_field_pointer = 0
    for group in range(0, 6):
      if (self.groups & (1 << group)):
        for data in range(0, 15):
          try:
            if (self.group_fields[group_field_pointer] & (1 << data)):
                self.data_items.append(VN_TYPES[group][data])
          except:
            return False

        # Next group field
        group_field_pointer += 1

    return True

  # Get the count of groups in the packet
  def get_group_count(self):
    return self.group_count

  # Get the payload size of groups
  def get_group_size(self):
    return self.group_count * 2

  # Calculate the payload size
  def calculate_payload_size(self):
    payload_size = 0

    # Iterate through each item and compute payload size
    for data_item in self.data_items:
      # If this item has no size, we have a bad packet
      if (data_item[1] == None):
        return False

      # Add the size of the data item
      payload_size += len(data_item[1])

    return payload_size

  def process_payload(self, payload):
    parse_index = 0
    extracted_data_items = {}

    #print(self.data_items)
    #print('')

    # Extract each item
    for item in self.data_items:
      # If we don't have a decoder, just advance
      # We deal with this when compiling the data items
      # So this should really never happen
      if (item[1] == None):
        return False

      # Unpack the data
      unpacked_data = item[1]()
      data_item_length = len(unpacked_data)
      unpacked_data.unpack(payload[parse_index:parse_index + data_item_length])
      parse_index += data_item_length

      # If this is a single value field, append just the value
      if (len(unpacked_data.__fields__) == 1):
        extracted_data_items.update({item[0]: unpacked_data.value})
      else:
        extracted_data_items.update({item[0]: unpacked_data})

    return extracted_data_items

class VectornavProvider(threading.Thread):
  def __init__(self, port, baud, ins_queue):
    super().__init__()

    self.serial_port = serial.Serial(port, baud)
    self.ins_queue = ins_queue

  def run(self):
    sync_buffer = bytearray()
    parse_pointer = 0
    parse_state = PARSER_STATE_HEADER
    parse_segment_size = VN_HEADER_SIZE
    packet_decoder = VectorNavPacketDecoder()

    while True:
      # Read a new byte
      sync_buffer.extend(self.serial_port.read(1))

      # Parse while we have data
      while (len(sync_buffer) > parse_pointer + parse_segment_size):
        # We need to find the header first
        if (parse_state == PARSER_STATE_HEADER):
          # Check if the first byte is a packet start value
          if (sync_buffer[0] == VECTORNAV_START):
            packet_decoder = VectorNavPacketDecoder()
            parse_state = PARSER_STATE_GROUPS

          # Regardless, remove the byte
          del sync_buffer[0]
          parse_pointer = 0
          parse_segment_size = VN_GROUPS_SIZE
        elif (parse_state == PARSER_STATE_GROUPS):
          packet_decoder.set_groups(sync_buffer[parse_pointer])
          parse_pointer += VN_GROUPS_SIZE

          parse_state = PARSER_STATE_GROUP_FIELDS
          parse_segment_size = packet_decoder.get_group_size()
        elif (parse_state == PARSER_STATE_GROUP_FIELDS):
          # Add the group bytes to the decoder
          packet_decoder.set_group_fields(sync_buffer[VN_GROUPS_SIZE:VN_GROUPS_SIZE + packet_decoder.get_group_size()])

          payload_size = packet_decoder.calculate_payload_size()

          # Verify that we were able to calculate the payload size
          if (payload_size == False):
            # TODO: Instrumentation
            # Reset the parser
            packet_decoder = VectorNavPacketDecoder()
            parse_pointer = 0
            parse_segment_size = VN_HEADER_SIZE
            parse_state = PARSER_STATE_HEADER
            continue

          # Advance the parser
          parse_pointer += parse_segment_size
          parse_segment_size = payload_size
          parse_state = PARSER_STATE_PAYLOAD
        elif (parse_state == PARSER_STATE_PAYLOAD):
          parse_pointer += parse_segment_size
          parse_segment_size = VN_CRC_SIZE
          parse_state = PARSER_STATE_CRC
        elif (parse_state == PARSER_STATE_CRC):
          # CRC the packet
          if (self._verify_crc(sync_buffer[:parse_pointer + VN_CRC_SIZE])):

            # Process the packet
            payload_start = VN_GROUPS_SIZE + packet_decoder.get_group_size()
            new_packet = packet_decoder.process_payload(sync_buffer[payload_start:payload_start + packet_decoder.calculate_payload_size()])

            # Enqueue the result
            self.ins_queue.put(new_packet)
            
            # Purge the entire buffer
            del sync_buffer[0:(parse_pointer + VN_CRC_SIZE)]
          else:
            # TODO: Instrumentation
            pass

          # Reset the parser
          parse_pointer = 0
          parse_segment_size = VN_HEADER_SIZE
          parse_state = PARSER_STATE_HEADER
          continue

  # Verify the CRC of a complete packet
  def _verify_crc(self, buffer):
    crc = 0

    for x in range(0, len(buffer)):
      crc = ((crc >> 8) | (crc << 8)) & 0xffff
      crc ^= buffer[x]
      crc ^= ((crc & 0xff) >> 4) & 0xffff
      crc ^= (crc << 12) & 0xffff
      crc ^= ((crc & 0x00ff) << 5) & 0xffff

    # Crc of a good packet should be 0x00
    return (crc == 0)