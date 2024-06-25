from password_strength import PasswordPolicy

from src.utils.exceptions import BadRequestException
from src.utils import enums


def test_password_strength(role_name: str, password: str) -> None:

    if role_name == enums.Role.CARGO_SUPER_ADMIN.name:
        policy = PasswordPolicy.from_names(
            length=8,
            uppercase=1,
            numbers=1,
            special=1
        )
        strength = 'не менее 8 знаков, заглавные и прописные буквы, цифры, специальные символы.'

    elif role_name == enums.Role.CARGO_MANAGER.name:
        policy = PasswordPolicy.from_names(
            length=8,
            numbers=1,
        )
        strength = 'не менее 8 знаков, прописные буквы или цифры.'

    elif role_name == enums.Role.COMPANY_ADMIN.name:
        policy = PasswordPolicy.from_names(
            length=8,
            numbers=1,
        )
        strength = 'не менее 8 знаков, строчные буквы или цифры.'

    elif role_name == enums.Role.COMPANY_LOGIST.name:
        policy = PasswordPolicy.from_names(
            length=8,
            numbers=1,
        )
        strength = 'не менее 8 знаков, строчные буквы или цифры.'

    elif role_name == enums.Role.COMPANY_DRIVER.name:
        policy = PasswordPolicy.from_names(
            length=3,
        )
        strength = 'не менее 3 знаков.'

    else:
        policy = PasswordPolicy.from_names(
            length=8,
            uppercase=1,
            numbers=1,
            special=1
        )
        strength = 'не менее 8 знаков, заглавные и прописные буквы, цифры, специальные символы.'

    if policy.test(password):
        raise BadRequestException(message='Пароль не удовлетворяет требованиям сложности: ' + strength)
