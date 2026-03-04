# Standard Library
import hashlib
import hmac
import time
from abc import ABC, abstractmethod
from typing import Any, Literal, TypeVar

import requests
from pydantic import BaseModel, ValidationError

# Logger
from src.infrastructure.logging.set_logger import get_adapter, get_logger


logger = get_logger(__name__)

TBaseModel = TypeVar("TBaseModel", bound=BaseModel)


class HttpService(ABC):
    """
    A common base class for handling API requests, signature generation, and session management
    for different exchange SDKs (e.g., MEXC and Binance).
    """

    @staticmethod
    def snake_to_camel(
        s: str,
    ) -> str:
        parts = s.split("_")
        return parts[0].lower() + "".join(word.capitalize() for word in parts[1:])

    def generate_timestamp(self) -> int:
        return int(time.time() * 1_000)

    def parse_response(
        self,
        response: requests.Response,
        model: type[TBaseModel] | None = None,
    ) -> TBaseModel | list[TBaseModel] | dict[str, Any] | list[Any] | str | None:
        """Parse an HTTP response into structured data.

        Args:
            response: The raw ``requests.Response`` object returned from the session.
            model: Optional Pydantic ``BaseModel`` subclass used for validation.

        Returns:
            The decoded payload (dict/list/str/None) or a validated Pydantic model/
            list of models when ``model`` is provided.

        Raises:
            ValueError: When ``model`` is supplied but the response cannot be
                validated against it.
        """

        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text or None

        if model is None or payload is None:
            return payload

        try:
            if isinstance(payload, list):
                return [model.model_validate(item) for item in payload]
            if isinstance(payload, dict):
                return model.model_validate(payload)
        except ValidationError as e:  # pragma: no cover - pydantic detail
            self.logger.critical(
                f"[INVALID_RESPONSE] parse_response() | Expected: {model.__name__} | "
                f"Error: {type(e).__name__}: {e!s}"
            )

            raise ValueError(
                f"{__name__} - {self.__class__.__name__} - {self.name} - Failed to parse response into {model.__name__}: {e!s}"
            ) from e

        self.logger.critical(
            f"[INVALID_RESPONSE] parse_response() | Expected: {model.__name__} | "
            f"Got: {type(payload).__name__}"
        )
        raise ValueError(
            f"Response body of type {type(payload).__name__} cannot be parsed using {model.__name__}."
        )
        return

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self.name: str = name
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.base_url: str = base_url

        # Initialize a session
        self.session: requests.Session = requests.Session()

        # Class-Level Logger
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        self.logger.info(f"[SERVICE_INIT] {self.name} initialized")

    def set_content_type(self, content_type: str):
        """
        Set the Content-Type header for the session.
        """
        self.session.headers.update(
            {
                "Content-Type": content_type,
            }
        )

    def generate_signature(
        self,
        query_string: str,
    ) -> str:
        """
        ;func generate_signature:
            - Generate a signature for the request using HMAC SHA256.
            - This is used for authentication with the API.
            - Child classes would override this method if needed.

        param query_string:
        - The query string to be signed.

        return: The generated signature as a hex digest (readable string).
            - if we do not disgest using hexdigest, the signature will be a hmac object.
        """
        if not self.secret_key:
            # !: this api is not sigend.
            self.logger.warning(f"[CREDENTIAL_ERROR] {self.name} | Missing: secret_key")
            raise ValueError("Secret key is required for signature generation.")

        return hmac.new(
            key=self.secret_key.encode("utf-8"),
            msg=query_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

    @abstractmethod
    def call(
        self,
        method: Literal["GET"] | Literal["POST"] | Literal["PUT"] | Literal["DELETE"],
        url: str,
        api_key_title: str,
        params: dict | None = None,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict | None:
        """
        func call:
            - Make a generic API call with the specified method, URL, and parameters.
            - Automatically handles signature generation and timestamping.
            - Returns the JSON response from the API.

        param method: HTTP method (GET, POST, PUT, DELETE)
        param url: API endpoint URL (should start with "/")
        param params: Query parameters for the request
        param data: JSON body for the request
        param headers: Additional headers for the request

        return: JSON response from the API
        """
        return


if __name__ == "__main__":
    import unittest

    class TestSnakeToCamel(unittest.TestCase):
        """Unit tests for snake_to_camel conversion."""

        def test_single_word_no_underscores(self):
            """Single word with no underscores should remain lowercase."""
            self.assertEqual(HttpService.snake_to_camel("abc"), "abc")

        def test_two_words(self):
            """Two words separated by underscore should convert to camelCase."""
            self.assertEqual(HttpService.snake_to_camel("abc_cdf"), "abcCdf")

        def test_multiple_underscores(self):
            """Multiple underscores should convert each word."""
            self.assertEqual(HttpService.snake_to_camel("abc_cdf_efg"), "abcCdfEfg")

        def test_with_numbers(self):
            """Conversion should handle numbers correctly."""
            self.assertEqual(HttpService.snake_to_camel("page_num"), "pageNum")

        def test_single_letter(self):
            """Single letter should remain lowercase."""
            self.assertEqual(HttpService.snake_to_camel("a"), "a")

    unittest.main()
