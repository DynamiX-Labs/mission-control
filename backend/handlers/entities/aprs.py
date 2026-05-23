import logging

from common.constants import SocketEvents

logger = logging.getLogger("aprs-handler")


def register_aprs_handlers(sio, app):
    """Register Socket.IO handlers for APRS commands."""

    @sio.on("aprs-igate-connect")
    async def handle_aprs_igate_connect(sid, data):
        logger.info(f"Client {sid} requested APRS iGate connect: {data}")

    @sio.on("aprs-igate-disconnect")
    async def handle_aprs_igate_disconnect(sid, data):
        logger.info(f"Client {sid} requested APRS iGate disconnect: {data}")
