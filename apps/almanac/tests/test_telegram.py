import httpx
import pytest

from almanac.telegram import Telegram

TOKEN = "12345678" + ":" + "x" * 35


def _client(handler):
    return Telegram(TOKEN, 42, http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_send_posts_text_and_buttons():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    message_id = await _client(handler).send("⏰ 18:00 · Английский", [("Готово", "done:r_1")])
    assert message_id == 7
    assert seen["path"].endswith("/sendMessage")
    assert seen["body"]["chat_id"] == 42
    assert seen["body"]["reply_markup"] == {"inline_keyboard": [[{"text": "Готово", "callback_data": "done:r_1"}]]}


async def test_errors_never_carry_the_token():
    def refuse(_request):
        return httpx.Response(200, json={"ok": False, "description": "chat not found"})

    def explode(request):
        raise httpx.ConnectError("boom", request=request)

    for handler in (refuse, explode):
        with pytest.raises(RuntimeError) as failure:
            await _client(handler).send("текст")
        assert TOKEN not in str(failure.value)
        assert TOKEN not in repr(failure.value.__cause__)


async def test_requests_do_not_log_the_token(caplog):
    """httpx пишет адрес каждого запроса на уровне INFO, а в адресе стоит токен."""

    def handler(_request):
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    with caplog.at_level("DEBUG"):
        await _client(handler).send("текст")
    assert TOKEN not in caplog.text


async def test_answer_and_clear_buttons_call_their_methods():
    seen = []

    def handler(request):
        seen.append((request.url.path.rsplit("/", 1)[1], __import__("json").loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": True})

    client = _client(handler)
    await client.answer("cb1", "Готово")
    await client.clear_buttons(7)
    assert seen == [
        ("answerCallbackQuery", {"callback_query_id": "cb1", "text": "Готово"}),
        ("editMessageReplyMarkup", {"chat_id": 42, "message_id": 7, "reply_markup": {"inline_keyboard": []}}),
    ]


async def test_updates_omit_the_offset_until_there_is_one():
    bodies = []

    def handler(request):
        bodies.append(__import__("json").loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": [{"update_id": 5}]})

    client = _client(handler)
    assert await client.updates() == [{"update_id": 5}]
    await client.updates(6, timeout=10)
    assert "offset" not in bodies[0]
    assert (bodies[1]["offset"], bodies[1]["timeout"]) == (6, 10)
    assert bodies[1]["allowed_updates"] == ["message", "callback_query"]


async def test_a_non_json_answer_is_a_clean_error():
    def handler(_request):
        return httpx.Response(502, text="<html>bad gateway</html>")

    with pytest.raises(RuntimeError) as failure:
        await _client(handler).send("текст")
    assert TOKEN not in str(failure.value)
