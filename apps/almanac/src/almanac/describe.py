"""`get_schema`: описание инструментов для модели, которая собирает вызовы в скрипт.

Стандартный `get_schema` печатает имена и типы параметров, а форматы и допустимые значения
лежат в `description` и остаются невидимыми; ответ он показывает как `value (object)`.
Здесь у каждого инструмента — описание, параметры с их смыслом и значениями и поля ответа.
"""

import json
from collections.abc import Sequence
from typing import Annotated, Any

from fastmcp.experimental.transforms.code_mode import GetToolCatalog
from fastmcp.server.context import Context
from fastmcp.tools import Tool

FORMATS = {"date": "date", "date-time": "datetime"}
SCALARS = {"integer": "int", "number": "number", "boolean": "bool"}


def _resolve(schema: Any, defs: dict[str, Any]) -> Any:
    """Локальная ссылка `#/$defs/Имя` заменяется самим описанием."""
    ref = schema.get("$ref") if isinstance(schema, dict) else None
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        return defs.get(ref.removeprefix("#/$defs/"), schema)
    return schema


def _literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _type(schema: Any, defs: dict[str, Any]) -> str:
    """Тип одной строкой, значения закрытого набора — буквально: `"task" | "event" | null`."""
    schema = _resolve(schema, defs)
    if not isinstance(schema, dict):
        return "any"
    if "const" in schema:
        return _literal(schema["const"])
    if "enum" in schema:
        return " | ".join(_literal(value) for value in schema["enum"])
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return " | ".join(dict.fromkeys(_type(branch, defs) for branch in schema[key]))
    kind = schema.get("type")
    if kind == "array":
        return f"list[{_type(schema.get('items'), defs)}]"
    if kind == "string":
        return FORMATS.get(schema.get("format"), "string")
    if kind == "object":
        values = schema.get("additionalProperties")
        named = isinstance(values, dict) and "properties" not in schema
        return f"dict[string, {_type(values, defs)}]" if named else "object"
    return SCALARS.get(kind, kind) if isinstance(kind, str) else "any"


def _line(name: str, schema: Any, defs: dict[str, Any], *, qualifier: str = "", indent: int = 0) -> str:
    """`- имя (тип, признак) — описание`."""
    schema = _resolve(schema, defs)
    described = schema.get("description") if isinstance(schema, dict) else None
    qualified = ", ".join(part for part in (_type(schema, defs), qualifier) if part)
    return f"{'    ' * indent}- {name} ({qualified})" + (f" — {described}" if described else "")


def _parameters(schema: dict[str, Any] | None) -> list[str]:
    schema = schema or {}
    defs, required = schema.get("$defs") or {}, set(schema.get("required") or [])
    lines = []
    for name, field in (schema.get("properties") or {}).items():
        if name in required:
            qualifier = "required"
        elif isinstance(field, dict) and field.get("default") is not None:
            qualifier = f"default {_literal(field['default'])}"
        else:
            qualifier = "optional"
        lines.append(_line(name, field, defs, qualifier=qualifier))
    return lines


def _members(field: Any, defs: dict[str, Any]) -> dict[str, Any]:
    """Поля объекта, который лежит в поле ответа: сам объект или элемент списка объектов."""
    field = _resolve(field, defs)
    if isinstance(field, dict) and field.get("type") == "array":
        field = _resolve(field.get("items"), defs)
    return (field.get("properties") or {}) if isinstance(field, dict) else {}


def _answer(schema: dict[str, Any] | None) -> list[str]:
    """Поля ответа и на один уровень глубже — поля объектов в списках."""
    schema = schema or {}
    defs = schema.get("$defs") or {}
    lines = []
    for name, field in (schema.get("properties") or {}).items():
        lines.append(_line(name, field, defs))
        lines.extend(_line(inner, value, defs, indent=1) for inner, value in _members(field, defs).items())
    return lines


def describe(tool: Tool) -> str:
    """Одно описание инструмента: что делает, что принимает и что возвращает."""
    params = _parameters(tool.parameters)
    lines = [f"### {tool.name}", "", (tool.description or "").strip(), ""]
    lines += ["Parameters:", *params] if params else ["Parameters: none"]
    if tool.output_schema:
        lines += ["", "Returns:", *_answer(tool.output_schema)]
    return "\n".join(lines)


def describe_all(tools: Sequence[Tool], missing: Sequence[str], known: Sequence[str]) -> str:
    blocks = [describe(tool) for tool in tools]
    if missing:
        blocks.append(f"Unknown tools: {', '.join(missing)}. Known: {', '.join(sorted(known))}")
    return "\n\n".join(blocks)


class GetSchema:
    """Фабрика инструмента `get_schema` для `CodeMode(discovery_tools=…)`."""

    def __init__(self, *, name: str = "get_schema") -> None:
        self._name = name

    def __call__(self, get_catalog: GetToolCatalog) -> Tool:
        async def get_schema(
            tools: Annotated[list[str], "Tool names to describe, like ['item_add', 'items']"],
            ctx: Context = None,  # type: ignore[assignment]
        ) -> str:
            """Describe tools by name: what each parameter takes (allowed values, formats) and
            the fields of the answer. Call it before the first call to a tool you have not used."""
            catalog = {tool.name: tool for tool in await get_catalog(ctx)}
            found = [catalog[name] for name in tools if name in catalog]
            return describe_all(found, [name for name in tools if name not in catalog], list(catalog))

        return Tool.from_function(fn=get_schema, name=self._name)
