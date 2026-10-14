import hashlib
import socket
import threading
from urllib.parse import urlparse
from server.cache import Cache
from server.my_server import parse_http_request, parse_http_response


def extract_etag(data):

    return f'"{hashlib.sha256(data).hexdigest()}"'

class ProxyServer:

    def __init__(self, host, port, origin, cache_db_path="cache.db"):
        self.host = host
        self.port = port
        self.origin = origin

        self.cache = Cache(db_path=cache_db_path)

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
            thread = threading.Thread(
                target=self.handle_client,
                args=(client_socket,)
            )
            thread.start()

    def error_response(self, status_code, status_text, body):
        body_bytes = body.encode('utf-8')

        return (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            f"Content-Type: text/plain\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode('utf-8') + body_bytes

    def receive_request(self, client_socket):

        request_buffer = b""
        HEADER_DELIMITER = b"\r\n\r\n"

        while HEADER_DELIMITER not in request_buffer:
            chunk = client_socket.recv(4096)

            if not chunk:
                return request_buffer

            request_buffer += chunk

        header_part, body_part = request_buffer.split(HEADER_DELIMITER, 1)

        content_length = 0
        header_lines = header_part.decode('utf-8', errors='ignore').split('\r\n')

        for line in header_lines:
            if line.lower().startswith("content-length"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                except ValueError:
                    content_length = 0
                break

        bytes_needed = content_length - len(body_part)

        while bytes_needed > 0:

            chunk = client_socket.recv(min(4096, bytes_needed))
            if not chunk:
                break
            body_part += chunk
            bytes_needed -= len(chunk)

        return header_part + HEADER_DELIMITER + body_part

    def add_if_none_match(self, request, etag):
        header_part, separator, body = request.partition(b"\r\n\r\n")

        if not separator:
            return request

        lines = header_part.split(b"\r\n")

        # Remove any existing If-None-Match header.
        lines = [
            line
            for line in lines
            if not line.lower().startswith(b"if-none-match:")
        ]

        lines.append(
            b"If-None-Match: " + etag.encode("latin-1")
        )

        return b"\r\n".join(lines) + b"\r\n\r\n" + body

    def handle_client(self, client_socket):
        try:
            request = client_socket.recv(4096)

            if not request:
                return

            try:
                parsed_request = parse_http_request(request)
            except (ValueError, UnicodeDecodeError):
                response = (
                    b"HTTP/1.1 400 Bad Request\r\n"
                    b"Content-Length: 11\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                    b"Bad Request"
                )
                client_socket.sendall(response)
                return

            method = parsed_request["method"]
            path = parsed_request["path"]
            cache_key = f"{method}:{path}"

            print(f"{method} {path}")

            # Only GET requests use this cache.
            if method != "GET":
                response = self.forward_request(request)
                client_socket.sendall(response)
                return

            entry = self.cache.get_entry(cache_key)

            # Fresh cache entry: no origin request is necessary.
            if entry is not None and not entry["stale"]:
                print(f"[CACHE] HIT: {cache_key}")
                client_socket.sendall(entry["response"])
                return

            # Stale entry with an ETag: ask the origin if it changed.
            if entry is not None and entry["etag"]:
                print(f"[CACHE] REVALIDATING: {cache_key}")

                conditional_request = self.add_if_none_match(
                    request,
                    entry["etag"],
                )

                response = self.forward_request(conditional_request)

                try:
                    parsed_response = parse_http_response(response)
                except ValueError:
                    client_socket.sendall(response)
                    return

                status_code = parsed_response["status_code"]
                headers = parsed_response["headers"]

                if status_code == 304:
                    print(f"[CACHE] REVALIDATED: {cache_key}")

                    self.cache.refresh(cache_key, headers)

                    # Send the original cached 200 response, not the 304.
                    client_socket.sendall(entry["response"])
                    return

                if status_code == 200:
                    print(f"[CACHE] UPDATED: {cache_key}")

                    self.cache.set(
                        cache_key,
                        response,
                        headers,
                        status_code,
                    )

                client_socket.sendall(response)
                return

            # Cache miss: retrieve the resource from the origin.
            print(f"[CACHE] MISS: {cache_key}")

            try:
                response = self.forward_request(request)

            except socket.timeout:
                response = self.error_response(
                    504,
                    "Gateway Timeout",
                    "Gateway Timeout",
                )
            except OSError:
                response = self.error_response(
                    502,
                    "Bad Gateway",
                    "Bad Gateway"
                )

            try:
                parsed_response = parse_http_response(response)
            except ValueError:
                # Forward the response, but do not cache an unparseable response.
                client_socket.sendall(response)
                return

            self.cache.set(
                cache_key,
                response,
                parsed_response["headers"],
                parsed_response["status_code"],
            )

            client_socket.sendall(response)

        finally:
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