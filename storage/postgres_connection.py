"""Strict PostgreSQL TLS boundary with a terminal DBAPI creator."""

from __future__ import annotations

import os
import re
import stat
import tempfile
import weakref
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url

DATABASE_URL_ENV = "DATABASE_URL"
POSTGRES_SSL_ROOT_CERT_ENV = "POSTGRES_SSL_ROOT_CERT"
POSTGRES_APP_SCHEMA = "my_money_went"
POSTGRES_SAFE_SEARCH_PATH = f"{POSTGRES_APP_SCHEMA},pg_temp"
_MAX_CERTIFICATE_BYTES = 1024 * 1024
# libpq leaves the connection attempt unbounded when connect_timeout is
# absent, so a blackholed TCP/TLS/auth handshake would block synchronous
# pool creation forever. PG* overrides are rejected, so pin it here.
_CONNECT_TIMEOUT_SECONDS = 10
_TCP_HOSTNAME = re.compile(
    r"^(?=.{1,253}\.?$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}"
    r"[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.?$"
)


@dataclass(frozen=True)
class _TlsRoot:
    value: str
    contents: bytes | None
    directory: Path | None = None


def _effective_environment(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def _reject_environment_overrides(environ: Mapping[str, str]) -> None:
    if any(name.startswith("PG") for name in environ):
        raise ValueError("PostgreSQL environment overrides are not allowed")
    if any(
        name in environ
        for name in (
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "OPENSSL_CONF",
            "OPENSSL_CONF_INCLUDE",
            "OPENSSL_MODULES",
            "OPENSSL_ENGINES",
        )
    ):
        raise ValueError("TLS trust environment overrides are not allowed")


def _verify_effective_environment(environ: Mapping[str, str]) -> None:
    _reject_environment_overrides(os.environ)
    if environ is not os.environ:
        _reject_environment_overrides(environ)


def _one_tcp_host(host: str) -> bool:
    if not host or "," in host or host.startswith("@"):
        return False
    try:
        ip_address(host)
    except ValueError:
        return bool(_TCP_HOSTNAME.fullmatch(host))
    return True


def _require_url_text(value: object | None, field: str) -> str:
    """Materialize a DBAPI-bound URL field once and reject libpq delimiters."""
    text = "" if value is None else str(value)
    if not text or "\x00" in text:
        raise ValueError(f"DATABASE_URL requires a non-empty {field} without NUL bytes")
    return text


def _trusted_uids() -> frozenset[int]:
    """Owners allowed to supply a trust anchor: root or this process."""
    return frozenset({0, os.geteuid()})


def _require_trusted_directory(directory: Path) -> None:
    """Reject a certificate an untrusted user could replace by rename."""
    try:
        info = os.stat(directory)
    except OSError as exc:
        raise ValueError(
            f"{POSTGRES_SSL_ROOT_CERT_ENV} must live in a readable directory"
        ) from exc
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError(f"{POSTGRES_SSL_ROOT_CERT_ENV} must live in a directory")
    if info.st_uid not in _trusted_uids():
        raise ValueError(
            f"{POSTGRES_SSL_ROOT_CERT_ENV} directory must be owned by root or by this process"
        )
    # The sticky bit is what makes a shared writable directory safe: only an
    # entry's owner may unlink or rename it there.
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH) and not info.st_mode & stat.S_ISVTX:
        raise ValueError(
            f"{POSTGRES_SSL_ROOT_CERT_ENV} directory must not be group- or world-writable"
        )


def _read_tls_root(environ: Mapping[str, str]) -> _TlsRoot:
    configured = environ.get(POSTGRES_SSL_ROOT_CERT_ENV, "")
    if not configured:
        return _TlsRoot(value="system", contents=None)
    path = Path(configured)
    if not path.is_absolute():
        raise ValueError(f"{POSTGRES_SSL_ROOT_CERT_ENV} must be an absolute certificate path")
    if not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("secure PostgreSQL certificate handling requires O_NOFOLLOW")
    _require_trusted_directory(path.parent)

    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ValueError(
                f"{POSTGRES_SSL_ROOT_CERT_ENV} must reference a non-group-writable regular file"
            )
        if before.st_uid not in _trusted_uids():
            raise ValueError(
                f"{POSTGRES_SSL_ROOT_CERT_ENV} must be owned by root or by this process"
            )
        if not 0 < before.st_size <= _MAX_CERTIFICATE_BYTES:
            raise ValueError(
                f"{POSTGRES_SSL_ROOT_CERT_ENV} must be a non-empty certificate no larger than 1 MiB"
            )
        contents = os.read(descriptor, before.st_size + 1)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ValueError(
            f"{POSTGRES_SSL_ROOT_CERT_ENV} must reference a readable certificate file"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)

    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if len(contents) != before.st_size or identity_before != identity_after:
        raise ValueError(f"{POSTGRES_SSL_ROOT_CERT_ENV} changed while it was being validated")
    return _TlsRoot(value=str(path), contents=contents)


def _delete_tls_root(root: _TlsRoot) -> None:
    if root.directory is None:
        return
    try:
        (root.directory / "root.crt").unlink()
    except FileNotFoundError:
        pass
    except OSError:
        return
    try:
        root.directory.rmdir()
    except OSError:
        pass


