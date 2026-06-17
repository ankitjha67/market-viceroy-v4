"""Unit tests for migration discovery/ordering (pure; no DB)."""

from __future__ import annotations

from pathlib import Path

import pytest
from mv.failover.migrate import Migration, discover_migrations, pending


def _write(directory: Path, name: str, sql: str = "SELECT 1;") -> None:
    (directory / name).write_text(sql, encoding="utf-8")


def test_discover_orders_by_version(tmp_path: Path) -> None:
    _write(tmp_path, "0002_second.sql")
    _write(tmp_path, "0001_first.sql")
    _write(tmp_path, "0010_tenth.sql")
    migrations = discover_migrations(tmp_path)
    assert [m.version for m in migrations] == ["0001", "0002", "0010"]
    assert migrations[0].name == "0001_first"


def test_read_sql(tmp_path: Path) -> None:
    _write(tmp_path, "0001_x.sql", "CREATE TABLE t (id INT);")
    migration = discover_migrations(tmp_path)[0]
    assert migration.read_sql() == "CREATE TABLE t (id INT);"


def test_misnamed_file_raises(tmp_path: Path) -> None:
    _write(tmp_path, "init.sql")
    with pytest.raises(ValueError, match=r"NNNN_description\.sql"):
        discover_migrations(tmp_path)


def test_duplicate_version_raises(tmp_path: Path) -> None:
    _write(tmp_path, "0001_a.sql")
    _write(tmp_path, "0001_b.sql")
    with pytest.raises(ValueError, match="duplicate migration version"):
        discover_migrations(tmp_path)


def test_pending_filters_applied() -> None:
    migrations = [
        Migration("0001", "0001_a", Path("0001_a.sql")),
        Migration("0002", "0002_b", Path("0002_b.sql")),
        Migration("0003", "0003_c", Path("0003_c.sql")),
    ]
    result = pending(migrations, applied={"0001", "0002"})
    assert [m.version for m in result] == ["0003"]


def test_repo_migrations_are_discoverable() -> None:
    # The real Phase-1 migration directory parses cleanly.
    repo_dir = Path(__file__).resolve().parents[3] / "infra" / "postgres" / "migrations"
    migrations = discover_migrations(repo_dir)
    assert any(m.name == "0001_phase1" for m in migrations)
