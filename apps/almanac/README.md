# almanac

Личный серверный источник истины: факты, страницы, задачи и события, доступ
для моделей через MCP. Замысел и границы POC — в [SPEC.md](./SPEC.md).

Состояние: собраны ядро и HTTP API (этап 1 из 4). Доступа и MCP ещё нет —
наружу не выставлять.

```bash
cd apps/almanac
uv run pytest -q
uv run uvicorn almanac.app:create_app --factory --reload
```
