from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

log = logging.getLogger("mc-router")


@dataclass
class Backend:
    host: str
    port: int
    wake: callable | None = None


_backends: dict[str, Backend] = {}
_server: asyncio.AbstractServer | None = None


def register(hostname: str, port: int, wake=None) -> None:
    _backends[hostname.lower()] = Backend("127.0.0.1", port, wake)
    log.info("route %s -> 127.0.0.1:%s", hostname, port)


def unregister(hostname: str) -> None:
    _backends.pop(hostname.lower(), None)


def lookup(hostname: str) -> Backend | None:
    key = hostname.lower().rstrip(".")
    if key in _backends:
        return _backends[key]
    short = key.split(".")[0]
    matches = [backend for name, backend in _backends.items() if name.split(".")[0] == short]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        unique = {id(m): m for m in matches}
        if len(unique) == 1:
            return next(iter(unique.values()))
        return None
    return None


def _read_varint(buf: bytes, idx: int) -> tuple[int, int]:
    num = 0
    shift = 0
    while True:
        if idx >= len(buf):
            raise ValueError("short varint")
        byte = buf[idx]
        idx += 1
        num |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return num, idx
        shift += 7
        if shift > 35:
            raise ValueError("varint too long")


def parse_handshake_host(packet: bytes) -> str | None:
    try:
        _length, idx = _read_varint(packet, 0)
        packet_id, idx = _read_varint(packet, idx)
        if packet_id != 0:
            return None
        _proto, idx = _read_varint(packet, idx)
        slen, idx = _read_varint(packet, idx)
        host = packet[idx : idx + slen].decode("utf-8", errors="replace")
        return host.split("\x00")[0]
    except (ValueError, IndexError):
        return None


async def _read_packet(reader: asyncio.StreamReader) -> bytes:
    length_bytes = bytearray()
    for _ in range(5):
        chunk = await reader.readexactly(1)
        length_bytes.extend(chunk)
        if not (chunk[0] & 0x80):
            break
    length, _ = _read_varint(bytes(length_bytes), 0)
    body = await reader.readexactly(length)
    return bytes(length_bytes) + body


async def _pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except (ConnectionError, asyncio.IncompleteReadError, OSError):
        pass
    finally:
        try:
            dst.close()
        except Exception:
            pass


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    try:
        first = await asyncio.wait_for(_read_packet(reader), timeout=10)
    except Exception:
        writer.close()
        return
    host = parse_handshake_host(first) or ""
    backend = lookup(host)
    if backend is None:
        log.info("no backend for host=%s peer=%s", host, peer)
        writer.close()
        return
    if backend.wake:
        try:
            await backend.wake()
        except Exception:
            log.exception("wake failed for %s", host)
    try:
        br, bw = await asyncio.open_connection(backend.host, backend.port)
    except OSError:
        log.warning("backend down %s:%s", backend.host, backend.port)
        writer.close()
        return
    bw.write(first)
    await bw.drain()
    await asyncio.gather(_pipe(reader, bw), _pipe(br, writer), return_exceptions=True)


async def start(port: int) -> None:
    global _server
    _server = await asyncio.start_server(_handle, "0.0.0.0", port)
    log.info("mc-router listening on 0.0.0.0:%s", port)


async def stop() -> None:
    global _server
    if _server:
        _server.close()
        await _server.wait_closed()
        _server = None
