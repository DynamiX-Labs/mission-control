import logging

from common.constants import SocketEvents

logger = logging.getLogger("tx-handler")


def register_tx_handlers(sio, app):
    """Register Socket.IO handlers for TX pipeline commands."""

    @sio.on("tx-schedule-arm")
    async def handle_tx_schedule_arm(sid, data):
        logger.info(f"Client {sid} armed TX schedule: {data}")
        # Send to backend manager via Queue or method
        # implementation will tie into tx_scheduler

    @sio.on("tx-schedule-disarm")
    async def handle_tx_schedule_disarm(sid, data):
        logger.info(f"Client {sid} disarmed TX schedule: {data}")

    @sio.on("tx-emergency-stop")
    async def handle_tx_emergency_stop(sid, data):
        logger.warning(f"Client {sid} issued TX EMERGENCY STOP")
        # Route to tx_scheduler.emergency_stop()
