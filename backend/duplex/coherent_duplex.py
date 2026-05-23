import logging
import queue
import threading
import time
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger("coherent-duplex")


class CoherentDuplex(threading.Thread):
    """
    Manages phase coherent TX/RX using USRP internal reference clocks.
    Enables precise ranging and Doppler measurements.
    """

    def __init__(self, sdr_controller=None):
        super().__init__(daemon=True, name="CoherentDuplex")
        self.sdr_controller = sdr_controller
        self.running = True
        self.coherent_mode = False
        
        self.phase_offset_rad = 0.0

    def enable_coherent_mode(self):
        """Configure SDR for phase coherent operation."""
        self.coherent_mode = True
        logger.info("Enabling phase coherent mode on SDR")
        
        if self.sdr_controller:
            try:
                # Require UHD backend to set clock/time source to internal/external reference
                # self.sdr_controller.set_clock_source("internal")
                # self.sdr_controller.set_time_source("internal")
                pass
            except Exception as e:
                logger.error(f"Failed to set coherent clock sources: {e}")

    def measure_phase_offset(self, tx_ref_samples: np.ndarray, rx_samples: np.ndarray) -> float:
        """
        Measure phase difference between TX and RX baseband signals.
        Useful for ranging or calibrating LO phase ambiguity.
        """
        if len(tx_ref_samples) == 0 or len(rx_samples) == 0:
            return 0.0
            
        n = min(len(tx_ref_samples), len(rx_samples))
        
        # Cross-correlation to find phase difference
        cross_corr = np.sum(rx_samples[:n] * np.conjugate(tx_ref_samples[:n]))
        phase_rad = np.angle(cross_corr)
        
        self.phase_offset_rad = phase_rad
        return phase_rad

    def run(self):
        logger.info("Coherent Duplex manager started")
        while self.running:
            time.sleep(1.0)
            
    def stop(self):
        self.running = False
