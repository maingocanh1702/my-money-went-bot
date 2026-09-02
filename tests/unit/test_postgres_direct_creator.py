"""Closed-contract tests for the PostgreSQL direct-creator TLS boundary."""

from __future__ import annotations

import gc
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import event
from sqlalchemy.engine import URL

import storage.postgres_connection as postgres


class _TruthyEmptyText:
    def __bool__(self) -> bool:
        return True

    def __str__(self) -> str:
        return ""


class _TruthyNulText:
    def __bool__(self) -> bool:
        return True

    def __str__(self) -> str:
        return "pw\x00shadow"


@pytest.mark.parametrize(
    "url",
    [
        None,
        "sqlite:///:memory:",
        "postgresql://app@db/money?sslmode=verify-full",
        "postgresql://app:pw@db/money",
        "postgresql://app:pw@db/money?sslmode=require",
        "postgresql://app:pw@db,mysql/money?sslmode=verify-full",
        "postgresql://app:pw@db/money?sslmode=verify-full&target_session_attrs=",
        "postgresql://app:pw@db/money?sslmode=verify-full&sslmode=verify-full",
    ],
)
def test_rejects_ambiguous_or_insecure_urls(url: str | None) -> None:
    with pytest.raises(ValueError):
        postgres.require_postgres_url(url, environ={})


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://app%00shadow:pw@db.example/money?sslmode=verify-full",
        "postgresql://app:pw%00shadow@db.example/money?sslmode=verify-full",
    ],
)
def test_rejects_percent_decoded_nul_url_fields(url: str) -> None:
    with pytest.raises(ValueError, match="NUL"):
        postgres.require_postgres_url(url, environ={})


@pytest.mark.parametrize("field", ["username", "password", "host", "database"])
def test_rejects_sqlalchemy_url_objects_with_nul_bound_fields(field: str) -> None:
    values: dict[str, object] = {
        "username": "app",
        "password": "pw",
        "host": "db.example",
        "database": "money",
    }
    values[field] = f"{values[field]}\x00shadow"
    url = URL.create("postgresql", query={"sslmode": "verify-full"}, **values)
    with pytest.raises(ValueError, match="NUL"):
        postgres.require_postgres_url(url, environ={})


@pytest.mark.parametrize("password", [_TruthyEmptyText(), _TruthyNulText()])
def test_rejects_sqlalchemy_url_objects_with_unsafe_materialized_credentials(
    password: object,
) -> None:
    url = URL.create(
        "postgresql",
        username="app",
        password=password,
        host="db.example",
        database="money",
        query={"sslmode": "verify-full"},
    )
    with pytest.raises(ValueError, match="password"):
        postgres.require_postgres_url(url, environ={})


def test_dbapi_parameters_serialize_all_pinned_security_controls(tmp_path: Path) -> None:
    url = postgres.require_postgres_url(
        "postgresql://app:pw@db.example/money?sslmode=verify-full",
        environ={},
    )
    private_directory = tmp_path / "private"
    private_directory.mkdir(mode=0o700)
    conninfo = psycopg.conninfo.make_conninfo(
        "",
        **postgres._dbapi_parameters(
            url,
            postgres._TlsRoot(value="system", contents=None, directory=private_directory),
        ),
    )
    for expected in (
        "sslmode=verify-full",
        "sslrootcert=system",
        f"sslcrl={private_directory / 'root.crl'}",
        "sslcertmode=disable",
        "gssencmode=disable",
        "require_auth=scram-sha-256",
        "search_path=my_money_went,pg_temp",
    ):
        assert expected in conninfo


@pytest.mark.parametrize(
    "name",
    [
        "PGSERVICE",
        "PGSSLMODE",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "OPENSSL_CONF",
        "OPENSSL_CONF_INCLUDE",
        "OPENSSL_MODULES",
        "OPENSSL_ENGINES",
    ],
)
@pytest.mark.parametrize("value", ["untrusted", ""])
def test_rejects_present_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="overrides"):
        postgres.require_postgres_url(
            "postgresql://app:pw@db.example/money?sslmode=verify-full",
            environ={},
        )
    monkeypatch.delenv(name)
    with pytest.raises(ValueError, match="overrides"):
        postgres.require_postgres_url(
            "postgresql://app:pw@db.example/money?sslmode=verify-full",
            environ={name: value},
        )


