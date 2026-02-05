# Built in libraries
from typing import Optional, Union, Literal
import json

# Custom libraries
from src.infrastructure.logging.set_logger import operation_logger
from src.brokers.base.rest_sdk import RestService


class MexcFutureGateway(RestService):
    """
    Class for Base SDK for MEXC APIs including SpotV3, Spot V2, Futures V1 and so on
    SDK for MEXC API, inheriting from CommonBaseAPI.
    """
    def __init__(
        self,
        name: str | None = None,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: str = "https://contract.mexc.com",
    ):
        super().__init__(
            name = name if name is not None else "MEXC_FUTURE_REST_CLIENT",
            api_key = api_key,
            secret_key = secret_key,
            base_url = base_url,
        )
        # Set the specific content type for MEXC
        self.set_content_type("application/json")

    def call(
        self,
        method: Union[
            Literal["GET"],
            Literal["POST"],
            Literal["PUT"],
            Literal["DELETE"],
        ],
        url: str,
        api_key_title: str = "ApiKey",
        params: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict | None:
        """
        Make a call to the MEXC API.
        """
        # Ensure the URL starts with "/"
        if not url.startswith("/"):
            url = f"/{url}"

        timestamp: int = self.generate_timestamp()

        if params is not None:
            params = {key: value for key, value in params.items() if value is not None}
            query_string = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
        else:
            query_string: str = ""

        query_string = f"{self.api_key}{timestamp}{query_string}"

        # apiKey in header
        if self.api_key and self.secret_key:  # menas it is signed instance.
            if headers is None:
                headers = {
                    "Request-Time": str(timestamp),
                    api_key_title: self.api_key,
                    "Signature": self.generate_signature(query_string),
                }
            else:
                headers.update(
                    {
                        api_key_title: self.api_key,
                        "Request-Time": str(timestamp),
                        "Signature": self.generate_signature(query_string),
                    }
                )

        try:
            response = self.session.request(
                method = method,
                url = f"{self.base_url}{url}",
                params = params,
                headers = headers,
                data = data if data is None else json.dumps(data),
            )

            payload = self.parse_response(response)

            # TODO: make a custom data structure for O(1) data-get for logging and Exception handling
            if response.status_code >= 400:
                status: int = response.status_code
                error_msg: str = (
                    payload.get("msg")  # type: ignore[union-attr]
                    if isinstance(payload, dict)
                    else str(payload)
                )

                if status == 400:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - BadRequest Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 401:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - Unauthorized Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 402:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - ApiKeyExpired Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 406:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - AccessIPNotInWhiteList Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 500:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - ServerInternal Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )  # TODO: Implement retry logic
                elif status == 506:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - UnknownSourceOfRequest Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 510:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - ExcessiveFrequencyOfRequest Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )  # TODO: implement retry logic
                elif status == 511:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - EndpointInaccurate Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )
                elif status == 513:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - InvalidRequest Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )
                else:
                    operation_logger.critical(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - ClientError Error "
                        f"from MexC USDT-M Future API: {str(error_msg)}"
                    )

                raise Exception(error_msg)

            return payload
        except ValueError:
            response.raise_for_status()
            return None
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - Unexpected Error "
                f"while communicating to Mexc Rest API: {str(e)}"
            )
            return None
