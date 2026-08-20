from server.proxy_server import ProxyServer

HOST = "127.0.0.1"
PORT = int(input("--port: "))

ORIGIN = input("--url: ")


proxy = ProxyServer(
    host=HOST,
    port=PORT,
    origin=ORIGIN,
)

proxy.start()