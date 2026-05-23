import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from common.constants import SocketEvents

logger = logging.getLogger("tx-scheduler")


class TXScheduler(threading.Thread):
    """
    Schedules and manages TX sessions based on satellite passes (AOS/LOS).
    Coordinates with Doppler Predictor and TX Power Controller.
    """

    def __init__(self, socket_manager):
        super().__init__(daemon=True, name="TXScheduler")
        self.socket_manager = socket_manager
        self.running = True
        
        # Scheduled passes
        self.scheduled_passes: List[Dict] = []
        self.schedule_lock = threading.Lock()
        
        # State
        self.active_tx_session = None
        
        # Configuration
        self.pre_aos_arm_seconds = 2.0
        self.post_los_stop_seconds = 1.0
        self.max_tx_duration_seconds = 15 * 60  # 15 minutes max
        
        # Emergency stop flag
        self.emergency_stop_active = False

    def schedule_pass(self, norad_id: int, aos_iso: str, los_iso: str, profile: Dict):
        """
        Schedule a TX session for an upcoming pass.
        """
        try:
            # Parse times
            from dateutil import parser
            aos_dt = parser.parse(aos_iso)
            los_dt = parser.parse(los_iso)
        except ImportError:
            from datetime import datetime
            aos_dt = datetime.fromisoformat(aos_iso.replace('Z', '+00:00'))
            los_dt = datetime.fromisoformat(los_iso.replace('Z', '+00:00'))

        pass_info = {
            "session_id": f"tx_{norad_id}_{int(aos_dt.timestamp())}",
            "norad_id": norad_id,
            "aos_time": aos_dt.timestamp(),
            "los_time": los_dt.timestamp(),
            "profile": profile,
            "state": "scheduled" # scheduled, armed, active, completed, cancelled
        }
        
        with self.schedule_lock:
            self.scheduled_passes.append(pass_info)
            # Sort by AOS
            self.scheduled_passes.sort(key=lambda x: x["aos_time"])
            
        logger.info(f"Scheduled TX pass for NORAD {norad_id} at {aos_iso}")
        self._broadcast_state()
        return pass_info["session_id"]

    def emergency_stop(self):
        """Immediately abort any active TX session and prevent new ones."""
        self.emergency_stop_active = True
        if self.active_tx_session:
            logger.warning(f"EMERGENCY STOP: Aborting active TX session {self.active_tx_session['session_id']}")
            self._stop_tx(self.active_tx_session)
        self._broadcast_state()

    def clear_emergency_stop(self):
        """Clear emergency stop flag."""
        self.emergency_stop_active = False
        self._broadcast_state()

    def _arm_tx(self, pass_info: Dict):
        pass_info["state"] = "armed"
        logger.info(f"Armed TX session {pass_info['session_id']}")
        # TODO: Command SDR hardware/worker to prepare TX chain (load Doppler curve, setup PA)
        self._broadcast_state()

    def _start_tx(self, pass_info: Dict):
        pass_info["state"] = "active"
        pass_info["actual_start"] = time.time()
        self.active_tx_session = pass_info
        logger.info(f"Started TX session {pass_info['session_id']}")
        # TODO: Command SDR hardware/worker to enable PTT
        self._broadcast_state()

    def _stop_tx(self, pass_info: Dict):
        pass_info["state"] = "completed"
        pass_info["actual_stop"] = time.time()
        self.active_tx_session = None
        logger.info(f"Stopped TX session {pass_info['session_id']}")
        # TODO: Command SDR hardware/worker to disable PTT
        self._broadcast_state()

    def run(self):
        logger.info("TX Scheduler started")
        
        while self.running:
            now = time.time()
            
            with self.schedule_lock:
                if self.emergency_stop_active:
                    time.sleep(1.0)
                    continue
                    
                # Handle active session timeouts (safety feature)
                if self.active_tx_session:
                    active_duration = now - self.active_tx_session.get("actual_start", now)
                    if active_duration > self.max_tx_duration_seconds:
                        logger.error(f"TX Safety Timeout: Session {self.active_tx_session['session_id']} exceeded {self.max_tx_duration_seconds}s limit.")
                        self._stop_tx(self.active_tx_session)
                    
                    # Normal LOS + margin
                    elif now >= self.active_tx_session["los_time"] + self.post_los_stop_seconds:
                        self._stop_tx(self.active_tx_session)

                # Process upcoming passes
                for p in self.scheduled_passes:
                    if p["state"] == "scheduled":
                        if now >= p["aos_time"] - self.pre_aos_arm_seconds:
                            self._arm_tx(p)
                    elif p["state"] == "armed":
                        if now >= p["aos_time"]:
                            # Don't start if another session is already active
                            if self.active_tx_session is None:
                                self._start_tx(p)
                            else:
                                logger.warning(f"Cannot start TX session {p['session_id']}, another session is active.")
                                p["state"] = "cancelled"

                # Cleanup old passes
                self.scheduled_passes = [p for p in self.scheduled_passes if p["state"] not in ("completed", "cancelled") or (now - p.get("actual_stop", p["los_time"]) < 3600)]

            time.sleep(0.5)

    def _broadcast_state(self):
        """Broadcast state to UI via Socket.IO"""
        if hasattr(self, "socket_manager") and self.socket_manager:
            state_msg = {
                "active_session": self.active_tx_session,
                "scheduled_passes": self.scheduled_passes,
                "emergency_stop": self.emergency_stop_active
            }
            # Assuming constants.py was updated with TX_SCHEDULE
            self.socket_manager.emit("tx-schedule", state_msg)

    def stop(self):
        self.running = False
        if self.active_tx_session:
            self._stop_tx(self.active_tx_session)
