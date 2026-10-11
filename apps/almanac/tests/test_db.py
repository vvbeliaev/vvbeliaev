import re
from datetime import datetime

import pytest
from sqlalchemy.exc import StatementError

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


def test_new_id_shape():
    assert re.fullmatch(r"f_[0-9a-hjkmnp-tv-z]{8}", new_id("f"))
    assert new_id("i").startswith("i_")
