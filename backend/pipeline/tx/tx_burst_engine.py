import logging
import queue
import threading
import time
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger("tx-burst")


class TXBurstEngine(threading.Thread):
    """
    Executes precisely timed bursts of TX IQ data for command uplinks.
    """

    def __init__(self, tx_iq_queue: queue.Queue):
        super().__init__(daemon=True, name="TXBurstEngine")
        self.tx_iq_queue = tx_iq_queue
        
        self.running = True
        self.command_queue = queue.PriorityQueue()
        
        self.active = False
        
    def enqueue_burst(self, iq_samples: np.ndarray, execute_at: float, priority: int = 1):
        """
        Enqueue a burst to be transmitted at a specific time (unix timestamp).
        """
        self.command_queue.put((execute_at, priority, id(iq_samples), iq_samples))
        logger.info(f"Enqueued TX burst for t={execute_at}")

    def run(self):
        logger.info("TX Burst Engine started")
        
        while self.running:
            try:
                # Peek at the next command without removing it
                if self.command_queue.empty():
                    time.sleep(0.01)
                    continue
                    
                execute_at, priority, _, iq_samples = self.command_queue.queue[0]
                
                now = time.time()
                
                if now >= execute_at:
                    # Time to execute! Remove it from queue
                    self.command_queue.get()
                    
                    self._transmit_burst(iq_samples)
                    
                else:
                    # Wait for the right time, but don't sleep too long
                    wait_time = execute_at - now
                    if wait_time > 0.05:
                        time.sleep(0.05)
                    else:
                        # Spin lock for precision < 50ms
                        while time.time() < execute_at and self.running:
                            pass
                            
            except Exception as e:
                logger.error(f"Error in TX Burst Engine: {e}")
                time.sleep(0.1)

    def _transmit_burst(self, iq_samples: np.ndarray):
        """Send the IQ samples to the TX queue."""
        logger.debug(f"Transmitting burst of {len(iq_samples)} samples")
        
        # Package into standard IQ message format
        msg = {
            "samples": iq_samples,
            "timestamp": time.time(),
            "is_burst": True
        }
        
        try:
            self.tx_iq_queue.put(msg, block=False)
        except queue.Full:
            logger.error("TX IQ queue full, dropped command burst!")

    def stop(self):
        self.running = False
