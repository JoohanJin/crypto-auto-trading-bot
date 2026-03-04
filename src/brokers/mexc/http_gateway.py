# Built in libraries
import json
from typing import Literal

from src.brokers.base.http_service import HttpService

# Custom libraries
from src.infrastructure.logging.set_logger import get_adapter, get_logger


logger = get_logger(__name__)


class MexcFutureGateway(HttpService):
    """
    Class for Base SDK for MEXC APIs including SpotV3, Spot V2, Futures V1 and so on
    SDK for MEXC API, inheriting from CommonBaseAPI.
    """

    def __init__(
        self,
        name: str | None = None,
        api_key: str | None = None,
        secret_key: str | None = None,
        base_url: str = "https://contract.mexc.com",
    ):
        super().__init__(
            name=name if name is not None else "MEXC_FUTURE_REST_CLIENT",
            api_key=api_key,
            secret_key=secret_key,
            base_url=base_url,
        )
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        # Set the specific content type for MEXC
        self.set_content_type("application/json")

    def call(
        self,
        method: Literal["GET"] | Literal["POST"] | Literal["PUT"] | Literal["DELETE"],
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
            query_string = "&".join(
                f"{key}={value}" for key, value in sorted(params.items())
            )
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
                method=method,
                url=f"{self.base_url}{url}",
                params=params,
                headers=headers,
                data=data if data is None else json.dumps(data),
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
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: BadRequest: {error_msg!s}"
                    )
                elif status == 401:
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: Unauthorized: {error_msg!s}"
                    )
                elif status == 402:
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: ApiKeyExpired: {error_msg!s}"
                    )
                elif status == 406:
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: AccessIPNotInWhiteList: {error_msg!s}"
                    )
                elif status == 500:
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: ServerInternal: {error_msg!s}"
                    )  # TODO: Implement retry logic
                elif status == 506:
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: UnknownSourceOfRequest: {error_msg!s}"
                    )
                elif status == 510:
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: ExcessiveFrequencyOfRequest: {error_msg!s}"
                    )  # TODO: implement retry logic
                elif status == 511:
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: EndpointInaccurate: {error_msg!s}"
                    )
                elif status == 513:
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: InvalidRequest: {error_msg!s}"
                    )
                else:
                    self.logger.critical(
                        f"[BROKER_ERROR] MexC | Status: {status} | Error: ClientError: {error_msg!s}"
                    )

                raise Exception(error_msg)

            return payload
        except ValueError:
            response.raise_for_status()
            return None
        except Exception as e:
            self.logger.critical(
                f"[BROKER_ERROR] MexC | Error: {type(e).__name__}: {e!s}"
            )
            return None