def _seal_tls_root(source: _TlsRoot) -> _TlsRoot:
    directory = Path(tempfile.mkdtemp(prefix="my-money-went-postgres-ca-"))
    root = _TlsRoot(
        value=source.value if source.contents is None else str(directory / "root.crt"),
        contents=None,
        directory=directory,
    )
    descriptor = None
    try:
        os.chmod(directory, 0o700)
        if source.contents is None:
            return root
        descriptor = os.open(root.value, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fchmod(descriptor, 0o600)
        remaining = memoryview(source.contents)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("short write while sealing PostgreSQL TLS root certificate")
            remaining = remaining[written:]
    except OSError as exc:
        _delete_tls_root(root)
        raise RuntimeError("unable to create the sealed PostgreSQL TLS root certificate") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                _delete_tls_root(root)
                raise
    return root


def require_postgres_url(
    database_url: str | URL | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> URL:
    """Accept exactly one password-authenticated, TLS-verified TCP endpoint."""
    environment = _effective_environment(environ)
    _verify_effective_environment(environment)
    if isinstance(database_url, URL):
        url = database_url
    elif isinstance(database_url, str) and database_url.strip():
        raw_url = database_url.strip()
        if urlsplit(raw_url).query != "sslmode=verify-full":
            raise ValueError("DATABASE_URL must contain only sslmode=verify-full")
        try:
            url = make_url(raw_url)
        except Exception as exc:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL URL") from exc
    else:
        raise ValueError("DATABASE_URL is required")

    if url.drivername.split("+", 1)[0] not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use a PostgreSQL backend")
    username = _require_url_text(url.username, "user")
    password = _require_url_text(url.password, "password")
    host = _require_url_text(url.host, "host")
    database = _require_url_text(url.database, "database")
    if not _one_tcp_host(host):
        raise ValueError("DATABASE_URL host must be exactly one TCP hostname or IP address")
    port = 5432 if url.port is None else url.port
    if not 1 <= port <= 65535:
        raise ValueError("DATABASE_URL port must be between 1 and 65535")
    if {str(key) for key in url.query} != {"sslmode"} or url.query.get("sslmode") != "verify-full":
        raise ValueError("DATABASE_URL must contain only sslmode=verify-full")

    _read_tls_root(environment)
    return url.set(
        drivername="postgresql+psycopg",
        username=username,
        password=password,
        host=host,
        database=database,
        port=port,
        query={"sslmode": "verify-full"},
    )


def _dbapi_parameters(url: URL, tls_root: _TlsRoot) -> dict[str, str | int]:
    if tls_root.directory is None:
        raise RuntimeError("sealed PostgreSQL TLS root is missing its private directory")
    return {
        "host": url.host,
        "port": url.port or 5432,
        "dbname": url.database,
        "user": url.username,
        "password": url.password,
        "sslmode": "verify-full",
        "sslrootcert": tls_root.value,
        "sslcrl": str(tls_root.directory / "root.crl"),
        "sslcertmode": "disable",
        "gssencmode": "disable",
        "require_auth": "scram-sha-256",
        "connect_timeout": _CONNECT_TIMEOUT_SECONDS,
        "options": f"-c search_path={POSTGRES_SAFE_SEARCH_PATH}",
    }


def create_postgres_engine(
    database_url: str | URL,
    *,
    environ: Mapping[str, str] | None = None,
) -> Engine:
    """Create an Engine whose pool uses the only DBAPI connection chokepoint."""
    environment = _effective_environment(environ)
    url = require_postgres_url(database_url, environ=environment)
    root: _TlsRoot | None = None
    try:
        root = _seal_tls_root(_read_tls_root(environment))
        parameters = _dbapi_parameters(url, root)

        # The dialect is captured after construction so the creator can read
        # the AdaptersMap SQLAlchemy builds during initialize(). Holding the
        # dialect (not the Engine) keeps the Engine collectable, so the
        # finalizer below still deletes the sealed certificate.
        dialect_holder: list[object] = []

        def creator():
            _verify_effective_environment(environment)
            connect_parameters = dict(parameters)
            # SQLAlchemy registers dynamically discovered types (hstore among
            # them) on the dialect's AdaptersMap and passes it to psycopg as
            # ``context``. A terminal creator must forward the same map or a
            # later pool connection decodes values differently from the first.
            adapters_map = (
                getattr(dialect_holder[0], "_psycopg_adapters_map", None)
                if dialect_holder
                else None
            )
            if adapters_map is not None:
                connect_parameters["context"] = adapters_map
            return psycopg.connect(**connect_parameters)

        engine = create_engine(url, creator=creator, pool_pre_ping=True)
        dialect_holder.append(engine.dialect)
    except Exception:
        if root is not None:
            _delete_tls_root(root)
        raise
    weakref.finalize(engine, _delete_tls_root, root)
    return engine


def create_postgres_engine_from_environment(
    environ: Mapping[str, str] | None = None,
) -> Engine:
    environment = _effective_environment(environ)
    return create_postgres_engine(environment.get(DATABASE_URL_ENV), environ=environment)
