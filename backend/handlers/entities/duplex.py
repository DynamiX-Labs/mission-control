import logging

from common.constants import SocketEvents

logger = logging.getLogger("duplex-handler")


def register_duplex_handlers(sio, app):
    """Register Socket.IO handlers for duplex commands."""

    @sio.on("duplex-calibrate")
    async def handle_duplex_calibrate(sid, data):
        logger.info(f"Client {sid} requested duplex calibration: {data}")

    @sio.on("duplex-sic-control")
    async def handle_duplex_sic_control(sid, data):
        logger.info(f"Client {sid} requested SIC control: {data}")
