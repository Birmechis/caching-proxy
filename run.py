import socket

from server.my_server import parse_http_request, http_response
from server.proxy_server import forward_request

HOST = '127.0.0.1'
PORT = 8000

ORIGIN = "http://127.0.0.1:9000"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server.bind((HOST, PORT))
server.listen(5)

print(f"Server listening on {HOST}:{PORT}")
print(f"Origin server: {ORIGIN}")

while True:
    client_socket, client_address = server.accept()

    print(f"\nConnection from {client_address}")

    request = client_socket.recv(4096)

    parsed_request = parse_http_request(request)

    print(
        f"{parsed_request['method']} "
        f"{parsed_request['path']} "
    )

    response = forward_request(
        request,
        ORIGIN
    )

    client_socket.sendall(response)

    client_socket.close()