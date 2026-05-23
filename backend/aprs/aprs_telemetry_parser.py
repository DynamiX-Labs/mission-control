import logging
from typing import Dict, Optional

logger = logging.getLogger("aprs-telemetry")


class APRSTelemetryParser:
    """
    Parses APRS Telemetry packets (T# format).
    """

    def parse_telemetry(self, payload: str) -> Optional[Dict]:
        """
        Parse APRS Base91 or standard comma-separated telemetry.
        Format: T#SEQ,A1,A2,A3,A4,A5,D
        """
        if not payload.startswith("T#"):
            return None
            
        try:
            parts = payload.split(',')
            if len(parts) < 2:
                return None
                
            seq = parts[0][2:]
            
            telemetry = {
                "sequence": seq,
                "analog": [],
                "digital": 0
            }
            
            # Analog channels (up to 5)
            for i in range(1, min(6, len(parts))):
                try:
                    telemetry["analog"].append(float(parts[i]))
                except ValueError:
                    telemetry["analog"].append(0.0)
                    
            # Digital channel (bits)
            if len(parts) > 6:
                try:
                    telemetry["digital"] = int(parts[6], 2) if set(parts[6]).issubset({'0', '1'}) else int(parts[6])
                except:
                    pass
                    
            return telemetry
            
        except Exception as e:
            logger.debug(f"Failed to parse APRS telemetry: {e}")
            return None
