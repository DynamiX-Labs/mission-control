import logging
import queue
import threading
import time
from typing import Any, Dict

import numpy as np
from scipy import signal

logger = logging.getLogger("linear-transponder")


class LinearTransponder(threading.Thread):
    """
    Linear Transponder (e.g. FO-29 style).
    Receives wideband IQ, filters to a passband, inverts the spectrum,
    and applies frequency translation.
    """

    def __init__(
        self,
        rx_iq_queue: queue.Queue,
        tx_iq_queue: queue.Queue,
        session_id: str,
        passband_width_hz: float = 30000.0,
        inverting: bool = True,
        agc_target_dbfs: float = -10.0,
    ):
        super().__init__(daemon=True, name=f"Transponder-{session_id}")
        self.rx_iq_queue = rx_iq_queue
        self.tx_iq_queue = tx_iq_queue
        self.session_id = session_id
        
        self.passband_width_hz = passband_width_hz
        self.inverting = inverting
        self.agc_target_dbfs = agc_target_dbfs
        
        self.running = True
        
        self.stats: Dict[str, Any] = {
            "rx_chunks_in": 0,
            "tx_chunks_out": 0,
            "rx_power_db": -100.0,
            "tx_power_db": -100.0,
            "agc_gain": 1.0,
            "errors": 0,
            "last_activity": None
        }
        self.stats_lock = threading.Lock()
        
        self.sample_rate = None
        self.b = None
        self.a = None

    def _setup_filter(self, sample_rate: float):
        if self.sample_rate == sample_rate and self.b is not None:
            return
            
        self.sample_rate = sample_rate
        # Create a lowpass filter for half the passband width
        # (Since it's centered at DC, a 15kHz lowpass gives 30kHz total passband)
        cutoff = min(self.passband_width_hz / 2.0, (sample_rate / 2.0) * 0.9)
        nyq = sample_rate / 2.0
        
        # 6th order butterworth
        self.b, self.a = signal.butter(6, cutoff / nyq, btype='low')
        logger.info(f"Transponder filter initialized for {cutoff*2} Hz passband at {sample_rate} sps")

    def run(self):
        logger.info(f"Linear Transponder started for session {self.session_id}")
        
        filter_state = None
        agc_gain = 1.0
        agc_alpha_attack = 0.1
        agc_alpha_decay = 0.01

        while self.running:
            try:
                try:
                    rx_msg = self.rx_iq_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                rx_samples = rx_msg.get("samples")
                if rx_samples is None or len(rx_samples) == 0:
                    continue

                sample_rate = rx_msg.get("sample_rate", 2048000)
                self._setup_filter(sample_rate)

                with self.stats_lock:
                    self.stats["rx_chunks_in"] += 1
                    self.stats["last_activity"] = time.time()

                # Calculate RX Power
                rx_power = np.mean(np.abs(rx_samples)**2) + 1e-12
                rx_power_db = 10 * np.log10(rx_power)

                # 1. Filter passband
                if filter_state is None:
                    filter_state = signal.lfilter_zi(self.b, self.a) * rx_samples[0]
                
                filtered_samples, filter_state = signal.lfilter(self.b, self.a, rx_samples, zi=filter_state)

                # 2. Invert spectrum if configured
                # To invert a complex signal around DC, take the complex conjugate
                if self.inverting:
                    tx_samples = np.conjugate(filtered_samples)
                else:
                    tx_samples = filtered_samples

                # 3. AGC (Automatic Gain Control)
                # Calculate power of the filtered signal
                signal_power = np.mean(np.abs(tx_samples)**2) + 1e-12
                signal_dbfs = 10 * np.log10(signal_power)
                
                # Simple AGC loop
                error_db = self.agc_target_dbfs - signal_dbfs
                
                # Apply asymmetric attack/decay
                if error_db > 0:
                    # Signal is too quiet -> increase gain (decay)
                    agc_gain_target = agc_gain * (10 ** (error_db / 20.0))
                    agc_gain = agc_gain * (1 - agc_alpha_decay) + agc_gain_target * agc_alpha_decay
                else:
                    # Signal is too loud -> decrease gain (attack)
                    agc_gain_target = agc_gain * (10 ** (error_db / 20.0))
                    agc_gain = agc_gain * (1 - agc_alpha_attack) + agc_gain_target * agc_alpha_attack
                
                # Limit maximum gain
                agc_gain = min(agc_gain, 100.0) 
                
                # Apply gain
                tx_samples = tx_samples * agc_gain
                
                # Calculate TX power
                tx_power = np.mean(np.abs(tx_samples)**2) + 1e-12
                tx_power_db = 10 * np.log10(tx_power)

                with self.stats_lock:
                    self.stats["rx_power_db"] = rx_power_db
                    self.stats["tx_power_db"] = tx_power_db
                    self.stats["agc_gain"] = agc_gain

                # 4. Prepare output message
                tx_msg = rx_msg.copy()
                tx_msg["samples"] = tx_samples
                
                # Send to TX queue
                try:
                    self.tx_iq_queue.put(tx_msg, block=False)
                    with self.stats_lock:
                        self.stats["tx_chunks_out"] += 1
                except queue.Full:
                    logger.warning("Transponder TX queue full, dropping samples")

            except Exception as e:
                logger.error(f"Error in Linear Transponder: {e}")
                with self.stats_lock:
                    self.stats["errors"] += 1
                time.sleep(0.1)

        logger.info(f"Linear Transponder stopped for session {self.session_id}")

    def stop(self):
        self.running = False
