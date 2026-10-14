import socket
import sqlite3
from server.proxy_server import ProxyServer
from unittest.mock import Mock

def test_proxy_returns_400_for_invalid_request_line(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path=tmp_path / "invalid_request_line.db",
    )

    client_socket = Mock()
    client_socket.recv.return_value = b"INVALID REQUEST\r\n\r\n"
    proxy.handle_client(client_socket)

    print("sendall called:", client_socket.sendall.called)
    print("sendall call:", client_socket.sendall.call_args)
    send_response = client_socket.sendall.call_args[0][0]
    assert b"400 Bad Request" in send_response

def test_proxy_forwards_valid_request(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path=tmp_path / "valid_request.db",
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

def test_proxy_returns_origin_response(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path=tmp_path / "origin_response.db",
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

def test_get_cache_hit_does_not_contacts_origin(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path = tmp_path / "proxy_cache_db"
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


def test_post_request_is_not_cached(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path=tmp_path / "post_not_cached.db"
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

def test_get_requests_with_different_query_strings_use_different_cache_entries(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path=tmp_path / "different_cache_entry.db"
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
    first_socket.recv.return_value = first_request

    second_socket = Mock()
    second_socket.recv.return_value = second_request

    proxy.handle_client(first_socket)
    proxy.handle_client(second_socket)

    assert proxy.forward_request.call_count == 2

def test_proxy_returns_502_when_origin_is_unavailable(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path=tmp_path / "proxy_502.db",
    )

    client_socket = Mock()

    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    client_socket.recv.return_value = request

    proxy.forward_request = Mock(
        side_effect=ConnectionRefusedError()
    )

    proxy.handle_client(client_socket)

    response = client_socket.sendall.call_args[0][0]

    assert b"502 Bad Gateway" in response

def test_proxy_returns_504_when_origin_times_out(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path=tmp_path / "proxy_504.db",
    )

    client_socket = Mock()

    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    client_socket.recv.return_value = request

    proxy.forward_request = Mock(
        side_effect=socket.timeout()
    )

    proxy.handle_client(client_socket)

    response = client_socket.sendall.call_args[0][0]

    assert b"504 Gateway Timeout" in response

def test_stale_etag_cache_sends_conditional_request(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path=tmp_path / "stale_etag.db",
    )

    cache_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: test/plain\r\n"
        b'Etag: "hello-v1"\r\n'
        b"Content-Length: 5\r\n"
        b'Connection: close\r\n'
        b"\r\n"
        b"Hello"
    )

    proxy.cache.set(
        "GET:/products",
        cache_response,
        {"Etag": '"hello-v1"'},
        200,
    )

    with sqlite3.connect(proxy.cache.db_path) as conn:
        conn.execute(
            """
            UPDATE http_cache
            SET expires_at = 0
            WHERE cache_key = ?
            """,
            ("GET:/products",),
        )

    client_socket = Mock()

    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    client_socket.recv.return_value = request

    proxy.forward_request = Mock(
        return_value=(
            b"HTTP/1.1 304 Not Modified\r\n"
            b'Etag: "hello-v1"\r\n'
            b"Connection: close\r\n"
            b"\r\n"
        )
    )

    proxy.handle_client(client_socket)

    conditional_request = proxy.forward_request.call_args[0][0]

    assert b'If-None-Match: "hello-v1"' in conditional_request

    client_socket.sendall.assert_called_once_with(cache_response)

def test_etag_revalidation_updates_changed_response(tmp_path):
    proxy = ProxyServer(
        "127.0.0.1",
        8000,
        "http://127.0.0.1:9000",
        cache_db_path=tmp_path / "etag_update.db",
    )

    old_response = (
        b'HTTP/1.1 200 OK\r\n'
        b'ETag: "v1"\r\n'
        b'Content-Length: 3\r\n'
        b'Connection: close\r\n'
        b'\r\n'
        b'Old'
    )

    new_response = (
        b'HTTP/1.1 200 OK\r\n'
        b'ETag: "v2"\r\n'
        b'Content-Length: 3\r\n'
        b'Connection: close\r\n'
        b'\r\n'
        b'New'
    )

    proxy.cache.set(
        "GET:/products",
        old_response,
        {"ETag": '"v1"'},
        200,
    )

    with sqlite3.connect(proxy.cache.db_path) as conn:
        conn.execute(
            """
            UPDATE http_cache
            SET expires_at = 0
            WHERE cache_key = ?
            """,
            ("GET:/products",),
        )

    client_socket = Mock()
    client_socket.recv.return_value = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    proxy.forward_request = Mock(return_value=new_response)

    proxy.handle_client(client_socket)

    client_socket.sendall.assert_called_once_with(new_response)

    with sqlite3.connect(proxy.cache.db_path) as conn:
        row = conn.execute(
            """
            SELECT response, etag
            FROM http_cache
            WHERE cache_key = ?
            """,
            ("GET:/products",),
        ).fetchone()

    assert row is not None
    assert row[0] == new_response
    assert row[1] == '"v2"'