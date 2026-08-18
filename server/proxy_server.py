import socket
from urllib.parse import urlparse


def forward_request(request, origin):
    parsed_origin = urlparse(origin)

    origin_host = parsed_origin.hostname
    origin_port = parsed_origin.port

    request_text = request.decode('utf-8')

    header_part, _, body = request_text.partition('\r\n\r\n')

    lines = header_part.split('\r\n')

    method, path, version = lines[0].split(' ', 2)

    origin_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    origin_socket.connect(
        (origin_host, origin_port)
    )

    origin_request = (
        f"{method} {path} {version}\r\n"
        f"Host: {origin_host}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )

    origin_socket.sendall(
        origin_request.encode('utf-8')
    )

    response = b""

    while True:
        data = origin_socket.recv(4096)

        if not data:
            break

        response += data

    origin_socket.close()
    return response


