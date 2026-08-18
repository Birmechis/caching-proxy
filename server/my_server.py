def parse_http_request(request):
    request = request.decode()

    header_part, _, body = request.partition('\r\n\r\n')

    lines = header_part.split('\r\n')

    request_lines = lines[0]
    method, path, version = request_lines.split(' ')

    headers = {}
    for line in lines[1:]:
        key, value = line.split(':', 1)
        headers[key.strip()] = value.strip()

    return {
        'method': method,
        'path': path,
        'version': version,
        'headers': headers,
        'body': body
    }

def http_response(body, status_code=200, status_text="ok"):
    body = body.encode('utf-8')

    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content_Type: text/plain\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode('utf-8')

    return response + body
