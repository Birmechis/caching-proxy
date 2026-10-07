import socket
import hashlib

HOST = '127.0.0.1'
PORT = 9000

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(5)
print(f"Origin server listening on {HOST}:{PORT}")

while True:
    client_socket, client_address = server.accept()

    print(f"Client {client_address} connected")

    request = client_socket.recv(4096)

    print("\n[ORIGIN] Received request:")
    print(request.decode("utf-8"))

    body = "Hello from the origin server!"

    body_bytes = body.encode("utf-8")

    etag = hashlib.sha256(
        body_bytes
    ).hexdigest()

    response_headers = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/plain\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        f"ETag: {etag}\r\n"
        "Cache-Control: max-age=60\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    response = response_headers.encode("utf-8") + body_bytes

    print("\n[ORIGIN] Sending response:")
    print(response.decode("utf-8"))

    client_socket.sendall(response)

    client_socket.close()

    print("[ORIGIN] Connection closed")