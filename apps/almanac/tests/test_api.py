import pytest

ANNA = "pages/people/anna.md"
PAGE = {
    "path": ANNA,
    "title": "Анна Петрова",
    "description": "Подруга из Берлина",
    "body": "Живёт в Берлине.\n",
    "aliases": ["Аня"],
    "said": "Аня переехала в Берлин",
    "reason": "новый человек",
}
TOOLS = {
    "guide", "ls", "grep", "read", "note", "dismiss", "write", "edit", "move", "remove", "history",
    "item_add", "item_update", "items",
}


async def _inbox(api):
    return (await api.get("/api/file", params={"path": "views/inbox.md"})).json()["text"]


async def test_health(api):
    response = await api.get("/healthz")
    assert (response.status_code, response.json()) == (200, {"ok": True})


async def test_tool_names_are_operation_ids(app):
    spec = app.openapi()
    names = {operation["operationId"] for methods in spec["paths"].values() for operation in methods.values()}
    assert names == TOOLS


async def test_interactive_docs_are_off(anon):
    # Схема нужна MCP и берётся из `app.openapi()`; наружу она не торчит.
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert (await anon.get(path)).status_code == 404, path


async def test_page_round_trip(api):
    created = await api.put("/api/pages", json=PAGE)
    assert created.status_code == 200
    assert (created.json()["rev"], created.json()["warnings"]) == (1, [])

    read = (await api.get("/api/file", params={"path": ANNA})).json()
    assert (read["rev"], read["writable"]) == (1, True)
    assert "Живёт в Берлине." in read["text"]

    edited = await api.post(
        "/api/pages/edit",
        json={"path": ANNA, "old": "Берлине", "new": "Мюнхене", "rev": 1,
              "said": "Аня переехала в Мюнхен", "reason": "переезд"},
    )
    assert edited.json()["rev"] == 2

    history = (await api.get("/api/pages/history", params={"path": ANNA})).json()["revisions"]
    assert [(row["rev"], row["reason"]) for row in history] == [(2, "переезд"), (1, "новый человек")]

    removed = await api.post("/api/pages/remove", json={"path": ANNA, "rev": 2, "reason": "ошибка"})
    assert removed.json()["rev"] == 3
    assert (await api.get("/api/file", params={"path": ANNA})).status_code == 404


async def test_move_renames_a_page_and_the_links_follow(api):
    await api.put("/api/pages", json={**PAGE, "body": "Живёт в Берлине.\n"})
    boris = {**PAGE, "path": "pages/people/boris.md", "title": "Борис", "aliases": [],
             "body": "Знает [[people/anna|Аню]].\n", "said": "Борис знает Аню"}
    await api.put("/api/pages", json=boris)

    moved = await api.post(
        "/api/pages/move",
        json={"path": ANNA, "to": "pages/people/anna-petrova.md", "rev": 1, "reason": "полное имя"},
    )
    assert moved.status_code == 200
    assert moved.json() == {"path": "pages/people/anna-petrova.md", "rev": 2, "relinked": ["pages/people/boris.md"]}

    assert (await api.get("/api/file", params={"path": ANNA})).status_code == 404
    new = (await api.get("/api/file", params={"path": "pages/people/anna-petrova.md"})).json()
    assert (new["rev"], new["backlinks"]) == (2, ["pages/people/boris.md"])
    text = (await api.get("/api/file", params={"path": "pages/people/boris.md"})).json()["text"]
    assert "[[people/anna-petrova|Аню]]" in text
    history = (await api.get("/api/pages/history", params={"path": "pages/people/anna-petrova.md"})).json()
    assert [(row["rev"], row["reason"]) for row in history["revisions"]] == [(2, "полное имя"), (1, "новый человек")]


async def test_move_refusals_carry_instructions(api):
    await api.put("/api/pages", json=PAGE)
    taken = {**PAGE, "path": "pages/projects/anna.md", "title": "Проект", "aliases": [], "said": "проект"}
    await api.put("/api/pages", json=taken)
    base = {"path": ANNA, "to": "pages/projects/anna-two.md", "rev": 1, "reason": "перенос"}

    stale = await api.post("/api/pages/move", json={**base, "rev": 9})
    assert (stale.status_code, "current rev is 1" in stale.json()["detail"]) == (409, True)
    busy = await api.post("/api/pages/move", json={**base, "to": "pages/projects/anna.md"})
    assert busy.status_code == 409
    assert "pick another slug" in busy.json()["detail"]
    unknown = await api.post("/api/pages/move", json={**base, "to": "pages/pets/anna.md"})
    assert (unknown.status_code, "unknown page type" in unknown.json()["detail"]) == (422, True)
    extra = await api.post("/api/pages/move", json={**base, "colour": "red"})
    assert extra.status_code == 422


async def test_refusals_carry_instructions(api):
    await api.put("/api/pages", json=PAGE)

    stale = await api.put("/api/pages", json={**PAGE, "rev": 9})
    assert stale.status_code == 409
    assert "current rev is 1" in stale.json()["detail"]

    sourceless = {key: value for key, value in PAGE.items() if key != "said"}
    sourceless.update(path="pages/people/boris.md", title="Борис", aliases=[])
    refused = await api.put("/api/pages", json=sourceless)
    assert refused.status_code == 422
    assert "name the source" in refused.json()["detail"]

    unknown_field = await api.put("/api/pages", json={**PAGE, "colour": "red"})
    assert unknown_field.status_code == 422


