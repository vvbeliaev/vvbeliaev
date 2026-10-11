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
    "guide", "ls", "grep", "read", "note", "dismiss", "write", "edit", "remove", "history",
    "item_add", "item_update", "items",
}


async def _inbox(api):
    return (await api.get("/api/file", params={"path": "views/inbox.md"})).json()["text"]


async def test_health(api):
    response = await api.get("/healthz")
    assert (response.status_code, response.json()) == (200, {"ok": True})


async def test_tool_names_are_operation_ids(api):
    spec = (await api.get("/openapi.json")).json()
    names = {operation["operationId"] for methods in spec["paths"].values() for operation in methods.values()}
    assert names == TOOLS


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

    history = (await api.get("/api/pages/history", params={"path": ANNA})).json()
    assert [(row["rev"], row["reason"]) for row in history] == [(2, "переезд"), (1, "новый человек")]

    removed = await api.post("/api/pages/remove", json={"path": ANNA, "rev": 2, "reason": "ошибка"})
    assert removed.json()["rev"] == 3
    assert (await api.get("/api/file", params={"path": ANNA})).status_code == 404


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

    week = (await api.get("/api/items", params={"from": "2026-10-12", "to": "2026-10-18"})).json()
    assert {row["title"] for row in week} == {"Купить молоко", "Английский"}
    shopping = (await api.get("/api/items", params={"list": "shopping"})).json()
    assert [row["id"] for row in shopping] == [item["id"]]

    done = await api.patch(f"/api/items/{item['id']}", json={"rev": 1, "status": "done", "reason": "куплено"})
    assert (done.json()["status"], done.json()["rev"]) == ("done", 2)
    assert (await api.get("/api/items", params={"list": "shopping"})).json() == []

    aware = await api.post(
        "/api/items",
        json={"kind": "event", "title": "Звонок", "at": "2026-10-12T18:00+02:00",
              "said": "звонок в шесть", "reason": "встреча"},
    )
    assert aware.status_code == 422
    assert "without an offset" in aware.json()["detail"]


async def test_tree_grep_and_guide(api):
    await api.put("/api/pages", json=PAGE)
    catalog = (await api.get("/api/tree", params={"path": "pages", "depth": 2})).json()
    assert {"path": ANNA, "kind": "file", "description": "Подруга из Берлина"} in catalog

    found = (await api.get("/api/grep", params={"pattern": "берлин", "path": "pages"})).json()
    assert {match["path"] for match in found} == {ANNA}

    guide = (await api.get("/api/guide")).json()
    assert guide["text"].startswith("# almanac guide")
    assert "people" in guide["types"]
