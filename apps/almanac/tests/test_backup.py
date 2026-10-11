import sqlite3

from almanac import backup
from almanac.store import facts


async def test_snapshot_is_a_readable_copy_and_old_ones_are_pruned(db, now, tmp_path):
    async with db.write() as session:
        await facts.add(session, client="test", text="важная запись")
    directory = tmp_path / "backups"
    for stale in range(3):
        directory.mkdir(exist_ok=True)
        (directory / f"almanac-2026010{stale}-000000.db").write_bytes(b"old")

    copy = await backup.snapshot(db, directory, keep=2)

    with sqlite3.connect(copy) as connection:
        assert connection.execute("select text from facts").fetchall() == [("важная запись",)]
    names = sorted(path.name for path in directory.glob("almanac-*.db"))
    assert names == ["almanac-20260102-000000.db", copy.name]
