import pytest
from pydantic import ValidationError

from almanac.config import Settings


@pytest.mark.parametrize("day_start", ["9", "25:00", "09:60", "9:00", "09:00:00", "ab:cd", ""])
def test_bad_day_start_is_refused(day_start):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, day_start=day_start)


def test_unknown_time_zone_is_refused():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, owner_tz="Mars/Olympus")


def test_good_day_start_and_zone_are_accepted():
    settings = Settings(_env_file=None, day_start="07:30", owner_tz="Europe/Berlin")
    assert (settings.day_start, settings.owner_tz) == ("07:30", "Europe/Berlin")


@pytest.mark.parametrize(
    "base_url",
    [
        "http://almanac.example",
        "http://localhost.evil.example",
        "http://almanac.example/localhost",
        "ftp://almanac.example",
        "almanac.example",
        "https://",
        "https:///path",
        "",
    ],
)
def test_base_url_must_be_https_or_loopback(base_url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, base_url=base_url)


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://almanac.example", "https://almanac.example"),
        ("https://almanac.example/", "https://almanac.example"),
        ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("http://localhost:8000/", "http://localhost:8000"),
        ("http://[::1]:8000", "http://[::1]:8000"),
    ],
)
def test_good_base_url_is_accepted_without_a_trailing_slash(base_url, expected):
    assert Settings(_env_file=None, base_url=base_url).base_url == expected


def test_default_base_url_is_loopback():
    assert Settings(_env_file=None).base_url == "http://127.0.0.1:8000"


@pytest.mark.parametrize("token", ["a", "feed-" + "a" * 26])
def test_short_calendar_secret_is_refused(token):
    assert len(token) < 32
    with pytest.raises(ValidationError, match="ICS_TOKEN"):
        Settings(_env_file=None, ics_token=token)


def test_empty_and_long_calendar_secrets_are_accepted():
    assert Settings(_env_file=None, ics_token="").ics_token == ""
    assert Settings(_env_file=None).ics_token == ""
    long = "feed-" + "a" * 27
    assert len(long) == 32
    assert Settings(_env_file=None, ics_token=long).ics_token == long


def test_default_database_is_the_local_one_from_compose(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings(_env_file=None).database_url == "postgresql+asyncpg://almanac@127.0.0.1:5434/almanac"


@pytest.mark.parametrize(
    "url",
    [
        "mysql+aiomysql://almanac@127.0.0.1/almanac",
        "postgresql://almanac@127.0.0.1/almanac",  # без драйвера: SQLAlchemy взял бы psycopg2, которого нет
        "postgres://almanac@127.0.0.1/almanac",  # так адрес выдаёт панель хостинга
        "postgresql+psycopg://almanac@127.0.0.1/almanac",
        "127.0.0.1:5434/almanac",
        "",
    ],
)
def test_database_url_must_name_the_asyncpg_driver(url):
    with pytest.raises(ValidationError, match=r"DATABASE_URL must start with postgresql\+asyncpg://"):
        Settings(_env_file=None, database_url=url)


def test_a_refused_database_url_does_not_leak_its_password():
    with pytest.raises(ValidationError) as refused:
        Settings(_env_file=None, database_url="postgres://almanac:hunter2-not-a-real-one@db.example/almanac")
    assert "hunter2" not in str(refused.value)


def test_good_database_url_is_kept_as_is():
    url = "postgresql+asyncpg://almanac:pw@db.example:5432/almanac"
    assert Settings(_env_file=None, database_url=url).database_url == url
