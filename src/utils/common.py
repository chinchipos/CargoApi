import random
import ssl
import socket


def get_server_certificate(server: str, port: int, our_cert_path: str = None, our_key_path: str = None) -> str:
    """
    Метод используется для получения сертификата сервера в формате PEM.
    Актуален при первичной настройке или смене серверного сертификата,
    для постоянного использования не нужен.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    if our_cert_path:
        context.load_cert_chain(our_cert_path, our_key_path)
    conn = socket.create_connection((server, port))
    sock = context.wrap_socket(conn, server_hostname=server)
    sock.settimeout(10)
    try:
        der_cert = sock.getpeercert(True)
        server_cert = ssl.DER_cert_to_PEM_cert(der_cert)
    finally:
        sock.close()

    return server_cert


def make_personal_account() -> str:
    return ('000000' + str(random.randint(1, 9999999)))[-7:]


def calc_available_balance(current_balance: float, min_balance: float, overdraft_on: bool, overdraft_sum: float) \
        -> float:
    # overdraft_on - переменная добавлена в функцию для устранения ошибки когда в БД записано, что овердрафт отключен,
    # о сумма задана не нулевая
    _overdraft_sum = overdraft_sum if overdraft_on else 0
    boundary = min_balance - _overdraft_sum
    available_balance = current_balance - boundary if current_balance > boundary else 0
    print(f"current_balance: {current_balance}")
    print(f"min_balance: {min_balance}")
    print(f"overdraft_on: {overdraft_on}")
    print(f"overdraft_sum: {overdraft_sum}")
    print(f"_overdraft_sum: {_overdraft_sum}")
    print(f"boundary: {boundary}")
    print(f"available_balance: {available_balance}")
    return available_balance
