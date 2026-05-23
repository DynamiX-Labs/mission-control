import logging
import queue
import threading
import time
from typing import Dict, Optional

import numpy as np
from scipy import signal

logger = logging.getLogger("ssb-transceiver")


class SSBTransceiver(threading.Thread):
    """
    SSB Voice Transceiver.
    RX: Demodulates SSB (USB/LSB) from IQ to Audio.
    TX: Modulates Audio to SSB (USB/LSB) IQ.
    """

    def __init__(
        self,
        rx_iq_queue: Optional[queue.Queue] = None,
        rx_audio_queue: Optional[queue.Queue] = None,
        tx_audio_queue: Optional[queue.Queue] = None,
        tx_iq_queue: Optional[queue.Queue] = None,
        mode: str = "USB",
        bfo_offset_hz: float = 0.0,
    ):
        super().__init__(daemon=True, name="SSBTransceiver")
        self.rx_iq_queue = rx_iq_queue
        self.rx_audio_queue = rx_audio_queue
        self.tx_audio_queue = tx_audio_queue
        self.tx_iq_queue = tx_iq_queue
        
        self.mode = mode.upper() # "USB" or "LSB"
        self.bfo_offset_hz = bfo_offset_hz
        self.running = True

    def _ssb_modulate(self, audio_samples: np.ndarray, sample_rate: float) -> np.ndarray:
        """Modulate real audio into analytic SSB signal (IQ)."""
        # Hilbert transform to get analytic signal
        analytic_signal = signal.hilbert(audio_samples)
        
        if self.mode == "LSB":
            # For LSB, take the complex conjugate of the analytic signal
            analytic_signal = np.conjugate(analytic_signal)
            
        # Optional BFO / carrier shift
        if self.bfo_offset_hz != 0.0:
            t = np.arange(len(audio_samples)) / sample_rate
            shift = np.exp(1j * 2 * np.pi * self.bfo_offset_hz * t)
            analytic_signal = analytic_signal * shift
            
        return analytic_signal.astype(np.complex64)

    def run(self):
        logger.info(f"SSB Transceiver started in {self.mode} mode")
        
        while self.running:
            # Simple placeholder for TX path
            if self.tx_audio_queue and self.tx_iq_queue:
                try:
                    audio_msg = self.tx_audio_queue.get(timeout=0.1)
                    audio_samples = audio_msg.get("audio")
                    
                    if audio_samples is not None:
                        # Normalize audio
                        audio_samples = audio_samples / (np.max(np.abs(audio_samples)) + 1e-6)
                        
                        # Modulate
                        sample_rate = audio_msg.get("sample_rate", 48000)
                        iq_samples = self._ssb_modulate(audio_samples, sample_rate)
                        
                        # Output
                        tx_msg = {
                            "samples": iq_samples,
                            "sample_rate": sample_rate,
                            "timestamp": time.time()
                        }
                        self.tx_iq_queue.put(tx_msg, block=False)
                        
                except queue.Empty:
                    pass
                except Exception as e:
                    logger.error(f"TX SSB modulation error: {e}")
            else:
                time.sleep(0.5)

    def stop(self):
        self.running = False
