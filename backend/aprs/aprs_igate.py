import logging
import queue
import socket
import threading
import time
from typing import Dict, List, Optional

logger = logging.getLogger("aprs-igate")


class APRSIGate(threading.Thread):
    """
    Connects to the APRS-IS network and forwards received AX.25 packets.
    """

    def __init__(
        self,
        callsign: str,
        passcode: str,
        server: str = "rotate.aprs2.net",
        port: int = 14580,
        packet_queue: Optional[queue.Queue] = None,
        socket_manager=None
    ):
        super().__init__(daemon=True, name="APRS-IGate")
        self.callsign = callsign
        self.passcode = passcode
        self.server = server
        self.port = port
        
        self.packet_queue = packet_queue or queue.Queue()
        self.socket_manager = socket_manager
        
        self.running = True
        self.connected = False
        self.sock = None
        
        self.stats = {
            "packets_gated": 0,
            "bytes_sent": 0,
            "reconnects": 0,
            "last_packet": None,
            "errors": 0
        }

    def _connect(self) -> bool:
        try:
            if self.sock:
                self.sock.close()
                
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10.0)
            self.sock.connect((self.server, self.port))
            
            # Login string: user <callsign> pass <passcode> vers DynamiX-GroundStation 1.0
            login_str = f"user {self.callsign} pass {self.passcode} vers DynamiX-GS 1.0\r\n"
            self.sock.send(login_str.encode('ascii'))
            
            # Wait for response
            response = self.sock.recv(1024).decode('ascii')
            logger.info(f"APRS-IS login response: {response.strip()}")
            
            if "verified" in response.lower() or "unverified" in response.lower():
                self.connected = True
                self._broadcast_status()
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Failed to connect to APRS-IS: {e}")
            self.connected = False
            self.sock = None
            self._broadcast_status()
            return False

    def _format_for_igate(self, raw_packet: bytes, callsigns: Dict) -> Optional[str]:
        """
        Formats a raw AX.25 packet for APRS-IS.
        Requires decoding the payload. For simplicity, we assume we receive
        a TNC2 formatted string or we extract it.
        If we receive raw bytes, we'd need a full AX.25 decoder here.
        Assuming we receive pre-formatted TNC2 string or we build it from callsigns.
        """
        # For this implementation, we expect a tuple of (payload_bytes, callsigns_dict)
        # in the queue, or a pre-formatted TNC2 string.
        # Let's assume the payload is a TNC2 string for now.
        if isinstance(raw_packet, str):
            # Already TNC2 formatted: SRCCALL>DSTCALL,PATH:Payload
            return raw_packet
            
        # If it's a dict with payload and callsigns
        if isinstance(raw_packet, dict) and "payload" in raw_packet and "callsigns" in raw_packet:
            c = raw_packet["callsigns"]
            p = raw_packet["payload"]
            if isinstance(p, bytes):
                try:
                    p = p.decode('ascii')
                except:
                    return None # Not ASCII text, can't gate to APRS-IS easily
                    
            # TNC2 format: SRC>DST,qAR,IGATECALL:Payload
            # qAR signifies it was gated by an IGate
            src = c.get("from", "UNKNOWN")
            dst = c.get("to", "UNKNOWN")
            return f"{src}>{dst},qAR,{self.callsign}:{p}"

        return None

    def run(self):
        logger.info(f"APRS iGate starting. Connecting to {self.server}:{self.port} as {self.callsign}")
        
        while self.running:
            if not self.connected:
                if not self._connect():
                    time.sleep(30.0) # Backoff
                    continue
            
            try:
                # Wait for packets
                try:
                    packet_data = self.packet_queue.get(timeout=1.0)
                except queue.Empty:
                    # Send keepalive occasionally
                    continue

                formatted_packet = self._format_for_igate(packet_data, None)
                if formatted_packet:
                    # Send to APRS-IS
                    if not formatted_packet.endswith("\r\n"):
                        formatted_packet += "\r\n"
                        
                    self.sock.send(formatted_packet.encode('ascii'))
                    
                    self.stats["packets_gated"] += 1
                    self.stats["bytes_sent"] += len(formatted_packet)
                    self.stats["last_packet"] = formatted_packet.strip()
                    self._broadcast_status()
                    
                    logger.debug(f"Gated packet: {formatted_packet.strip()}")
                    
            except socket.timeout:
                continue
            except (socket.error, BrokenPipeError) as e:
                logger.error(f"APRS-IS connection error: {e}")
                self.connected = False
                self.stats["reconnects"] += 1
                self.stats["errors"] += 1
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                self.sock = None
            except Exception as e:
                logger.error(f"Error processing APRS packet: {e}")
                self.stats["errors"] += 1

        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        logger.info("APRS iGate stopped")

    def _broadcast_status(self):
        if self.socket_manager:
            status = {
                "connected": self.connected,
                "server": self.server,
                "callsign": self.callsign,
                "stats": self.stats
            }
            # Update constants.py to include APRS_IGATE_STATUS
            self.socket_manager.emit("aprs-igate-status", status)

    def stop(self):
        self.running = False
