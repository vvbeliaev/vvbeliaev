from datetime import timedelta

import pytest

from almanac import checks
from almanac.errors import Refused

TYPES = {"people", "areas", "projects", "topics", "ideas"}


def test_page_path_accepts_type_and_slug():
    assert checks.page_path("pages/people/anna-petrova.md", TYPES) == ("people", "anna-petrova")


@pytest.mark.parametrize(
    "path",
    [
        "people/anna.md",
        "pages/people/Anna.md",
        "pages/people/anna",
        "pages/people/anna.md\n",
        "pages/people/anna--b.md",
        "pages/people/sub/anna.md",
        "pages/people/" + "a" * 61 + ".md",
    ],
)
def test_page_path_refuses_bad_shape(path):
    with pytest.raises(Refused):
        checks.page_path(path, TYPES)


def test_page_path_names_known_types():
    with pytest.raises(Refused, match="areas, ideas, people, projects, topics"):
        checks.page_path("pages/pets/rex.md", TYPES)


def test_one_line_trims_and_limits():
    assert checks.one_line("  Подруга из Берлина ", name="description", limit=200) == "Подруга из Берлина"
    for bad in ("", "   ", "две\nстроки", "x" * 201):
        with pytest.raises(Refused, match="description"):
            checks.one_line(bad, name="description", limit=200)


def test_norm_name_ignores_case_yo_and_spaces():
    assert checks.norm_name("  Алёна   Иванова ") == checks.norm_name("алена иванова")


def test_fragment_must_be_unique():
    checks.fragment("раз два три", "два")
    with pytest.raises(Refused, match="not found"):
        checks.fragment("раз два три", "пять")
    with pytest.raises(Refused, match="occurs 2 times"):
        checks.fragment("раз два раз", "раз")
    with pytest.raises(Refused, match="empty"):
        checks.fragment("раз", "")


@pytest.mark.parametrize(
    "text",
    [
        "ключ " + "sk-" + "a" * 24,
        "токен " + "ghp_" + "A" * 36,
        "-----BEGIN RSA " + "PRIVATE KEY-----",
        "карта 4111 1111 1111 1111",
        "карта 4111-1111-1111-1111",
        "карта 4111 1111 1111 1111 123",
        "4111111111111111 12/25",
        "exp 12/25 4111 1111 1111 1111",
        "2 4111111111111111",
        "4111.1111.1111.1111",
        "4111  1111  1111  1111",
        "3782 822463 10005",
        "бот " + "1234567890" + ":" + "A" * 35,
    ],
)
def test_secret_is_refused(text):
    with pytest.raises(Refused, match="looks like a secret"):
        checks.no_secret("обычный текст", text)


@pytest.mark.parametrize(
    "text",
    [
        "встреча 2026-10-14 в 18:00",
        "заказ 4111 1111 1111 1112",
        "отметка 1760263200000",
        "отпуск 2026-10-14 - 2026-10-21",
        "2026-10-14 2026-10-21 2026-10-28",
        None,
        "",
    ],
)
def test_ordinary_text_passes(text):
    checks.no_secret(text)


def test_duration_parses_offsets():
    assert checks.duration("PT0M") == timedelta(0)
    assert checks.duration("PT30M") == timedelta(minutes=30)
    assert checks.duration("PT1H") == timedelta(hours=1)
    assert checks.duration("P1D") == timedelta(days=1)
    assert checks.duration("P1DT2H") == timedelta(days=1, hours=2)
    assert checks.duration("P1W") == timedelta(weeks=1)


@pytest.mark.parametrize(
    "value", ["", "P", "PT", "P1DT", "1H", "PT1S", "-PT1H", "PT1.5H", "P99999999999D", "P10000W", "PT1H\n"]
)
def test_duration_refuses_bad_values(value):
    with pytest.raises(Refused, match="bad duration"):
        checks.duration(value)


def test_reason_is_one_line_without_secrets():
    assert checks.reason("  правка  ") == "правка"
    for bad in ("", "две\nстроки", "x" * 201):
        with pytest.raises(Refused, match="reason"):
            checks.reason(bad)
    with pytest.raises(Refused, match="looks like a secret"):
        checks.reason("ключ " + "sk-" + "a" * 24)
