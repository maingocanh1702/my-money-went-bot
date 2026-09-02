# PostgreSQL direct-creator TLS boundary — R25

R25 replaces the halted event-listener design. It contains only the TLS
connection boundary; schema authority, migrations, Docker proof, and source of
truth cutover remain separate dependent work.

| Boundary | Decision | Failure behavior |
| --- | --- | --- |
| URL and environment | Require one password-authenticated PostgreSQL TCP endpoint and the raw query sslmode=verify-full. Materialize user, password, host, and database once; reject empty or NUL-containing values. Reject PG, TLS trust, and OpenSSL configuration environment keys by presence, including empty values. | No URL field can truncate a libpq conninfo string, and ambient configuration cannot add hosts, alter TLS, or supply a fallback password. |
| Private CA and CRL | Read only an absolute regular non-group/world-writable root via O_NOFOLLOW. Seal stable bytes into an Engine-private 0700 directory and 0600 file; create that directory even with system roots, and pin `sslcrl` to its absent private path. | Reject unsafe, changing, or invalid roots; libpq cannot use the home-directory CRL fallback; delete the private directory after write, close, or construction failure. |
| Connection chokepoint | SQLAlchemy Pool creator calls psycopg directly with a complete pinned parameter set: host, port, dbname, user, password, verify-full, sealed root, disabled GSS, and private search path. | Later do_connect listeners do not participate and cannot weaken DBAPI parameters. |
