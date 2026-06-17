"""Minimal forward-only SQL migration runner for PostgreSQL.

Versioned ``NNNN_name.sql`` files in a directory are applied in order, each in
its own transaction, and recorded in a ``schema_migrations`` table so re-runs
are idempotent. Discovery/ordering is pure (unit-tested); ``apply_all`` does
DB I/O and is exercised by the CI integration job.

Run from the repo root:  ``uv run mv-migrate``
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from mv.failover.db import postgres_connect
from mv.failover.settings import Settings

DEFAULT_MIGRATIONS_DIR = "infra/postgres/migrations"
_VERSION_RE = re.compile(r"^(\d+)_.+\.sql$")


@dataclass(frozen=True, slots=True)
class Migration:
    """A single migration file."""

    version: str
    name: str
    path: Path

    def read_sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def discover_migrations(directory: Path) -> list[Migration]:
    """Return migrations in ``directory`` ordered by version.

    Files must be named ``NNNN_description.sql``. Raises ``ValueError`` on a
    misnamed ``.sql`` file (a misnamed migration must fail loudly, not be
    silently skipped) or on a duplicate version.
    """
    migrations: list[Migration] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.sql")):
        match = _VERSION_RE.match(path.name)
        if match is None:
            raise ValueError(f"migration file {path.name!r} must be named 'NNNN_description.sql'")
        version = match.group(1)
        if version in seen:
            raise ValueError(f"duplicate migration version {version!r}")
        seen.add(version)
        migrations.append(Migration(version=version, name=path.stem, path=path))
    return sorted(migrations, key=lambda m: m.version)


def pending(migrations: list[Migration], applied: set[str]) -> list[Migration]:
    """Filter to migrations whose version is not in ``applied`` (order kept)."""
    return [m for m in migrations if m.version not in applied]


def apply_all(settings: Settings, directory: Path) -> list[str]:  # pragma: no cover - DB I/O
    """Apply all pending migrations; return the versions applied this run."""
    migrations = discover_migrations(directory)
    applied_now: list[str] = []
    conn = postgres_connect(settings)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "  version TEXT PRIMARY KEY,"
                "  name TEXT NOT NULL,"
                "  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")"
            )
            conn.commit()
            cur.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
        for migration in pending(migrations, applied):
            with conn.cursor() as cur:
                cur.execute(migration.read_sql())
                cur.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                    (migration.version, migration.name),
                )
            conn.commit()
            applied_now.append(migration.version)
    finally:
        conn.close()
    return applied_now


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - CLI/I/O wrapper
    args = sys.argv[1:] if argv is None else argv
    directory = Path(
        args[0] if args else os.environ.get("MV_MIGRATIONS_DIR", DEFAULT_MIGRATIONS_DIR)
    )
    applied = apply_all(Settings(), directory)
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("No pending migrations.")


if __name__ == "__main__":  # pragma: no cover
    main()
