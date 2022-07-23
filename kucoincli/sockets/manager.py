import json
import asyncio
import time
import logging

logging.getLogger(__name__)


async def consumer(self, socket):
    """Consume server websocket messages and handle keep alive pings"""
    keep_waiting = True
    while keep_waiting:
        last_ping = time.time()
        if time.time() - last_ping > self.timeout:
            await self._send_ping(socket)
        try:
            evt = await asyncio.wait_for(socket.recv(), timeout=self.timeout)
        except asyncio.TimeoutError:
            logging.debug(f"No message in {self.timeout} seconds")
            await self._send_ping(socket)
        except asyncio.CancelledError:
            logging.debug("Cancelled error thrown")
            await self._send_ping(socket)
        else:
            # Handle any data manipulations that need to occur
            resp = json.loads(evt)
            return resp


async def _send_ping(socket):
    """Sends a ping message to socket connection"""
    msg = {"id": str(int(time.time() * 1000)), "type": "ping"}
    await socket.send(json.dumps(msg))
