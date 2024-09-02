import os
import urllib3
from datetime import datetime
from typing import Dict, Any

import requests
from zeep import Client, Settings
from zeep.helpers import serialize_object
from zeep.plugins import HistoryPlugin
from zeep.transports import Transport
from zeep.xsd import ComplexType, Element, String

from src.config import TZ, PRODUCTION, OPS_SSH_HOST, OPS_SSH_PORT, OPS_SSH_USER, OPS_SSH_PRIVATE_KEY_FILE, OPS_SERVER, \
    OPS_PORT, OPS_CONTRACT_ID
from src.utils.loggers import get_logger

if not PRODUCTION:
    import paramiko
    from sshtunnel import SSHTunnelForwarder


class OpsApi:

    def __init__(self):
        self.logger = get_logger(name="OPS-API", filename="celery.log")
        self.now = datetime.now(tz=TZ)
        self.today = self.now.date()
        self.history = HistoryPlugin()

        if PRODUCTION:
            self.host = OPS_SSH_HOST
            self.port = OPS_SSH_PORT
        else:
            urllib3.disable_warnings()
            self.host = "localhost"
            self.port = 22553
            self.tunnel_forwarder = SSHTunnelForwarder(
                ssh_address_or_host=(OPS_SSH_HOST, OPS_SSH_PORT),
                ssh_username=OPS_SSH_USER,
                ssh_pkey=paramiko.RSAKey.from_private_key_file(OPS_SSH_PRIVATE_KEY_FILE),
                remote_bind_address=(OPS_SERVER, OPS_PORT),
                local_bind_address=(self.host, self.port)
            )

    def get_client(self, endpoint_tag: str) -> Client:
        session = requests.Session()
        if not PRODUCTION:
            session.verify = False
        session.headers.update({
            'Content-Type': 'text/xml; charset=utf-8',
            'Accept': 'application/soap+xml'
        })
        transport = Transport(session=session)
        settings = Settings(strict=False, xml_huge_tree=True)
        wsdl_url = f"https://{self.host}:{self.port}/ws/{endpoint_tag}?wsdl"
        client = Client(wsdl_url, transport=transport, settings=settings, plugins=[self.history])
        return client

    def __parse_elements(self, elements):
        all_elements = {}
        for name, element in elements:
            all_elements[name] = {}
            all_elements[name]['optional'] = element.is_optional
            if hasattr(element.type, 'elements'):
                all_elements[name]['type'] = self.__parse_elements(element.type.elements)
            else:
                all_elements[name]['type'] = str(element.type)

        return all_elements

    def show_wsdl_methods(self, endpoint_tag: str, method: str | None = None) -> None:
        interface = {}

        if not PRODUCTION:
            self.tunnel_forwarder.start()

        client = self.get_client(endpoint_tag)
        services = client.wsdl.services.values()

        if not PRODUCTION:
            self.tunnel_forwarder.close()

        for service in services:
            interface[service.name] = {}
            for port in service.ports.values():
                interface[service.name][port.name] = {}
                operations = {}
                for operation in port.binding._operations.values():
                    operations[operation.name] = {}
                    operations[operation.name]['input'] = {}
                    elements = operation.input.body.type.elements
                    operations[operation.name]['input'] = self.__parse_elements(elements)

                interface[service.name][port.name]['operations'] = operations

        text = f" {os.linesep}"
        to_break = False
        for service_name, service_data in interface.items():
            text += f"{service_name}{os.linesep}"
            for port_name, port_data in service_data.items():
                text += f" {port_name}{os.linesep}"
                if method:
                    text += f" {os.linesep}"
                    text += f"   -------------------------------------{os.linesep}"
                    text += f"   Method: {method}{os.linesep}"
                    text += f"   Params:{os.linesep}"
                    for param_name, param_data in port_data['operations'][method]['input'].items():
                        text += f"      {param_name}: {param_data}{os.linesep}"

                    to_break = True
                    break

                else:
                    for operation_name, operation_data in port_data['operations'].items():
                        text += f" {os.linesep}"
                        text += f"   -------------------------------------{os.linesep}"
                        text += f"   Method: {operation_name}{os.linesep}"
                        text += f"   Params:{os.linesep}"
                        for param_name, param_data in operation_data['input'].items():
                            text += f"      {param_name}: {param_data}{os.linesep}"

            if to_break:
                break

        text += f" {os.linesep}"
        print(text)

    def request(self, endpoint_tag: str, method: str, params: Dict[str, Any] = None) -> ComplexType:
        if params is None:
            params = {}

        header = ComplexType([
            Element('login', String()),
            Element('password', String())
        ])
        header_value = header(login='cargofuel@cargonomica.com', password='DBr>8qshPWkZCd?')

        client = self.get_client(endpoint_tag)
        func = getattr(client.service, method)
        result = func(**params, _soapheaders=[header_value])
        return result

    def get_remote_cards(self) -> Any:
        if not PRODUCTION:
            self.tunnel_forwarder.start()

        endpoint_tag = "Cards"
        method = "getCards"
        params = {"idContract": OPS_CONTRACT_ID}
        result = serialize_object(self.request(endpoint_tag, method, params))
        cards = result["cards"]["item"]
        session_id = result.get("idSession", None)
        while session_id:
            params = {"idContract": OPS_CONTRACT_ID, "idSession": session_id}
            result = serialize_object(self.request(endpoint_tag, method, params))
            cards.extend(result["cards"]["item"])
            session_id = result.get("idSession", None)

        if not PRODUCTION:
            self.tunnel_forwarder.close()

        return cards
