import asyncio
import threading

from telegram import Bot

# Custom Module
from src.infrastructure.logging.set_logger import get_adapter, get_logger


logger = get_logger(__name__)


class Test:
    def __init__(self) -> None:
        self._telegram_bot = CustomTelegramBot()

    async def testing_message(self) -> str:
        print(
            'Sending the request to send a messge "Testing"'
        )  # Doing Some Synchronous Task

        await self._telegram_bot.send_text("test messaging")

        return "Testing"


class CustomTelegramBot:
    # Persistent background event loop shared across all instances.
    # This keeps one loop alive so the Bot's httpx client is never
    # invalidated by loop teardown between calls.
    _loop: asyncio.AbstractEventLoop | None = None
    _loop_thread: threading.Thread | None = None
    _lock = threading.Lock()

    @classmethod
    def _ensure_loop(cls) -> asyncio.AbstractEventLoop:
        """Start a persistent background event loop (once) and return it."""
        if cls._loop is None or cls._loop.is_closed():
            with cls._lock:
                # Double-check after acquiring lock
                if cls._loop is None or cls._loop.is_closed():
                    cls._loop = asyncio.new_event_loop()
                    cls._loop_thread = threading.Thread(
                        target=cls._loop.run_forever,
                        daemon=True,
                        name="telegram-event-loop",
                    )
                    cls._loop_thread.start()
        return cls._loop

    def __init__(
        self,
        api_key: str,
        channel_id: str,
        name: str | None = None,
    ) -> None:
        self.name = name if name else "TELEGRAM_BOT"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        # Get the credential from the json
        # will be considered as private attributes.
        self.__api_key = api_key
        self.__channel_id = channel_id

        # # Create request object with larger connection pool
        # request = HTTPXRequest(
        #     http_version="2",
        #     connection_pool_size=100,
        #     read_timeout=30.0,
        # )

        # make the bot instance
        self._bot = Bot(self.__api_key)

        self.logger.info(f"[INTEGRATION_INIT] {self.name} | Status: ready")

    def send_text(self, message: str) -> None:
        try:
            self._run_async(
                self._bot.send_message(
                    chat_id=self.__channel_id,
                    text=message,
                )
            )
            self.logger.info("[MSG_SEND] Platform: Telegram | Status: sent")
        except Exception as e:
            self.logger.error(
                f"[MSG_ERROR] Platform: Telegram | Error: {type(e).__name__}: {e!s}"
            )

    @classmethod
    def _run_async(cls, coro) -> None:
        """Run a coroutine synchronously using a persistent background loop.

        A single long-lived event loop is reused for every call so that the
        Bot's internal httpx connection pool is never invalidated by loop
        teardown between messages.
        """
        loop = cls._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        future.result()  # block until done, propagate exceptions


"""
###################################################################################################
#                                       Test Run Zone                                             #
###################################################################################################
"""

if __name__ == "__main__":

    def get_credentials() -> tuple[str, str]:
        import os

        from dotenv import load_dotenv

        load_dotenv()

        api_key: str = os.getenv("TELEGRAM_API_KEY")
        channel_id: str = os.getenv("TELEGRAM_CHANNEL_ID")

        return api_key, channel_id

    async def main():
        import time

        api_key, channel_id = get_credentials()
        test = CustomTelegramBot(
            api_key=api_key,
            channel_id=channel_id,
        )

        for i in range(1, 11):
            test.send_text(f"test messaging {i}")
            time.sleep(2.0)

    asyncio.run(main())
