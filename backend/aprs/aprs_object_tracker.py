import logging
import queue
import threading
import time
from typing import Dict, List, Optional

logger = logging.getLogger("aprs-tracker")


class APRSObjectTracker(threading.Thread):
    """
    Tracks APRS objects (balloons, vehicles) from decoded packets.
    """

    def __init__(self, packet_queue: queue.Queue, socket_manager=None):
        super().__init__(daemon=True, name="APRSObjectTracker")
        self.packet_queue = packet_queue
        self.socket_manager = socket_manager
        
        self.running = True
        self.objects: Dict[str, Dict] = {}

    def _parse_position(self, payload: str) -> Optional[Dict]:
        """Very basic APRS position parser (uncompressed only for demo)."""
        # Format: !DDMM.hhN/DDDMM.hhW$
        if len(payload) < 20:
            return None
            
        try:
            if payload[0] in ['!', '=', '@', '/']:
                # Find coordinates
                lat_str = payload[1:8]
                lat_dir = payload[8]
                lon_str = payload[10:18]
                lon_dir = payload[18]
                
                # Convert to decimal
                lat_deg = float(lat_str[:2])
                lat_min = float(lat_str[2:])
                lat = lat_deg + (lat_min / 60.0)
                if lat_dir == 'S': lat = -lat
                
                lon_deg = float(lon_str[:3])
                lon_min = float(lon_str[3:])
                lon = lon_deg + (lon_min / 60.0)
                if lon_dir == 'W': lon = -lon
                
                return {"lat": lat, "lon": lon}
        except:
            pass
            
        return None

    def run(self):
        logger.info("APRS Object Tracker started")
        
        while self.running:
            try:
                packet_data = self.packet_queue.get(timeout=1.0)
                
                if isinstance(packet_data, dict) and "callsigns" in packet_data and "payload" in packet_data:
                    callsigns = packet_data["callsigns"]
                    payload = packet_data["payload"]
                    
                    if isinstance(payload, bytes):
                        try:
                            payload = payload.decode('ascii')
                        except:
                            continue
                            
                    src_call = callsigns.get("from")
                    if not src_call:
                        continue
                        
                    pos = self._parse_position(payload)
                    if pos:
                        now = time.time()
                        
                        if src_call not in self.objects:
                            self.objects[src_call] = {
                                "callsign": src_call,
                                "first_seen": now,
                                "history": []
                            }
                            
                        obj = self.objects[src_call]
                        obj["last_seen"] = now
                        obj["lat"] = pos["lat"]
                        obj["lon"] = pos["lon"]
                        obj["history"].append({"time": now, "lat": pos["lat"], "lon": pos["lon"]})
                        
                        # Keep history bounded
                        if len(obj["history"]) > 100:
                            obj["history"] = obj["history"][-100:]
                            
                        self._broadcast_tracks()
                        
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error tracking APRS object: {e}")

    def _broadcast_tracks(self):
        if self.socket_manager:
            self.socket_manager.emit("aprs-tracks", {"objects": list(self.objects.values())})

    def stop(self):
        self.running = False
