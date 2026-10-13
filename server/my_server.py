def parse_http_request(request):
    request = request.decode('utf-8')

    header_part, _, body = request.partition('\r\n\r\n')

    lines = header_part.split('\r\n')

    request_lines = lines[0]
    parts = request_lines.split(' ')

    if len(parts) != 3:
        raise ValueError("Invalid HTTP request line")

    method,path,version = parts

    headers = {}
    for line in lines[1:]:

        if not line.strip():
            continue

        if ':' not in line:
            raise ValueError("Invalid HTTP header")

        key, value = line.split(':', 1)

        if not key.strip():
            raise ValueError("Invalid HTTP header")

        headers[key.strip()] = value.strip()

    return {
        'method': method,
        'path': path,
        'version': version,
        'headers': headers,
        'body': body
    }

def parse_http_response(response):
    header_part, separator, body = response.partition(b"\r\n\r\n")

    if not separator:
        raise ValueError("Invalid HTTP response")

    lines = header_part.decode("latin-1").split("\r\n")

    status_line = lines[0].split(" ", 2)

    if len(status_line) < 2:
        raise ValueError("Invalid HTTP status line")

    try:
        status_code = int(status_line[1])
    except ValueError:
        raise ValueError("Invalid HTTP status code")

    headers = {}

    for line in lines[1:]:
        if ":" not in line:
            raise ValueError("Invalid HTTP response header")

        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()

    return {
        "status_code": status_code,
        "headers": headers,
        "body": body
    }

def http_response(body, status_code=200, status_text="ok"):
    body = body.encode('utf-8')

    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: text/plain\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode('utf-8')

    return response + body
