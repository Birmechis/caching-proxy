import socket
from urllib.parse import urlparse

from server.cache import Cache
from server.my_server import parse_http_request


class ProxyServer:

    def __init__(self, host, port, origin):
        self.host = host
        self.port = port
        self.origin = origin

        self.cache = Cache()

    def start(self):

        server = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        server.bind(
            (self.host, self.port)
        )

        server.listen(5)

        print(
            f"Proxy server listening on "
            f"{self.host}:{self.port}"
        )

        print(
            f"Origin server: {self.origin}"
        )

        while True:

            client_socket, client_address = server.accept()

            print(
                f"\nConnection from "
                f"{client_address}"
            )

            self.handle_client(client_socket)

    def handle_client(self, client_socket):

        request = client_socket.recv(4096)

        if not request:
            client_socket.close()
            return

        parsed_request = parse_http_request(request)

        method = parsed_request["method"]
        path = parsed_request["path"]

        print(f"{method} {path}")

        if method == "GET":
            cache_response = self.cache.get(path)

            if cache_response is not None:
                print(f"[CACHE] HIT: {path}")

                client_socket.sendall(cache_response)
                client_socket.close()

                return

            print(f"[CACHE] MISS: {path}")

        response = self.forward_request(request)

        if method == "GET":
            print(f"[CACHE] storing: {path}")

            self.cache.set(path, response)

        client_socket.sendall(response)

        client_socket.close()

    def forward_request(self, request):

        print("[PROXY] Forwarding request to origin")

        parsed_origin = urlparse(self.origin)

        origin_host = parsed_origin.hostname
        origin_port = parsed_origin.port

        print(
            f"[PROXY] connecting to "
            f"{origin_host}:{origin_port}"
        )

        origin_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        origin_socket.settimeout(5)
        origin_socket.connect((origin_host, origin_port))
        print("[PROXY] Connected to origin")

        origin_socket.sendall(request)

        print("[PROXY] request sent to origin")

        origin_socket.shutdown(socket.SHUT_WR)

        print("[PROXY] request sending side closed")


        response = b""

        while True:

            print(f"[PROXY] waiting data from origin")
            data = origin_socket.recv(4096)

            if not data:
                print("[PROXY] origin closed  connection")
                break

            print(f"[PROXY] received {len(data)} bytes from origin")

            response += data

        origin_socket.close()

        print(
            f"[PROXY] received "
            f"{len(response)} bytes from origin"
        )

        return response