@pytest.mark.parametrize("mode", ["relative", "symlink", "unsafe", "empty", "oversized"])
def test_private_ca_rejects_unsafe_sources(tmp_path: Path, mode: str) -> None:
    source = tmp_path / "ca.crt"
    if mode == "relative":
        with pytest.raises(ValueError, match="absolute"):
            postgres._read_tls_root({postgres.POSTGRES_SSL_ROOT_CERT_ENV: "ca.crt"})
        return
    if mode == "symlink":
        target = tmp_path / "target.crt"
        target.write_text("root")
        source.symlink_to(target)
    elif mode == "unsafe":
        source.write_text("root")
        source.chmod(0o666)
    elif mode == "empty":
        source.touch()
    else:
        source.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(ValueError):
        postgres._read_tls_root({postgres.POSTGRES_SSL_ROOT_CERT_ENV: str(source)})


def test_private_ca_detects_same_size_mutation_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "ca.crt"
    source.write_text("first")
    source.chmod(0o644)
    real_read = postgres.os.read

    def mutate_after_read(descriptor: int, size: int) -> bytes:
        contents = real_read(descriptor, size)
        source.write_text("later")
        return contents

    monkeypatch.setattr(postgres.os, "read", mutate_after_read)
    with pytest.raises(ValueError, match="changed while"):
        postgres._read_tls_root({postgres.POSTGRES_SSL_ROOT_CERT_ENV: str(source)})


def test_private_ca_is_sealed_for_engine_lifetime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "ca.crt"
    source.write_text("first")
    source.chmod(0o644)
    captured: dict[str, object] = {}
    connected: dict[str, object] = {}
    sentinel = object()
    chmod_calls: list[int] = []
    real_create_engine = postgres.create_engine
    real_fchmod = postgres.os.fchmod

    def capture_engine(*args: object, **kwargs: object):
        captured.update(kwargs)
        return real_create_engine(*args, **kwargs)

    def connect(**parameters: object) -> object:
        connected.update(parameters)
        return sentinel

    def fchmod(descriptor: int, mode: int) -> None:
        chmod_calls.append(mode)
        real_fchmod(descriptor, mode)

    monkeypatch.setattr(postgres, "create_engine", capture_engine)
    monkeypatch.setattr(postgres.psycopg, "connect", connect)
    monkeypatch.setattr(postgres.os, "fchmod", fchmod)
    engine = postgres.create_postgres_engine(
        "postgresql://app:pw@db.example/money?sslmode=verify-full",
        environ={postgres.POSTGRES_SSL_ROOT_CERT_ENV: str(source)},
    )
    sealed_path = None
    try:
        creator = captured["creator"]
        assert callable(creator)
        source.write_text("later")
        assert creator() is sentinel
        sealed_path = Path(connected["sslrootcert"])
        assert sealed_path != source
        assert sealed_path.read_text() == "first"
        assert sealed_path.stat().st_mode & 0o777 == 0o600
        assert Path(connected["sslcrl"]) == sealed_path.parent / "root.crl"
        assert not Path(connected["sslcrl"]).exists()
        assert chmod_calls == [0o600]
        assert connected["options"] == "-c search_path=my_money_went,pg_temp"
        engine.dispose()
        assert sealed_path.exists()
    finally:
        engine.dispose()
        del engine
        gc.collect()
    assert sealed_path is not None
    assert not sealed_path.parent.exists()


