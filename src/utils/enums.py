from enum import Enum, StrEnum


class Role(Enum):

    CARGO_SUPER_ADMIN = {
        'title': 'Суперадмин ПроАВТО',
        'description': 'Суперпользователь информационной системы с максимальными правами.'
    }
    CARGO_MANAGER = {
        'title': 'Менеджер ПроАВТО',
        'description': 'Менеджер с административными правами по отношению к определенному списку организаций.'
    }
    COMPANY_ADMIN = {
        'title': 'Администратор',
        'description': 'Администратор организации - сотрудник организации c правами создания и администрирования \
                        пользователей этой организации, выставления лимитов и прочими административными функциями. \
                        Имеет права на просмотр всей информации по компании.'
    }
    COMPANY_LOGIST = {
        'title': 'Логист',
        'description': 'Сотрудник организации. Имеет право просматривать определенный \
                        список карт этой организации, менять лимиты, создавать водителей.'
    }
    COMPANY_DRIVER = {
        'title': 'Водитель',
        'description': 'Водитель организации. Имеет права на просмотр транзакций по своим картам.'
    }


class Permition(StrEnum):

    DB_SYNC = 'DB_SYNC'


class LogType(StrEnum):
    USERS = 'USERS'
    CARDS = 'CARDS'
    CARS = 'CARS'
    COMPANIES = 'COMPANIES'
    SYSTEMS = 'SYSTEMS'
    TRANSACTIONS = 'TRANSACTIONS'
    TARIFFS = 'TARIFFS'
    COMMON = 'COMMON'
