import logging
import math
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger("tx-power")


class TXPowerController(threading.Thread):
    """
    Dynamically adjusts TX power based on satellite elevation.
    Compensates for path loss while avoiding excessive power at high elevations.
    """

    def __init__(self, sdr_controller=None, socket_manager=None):
        super().__init__(daemon=True, name="TXPowerController")
        self.sdr_controller = sdr_controller
        self.socket_manager = socket_manager
        
        self.running = True
        
        # Configuration
        self.min_power_dbm = 10.0   # Power at 90 deg elevation
        self.max_power_dbm = 40.0   # Power at 0 deg elevation
        self.curve_type = "cosine"  # "linear", "cosine", "path_loss"
        
        # State
        self.active = False
        self.current_elevation = 0.0
        self.current_target_power = 0.0
        self.last_applied_power = 0.0
        
        self.target_satellite_norad = None

    def enable(self, norad_id: int):
        self.target_satellite_norad = norad_id
        self.active = True
        logger.info(f"TX Power Controller enabled for NORAD {norad_id}")

    def disable(self):
        self.active = False
        self.target_satellite_norad = None
        logger.info("TX Power Controller disabled")

    def update_elevation(self, norad_id: int, elevation_deg: float):
        if self.active and self.target_satellite_norad == norad_id:
            self.current_elevation = elevation_deg

    def _calculate_target_power(self, elevation_deg: float) -> float:
        """Calculate target power based on elevation."""
        if elevation_deg < 0:
            return self.max_power_dbm
            
        if elevation_deg > 90:
            return self.min_power_dbm

        if self.curve_type == "linear":
            # Linear scaling from max to min
            fraction = elevation_deg / 90.0
            return self.max_power_dbm - fraction * (self.max_power_dbm - self.min_power_dbm)
            
        elif self.curve_type == "cosine":
            # Cosine scaling (more power at low elevations, drops off faster at high)
            fraction = math.cos(math.radians(elevation_deg))
            return self.min_power_dbm + fraction * (self.max_power_dbm - self.min_power_dbm)
            
        elif self.curve_type == "path_loss":
            # Simplified free space path loss approximation relative to zenith
            # Slant range roughly proportional to 1/sin(el) for el > 10
            el_rad = math.radians(max(elevation_deg, 5.0)) # cap at 5 deg to prevent infinity
            relative_range = 1.0 / math.sin(el_rad)
            # 20 * log10(range)
            loss_db = 20 * math.log10(relative_range)
            target = self.min_power_dbm + loss_db
            return min(self.max_power_dbm, max(self.min_power_dbm, target))
            
        return self.max_power_dbm

    def run(self):
        logger.info("TX Power Controller thread started")
        
        while self.running:
            if self.active:
                target_power = self._calculate_target_power(self.current_elevation)
                
                # Only apply if changed significantly (e.g. > 0.5 dB)
                if abs(target_power - self.last_applied_power) > 0.5:
                    self.current_target_power = target_power
                    self._apply_power(target_power)
                    
            time.sleep(1.0) # Check every second

    def _apply_power(self, power_dbm: float):
        self.last_applied_power = power_dbm
        
        # In a real system, we'd command the SDR or PA here
        if self.sdr_controller:
            try:
                # Convert dBm to hardware specific gain value
                # self.sdr_controller.set_tx_gain(power_dbm)
                pass
            except Exception as e:
                logger.error(f"Failed to set TX power: {e}")
                
        # Broadcast status
        if self.socket_manager:
            status = {
                "active": self.active,
                "elevation_deg": self.current_elevation,
                "target_power_dbm": self.current_target_power,
                "curve": self.curve_type
            }
            self.socket_manager.emit("tx-power-status", status)

    def stop(self):
        self.running = False
