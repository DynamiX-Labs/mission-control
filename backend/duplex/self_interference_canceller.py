import logging
import queue
import threading
import time
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger("self-interference-canceller")


class SelfInterferenceCanceller(threading.Thread):
    """
    Self-Interference Canceller (SIC) for Full Duplex operation.

    Uses an adaptive LMS (Least Mean Squares) filter to subtract the TX reference
    signal from the RX signal to cancel self-interference.
    """

    def __init__(
        self,
        rx_iq_queue: queue.Queue,
        tx_ref_queue: queue.Queue,
        out_iq_queue: queue.Queue,
        session_id: str,
        filter_order: int = 128,
        step_size: float = 0.05,
    ):
        super().__init__(daemon=True, name=f"SIC-{session_id}")
        self.rx_iq_queue = rx_iq_queue
        self.tx_ref_queue = tx_ref_queue
        self.out_iq_queue = out_iq_queue
        self.session_id = session_id

        self.running = True
        self.filter_order = filter_order
        self.step_size = step_size

        # LMS filter weights
        self.weights = np.zeros(self.filter_order, dtype=np.complex64)

        # Buffer for previous TX reference samples
        self.tx_buffer = np.zeros(self.filter_order, dtype=np.complex64)

        # Performance monitoring stats
        self.stats: Dict[str, Any] = {
            "rx_chunks_in": 0,
            "tx_chunks_in": 0,
            "chunks_out": 0,
            "errors": 0,
            "cancellation_ratio_db": 0.0,
            "last_activity": None,
        }
        self.stats_lock = threading.Lock()

        # Track remaining TX samples to align with RX samples if sizes differ
        self._tx_residue = np.array([], dtype=np.complex64)

    def _lms_filter(self, rx_samples: np.ndarray, tx_samples: np.ndarray) -> np.ndarray:
        """
        Apply Normalized LMS (NLMS) filter.

        Args:
            rx_samples: Received signal (contains target + interference)
            tx_samples: Reference signal (the interference to be canceled)

        Returns:
            Cleaned RX signal
        """
        N = len(rx_samples)
        e = np.zeros(N, dtype=np.complex64)

        # To avoid Python for-loop overhead, we could use Cython or a vectorized approach,
        # but for simplicity we implement the standard LMS loop here. In a real high-rate system,
        # this would need to be optimized (e.g., block LMS or Numba/Cython).
        
        # Calculate powers for cancellation ratio metric
        rx_power = np.mean(np.abs(rx_samples)**2)

        for n in range(N):
            # Shift new TX sample into buffer
            self.tx_buffer[1:] = self.tx_buffer[:-1]
            self.tx_buffer[0] = tx_samples[n]

            # Calculate filter output (estimated interference)
            y = np.vdot(self.weights, self.tx_buffer)

            # Calculate error (cleaned signal)
            e[n] = rx_samples[n] - y

            # NLMS weight update: w = w + mu * e * conj(x) / (||x||^2 + epsilon)
            norm_factor = np.vdot(self.tx_buffer, self.tx_buffer).real + 1e-6
            mu_normalized = self.step_size / norm_factor
            self.weights += mu_normalized * e[n] * np.conj(self.tx_buffer)

        # Calculate cancellation ratio
        e_power = np.mean(np.abs(e)**2) + 1e-12
        rx_power = max(rx_power, 1e-12)
        cancellation_ratio = 10 * np.log10(rx_power / e_power)

        with self.stats_lock:
            self.stats["cancellation_ratio_db"] = cancellation_ratio

        return e

    def run(self):
        logger.info(f"Self-Interference Canceller started for session {self.session_id}")

        while self.running:
            try:
                # Get RX samples
                try:
                    rx_msg = self.rx_iq_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                rx_samples = rx_msg.get("samples")
                if rx_samples is None or len(rx_samples) == 0:
                    continue

                with self.stats_lock:
                    self.stats["rx_chunks_in"] += 1
                    self.stats["last_activity"] = time.time()

                rx_len = len(rx_samples)
                tx_samples = np.zeros(rx_len, dtype=np.complex64)
                tx_idx = 0

                # Use residual TX samples from previous chunk
                res_len = len(self._tx_residue)
                if res_len > 0:
                    take = min(rx_len, res_len)
                    tx_samples[:take] = self._tx_residue[:take]
                    self._tx_residue = self._tx_residue[take:]
                    tx_idx += take

                # Get enough TX samples to match RX samples
                while tx_idx < rx_len and self.running:
                    try:
                        tx_msg = self.tx_ref_queue.get(timeout=0.01)
                        tx_chunk = tx_msg.get("samples")
                        if tx_chunk is not None and len(tx_chunk) > 0:
                            with self.stats_lock:
                                self.stats["tx_chunks_in"] += 1

                            chunk_len = len(tx_chunk)
                            needed = rx_len - tx_idx
                            take = min(needed, chunk_len)

                            tx_samples[tx_idx : tx_idx + take] = tx_chunk[:take]
                            tx_idx += take

                            # Save any leftover TX samples for the next RX chunk
                            if chunk_len > take:
                                self._tx_residue = tx_chunk[take:]

                    except queue.Empty:
                        break # If no TX reference, we'll just use zeros (no cancellation)

                # Process through LMS filter
                cleaned_samples = self._lms_filter(rx_samples, tx_samples)

                # Construct output message (copying metadata from RX msg)
                out_msg = rx_msg.copy()
                out_msg["samples"] = cleaned_samples

                # Forward to downstream consumers
                try:
                    self.out_iq_queue.put(out_msg, block=False)
                    with self.stats_lock:
                        self.stats["chunks_out"] += 1
                except queue.Full:
                    logger.warning("SIC output queue full, dropping samples")

            except Exception as e:
                logger.error(f"Error in SIC loop: {e}")
                with self.stats_lock:
                    self.stats["errors"] += 1
                time.sleep(0.1)

        logger.info(f"Self-Interference Canceller stopped for session {self.session_id}")

    def stop(self):
        self.running = False
