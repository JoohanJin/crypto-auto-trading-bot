# Standard Library
from typing import Union, Literal
from urllib.parse import urlencode
import json

# Custom Library
from src.infrastructure.logging.set_logger import get_logger, get_adapter
from src.brokers.base.http_sdk import HttpService

logger = get_logger(__name__)


class BinanceFutureGateway(HttpService):
    """
    SDK for Binance Futures API, inheriting from CommonBaseAPI.
    """
    def __init__(
        self,
        name: str | None = None,
        base_url: str = "https://fapi.binance.com",
        api_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        # Please comment the following line if you want to turn off the testNet.
        # base_url = "https://testnet.binancefuture.com"  # this is the testNet

        super().__init__(
            name = name if name is not None else "BINANCE_FUTURE_REST_CLIENT",
            api_key = api_key,
            secret_key = secret_key,
            base_url = base_url,
        )
        self.logger = get_adapter(logger, self.name)
        # Set the specific content type for Binance
        self.set_content_type("application/x-www-form-urlencoded")
        return

    def call(
        self,
        method: Union[
            Literal["GET"],
            Literal["POST"],
            Literal["PUT"],
            Literal["DELETE"],
        ],
        url: str,
        api_key_title: str = "X-MBX-APIKEY",
        params: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict | None:
        """
        Make a call to the Binance API.
        """
        url = url if url.startswith("/") else f"/{url}"

        filtered_params: dict[str, str | int] = {
            self.__class__.snake_to_camel(key): value
            for key, value in (params.items() if params else {})
            if value is not None
        }

        request_headers: dict[str, str | int | float] = headers.copy() if headers else {}

        if (self.api_key and self.secret_key):
            request_headers[api_key_title] = self.api_key
            query_string = urlencode(list(filtered_params.items()))
            filtered_params["signature"] = self.generate_signature(query_string)

        request_params = filtered_params or None
        request_data = (
            json.dumps(data)
            if data is not None and not isinstance(data, (str, bytes))
            else data
        )

        try:
            response = self.session.request(
                url = f"{self.base_url}{url}",
                method = method,
                params = request_params,
                headers = request_headers,
                data = request_data,
            )

            payload = self.parse_response(response)

            if response.status_code >= 400:
                status: int = response.status_code  # Status Code of the response.
                error_msg: str = (
                    payload.get("msg")  # type: ignore[union-attr]
                    if isinstance(payload, dict)
                    else str(payload)
                )

                if status == 400:
                    self.logger.critical(
                        f"BadRequest Error from Binance USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 401:
                    self.logger.critical(
                        f"Unauthorized Error from Binance USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 403:
                    self.logger.critical(
                        f"Forbidden Error from Binance USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 404:
                    self.logger.critical(
                        f"NotFound Error from Binance USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 418:
                    self.logger.critical(
                        f"RateLimitBan Error from Binance USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 429:
                    self.logger.critical(
                        f"ToomanyRequests Error from Binance USDT-M Future API: {str(error_msg)}"
                    )
                elif 500 <= status < 600:
                    self.logger.critical(
                        f"Server Error from Binance USDT-M Future API: {str(error_msg)}"
                    )
                else:
                    self.logger.critical(
                        f"ClientError Error from Binance USDT-M Future API: {str(error_msg)}"
                    )

                raise Exception(error_msg)

            return payload
        except ValueError:
            response.raise_for_status()
            return None
        except Exception as e:
            self.logger.critical(f"Unknown Error while communicating with broker: {str(e)}")
            return None
