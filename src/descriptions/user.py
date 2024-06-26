user_tag_description = "Операции с пользователями и сотрудниками."

get_me_description = (
    """
    Получение собственного профиля.
    """
)

create_user_description = (
    "Создание пользователя.<br><br>"
    "Имя пользователя задается в формате Email (см. пример).<br><br>"
    "Сложность пароля зависит от назначаемой роли:<br>"
    "<u>Водитель организации</u>: буквы или цифры, длина - не менее 3 знаков.<br>" 
    "<u>Логист организации</u>: буквы, не менее 1 цифры, длина - не менее 8 знаков.<br>"
    "<u>Администратор организации</u>: буквы, не менее 1 цифры, длина - не менее 8 знаков.<br>"
    "<u>Менеджер ПроАВТО</u>: буквы, не менее 1 цифры, длина - не менее 8 знаков.<br>"
    "<u>Суперадмин ПроАВТО</u>: строчные и прописные буквы, не менее 1 цифры, не менее 1 спецсимвола, длина - "
    "не менее 8 знаков.<br><br>"
    "Пользователю может быть присвоена только одна роль.<br>"
    "Пользователям с ролями <Водитель организации>, <Логист организации>, <Администратор организации> должна быть "
    "назначена организация с помощью параметра **company_id**.<br>"
    "Пользователю с ролью <Менеджер ПроАВТО> должна быть назначена хотя бы одна организация с помощью параметра "
    "**managed_companies**<br>"
    "Пользователю с ролью <Суперадмин ПроАВТО> организация не назначается."
)

get_companies_users_description = "Получение всех сотрудников организаций"

get_cargo_users_description = "Получение всех сотрудников ПроАВТО"

edit_user_description = "Редактирование пользователя"

delete_user_description = "Удаление пользователя"
