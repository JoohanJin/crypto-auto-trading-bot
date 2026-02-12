from src.brokers.base.http_client import HttpClient
from src.core.models.service_dto import AccountInformation, Ping, Position
from src.interfaces.base.base_interface import BaseInterface
from src.interfaces.http_client_registry import HttpClientRegistry


class HttpInterface(BaseInterface[HttpClientRegistry, HttpClient]):
    def __init__(
        self,
        name: str | None = None,
        client_registry: HttpClientRegistry | None = None,
    ) -> None:
        registry = (
            client_registry
            if client_registry
            else HttpClientRegistry(name=f"{name.upper()}_REGISTRY" if name else "HTTP_CLIENT_INTERFACE_REGISTRY")
        )
        
        super().__init__(
            client_registry=registry,
            name=name.upper() if name else "HTTP_CLIENT_INTERFACE"
        )

    def push_client(self, key: str, client: HttpClient) -> None:
        if isinstance(client, HttpClient):
            super().push_client(key, client)
        else:
            raise TypeError(f"Expected HttpClient, got {type(client)}")
    
    def ping(self) -> dict[str, Ping]:
        pings: dict[str, Ping] = {}
        for key, client in self.client_registry.registry.items():
            try:
                response = client.ping()
                if isinstance(response, Ping):
                    pings[response.source] = response
            except Exception as e:
                self.logger(f"[{key}] Failed to ping: {str(e)}")
                continue
        return pings

    def get_open_orders(self) -> dict[str, list[Position]]:
        positions: dict[str, list[Position]] = {}
        for key, client in self.client_registry.registry.items():
            try:
                response = client.get_open_orders()
                if isinstance(response, list) and response:
                    source = response[0].source
                    positions[source] = response
            except Exception as e:
                self.logger.error(f"[{key}] Failed to fetch open orders: {str(e)}")
                continue
        
        return positions

    def get_account_balance(
        self,
        asset: str | None = None,
    ) -> dict[str, AccountInformation | list[AccountInformation]]:
        account_balances: dict[str, AccountInformation | list[AccountInformation]] = {}

        for key, client in self.client_registry.registry.items():
            try:
                response = client.get_account_balance(
                    asset=asset,
                )
                if isinstance(response, AccountInformation):
                    account_balances[response.source] = response
                elif isinstance(response, list):
                    account_balances[response[0].source] = response
            except Exception as e:
                self.logger.errors(f"[{key}] Failed to fetch account balance{str(e)}")
        return account_balances
