from typing import Tuple
from telegram import Bot
import asyncio
import json

# Custom Module
from src.infrastructure.logging.set_logger import get_logger, get_adapter

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

        # make the bot instance
        self._bot = Bot(self.__api_key)

        self.logger.info(f"[INTEGRATION_INIT] {self.name} | Status: ready")

        return

    def send_text(self, message: str) -> None:
        try:
            asyncio.run(self._bot.send_message(
                chat_id=self.__channel_id,
                text=message,
            ))
            self.logger.info("[MSG_SEND] Platform: Telegram | Status: sent")
        except Exception as e:
            self.logger.error(f"[MSG_ERROR] Platform: Telegram | Error: {type(e).__name__}: {str(e)}")
        return

    async def async_send_test(self, msg: str) -> None:
        try:
            await self._bot.send_message(text=msg, chat_id=self.__channel_id,)
        except Exception as e:
            self.logger.error(f"[MSG_ERROR] Platform: Telegram | Error: {type(e).__name__}: {str(e)}")
        return


"""
###################################################################################################
#                                       Test Run Zone                                             #
###################################################################################################
"""

if __name__ == "__main__":
    def get_credentials() -> Tuple[str, str]:
        with open("../credentials/telegram_key.json", "r") as file:
            data = json.load(file)
            return data["api_key"], data["channel_id"]

    async def main():
        api_key, channel_id = get_credentials()
        test = CustomTelegramBot(
            api_key=api_key,
            channel_id=channel_id,
        )

        await test.send_text("test messaging")

        return
    asyncio.run(main())
