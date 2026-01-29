import os
from dotenv import load_dotenv

from brokers.mexc.future import FutureWebSocketClient as MexcFutureWebSocketClient
from brokers.binance.future import FutureWebSocketClient as BinanceFutureWebScoektClient


def print_msg(msg):
    print(f"{msg}")
    # print(f"{msg.get('result', None)}\n")


def mexc_test():
    fws = MexcFutureWebSocketClient(
        name="mexc_testing_future_wsc"
    )

    fws.start()

    fws.sub_depth(callback_function=print_msg)


def binance_test():
    load_dotenv()
    binance_api_key: str = os.getenv("BINANCE_ED25519_API_KEY")
    binance_secret_key: str = os.getenv("BINANCE_ED25519_SECRET_KEY")

    bwc = BinanceFutureWebScoektClient(
        api_key=binance_api_key,
        secret_key=binance_secret_key,
        name="TEST_BINANCE_WEBSOCKET_CLIENT",
    )

    bwc.start()

    # bwc.ticker(callback=print_msg)
    bwc.ticker(callback=print_msg)

    return


def main():
    # mexc_test()
    binance_test()

    while True:
        pass


if __name__ == "__main__":
    main()
