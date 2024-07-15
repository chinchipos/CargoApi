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
