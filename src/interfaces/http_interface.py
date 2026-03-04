from collections.abc import Callable
from typing import Any

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

    def _execute_on_all_clients(
        self,
        method_name: str,
        response_validator: Callable[[Any], bool],
        result_key_extractor: Callable[[Any], str],
        method_args: dict | None = None,
    ) -> dict[str, Any]:
        """
        Common helper method: Execute method on all clients and collect results.

        param method_name: Name of the method to call on each client
        param response_validator: Function to validate if response is valid
        param result_key_extractor: Function to extract key for result dictionary
        param method_args: Arguments to pass to method (default: None)

        return: Dictionary mapping client key to results
        """
        results = {}
        method_args = method_args or {}

        for key, client in self.client_registry.registry.items():
            try:
                method = getattr(client, method_name)
                response = method(**method_args)

                if response_validator(response):
                    result_key = result_key_extractor(response)
                    results[result_key] = response
            except Exception as e:
                self.logger.error(f"[SERVICE_INIT_ERROR] {key} | Failed to execute {method_name} | Error: {type(e).__name__}: {e!s}")

        return results

    def ping(self) -> dict[str, Ping]:
        return self._execute_on_all_clients(
            method_name="ping",
            response_validator=lambda r: isinstance(r, Ping),
            result_key_extractor=lambda r: r.source,
        )

    def get_open_orders(self) -> dict[str, list[Position]]:
        def validate_response(response) -> bool:
            return isinstance(response, list) and len(response) > 0

        return self._execute_on_all_clients(
            method_name="get_open_orders",
            response_validator=validate_response,
            result_key_extractor=lambda r: r[0].source,
        )

    def get_account_balance(
        self,
        asset: str | None = None,
    ) -> dict[str, AccountInformation | list[AccountInformation]]:
        def validate_response(response) -> bool:
            return isinstance(response, (AccountInformation, list))

        return self._execute_on_all_clients(
            method_name="get_account_balance",
            response_validator=validate_response,
            result_key_extractor=lambda r: r.source if isinstance(r, AccountInformation) else r[0].source,
            method_args={"asset": asset},
        )
