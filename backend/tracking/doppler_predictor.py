import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from skyfield.api import EarthSatellite, Topos, load

logger = logging.getLogger("doppler-predictor")


class DopplerPredictor:
    """
    Pre-calculates entire pass Doppler curves to eliminate real-time calculation overhead.
    """
    
    def __init__(self):
        self.ts = load.timescale()
        self.c_km_s = 299792.458  # Speed of light in km/s

    def generate_curve(
        self,
        tle_line1: str,
        tle_line2: str,
        observer_lat: float,
        observer_lon: float,
        observer_elevation: float,
        start_time_iso: str,
        end_time_iso: str,
        downlink_freq_hz: float,
        uplink_freq_hz: float,
        resolution_ms: int = 100,
    ) -> Dict[str, np.ndarray]:
        """
        Pre-calculates the Doppler curve for an entire pass.

        Args:
            tle_line1: TLE line 1
            tle_line2: TLE line 2
            observer_lat: Observer latitude in degrees
            observer_lon: Observer longitude in degrees
            observer_elevation: Observer elevation in meters
            start_time_iso: ISO 8601 start time of pass
            end_time_iso: ISO 8601 end time of pass
            downlink_freq_hz: Downlink frequency in Hz
            uplink_freq_hz: Uplink frequency in Hz
            resolution_ms: Time step between pre-calculated points in milliseconds

        Returns:
            Dict containing arrays of 'timestamps' (Unix time), 'downlink_hz', 'uplink_hz'
        """
        try:
            from dateutil import parser
            start_dt = parser.parse(start_time_iso)
            end_dt = parser.parse(end_time_iso)
        except ImportError:
            # Fallback if dateutil is not available
            from datetime import datetime
            start_dt = datetime.fromisoformat(start_time_iso.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time_iso.replace('Z', '+00:00'))

        start_unix = start_dt.timestamp()
        end_unix = end_dt.timestamp()
        duration_s = end_unix - start_unix
        
        # Ensure minimum duration
        if duration_s <= 0:
            duration_s = 1.0

        # Create time array
        num_points = max(2, int((duration_s * 1000) / resolution_ms) + 1)
        unix_times = np.linspace(start_unix, end_unix, num_points)
        
        # Convert to skyfield times
        # To avoid slow iteration, we create a batched time array
        from datetime import datetime, timezone
        dts = [datetime.fromtimestamp(t, tz=timezone.utc) for t in unix_times]
        t_array = self.ts.from_datetimes(dts)

        # Setup skyfield objects
        satellite = EarthSatellite(tle_line1, tle_line2, "Target", self.ts)
        topos = Topos(
            latitude_degrees=observer_lat,
            longitude_degrees=observer_lon,
            elevation_m=observer_elevation,
        )

        # Compute positions and velocities for all times at once
        difference = satellite - topos
        topocentric = difference.at(t_array)
        
        # Radial velocity calculation
        pos = topocentric.position.km        # Shape: (3, N)
        vel = topocentric.velocity.km_per_s  # Shape: (3, N)
        
        # Compute range (distance) for each point
        range_km = np.sqrt(np.sum(pos**2, axis=0))  # Shape: (N,)
        
        # Unit vectors
        pos_unit = pos / range_km
        
        # Radial velocity (dot product of unit pos and vel along axis 0)
        range_rate = np.sum(pos_unit * vel, axis=0)  # Shape: (N,)
        
        # Doppler factors
        doppler_factor = 1.0 - (range_rate / self.c_km_s)
        
        # Apply to frequencies
        downlink_observed = downlink_freq_hz * doppler_factor
        uplink_observed = uplink_freq_hz * doppler_factor
        
        # The shift is Observed - Nominal
        downlink_shift = downlink_observed - downlink_freq_hz
        uplink_shift = uplink_observed - uplink_freq_hz
        
        # NOTE: For uplink, we typically want the inverted shift to transmit so it arrives correctly at the satellite.
        # But this function just returns the physical shift. The transmitter will apply the inverse.

        return {
            "timestamps": unix_times,
            "downlink_shift_hz": downlink_shift,
            "uplink_shift_hz": uplink_shift,
        }


class DopplerPredictorThread(threading.Thread):
    """
    Real-time thread that provides interpolated Doppler corrections.
    """
    
    def __init__(self):
        super().__init__(daemon=True, name="DopplerPredictorThread")
        self.running = True
        self.predictor = DopplerPredictor()
        self.curve_lock = threading.Lock()
        
        # Current active curve
        self.timestamps = None
        self.downlink_shift = None
        self.uplink_shift = None

    def load_curve(self, curve_data: Dict[str, np.ndarray]):
        with self.curve_lock:
            self.timestamps = curve_data["timestamps"]
            self.downlink_shift = curve_data["downlink_shift_hz"]
            self.uplink_shift = curve_data["uplink_shift_hz"]

    def get_doppler_at(self, unix_time: float) -> Tuple[float, float]:
        """
        Returns interpolated (downlink_shift_hz, uplink_shift_hz) for the given time.
        """
        with self.curve_lock:
            if self.timestamps is None or len(self.timestamps) == 0:
                return 0.0, 0.0
            
            # If before curve, return first value
            if unix_time <= self.timestamps[0]:
                return float(self.downlink_shift[0]), float(self.uplink_shift[0])
                
            # If after curve, return last value
            if unix_time >= self.timestamps[-1]:
                return float(self.downlink_shift[-1]), float(self.uplink_shift[-1])
                
            # Interpolate
            dl = np.interp(unix_time, self.timestamps, self.downlink_shift)
            ul = np.interp(unix_time, self.timestamps, self.uplink_shift)
            
            return float(dl), float(ul)

    def run(self):
        # This thread just stays alive to hold state in memory and could handle async loading
        while self.running:
            time.sleep(1.0)
            
    def stop(self):
        self.running = False
