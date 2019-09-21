# Container for ADSB target
class AdsbTarget:
  lat = 0
  lon = 0
  altitude = 0
  horizontal_speed = 0
  vertical_rate = 0
  track = 0
  callsign = "-"
  mode_s_code = 0x000000
  last_seen = 0
  
  def __init__(self, lat, lon, altitude, horizontal_speed, vertical_rate, track, callsign, address):
    self.lat = lat
    self.lon = lon
    self.altitude = altitude
    self.horizontal_speed = horizontal_speed
    self.vertical_rate = vertical_rate
    self.track = track
    self.mode_s_code = address
    self.callsign = callsign