import os
import urllib3
from datetime import datetime, timedelta, date
from typing import Dict, Any, List

import requests
from zeep import Client, Settings
from zeep.helpers import serialize_object
from zeep.plugins import HistoryPlugin
from zeep.transports import Transport
from zeep.xsd import ComplexType, Element, String

from src.config import TZ, PRODUCTION, OPS_SERVER, OPS_PORT, OPS_CONTRACT_ID
from src.utils.export_to_excel import ExportToExcel
from src.utils.loggers import get_logger

if not PRODUCTION:
    from src.config import OPS_SSH_HOST, OPS_SSH_PORT, OPS_SSH_USER, OPS_SSH_PRIVATE_KEY_FILE
    import paramiko
    from sshtunnel import SSHTunnelForwarder


class OpsApi:

    def __init__(self):
        self.logger = get_logger(name="OPS-API", filename="celery.log")
        self.now = datetime.now(tz=TZ)
        self.today = self.now.date()
        self.history = HistoryPlugin()

        if PRODUCTION:
            self.host = OPS_SERVER
            self.port = OPS_PORT
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

    def get_cards(self) -> List[Dict[str, Any]]:
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

        for card in cards:
            card["cardNumber"] = str(card["cardNumber"])

        return cards

    def get_transactions(self, transaction_days: int) -> List[Dict[str, Any]]:
        if not PRODUCTION:
            self.tunnel_forwarder.start()

        endpoint_tag = "TransactionReceipts"
        method = "getTransactionReceipts"

        date_from = self.today - timedelta(days=transaction_days)
        if date_from < date(year=2024, month=9, day=1):
            date_from = date(year=2024, month=9, day=1)
        date_from = date_from.isoformat()

        date_to = self.today + timedelta(days=1)
        date_to = date_to.isoformat()

        params = {
            "dateFrom": date_from,
            "dateTo": date_to,
        }

        result = serialize_object(self.request(endpoint_tag, method, params))
        transactions = result["transactionReceipts"]["item"]
        session_id = result.get("idSession", None)
        while session_id:
            params = {
                "dateFrom": date_from,
                "dateTo": date_to,
                "idSession": session_id
            }
            result = serialize_object(self.request(endpoint_tag, method, params))
            transactions.extend(result["transactionReceipts"]["item"])
            session_id = result.get("idSession", None)

        if not PRODUCTION:
            self.tunnel_forwarder.close()

        # В транзакции может быть несколько записей. Разбиваем до атомарных записей.
        transactions_ = []
        for transaction in transactions:
            for tr_item in transaction["receiptItem"]["item"]:
                transactions_.append({
                    "transactionID": str(transaction["transactionID"]),
                    "cardNumber": str(transaction["cardNumber"]),
                    "transactionDateTime": datetime.fromisoformat(transaction["transactionDateTime"]),
                    "terminalID": str(transaction["terminalID"]),
                    "transactionType": transaction["transactionType"],
                    "goodsID": str(tr_item["goodsID"]),
                    "priceWithoutDiscount": tr_item["priceWithoutDiscount"],
                    "price": tr_item["price"],
                    "quantity": tr_item["quantity"],
                    "amountWithoutDiscountRounded": tr_item["amountWithoutDiscountRounded"],
                    "amountRounded": tr_item["amountRounded"],
                })

        # Сортируем транзакции по времени совершения
        def sorting(tr):
            return tr['transactionDateTime']

        transactions = sorted(transactions_, key=sorting)
        return transactions

    def get_terminals(self, terminal_external_id: str = None) -> List[Dict[str, Any]]:
        if not PRODUCTION:
            self.tunnel_forwarder.start()

        endpoint_tag = "Terminals"
        method = "getTerminals"
        params = {"terminalID": int(terminal_external_id)} if terminal_external_id else None
        result = serialize_object(self.request(endpoint_tag, method, params))
        terminals = result["terminals"]["item"]
        session_id = result.get("idSession", None)
        while session_id:
            params = {"idSession": session_id}
            if terminal_external_id:
                params["terminalID"] = int(terminal_external_id)
            result = serialize_object(self.request(endpoint_tag, method, params))
            terminals.extend(result["terminals"]["item"])
            session_id = result.get("idSession", None)

        if not PRODUCTION:
            self.tunnel_forwarder.close()

        for terminal in terminals:
            terminal["terminalID"] = str(terminal["terminalID"])
            terminal["servicePointID"] = str(terminal["servicePointID"])

        if terminals:
            export = ExportToExcel()
            export.make_excel(
                data=terminals,
                headers=[k for k, v in terminals[0].items()],
                filename="OPS_TERMINALS.xlsx",
                export_dir="D:\\Temp"
            )

        return terminals

    def get_goods(self, goods_id: str = None) -> List[Dict[str, Any]]:
        if not PRODUCTION:
            self.tunnel_forwarder.start()

        endpoint_tag = "Goods"
        method = "getGoods"
        params = {"goodsID": int(goods_id)} if goods_id else None
        result = serialize_object(self.request(endpoint_tag, method, params))
        goods = result["goods"]["item"]
        session_id = result.get("idSession", None)
        while session_id:
            params = {"idSession": session_id}
            if goods_id:
                params["goodsID"] = int(goods_id)
            result = serialize_object(self.request(endpoint_tag, method, params))
            goods.extend(result["goods"]["item"])
            session_id = result.get("idSession", None)

        if not PRODUCTION:
            self.tunnel_forwarder.close()

        for goods_item in goods:
            goods_item["goodsID"] = str(goods_item["goodsID"])

        return goods

    def export_transactions(self):
        if not PRODUCTION:
            self.tunnel_forwarder.start()

        endpoint_tag = "TransactionReceipts"
        method = "getTransactionReceipts"

        periods = [
            (date(2024, 6, 1).isoformat(), date(2024, 7, 1).isoformat()),
            # (date(2024, 7, 1).isoformat(), date(2024, 8, 1).isoformat()),
            # (date(2024, 8, 1).isoformat(), date(2024, 9, 1).isoformat()),
            # (date(2024, 9, 1).isoformat(), date(2024, 9, 5).isoformat()),
        ]
        all_transactions = []
        for period in periods:
            params = {
                "dateFrom": period[0],
                "dateTo": period[1],
            }

            result = serialize_object(self.request(endpoint_tag, method, params))
            transactions = result["transactionReceipts"]["item"] if result["transactionReceipts"] else []
            session_id = result.get("idSession", None)
            while session_id:
                params = {
                    "dateFrom": period[0],
                    "dateTo": period[1],
                    "idSession": session_id
                }
                result = serialize_object(self.request(endpoint_tag, method, params))
                transactions.extend(result["transactionReceipts"]["item"])
                session_id = result.get("idSession", None)

            if not PRODUCTION:
                self.tunnel_forwarder.close()

            # В транзакции может быть несколько записей. Разбиваем до атомарных записей.
            transactions_ = []
            for transaction in transactions:
                for tr_item in transaction["receiptItem"]["item"]:
                    transactions_.append({
                        "transactionID": str(transaction["transactionID"]),
                        "transactionDateTime": datetime.fromisoformat(transaction["transactionDateTime"]),
                        "terminalID": str(transaction["terminalID"]),
                        "cardNumber": str(transaction["cardNumber"]),
                        "contractID": str(transaction["contractID"]),
                        "contractType": transaction["contractType"],
                        "clientID": str(transaction["clientID"]),
                        "contractOwnerID": str(transaction["contractOwnerID"]),
                        "transactionType": transaction["transactionType"],
                        "position": tr_item["position"],
                        "goodsID": str(tr_item["goodsID"]),
                        "paymentType": tr_item["paymentType"],
                        "priceWithoutDiscount": tr_item["priceWithoutDiscount"],
                        "price": tr_item["price"],
                        "quantity": tr_item["quantity"],
                        "amountWithoutDiscountRounded": tr_item["amountWithoutDiscountRounded"],
                        "amountRounded": tr_item["amountRounded"],
                        "receiptDiscount": transaction["receiptDiscount"],
                        "totalTransactionAmount": transaction["totalTransactionAmount"],
                    })

            all_transactions.extend(transactions_)

        # Сортируем транзакции по времени совершения
        def sorting(tr):
            return tr['transactionDateTime']

        transactions = sorted(all_transactions, key=sorting)

        if transactions:
            export = ExportToExcel()
            export.make_excel(
                data=transactions,
                headers=[k for k, v in transactions[0].items()],
                filename="OPS_TRANSACTIONS.xlsx",
                export_dir="D:\\Temp"
            )
