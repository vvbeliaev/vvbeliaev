import shutil
import sqlite3
from datetime import timedelta
from types import SimpleNamespace

import pytest

from almanac import backup, clock
from almanac.store import facts

DAY = timedelta(days=1)


def _daily(directory):
    return sorted(path.name for path in directory.glob("almanac-*.db"))


def _at(monkeypatch, moment):
    monkeypatch.setattr(clock, "_now", lambda: moment)


async def test_snapshot_is_a_readable_copy_named_by_the_day(db, now, tmp_path):
    async with db.write() as session:
        await facts.add(session, client="test", text="важная запись")
    directory = tmp_path / "backups"

    copy = await backup.snapshot(db, directory)

    assert copy == directory / "almanac-20261012.db"
    with sqlite3.connect(copy) as connection:
        assert connection.execute("select text from facts").fetchall() == [("важная запись",)]
    assert sorted(path.name for path in directory.iterdir()) == ["almanac-20261012.db"]


async def test_two_calls_on_one_day_make_one_file(db, now, tmp_path):
    directory = tmp_path / "backups"
    first = await backup.snapshot(db, directory)
    stamp = first.stat().st_mtime_ns
    async with db.write() as session:
        await facts.add(session, client="test", text="позже в тот же день")

    second = await backup.snapshot(db, directory)

    assert second == first
    assert _daily(directory) == ["almanac-20261012.db"]
    assert second.stat().st_mtime_ns == stamp  # ничего не перезаписано


async def test_restarts_on_the_last_day_do_not_push_older_copies_out(db, now, tmp_path, monkeypatch):
    directory = tmp_path / "backups"
    first_day = now - 13 * DAY
    for offset in range(14):
        _at(monkeypatch, first_day + offset * DAY)
        await backup.snapshot(db, directory)
    for restart in range(3):  # деплои и падения в последний день
        _at(monkeypatch, now + restart * timedelta(hours=1))
        await backup.snapshot(db, directory)

    names = _daily(directory)
    assert len(names) == 14
    assert names[0] == f"almanac-{first_day:%Y%m%d}.db"
    assert names[-1] == "almanac-20261012.db"


async def test_the_fifteenth_day_drops_only_the_oldest_copy(db, now, tmp_path, monkeypatch):
    directory = tmp_path / "backups"
    first_day = now - 14 * DAY
    for offset in range(15):
        _at(monkeypatch, first_day + offset * DAY)
        await backup.snapshot(db, directory)

    names = _daily(directory)
    assert len(names) == 14
    assert names[0] == f"almanac-{(first_day + DAY):%Y%m%d}.db"


async def test_pruning_never_touches_pre_migration_copies_or_other_files(db, now, tmp_path, monkeypatch):
    directory = tmp_path / "backups"
    directory.mkdir()
    for name in ("pre-0002.db", "pre-0003.db", "notes.txt", "almanac-old.db.bak"):
        (directory / name).write_bytes(b"keep me")
    first_day = now - 4 * DAY
    for offset in range(5):
        _at(monkeypatch, first_day + offset * DAY)
        await backup.snapshot(db, directory, keep=2)

    assert _daily(directory) == ["almanac-20261011.db", "almanac-20261012.db"]
    survivors = {path.name for path in directory.iterdir()}
    assert {"pre-0002.db", "pre-0003.db", "notes.txt", "almanac-old.db.bak"} <= survivors


async def test_a_copy_that_breaks_halfway_leaves_nothing_behind(db, now, tmp_path, monkeypatch):
    directory = tmp_path / "backups"

    async def broken_copy(_db, target):
        target.write_bytes(b"half a database")
        raise OSError("No space left on device")

    monkeypatch.setattr(backup, "_vacuum_into", broken_copy)

    with pytest.raises(OSError, match="No space left"):
        await backup.snapshot(db, directory)

    assert list(directory.iterdir()) == []


async def test_a_copy_that_fails_the_check_is_not_published(db, now, tmp_path, monkeypatch):
    directory = tmp_path / "backups"

    async def garbage_copy(_db, target):
        target.write_bytes(b"this is not a database " * 200)

    monkeypatch.setattr(backup, "_vacuum_into", garbage_copy)

    with pytest.raises(sqlite3.DatabaseError):
        await backup.snapshot(db, directory)

    assert list(directory.iterdir()) == []


async def test_a_failed_copy_does_not_become_the_newest_one(db, now, tmp_path, monkeypatch):
    directory = tmp_path / "backups"
    _at(monkeypatch, now - DAY)
    good = await backup.snapshot(db, directory)
    _at(monkeypatch, now)

    async def broken_copy(_db, target):
        target.write_bytes(b"x")
        raise OSError("I/O error")

    monkeypatch.setattr(backup, "_vacuum_into", broken_copy)
    with pytest.raises(OSError):
        await backup.snapshot(db, directory)

    assert _daily(directory) == [good.name]


async def test_a_partial_file_left_by_a_killed_process_does_not_block_the_next_copy(db, now, tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    (directory / "almanac-20261012.db.partial").write_bytes(b"left by a killed process")

    copy = await backup.snapshot(db, directory)

    assert copy.exists()
    assert [path.name for path in directory.iterdir()] == ["almanac-20261012.db"]


async def test_too_little_free_space_writes_nothing(db, now, tmp_path, monkeypatch):
    directory = tmp_path / "backups"
    size = (tmp_path / "test.db").stat().st_size
    seen = []

    def nearly_full(path):
        seen.append(path)
        return SimpleNamespace(total=10**9, used=10**9 - int(size * 1.1), free=int(size * 1.1))

    monkeypatch.setattr(shutil, "disk_usage", nearly_full)

    with pytest.raises(RuntimeError, match="not enough free space for a database copy"):
        await backup.snapshot(db, directory)

    assert seen == [directory]
    assert list(directory.iterdir()) == []


async def test_enough_free_space_lets_the_copy_through(db, now, tmp_path, monkeypatch):
    size = (tmp_path / "test.db").stat().st_size
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: SimpleNamespace(free=int(size * 1.3)))

    assert (await backup.snapshot(db, tmp_path / "backups")).exists()


def test_a_corrupted_copy_with_a_valid_header_fails_the_check(tmp_path):
    path = tmp_path / "damaged.db"
    with sqlite3.connect(path) as connection:
        connection.execute("create table t (v text)")
        connection.executemany("insert into t values (?)", [(f"строка номер {n}",) for n in range(2000)])
    raw = bytearray(path.read_bytes())
    raw[8192:12288] = b"\xff" * 4096  # страницы данных испорчены, заголовок цел
    path.write_bytes(bytes(raw))

    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        backup._quick_check(path)


def test_quick_check_accepts_a_healthy_database(db, tmp_path):
    backup._quick_check(tmp_path / "test.db")
