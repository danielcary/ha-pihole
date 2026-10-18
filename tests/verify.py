#!/usr/bin/env python3
"""Exercise the app with official Supervisor and Pi-hole images. No dependencies."""

import argparse
import json
import platform
from pathlib import Path
import re
import secrets
import socket
import struct
import subprocess
import time
import urllib.error
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "pihole/config.json").read_text())
SUPERVISOR_VERSION = "2026.10.2"
NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def docker(*args, check=True):
    result = subprocess.run(
        ["docker", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if check and result.returncode:
        raise RuntimeError("Docker operation failed: " + result.stderr.strip())
    return result.stdout.strip()


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def eventually(operation, timeout=60):
    """Allow Pi-hole's asynchronous restart after a native API config change."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return operation()
        except (OSError, urllib.error.URLError, AssertionError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def validate_with_supervisor():
    machine = platform.machine().lower()
    arch = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "amd64", "amd64": "amd64"}[machine]
    image = f"ghcr.io/home-assistant/{arch}-hassio-supervisor:{SUPERVISOR_VERSION}"
    print(f"Validating with official Supervisor {SUPERVISOR_VERSION} ({arch})...", flush=True)
    # Use the actual released Supervisor schema; catch unknown keys it discards.
    program = """
import copy
import json
from supervisor.apps.validate import SCHEMA_APP_CONFIG
from supervisor.apps.const import MappingType
from supervisor.store.validate import SCHEMA_REPOSITORY_CONFIG
raw = json.load(open('/package/pihole/config.json'))
config = SCHEMA_APP_CONFIG(copy.deepcopy(raw))
assert not (set(raw) - set(config)), 'Supervisor discarded unrecognized keys'
assert config['map'][0]['type'] == MappingType.DATA
assert config['map'][0]['path'] == '/etc/pihole'
SCHEMA_REPOSITORY_CONFIG(json.load(open('/package/repository.json')))
print('PASS: released Supervisor accepts the app and its persistent data mapping')
"""
    print(docker(
        "run", "--rm", "--network", "none", "--entrypoint", "python3",
        "--mount", f"type=bind,source={ROOT},target=/package,readonly", image,
        "-c", program,
    ), flush=True)


def read_exact(stream, length):
    data = bytearray()
    while len(data) < length:
        chunk = stream.recv(length - len(data))
        if not chunk:
            raise RuntimeError("DNS TCP connection closed early")
        data.extend(chunk)
    return bytes(data)


def dns_query(port, name, tcp=False):
    """Query published host ports, rather than just the container's loopback."""
    ident = secrets.randbelow(65536)
    labels = b"".join(bytes([len(s)]) + s.encode("ascii") for s in name.split(".")) + b"\0"
    query = struct.pack("!6H", ident, 0x0100, 1, 0, 0, 0) + labels + struct.pack("!2H", 1, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM) as client:
        client.settimeout(5)
        client.connect(("127.0.0.1", port))
        if tcp:
            client.sendall(struct.pack("!H", len(query)) + query)
            response = read_exact(client, struct.unpack("!H", read_exact(client, 2))[0])
        else:
            client.send(query)
            response = client.recv(65535)
    response_id, flags, questions, answers, _, _ = struct.unpack("!6H", response[:12])
    check(response_id == ident and flags & 0x8000, "Invalid DNS response")
    check(flags & 0x000F == 0, f"DNS returned error code {flags & 0x000F}")

    def skip_name(offset):
        while response[offset]:
            if response[offset] & 0xC0 == 0xC0:
                return offset + 2
            offset += response[offset] + 1
        return offset + 1

    offset = 12
    for _ in range(questions):
        offset = skip_name(offset) + 4
    addresses = []
    for _ in range(answers):
        offset = skip_name(offset)
        kind, cls, _, length = struct.unpack("!HHIH", response[offset:offset + 10])
        offset += 10
        if kind == 1 and cls == 1 and length == 4:
            addresses.append(socket.inet_ntoa(response[offset:offset + 4]))
        offset += length
    return addresses


class PiHole:
    def __init__(self, version=None):
        self.version = version or CONFIG["version"]
        self.name = "ha-pihole-test-" + uuid.uuid4().hex[:10]
        self.volume = self.name + "-data"
        self.password = None
        self.sid = None
        self.base = None
        self.ports = None

    def start(self):
        args = [
            "run", "--detach", "--name", self.name,
            # Approximate Supervisor's reduced capabilities; DNS needs neither
            # NET_ADMIN nor NET_RAW. The container's normal defaults otherwise apply.
            "--mount", f"type=volume,source={self.volume},target=/etc/pihole",
            "--tmpfs", "/dev/shm", "--env", "TZ=Etc/UTC",
            "--health-interval", "2s", "--health-timeout", "5s",
            "--health-start-period", "5s",
        ]
        if CONFIG.get("init", True):
            args.append("--init")
        requested_caps = CONFIG.get("privileged", [])
        for cap in ("NET_RAW", "MKNOD", "AUDIT_WRITE", "SETFCAP"):
            if cap not in requested_caps:
                args.extend(["--cap-drop", cap])
        for cap in requested_caps:
            args.extend(["--cap-add", cap])
        for key, value in CONFIG["environment"].items():
            args.extend(["--env", f"{key}={value}"])
        for port in CONFIG["ports"]:
            args.extend(["--publish", f"127.0.0.1::{port}"])
        args.append(f"{CONFIG['image']}:{self.version}")
        docker(*args)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            state = json.loads(docker("inspect", "--format", "{{json .State}}", self.name))
            check(state["Running"], "Pi-hole exited during startup")
            if state.get("Health", {}).get("Status") == "healthy":
                break
            time.sleep(1)
        else:
            raise TimeoutError("Pi-hole did not become healthy within 180 seconds")
        published = json.loads(docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", self.name))
        self.ports = {key: int(value[0]["HostPort"]) for key, value in published.items() if value}
        self.base = f"http://127.0.0.1:{self.ports['80/tcp']}"
        # Health becomes ready before the entrypoint finishes its startup tasks.
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with NO_PROXY.open(self.base + "/admin/", timeout=3) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(1)
        raise TimeoutError("Pi-hole admin page did not become ready")

    def api(self, path, method="GET", body=None, authenticated=True):
        headers = {"Content-Type": "application/json"}
        if authenticated and self.sid:
            headers["X-FTL-SID"] = self.sid
        request = urllib.request.Request(
            self.base + "/api" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers, method=method,
        )
        with NO_PROXY.open(request, timeout=15) as response:
            return json.load(response)

    def login(self):
        reply = self.api("/auth", "POST", {"password": self.password}, authenticated=False)
        check(reply["session"]["valid"], "Pi-hole refused the admin password")
        self.sid = reply["session"]["sid"]

    def recreate(self, version=None):
        docker("stop", "--time", str(CONFIG["timeout"]), self.name)
        state = json.loads(docker("inspect", "--format", "{{json .State}}", self.name))
        check(state["ExitCode"] == 0, "Pi-hole did not stop cleanly")
        docker("rm", self.name)
        self.sid = None
        if version is not None:
            self.version = version
        self.start()

    def cleanup(self):
        docker("rm", "--force", self.name, check=False)
        docker("volume", "rm", self.volume, check=False)


def smoke_test(initial_version=None):
    app = PiHole(initial_version)
    try:
        print(f"Starting official {CONFIG['image']}:{app.version}...", flush=True)
        app.start()
        print("PASS: DNS health check and admin page are ready", flush=True)
        # First boot must generate a password rather than expose an open admin UI.
        logs = docker("logs", app.name)
        match = re.search(r"random password:\s*(\S+)", logs, re.IGNORECASE)
        check(match is not None, "First start did not report a generated password")
        app.password = match[1]
        app.login()
        print("PASS: generated admin password authenticates", flush=True)

        configuration = app.api("/config")["config"]
        check(configuration["dns"]["listeningMode"] == "ALL", "Bridge DNS mode was not applied")
        check(configuration["dhcp"]["active"] is False, "DHCP unexpectedly enabled")
        check(configuration["ntp"]["ipv4"]["active"] is False, "IPv4 NTP unexpectedly enabled")
        check(configuration["ntp"]["ipv6"]["active"] is False, "IPv6 NTP unexpectedly enabled")
        check(configuration["ntp"]["sync"]["active"] is False, "NTP clock sync unexpectedly enabled")

        # Use the native API for user configuration, including the password;
        # no FTLCONF password or upstream variable masks persistence problems.
        replacement = secrets.token_urlsafe(24)
        app.api("/config", "PATCH", {"config": {
            "dns": {"upstreams": ["1.1.1.1", "1.0.0.1"],
                    "hosts": ["192.0.2.42 persisted.home.arpa"]},
            "webserver": {"api": {"password": replacement}},
        }})
        app.password = replacement
        app.sid = None
        eventually(app.login)

        def verify_dns():
            for tcp in (False, True):
                port = app.ports["53/tcp" if tcp else "53/udp"]
                check(dns_query(port, "persisted.home.arpa", tcp) == ["192.0.2.42"], "Local DNS record failed")
                result = dns_query(port, "example.com", tcp)
                check(result and "0.0.0.0" not in result, "Upstream DNS resolution failed")

        eventually(verify_dns)
        print("PASS: published UDP/TCP DNS resolves local records and Internet names", flush=True)

        app.api("/domains/deny/exact", "POST", {"domain": "blocked.example.com"})
        eventually(lambda: check(dns_query(app.ports["53/udp"], "blocked.example.com") == ["0.0.0.0"], "Denylist blocking failed"))
        print("PASS: a domain added through Pi-hole's API is blocked", flush=True)

        if initial_version:
            print(f"Upgrading saved data from {initial_version} to {CONFIG['version']}...", flush=True)
        app.recreate(version=CONFIG["version"])
        eventually(app.login)
        eventually(verify_dns)
        check(dns_query(app.ports["53/tcp"], "blocked.example.com", True) == ["0.0.0.0"], "Denylist entry was lost")
        configuration = app.api("/config")["config"]
        check(configuration["dns"]["upstreams"] == ["1.1.1.1", "1.0.0.1"], "Upstream settings were lost")
        operation = "upgrade" if initial_version else "clean stop/recreation"
        print(f"PASS: {operation} preserves password, DNS settings, and denylist", flush=True)
    except Exception:
        logs = docker("logs", "--tail", "60", app.name, check=False)
        logs = re.sub(r"(random password:)\s*\S+", r"\1 <redacted>", logs, flags=re.IGNORECASE)
        if app.password:
            logs = logs.replace(app.password, "<redacted>")
        print("Pi-hole diagnostics (password redacted):\n" + logs, flush=True)
        raise
    finally:
        app.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upgrade-from", metavar="TAG",
        help="also create data on an older official Pi-hole image and upgrade it to the app version",
    )
    args = parser.parse_args()
    validate_with_supervisor()
    smoke_test()
    if args.upgrade_from:
        smoke_test(initial_version=args.upgrade_from)
    print("All checks passed; temporary containers and volume removed.", flush=True)
