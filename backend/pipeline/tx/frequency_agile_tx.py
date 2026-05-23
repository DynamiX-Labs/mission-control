import logging
import threading
import time
from typing import Dict, List, Optional

logger = logging.getLogger("frequency-agile")


class FrequencyAgileTX(threading.Thread):
    """
    Manages frequency hopping mid-pass for multi-satellite operation
    or dynamic band plans.
    """

    def __init__(self, sdr_controller=None):
        super().__init__(daemon=True, name="FrequencyAgileTX")
        self.sdr_controller = sdr_controller
        self.running = True
        
        self.sequence: List[Dict] = []
        self.active = False
        self.current_idx = 0

    def load_sequence(self, hop_sequence: List[Dict]):
        """
        Load a sequence of frequency hops.
        Format: [{"time_offset_s": 0, "freq_hz": 435000000}, ...]
        """
        self.sequence = sorted(hop_sequence, key=lambda x: x["time_offset_s"])
        self.current_idx = 0
        logger.info(f"Loaded frequency sequence with {len(self.sequence)} hops")

    def start_sequence(self):
        self.active = True
        self.start_time = time.time()
        self.current_idx = 0
        logger.info("Started frequency agile sequence")

    def stop_sequence(self):
        self.active = False
        logger.info("Stopped frequency agile sequence")

    def run(self):
        logger.info("Frequency Agile TX thread started")
        
        while self.running:
            if self.active and self.sequence and self.current_idx < len(self.sequence):
                now = time.time()
                elapsed = now - self.start_time
                
                next_hop = self.sequence[self.current_idx]
                
                if elapsed >= next_hop["time_offset_s"]:
                    freq_hz = next_hop["freq_hz"]
                    logger.info(f"Hopping to {freq_hz} Hz (offset: {elapsed:.1f}s)")
                    
                    if self.sdr_controller:
                        try:
                            # Command SDR to retune TX
                            # self.sdr_controller.set_tx_frequency(freq_hz)
                            pass
                        except Exception as e:
                            logger.error(f"Failed to hop frequency: {e}")
                            
                    self.current_idx += 1
                    
            time.sleep(0.1)

    def stop(self):
        self.running = False
