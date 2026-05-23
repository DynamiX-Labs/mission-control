import logging
import queue
import threading
import time

import numpy as np

logger = logging.getLogger("cw-keyer")


class CWKeyer(threading.Thread):
    """
    Morse Code Keyer.
    Generates TX IQ for CW (Continuous Wave) transmissions.
    """

    # International Morse Code dict
    MORSE_CODE_DICT = {
        'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 
        'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 
        'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---', 
        'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-', 
        'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--', 
        'Z': '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--', 
        '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..', 
        '9': '----.', ' ': ' '
    }

    def __init__(
        self,
        tx_iq_queue: queue.Queue,
        wpm: int = 20,
        tone_hz: float = 700.0,
        sample_rate: float = 48000.0
    ):
        super().__init__(daemon=True, name="CWKeyer")
        self.tx_iq_queue = tx_iq_queue
        self.wpm = wpm
        self.tone_hz = tone_hz
        self.sample_rate = sample_rate
        
        self.running = True
        self.message_queue = queue.Queue()
        
        # Timing calculations
        self._calc_timing()

    def _calc_timing(self):
        # standard PARIS formula for WPM: 1 dot = 1.2 / WPM seconds
        self.dot_s = 1.2 / self.wpm
        self.dash_s = 3 * self.dot_s
        self.symbol_space_s = self.dot_s
        self.letter_space_s = 3 * self.dot_s
        self.word_space_s = 7 * self.dot_s
        
        # Soft edges (cosine raised)
        self.rise_time_s = 0.005 # 5ms
        
    def enqueue_message(self, text: str):
        self.message_queue.put(text.upper())
        logger.info(f"Enqueued CW message: {text}")

    def _generate_tone(self, duration_s: float) -> np.ndarray:
        num_samples = int(duration_s * self.sample_rate)
        t = np.arange(num_samples) / self.sample_rate
        
        # Complex tone
        signal = np.exp(1j * 2 * np.pi * self.tone_hz * t)
        
        # Apply envelope (raised cosine edges) to prevent key clicks
        rise_samples = min(int(self.rise_time_s * self.sample_rate), num_samples // 2)
        if rise_samples > 0:
            env = np.ones(num_samples)
            rise = 0.5 * (1 - np.cos(np.pi * np.arange(rise_samples) / rise_samples))
            env[:rise_samples] = rise
            env[-rise_samples:] = rise[::-1]
            signal = signal * env
            
        return signal.astype(np.complex64)

    def _generate_space(self, duration_s: float) -> np.ndarray:
        return np.zeros(int(duration_s * self.sample_rate), dtype=np.complex64)

    def run(self):
        logger.info(f"CW Keyer started ({self.wpm} WPM)")
        
        while self.running:
            try:
                msg = self.message_queue.get(timeout=0.5)
                self._calc_timing()
                
                for char in msg:
                    if not self.running:
                        break
                        
                    if char == ' ':
                        self._send_iq(self._generate_space(self.word_space_s))
                        continue
                        
                    code = self.MORSE_CODE_DICT.get(char, '')
                    
                    for i, symbol in enumerate(code):
                        if symbol == '.':
                            self._send_iq(self._generate_tone(self.dot_s))
                        elif symbol == '-':
                            self._send_iq(self._generate_tone(self.dash_s))
                            
                        # Space between symbols
                        if i < len(code) - 1:
                            self._send_iq(self._generate_space(self.symbol_space_s))
                            
                    # Space between letters
                    self._send_iq(self._generate_space(self.letter_space_s))
                    
            except queue.Empty:
                pass
                
    def _send_iq(self, samples: np.ndarray):
        # Break into chunks if too large
        chunk_size = 4096
        for i in range(0, len(samples), chunk_size):
            chunk = samples[i:i+chunk_size]
            msg = {
                "samples": chunk,
                "sample_rate": self.sample_rate,
                "timestamp": time.time()
            }
            try:
                self.tx_iq_queue.put(msg)
            except queue.Full:
                pass
            
            # Rate limit to approximate realtime
            time.sleep(len(chunk) / self.sample_rate * 0.9)

    def stop(self):
        self.running = False
