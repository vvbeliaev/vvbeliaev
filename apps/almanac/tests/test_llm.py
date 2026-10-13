"""Модель собеседника по настройке: цепочка `провайдер:модель`, ключ на провайдера, откат по порядку."""

import logging

import pytest

from almanac import llm

KEYS = {"anthropic": "a-key", "google": "g-key"}
CHAIN = "anthropic:claude-haiku-5-5,google:gemini-3.8-flash"


def test_a_chain_is_read_in_order():
    assert llm.routes(" anthropic:claude-haiku-5-5 , google:gemini-3.8-flash ") == (
        llm.Route("anthropic", "claude-haiku-5-5"),
        llm.Route("google", "gemini-3.8-flash"),
    )


def test_a_link_may_name_how_deep_it_thinks():
    assert llm.routes("anthropic:claude-haiku-5-5@medium,google:gemini-3.8-flash") == (
        llm.Route("anthropic", "claude-haiku-5-5", "medium"),
        llm.Route("google", "gemini-3.8-flash"),
    )


@pytest.mark.parametrize(
    "spec",
    [
        "anthropic:claude-haiku-5-5@",  # глубина объявлена и не названа
        "anthropic:claude-haiku-5-5@deep",  # такой ступени нет
        "anthropic:claude-haiku-5-5@low@high",
        "",
        " ",
        "gemini-3.8-flash",  # без провайдера: чья это модель, угадывать не станем
        "openai:gpt-6",  # провайдер, которого здесь нет
        "anthropic:",
        ":claude-haiku-5-5",
        "anthropic:claude-haiku-5-5,",  # пустое звено
        "anthropic: claude haiku",
    ],
)
def test_a_bad_chain_is_refused(spec):
    with pytest.raises(ValueError):
        llm.routes(spec)


def test_an_unknown_provider_is_named_with_the_known_ones():
    with pytest.raises(ValueError, match=r"openai.*anthropic.*google"):
        llm.routes("openai:gpt-6")


def test_one_link_is_that_provider_with_its_own_key():
    built = llm.model(llm.routes("anthropic:claude-haiku-5-5"), KEYS, thinking="low")
    assert (built.system, built.model_name) == ("anthropic", "claude-haiku-5-5")
    assert built.client.api_key == "a-key"

    built = llm.model(llm.routes("google:gemini-3.8-flash"), KEYS, thinking="low")
    assert (built.system, built.model_name) == ("google", "gemini-3.8-flash")
    assert built.client._api_client.api_key == "g-key"


def test_claude_thinks_as_deep_as_told_and_caches_the_constant_prompt():
    built = llm.model(llm.routes("anthropic:claude-haiku-5-5"), KEYS, thinking="medium")
    assert built.settings == {"thinking": "medium", "cache": True}


def test_gemini_thinks_as_deep_as_told_and_keeps_its_thoughts_to_itself():
    built = llm.model(llm.routes("google:gemini-3.8-flash"), KEYS, thinking="medium")
    # Свой параметр Google, а не общий `thinking`: общий заодно просит пересказ мыслей в каждом ответе.
    assert built.settings == {"google_thinking_config": {"thinking_level": "medium"}}


def test_a_link_thinks_as_deep_as_it_names_and_the_rest_as_told():
    built = llm.model(llm.routes("anthropic:claude-haiku-5-5@medium,google:gemini-3.8-flash"), KEYS, thinking="low")
    claude, gemini = built.models
    assert claude.settings == {"thinking": "medium", "cache": True}
    assert gemini.settings == {"google_thinking_config": {"thinking_level": "low"}}


def test_a_chain_falls_back_in_the_order_written():
    built = llm.model(llm.routes(CHAIN), KEYS, thinking="low")
    assert [(link.system, link.model_name) for link in built.models] == [
        ("anthropic", "claude-haiku-5-5"),
        ("google", "gemini-3.8-flash"),
    ]


def test_a_link_without_a_key_is_skipped_and_said_so(caplog):
    with caplog.at_level(logging.WARNING, logger="almanac.llm"):
        built = llm.model(llm.routes(CHAIN), {"anthropic": "", "google": "g-key"}, thinking="low")
    assert (built.system, built.model_name) == ("google", "gemini-3.8-flash")
    # В журнале — какое звено выпало; ключей там нет.
    assert "anthropic:claude-haiku-5-5" in caplog.text
    assert "@" not in caplog.text  # глубина не названа — в имени звена её нет
    assert "g-key" not in caplog.text


def test_a_chain_left_without_any_of_its_keys_is_no_model_and_says_so(caplog):
    # Ключ есть, но не того провайдера: собеседник выключен, и владелец должен узнать об этом из журнала.
    with caplog.at_level(logging.WARNING, logger="almanac.llm"):
        built = llm.model(llm.routes("anthropic:claude-haiku-5-5"), {"anthropic": "", "google": "g-key"}, thinking="low")
    assert built is None
    assert "anthropic:claude-haiku-5-5" in caplog.text
    assert "g-key" not in caplog.text


def test_no_keys_no_model_and_no_alarm(caplog):
    with caplog.at_level(logging.WARNING, logger="almanac.llm"):
        assert llm.model(llm.routes(CHAIN), {}, thinking="low") is None
    # Без единого ключа собеседника просто нет: это настройка, а не сбой.
    assert caplog.text == ""
