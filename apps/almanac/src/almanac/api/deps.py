from typing import Annotated

from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from almanac import tree
from almanac.db import Database
from almanac.identity import Caller, caller
from almanac.store.source import Source


def _db(request: Request) -> Database:
    return request.app.state.db


def _ctx(request: Request) -> tree.Context:
    return request.app.state.ctx


Db = Annotated[Database, Depends(_db)]
Ctx = Annotated[tree.Context, Depends(_ctx)]
Who = Annotated[Caller, Depends(caller)]


class Strict(BaseModel):
    """Тело запроса: лишнее поле — отказ, а не молча выброшенный параметр."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Sourced(Strict):
    """Поля правила источника, общие для пишущих ручек."""

    facts: list[str] = Field(default_factory=list, description="Ids of recorded facts this is built from.")
    said: str | None = Field(default=None, description="The owner's words, verbatim. Recorded as a new fact.")
    reason: str = Field(description="One line for the journal: why this change.")

    def source(self) -> Source:
        return Source(facts=tuple(self.facts), said=self.said, restructure=getattr(self, "restructure", False))
