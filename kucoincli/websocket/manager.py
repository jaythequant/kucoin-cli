import json
import websockets
import asyncio
import time
import logging
import random

logging.getLogger(__name__)


async def connection_manager(socket, timeout=5000):
    """
    Error handling and keep alive for socket server

    :param timeout: Timeout parameter for keep-alive messages

    :return: JSON object with subscription details
    """
    keep_waiting = True
    try:
        while keep_waiting:
            last_ping = time.time()
            if time.time() - last_ping > timeout:
                await _send_ping(socket)
            try:
                evt = await asyncio.wait_for(socket.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                logging.debug(f"No message in {timeout} seconds")
                await _send_ping(socket)
            except asyncio.CancelledError:
                logging.debug("Cancelled error thrown")
                await _send_ping(socket)
            else:
                # Handle any data manipulations that need to occur
                resp = json.loads(evt)
                return resp
    except websockets.ConnectionClosed:
        keep_waiting = False
        await connection_manager(socket, timeout)
    except Exception as e:
        keep_waiting = False
        await connection_manager(socket, timeout)


async def _send_ping(socket):
    """Sends a ping message to socket connection"""
    msg = {"id": str(int(time.time() * 1000)), "type": "ping"}
    await socket.send(json.dumps(msg))
