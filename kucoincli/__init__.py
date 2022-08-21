import socket
from urllib3.connection import HTTPConnection
from sys import platform

# Patch for timeout errors: https://github.com/psf/requests/issues/4937
if platform == "darwin":
    HTTPConnection.default_socket_options = (
        HTTPConnection.default_socket_options + [
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
            (socket.SOL_TCP, socket.TCP_KEEPINTVL, 10),
            (socket.SOL_TCP, socket.TCP_KEEPCNT, 6)
        ]
    )
else:
    HTTPConnection.default_socket_options = (
        HTTPConnection.default_socket_options + [
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
            (socket.SOL_TCP, socket.TCP_KEEPINTVL, 10),
            (socket.SOL_TCP, socket.TCP_KEEPIDLE, 45),
            (socket.SOL_TCP, socket.TCP_KEEPCNT, 6)
        ]
    )
