class BadRequestException(Exception):
    def __init__(self, message: str):
        self.message = message


class ForbiddenException(Exception):
    def __init__(self):
        self.message = 'Отсутствуют необходимые права доступа'


class DBException(Exception):
    def __init__(self):
        self.message = 'Ошибка при выполнении запроса к БД'
