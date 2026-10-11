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
