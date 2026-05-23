import logging
import queue
import threading
import time

import numpy as np

logger = logging.getLogger("spread-spectrum-tx")


class SpreadSpectrumTX(threading.Thread):
    """
    Direct Sequence Spread Spectrum (DSSS) TX for CubeSat command uplinks.
    """

    def __init__(
        self,
        tx_iq_queue: queue.Queue,
        sample_rate: float = 2000000.0,
        chip_rate: float = 1000000.0,
    ):
        super().__init__(daemon=True, name="SpreadSpectrumTX")
        self.tx_iq_queue = tx_iq_queue
        self.sample_rate = sample_rate
        self.chip_rate = chip_rate
        
        self.running = True
        self.data_queue = queue.Queue()

    def enqueue_data(self, data: bytes):
        self.data_queue.put(data)

    def _generate_prn(self, length: int) -> np.ndarray:
        """Generate a pseudo-random noise sequence (m-sequence)."""
        # Simple placeholder for LFSR
        return np.sign(np.random.randn(length)).astype(np.float32)

    def run(self):
        logger.info("Spread Spectrum TX started")
        
        sps = int(self.sample_rate / self.chip_rate)
        if sps < 1:
            sps = 1
            
        spreading_factor = 63 # chips per bit
            
        while self.running:
            try:
                data = self.data_queue.get(timeout=0.5)
                
                # 1. Convert bytes to bits (+1/-1)
                bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
                syms = (bits * 2) - 1
                
                # 2. Spread the signal
                prn = self._generate_prn(len(syms) * spreading_factor)
                spread_syms = np.repeat(syms, spreading_factor) * prn
                
                # 3. Upsample to chip rate and pulse shape (BPSK)
                # Rectangular pulse for simplicity
                iq_base = np.repeat(spread_syms, sps).astype(np.complex64)
                
                # Send
                msg = {
                    "samples": iq_base,
                    "sample_rate": self.sample_rate,
                    "timestamp": time.time()
                }
                self.tx_iq_queue.put(msg)
                
            except queue.Empty:
                pass

    def stop(self):
        self.running = False
