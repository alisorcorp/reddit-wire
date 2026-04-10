#!/usr/bin/env python3
"""Minimal HTTP file server with Range request support.

Python's stdlib http.server returns whole files on every request, which
breaks Apple Podcasts scrubbing and partial-download recovery. This wraps
SimpleHTTPRequestHandler with the minimum HTTP/1.1 Range support (RFC 7233)
that Podcasts needs: single open-ended ranges ("bytes=N-"), closed ranges
("bytes=N-M"), and suffix ranges ("bytes=-N"), with 206 Partial Content
responses and Accept-Ranges advertised on every file response.

Usage:
  python3 serve.py [port] [bind_addr]
  python3 serve.py 8080 127.0.0.1   # default
"""
import os
import re
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler + single-range HTTP Range support."""

    def send_head(self):
        range_header = self.headers.get("Range")
        if not range_header:
            return super().send_head()

        path = self.translate_path(self.path)
        # Let the parent handle directories, missing files, etc.
        if not os.path.isfile(path):
            return super().send_head()

        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        try:
            fs = os.fstat(f.fileno())
            file_len = fs.st_size

            m = RANGE_RE.match(range_header.strip())
            if not m:
                self.send_error(400, "Malformed Range header")
                return None

            start_str, end_str = m.groups()
            if start_str == "" and end_str == "":
                self.send_error(400, "Malformed Range header")
                return None

            if start_str == "":
                # Suffix: last N bytes
                suffix_len = int(end_str)
                if suffix_len == 0:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    return None
                start = max(0, file_len - suffix_len)
                end = file_len - 1
            else:
                start = int(start_str)
                end = int(end_str) if end_str else file_len - 1

            if start >= file_len or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_len}")
                self.end_headers()
                return None

            end = min(end, file_len - 1)
            length = end - start + 1

            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_len}")
            self.send_header("Content-Length", str(length))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()

            f.seek(start)
            remaining = length
            chunk_size = 64 * 1024
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
            return None  # signal do_GET that we've already written the body
        finally:
            f.close()

    def end_headers(self):
        # Advertise range support on every response so clients know to ask.
        # Harmless on directory listings and 404s; required on file GETs.
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    bind = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    server = HTTPServer((bind, port), RangeHTTPRequestHandler)
    print(f"Serving {os.getcwd()} on http://{bind}:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
