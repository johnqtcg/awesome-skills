"""Public-network-only HTTP(S) transport for deep-research."""

from __future__ import annotations

import http.client
import io
import ipaddress
import socket
import ssl
import urllib.error
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Mapping, Tuple

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
DEFAULT_MAX_REDIRECTS = 5


class UnsafeWebTargetError(ValueError):
    """Raised before any request can reach a non-public target."""


@dataclass(frozen=True)
class ResolvedWebTarget:
    url: str
    scheme: str
    hostname: str
    port: int
    request_target: str
    addresses: Tuple[str, ...]


@dataclass(frozen=True)
class HopResponse:
    status: int
    reason: str
    headers: Dict[str, str]
    body: bytes


@dataclass(frozen=True)
class PublicWebResponse:
    requested_url: str
    final_url: str
    status: int
    headers: Dict[str, str]
    body: bytes
    resolved_ips: Tuple[str, ...]


def _canonical_ip(raw: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    value = str(raw).split("%", 1)[0]
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def _is_public_unicast(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Use an explicit public-unicast policy across Python versions."""
    return bool(
        address.is_global
        and not address.is_multicast
        and not address.is_unspecified
        and not address.is_reserved
    )


def _resolve_addresses(hostname: str, port: int) -> Tuple[str, ...]:
    try:
        literal = _canonical_ip(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        return (str(literal),)

    try:
        rows = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise UnsafeWebTargetError(
            f"unable to resolve Web target {hostname}: {exc}"
        ) from exc
    addresses = tuple(
        dict.fromkeys(str(row[4][0]).split("%", 1)[0] for row in rows)
    )
    if not addresses:
        raise UnsafeWebTargetError(
            f"Web target did not resolve to an address: {hostname}"
        )
    return addresses


def resolve_public_target(url: str) -> ResolvedWebTarget:
    """Resolve an HTTP(S) URL and reject every non-global address."""
    raw = str(url or "").strip()
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeWebTargetError(f"invalid Web target: {exc}") from exc
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeWebTargetError("Web target scheme must be http/https")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeWebTargetError("Web target credentials are not allowed")
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if not hostname:
        raise UnsafeWebTargetError("Web target requires a hostname")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeWebTargetError("Web target resolves to a non-public host")
    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UnsafeWebTargetError("Web target hostname is invalid") from exc
    effective_port = port or (443 if scheme == "https" else 80)
    try:
        literal_address = _canonical_ip(ascii_hostname)
    except ValueError:
        literal_address = None
    if literal_address is not None and not _is_public_unicast(literal_address):
        raise UnsafeWebTargetError(
            f"Web target resolves to a non-public address: {literal_address}"
        )
    addresses = _resolve_addresses(ascii_hostname, effective_port)
    for raw_address in addresses:
        try:
            address = _canonical_ip(raw_address)
        except ValueError as exc:
            raise UnsafeWebTargetError(
                f"Web target resolved to an invalid address: {raw_address}"
            ) from exc
        if not _is_public_unicast(address):
            raise UnsafeWebTargetError(
                f"Web target resolved to a non-public address: {address}"
            )

    host_for_url = (
        f"[{ascii_hostname}]"
        if ":" in ascii_hostname
        else ascii_hostname
    )
    default_port = 443 if scheme == "https" else 80
    netloc = (
        host_for_url
        if effective_port == default_port
        else f"{host_for_url}:{effective_port}"
    )
    path = parsed.path or "/"
    normalized = urllib.parse.urlunsplit(
        (scheme, netloc, path, parsed.query, "")
    )
    request_target = urllib.parse.urlunsplit(
        ("", "", path, parsed.query, "")
    )
    return ResolvedWebTarget(
        url=normalized,
        scheme=scheme,
        hostname=ascii_hostname,
        port=effective_port,
        request_target=request_target,
        addresses=addresses,
    )


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(
        self,
        hostname: str,
        port: int,
        *,
        connect_ip: str,
        timeout: float,
    ) -> None:
        super().__init__(hostname, port=port, timeout=timeout)
        self._connect_ip = connect_ip

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self._connect_ip, self.port),
            self.timeout,
            self.source_address,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        hostname: str,
        port: int,
        *,
        connect_ip: str,
        timeout: float,
    ) -> None:
        super().__init__(
            hostname,
            port=port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._connect_ip = connect_ip

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._connect_ip, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(
            raw_socket,
            server_hostname=self.host,
        )


def _request_target(
    target: ResolvedWebTarget,
    *,
    connect_ip: str,
    method: str,
    headers: Mapping[str, str],
    timeout: float,
    max_bytes: int,
) -> HopResponse:
    connection_type = (
        _PinnedHTTPSConnection
        if target.scheme == "https"
        else _PinnedHTTPConnection
    )
    connection = connection_type(
        target.hostname,
        target.port,
        connect_ip=connect_ip,
        timeout=timeout,
    )
    try:
        connection.request(
            method,
            target.request_target,
            headers=dict(headers),
        )
        response = connection.getresponse()
        body = response.read(max_bytes if max_bytes > 0 else None)
        response_headers = {
            str(key).lower(): str(value)
            for key, value in response.getheaders()
        }
        return HopResponse(
            status=int(response.status),
            reason=str(response.reason or ""),
            headers=response_headers,
            body=body,
        )
    finally:
        connection.close()


def _request_any_validated_address(
    target: ResolvedWebTarget,
    *,
    method: str,
    headers: Mapping[str, str],
    timeout: float,
    max_bytes: int,
) -> HopResponse:
    last_error: OSError | ssl.SSLError | None = None
    for connect_ip in target.addresses:
        try:
            return _request_target(
                target,
                connect_ip=connect_ip,
                method=method,
                headers=headers,
                timeout=timeout,
                max_bytes=max_bytes,
            )
        except (OSError, ssl.SSLError) as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise UnsafeWebTargetError("Web target has no validated public address")


def fetch_public_url(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    timeout: float = 15.0,
    max_bytes: int = 0,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> PublicWebResponse:
    """Fetch through validated pinned addresses and recheck every redirect."""
    requested_url = str(url or "").strip()
    current_url = requested_url
    resolved_ips = []
    visited = set()
    request_headers: Mapping[str, str] = headers or {}

    for redirect_count in range(max_redirects + 1):
        target = resolve_public_target(current_url)
        if target.url in visited:
            raise UnsafeWebTargetError("Web redirect loop detected")
        visited.add(target.url)
        resolved_ips.extend(target.addresses)
        hop = _request_any_validated_address(
            target,
            method=method,
            headers=request_headers,
            timeout=timeout,
            max_bytes=max_bytes,
        )
        if hop.status in REDIRECT_STATUSES:
            location = hop.headers.get("location", "").strip()
            if not location:
                raise urllib.error.HTTPError(
                    target.url,
                    hop.status,
                    "redirect response is missing Location",
                    hop.headers,
                    io.BytesIO(hop.body),
                )
            if redirect_count >= max_redirects:
                raise UnsafeWebTargetError("Web redirect limit exceeded")
            current_url = urllib.parse.urljoin(target.url, location)
            continue
        if hop.status >= 300:
            raise urllib.error.HTTPError(
                target.url,
                hop.status,
                hop.reason,
                hop.headers,
                io.BytesIO(hop.body),
            )
        return PublicWebResponse(
            requested_url=requested_url,
            final_url=target.url,
            status=hop.status,
            headers=hop.headers,
            body=hop.body,
            resolved_ips=tuple(dict.fromkeys(resolved_ips)),
        )

    raise UnsafeWebTargetError("Web redirect limit exceeded")
