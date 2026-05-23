import logging
import queue
import threading
import time

import numpy as np

logger = logging.getLogger("loopback-tester")


class LoopbackTester:
    """
    Tests full duplex chain without antenna using USRP internal loopback.
    """

    def __init__(self, sdr_controller=None):
        self.sdr_controller = sdr_controller

    def start_loopback_test(self):
        """
        Enable internal loopback and inject test signal.
        """
        logger.info("Starting internal loopback test")
        if self.sdr_controller:
            try:
                # Example USRP loopback setting
                # self.sdr_controller.set_rx_antenna("TX/RX") # Usually handled by hardware routing
                # In SoapySDR some devices have an "internal" loopback routing
                pass
            except Exception as e:
                logger.error(f"Failed to configure loopback: {e}")

    def generate_test_signal(self, sample_rate: float, duration_s: float) -> np.ndarray:
        """Generate a chirp or PRBS test signal."""
        t = np.linspace(0, duration_s, int(sample_rate * duration_s))
        # Simple chirp
        f0, f1 = -sample_rate/4, sample_rate/4
        # Phase equation for chirp: 2*pi*(f0*t + 0.5*(f1-f0)/duration_s * t^2)
        phase = 2 * np.pi * (f0 * t + 0.5 * (f1 - f0) / duration_s * t**2)
        return np.exp(1j * phase).astype(np.complex64)
