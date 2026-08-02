#!/usr/bin/env python3
"""Check the PIPER reverse SSH endpoint and release a stale sshd listener."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import time
from pathlib import Path


TCP_LISTEN = "0A"


def has_ssh_banner(host: str, port: int, timeout_s: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s) as connection:
            connection.settimeout(timeout_s)
            return connection.recv(255).startswith(b"SSH-")
    except (OSError, TimeoutError):
        return False


def listener_inodes(port: int) -> set[str]:
    port_hex = f"{port:04X}"
    inodes: set[str] = set()
    for table_path in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        try:
            lines = table_path.read_text(encoding="ascii").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            local_address, state, inode = fields[1], fields[3], fields[9]
            if local_address.rsplit(":", 1)[1] == port_hex and state == TCP_LISTEN:
                inodes.add(inode)
    return inodes


def owners(inodes: set[str]) -> list[int]:
    socket_links = {f"socket:[{inode}]" for inode in inodes}
    result: list[int] = []
    for process_path in Path("/proc").iterdir():
        if not process_path.name.isdigit():
            continue
        try:
            links = {os.readlink(fd) for fd in (process_path / "fd").iterdir()}
            command = (process_path / "comm").read_text(encoding="ascii").strip()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if links.intersection(socket_links) and command == "sshd":
            result.append(int(process_path.name))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=22022)
    parser.add_argument("--probe-timeout", type=float, default=3.0)
    parser.add_argument("--reconnect-timeout", type=float, default=30.0)
    args = parser.parse_args()

    if has_ssh_banner(args.host, args.port, args.probe_timeout):
        print(f"Tunnel healthy: {args.host}:{args.port}")
        return 0

    stale_owners = owners(listener_inodes(args.port))
    if stale_owners:
        for pid in stale_owners:
            os.kill(pid, signal.SIGTERM)
        print(f"Released stale reverse-tunnel sshd session(s): {stale_owners}")
    else:
        print("No healthy banner and no stale listener owner; waiting for reconnect.")

    deadline = time.monotonic() + args.reconnect_timeout
    while time.monotonic() < deadline:
        if has_ssh_banner(args.host, args.port, args.probe_timeout):
            print(f"Tunnel recovered: {args.host}:{args.port}")
            return 0
        time.sleep(1.0)

    print("Tunnel did not recover; restart the Windows 'PIPER Remote Tunnel' task.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
