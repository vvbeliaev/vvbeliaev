"""Bot API Telegram: отправка, кнопки и приём сообщений длинным опросом.

Токен стоит в адресе запроса, поэтому исключения httpx наружу не выходят:
в их тексте есть адрес. Наружу идёт `RuntimeError` без адреса.
"""

import logging
from typing import Any

import httpx

API = "https://api.telegram.org"

# httpx пишет адрес каждого запроса на уровне INFO, а в адресе стоит токен.
logging.getLogger("httpx").setLevel(logging.WARNING)


class Telegram:
    def __init__(self, token: str, chat_id: int, http: httpx.AsyncClient | None = None) -> None:
        self._base = f"{API}/bot{token}"
        self._chat_id = chat_id
        self._http = http or httpx.AsyncClient(timeout=40)

    async def _call(self, method: str, **payload: Any) -> Any:
        try:
            response = await self._http.post(f"{self._base}/{method}", json=payload)
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError(f"telegram {method}: {type(error).__name__}") from None
        if not isinstance(data, dict) or not data.get("ok"):
            description = data.get("description") if isinstance(data, dict) else "unexpected answer"
            raise RuntimeError(f"telegram {method}: {description}")
        return data["result"]

    async def send(self, text: str, buttons: list[tuple[str, str]] | None = None) -> int:
        payload: dict[str, Any] = {"chat_id": self._chat_id, "text": text}
        if buttons:
            row = [{"text": label, "callback_data": data} for label, data in buttons]
            payload["reply_markup"] = {"inline_keyboard": [row]}
        return (await self._call("sendMessage", **payload))["message_id"]

    async def answer(self, callback_id: str, text: str = "") -> None:
        await self._call("answerCallbackQuery", callback_query_id=callback_id, text=text)

    async def clear_buttons(self, message_id: int) -> None:
        await self._call(
            "editMessageReplyMarkup", chat_id=self._chat_id, message_id=message_id,
            reply_markup={"inline_keyboard": []},
        )

    async def updates(self, offset: int | None = None, timeout: int = 25) -> list[dict]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        return await self._call("getUpdates", **payload)