async def test_fact_inbox_and_dismiss(api):
    fact = (await api.post("/api/facts", json={"text": "купить лампочки"})).json()
    assert fact["id"].startswith("f_")
    assert fact["client"] == "local"
    assert fact["id"] in await _inbox(api)

    closed = await api.post(f"/api/facts/{fact['id']}/dismiss", json={"reason": "купил"})
    assert closed.json()["dismissed"] is True
    assert fact["id"] not in await _inbox(api)


async def test_items_flow(api):
    added = await api.post(
        "/api/items",
        json={"kind": "task", "title": "Купить молоко", "list": "shopping", "due": "2026-10-14",
              "said": "молоко кончилось", "reason": "покупка"},
    )
    assert added.status_code == 200
    item = added.json()
    assert (item["list"], item["due"], item["status"], item["rev"]) == ("shopping", "2026-10-14", "open", 1)

    event = await api.post(
        "/api/items",
        json={"kind": "event", "title": "Английский", "at": "2026-10-12T18:00", "rrule": "FREQ=WEEKLY",
              "remind": ["PT1H"], "said": "английский по понедельникам", "reason": "расписание"},
    )
    assert event.json()["at"] == "2026-10-12T18:00"

    week = (await api.get("/api/items", params={"from": "2026-10-12", "to": "2026-10-18"})).json()["items"]
    assert {row["title"] for row in week} == {"Купить молоко", "Английский"}
    shopping = (await api.get("/api/items", params={"list": "shopping"})).json()["items"]
    assert [row["id"] for row in shopping] == [item["id"]]

    done = await api.patch(f"/api/items/{item['id']}", json={"rev": 1, "status": "done", "reason": "куплено"})
    assert (done.json()["status"], done.json()["rev"]) == ("done", 2)
    assert (await api.get("/api/items", params={"list": "shopping"})).json() == {"items": []}

    aware = await api.post(
        "/api/items",
        json={"kind": "event", "title": "Звонок", "at": "2026-10-12T18:00+02:00",
              "said": "звонок в шесть", "reason": "встреча"},
    )
    assert aware.status_code == 422
    assert "without an offset" in aware.json()["detail"]


async def test_items_refuse_a_wide_window_a_far_date_and_a_dense_rule_with_a_422(api):
    wide = await api.get("/api/items", params={"from": "2020-01-01", "to": "2026-01-01"})
    assert wide.status_code == 422
    assert "narrow" in wide.json()["detail"]

    base = {"kind": "task", "title": "Когда-нибудь", "said": "когда-нибудь", "reason": "срок"}
    far = await api.post("/api/items", json={**base, "due": "9999-12-31"})
    assert far.status_code == 422
    assert "between the years 1900 and 2200" in far.json()["detail"]

    dense = await api.post("/api/items", json={**base, "due": "2026-10-14", "rrule": "FREQ=MINUTELY"})
    assert dense.status_code == 422
    assert "FREQ=HOURLY" in dense.json()["detail"]
    assert (await api.get("/api/items", params={"status": "any"})).json() == {"items": []}


async def test_tree_grep_and_guide(api):
    await api.put("/api/pages", json=PAGE)
    catalog = (await api.get("/api/tree", params={"path": "pages", "depth": 2})).json()["entries"]
    assert {"path": ANNA, "kind": "file", "description": "Подруга из Берлина"} in catalog

    found = (await api.get("/api/grep", params={"pattern": "берлин", "path": "pages"})).json()["matches"]
    assert {match["path"] for match in found} == {ANNA}

    guide = (await api.get("/api/guide")).json()
    assert guide["text"].startswith("# almanac guide")
    assert "people" in guide["types"]


async def test_guide_says_what_time_it_is_for_the_owner(api, now):
    # `now` заморожен на 10:00 UTC; у владельца Europe/Berlin, летнее время.
    guide = (await api.get("/api/guide")).json()
    assert (guide["now"], guide["tz"]) == ("2026-10-12T12:00", "Europe/Berlin")
    assert guide["day_start"] == "09:00"  # от него считают напоминания целого дня и задачи со сроком


async def test_every_answer_is_an_object_with_named_fields(app):
    """Верх ответа — объект с объявленными полями, а не список: так его читает скрипт модели."""
    spec = app.openapi()
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
            if "$ref" in schema:
                schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
            where = f"{method.upper()} {path}"
            assert schema.get("type") == "object", where
            assert schema.get("properties"), where


@pytest.mark.parametrize(
    "call, field, bad",
    [
        ("item_add", "kind", "habit"),
        ("item_update", "status", "paused"),
        ("items", "status", "closed"),
        ("items", "kind", "habit"),
        ("note", "origin", "rumor"),
    ],
)
async def test_closed_sets_are_refused_by_the_schema_naming_the_values(api, call, field, bad):
    item = {"kind": "task", "title": "Купить молоко", "said": "молоко кончилось", "reason": "покупка"}
    if call == "item_add":
        response = await api.post("/api/items", json={**item, field: bad})
    elif call == "item_update":
        response = await api.patch("/api/items/i_abcdefgh", json={"rev": 1, "reason": "правка", field: bad})
    elif call == "items":
        response = await api.get("/api/items", params={field: bad})
    else:
        response = await api.post("/api/facts", json={"text": "слух", field: bad})
    assert response.status_code == 422
    assert "Input should be" in response.json()["detail"][0]["msg"]
