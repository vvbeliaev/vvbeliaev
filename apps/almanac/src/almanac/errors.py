class Refused(Exception):
    """Запрос отклонён. Текст — инструкция вызывающему: что исправить."""

    status = 422


class NotFound(Refused):
    status = 404


class Conflict(Refused):
    """Версия разошлась: объект изменился после чтения."""

    status = 409
