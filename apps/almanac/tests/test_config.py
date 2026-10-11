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
