"""Проверки, общие для любого приложения с агентом: над разницей состояний и над ответом."""

from evals.core.scenarios import Checks
from evals.core.state import Outcome

generic = Checks()


@generic.register
def untouched(result: Outcome, *, collections: list[str]) -> str | None:
    """Разговор не добавил, не убрал и не поменял ни одной записи в этих коллекциях."""
    touched = {collection: keys for collection in collections if (keys := result.diff.touched(collection))}
    return f"touched {touched}" if touched else None


@generic.register
def added(result: Outcome, *, collection: str, count: int) -> str | None:
    """Разговор добавил в коллекцию ровно столько записей."""
    made = len(result.diff.added.get(collection, []))
    return None if made == count else f"{collection}: added {made}, want {count}"


@generic.register
def says(result: Outcome, *, words: list[str]) -> str | None:
    """Последний ответ называет каждое из слов, без учёта регистра."""
    answer = result.answers[-1].casefold()
    missing = [word for word in words if word.casefold() not in answer]
    return f"the answer lacks {missing}" if missing else None


@generic.register
def asks(result: Outcome) -> str | None:
    """Последний ответ — вопрос владельцу."""
    return None if "?" in result.answers[-1] else "no question in the answer"
