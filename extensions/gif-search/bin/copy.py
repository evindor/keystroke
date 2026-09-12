#!/usr/bin/env python3
"""Copy GIF bytes or a URL to the Wayland clipboard without creating files."""
import subprocess
import sys
import urllib.parse
import urllib.request

MAX_BYTES = 25 * 1024 * 1024


def checked_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or not (host == "giphy.com" or host.endswith(".giphy.com"))
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Invalid GIPHY media URL")
    return url


class MediaRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, checked_url(newurl))


def payload(mode, url):
    checked_url(url)
    if mode == "link":
        return "text/plain;charset=utf-8", url.encode()
    if mode != "gif":
        raise ValueError("Unknown copy action")
    with urllib.request.build_opener(MediaRedirect).open(url, timeout=20) as response:
        if int(response.headers.get("Content-Length", 0)) > MAX_BYTES:
            raise ValueError("GIF exceeds the 25 MB copy limit; copy its link instead")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("GIF exceeds the 25 MB copy limit; copy its link instead")
    if not data.startswith((b"GIF87a", b"GIF89a")):
        raise ValueError("The download is not a GIF")
    return "image/gif", data


def main():
    try:
        mime, data = payload(*sys.argv[1:])
        subprocess.run(["wl-copy", "--type", mime], input=data, check=True, timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0
    except Exception as error:
        print("Copy failed: " + str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
