from urllib.request import Request

from server.proxy_server import ProxyServer
from unittest.mock import Mock

def test_proxy_returns_400_for_invalid_request_line():
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000"
    )

    client_socket = Mock()
    client_socket.recv.return_value = b"INVALID REQUEST\r\n\r\n"
    proxy.handle_client(client_socket)

    print("sendall called:", client_socket.sendall.called)
    print("sendall call:", client_socket.sendall.call_args)
    send_response = client_socket.sendall.call_args[0][0]
    assert b"400 Bad Request" in send_response

def test_proxy_forwards_valid_request():
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000"
    )

    client_socket = Mock()

    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    origin_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: 5\r\n"
        b"\r\n"
        b"Hello"
    )

    proxy.forward_request = Mock(
        return_value=origin_response
    )

    client_socket.recv.return_value = request

    proxy.handle_client(client_socket)

    proxy.forward_request.assert_called_once_with(request)

def test_proxy_returns_origin_response():
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000"
    )

    client_socket = Mock()

    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    origin_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: 5\r\n"
        b"\r\n"
        b"Hello"
    )

    proxy.forward_request = Mock(
        return_value=origin_response
    )

    client_socket.recv.return_value = request

    proxy.handle_client(client_socket)

    client_socket.sendall.assert_called_with(origin_response)

def test_get_cache_hit_does_not_contacts_origin():
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000"
    )

    client_socket = Mock()

    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    cache_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: 5\r\n"
        b"\r\n"
        b"Hello"
    )

    proxy.cache.set("GET:/products", cache_response)

    proxy.forward_request = Mock()

    client_socket.recv.return_value = request

    proxy.handle_client(client_socket)

    proxy.forward_request.assert_not_called()
    client_socket.sendall.assert_called_once_with(cache_response)


def test_post_request_is_not_cached():
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000"
    )

    client_socket = Mock()

    request = (
        b"POST /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: 5\r\n"
        b"\r\n"
        b"Hello"
    )

    origin_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: 5\r\n"
        b"\r\n"
        b"Saved"
    )

    proxy.forward_request = Mock(
        return_value=origin_response
    )

    client_socket.recv.return_value = request

    proxy.handle_client(client_socket)

    proxy.forward_request.assert_called_once_with(request)

    assert proxy.cache.get("/products") is None

def test_get_requests_with_different_query_strings_use_different_cache_entries():
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000"
    )

    first_request = (
        b"GET /products?page=1 HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    second_request = (
        b"GET /products?page=2 HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    first_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: 6\r\n"
        b"\r\n"
        b"Page 1"
    )

    second_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: 6\r\n"
        b"\r\n"
        b"Page 2"
    )

    proxy.forward_request = Mock(
        side_effect=[first_response, second_response]
    )

    first_socket = Mock()
    first_socket.recv.return_value = first_response

    second_socket = Mock()
    second_socket.recv.return_value = second_response

    proxy.handle_client(first_socket)
    proxy.handle_client(second_socket)

    assert proxy.forward_request.call_count == 2