def test_sealing_and_engine_construction_failures_delete_private_ca(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sealed_directory = tmp_path / "sealed"
    sealed_directory.mkdir()
    monkeypatch.setattr(postgres.tempfile, "mkdtemp", lambda **_: str(sealed_directory))
    monkeypatch.setattr(postgres.os, "write", lambda *_: 0)
    with pytest.raises(RuntimeError, match="sealed"):
        postgres._seal_tls_root(postgres._TlsRoot(value="source", contents=b"root"))
    assert not sealed_directory.exists()
    monkeypatch.undo()

    source = tmp_path / "ca.crt"
    source.write_text("root")
    source.chmod(0o644)
    sealed: list[postgres._TlsRoot] = []
    real_seal = postgres._seal_tls_root

    def capture_sealed(root: postgres._TlsRoot) -> postgres._TlsRoot:
        captured = real_seal(root)
        sealed.append(captured)
        return captured

    monkeypatch.setattr(postgres, "_seal_tls_root", capture_sealed)
    monkeypatch.setattr(
        postgres,
        "create_engine",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError, match="boom"):
        postgres.create_postgres_engine(
            "postgresql://app:pw@db.example/money?sslmode=verify-full",
            environ={postgres.POSTGRES_SSL_ROOT_CERT_ENV: str(source)},
        )
    assert sealed and sealed[0].directory is not None
    assert not sealed[0].directory.exists()


def test_close_failure_deletes_the_sealed_ca(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sealed_directory = tmp_path / "sealed"
    sealed_directory.mkdir()
    monkeypatch.setattr(postgres.tempfile, "mkdtemp", lambda **_: str(sealed_directory))
    real_close = postgres.os.close

    def close_then_fail(descriptor: int) -> None:
        real_close(descriptor)
        raise OSError("delayed close failure")

    monkeypatch.setattr(postgres.os, "close", close_then_fail)
    with pytest.raises(OSError, match="delayed close"):
        postgres._seal_tls_root(postgres._TlsRoot(value="source", contents=b"root"))
    assert not sealed_directory.exists()


def test_creator_is_the_terminal_connection_chokepoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    sentinel = object()

    def connect(**parameters: object) -> object:
        calls.update(parameters)
        return sentinel

    monkeypatch.setattr(postgres.psycopg, "connect", connect)
    engine = postgres.create_postgres_engine(
        "postgresql://app:pw@db.example/money?sslmode=verify-full",
        environ={},
    )

    @event.listens_for(engine, "do_connect")
    def mutate_later(
        dialect: object,
        connection_record: object,
        cargs: object,
        cparams: dict[str, str],
    ) -> None:
        del dialect, connection_record, cargs
        cparams["sslmode"] = "disable"

    try:
        assert engine.pool._creator() is sentinel
        assert calls["sslmode"] == "verify-full"
        assert calls["sslrootcert"] == "system"
        assert Path(calls["sslcrl"]).parent != Path.home() / ".postgresql"
        assert not Path(calls["sslcrl"]).exists()
        assert Path(calls["sslcrl"]).parent.stat().st_mode & 0o777 == 0o700
        assert calls["sslcertmode"] == "disable"
        assert calls["gssencmode"] == "disable"
        assert calls["require_auth"] == "scram-sha-256"
        assert calls["options"] == "-c search_path=my_money_went,pg_temp"
    finally:
        engine.dispose()


def test_system_tls_root_gets_a_private_absent_crl_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_directory = tmp_path / "sealed"
    private_directory.mkdir()
    monkeypatch.setattr(postgres.tempfile, "mkdtemp", lambda **_: str(private_directory))
    root = postgres._seal_tls_root(postgres._TlsRoot(value="system", contents=None))
    try:
        parameters = postgres._dbapi_parameters(
            postgres.require_postgres_url(
                "postgresql://app:pw@db.example/money?sslmode=verify-full",
                environ={},
            ),
            root,
        )
        assert parameters["sslrootcert"] == "system"
        assert parameters["sslcrl"] == str(private_directory / "root.crl")
        assert not (private_directory / "root.crl").exists()
        assert private_directory.stat().st_mode & 0o777 == 0o700
    finally:
        postgres._delete_tls_root(root)
    assert not private_directory.exists()
