import asyncio
import re
from datetime import datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import StatementError

from almanac.db import Database
from almanac.ids import new_id
from almanac.models import Fact


def _fact(fact_id, at):
    return Fact(id=fact_id, at=at, client="test", origin="said", text="hello")


async def test_moment_comes_back_aware_and_equal(db, now):
    async with db.write() as session:
        session.add(_fact("f_test0001", now))
    async with db.read() as session:
        fact = await session.get(Fact, "f_test0001")
    assert fact.at == now
    assert fact.at.tzinfo is not None


async def test_naive_moment_is_refused(db):
    with pytest.raises(StatementError):
        async with db.write() as session:
            session.add(_fact("f_test0002", datetime(2026, 10, 12, 10, 0)))


async def test_failed_write_leaves_nothing(db, now):
    with pytest.raises(RuntimeError):
        async with db.write() as session:
            session.add(_fact("f_test0003", now))
            await session.flush()
            raise RuntimeError("boom")
    async with db.read() as session:
        assert await session.get(Fact, "f_test0003") is None


async def _waiting_writers(db):
    async with db.read() as session:
        return await session.scalar(text("select count(*) from pg_locks where locktype = 'advisory' and not granted"))


async def _until_one_writer_waits(db):
    while await _waiting_writers(db) < 1:
        await asyncio.sleep(0.02)


async def test_two_databases_on_one_server_write_in_turn(db, pg_url, now):
    """Замок общий для всех, кто пишет в базу: второй процесс ждёт, пока первый не закоммитит."""
    other = Database(pg_url)
    seen = []

    async def second_writer():
        async with other.write() as session:
            # Первый уже закоммитил: второй видит его запись, и проверка версии перед своей не расходится с ней.
            seen.append(("second in", await session.get(Fact, "f_test0001") is not None))
            session.add(_fact("f_test0002", now))

    try:
        async with asyncio.timeout(10):
            async with db.write() as session:
                session.add(_fact("f_test0001", now))
                await session.flush()
                task = asyncio.create_task(second_writer())
                await _until_one_writer_waits(db)  # второй дошёл до замка и стоит на нём
                seen.append(("first leaves", None))
            await task
    finally:
        await other.dispose()

    assert seen == [("first leaves", None), ("second in", True)]
    async with db.read() as session:
        assert {fact.id for fact in await session.scalars(select(Fact))} == {
            "f_test0001", "f_test0002"
        }


async def test_a_failed_write_releases_the_lock(db, pg_url, now):
    other = Database(pg_url)
    try:
        with pytest.raises(RuntimeError):
            async with db.write() as session:
                session.add(_fact("f_test0003", now))
                raise RuntimeError("boom")
        async with asyncio.timeout(10), other.write() as session:
            session.add(_fact("f_test0004", now))
    finally:
        await other.dispose()
    async with db.read() as session:
        assert await session.get(Fact, "f_test0003") is None
        assert await session.get(Fact, "f_test0004") is not None


def test_new_id_shape():
    assert re.fullmatch(r"f_[0-9a-hjkmnp-tv-z]{8}", new_id("f"))
    assert new_id("i").startswith("i_")
