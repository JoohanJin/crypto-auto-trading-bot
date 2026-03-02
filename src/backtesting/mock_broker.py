import logging

from src.core.models.order import Order
from src.core.models.service_dto import AccountInformation, MarkPrice, Position
from src.core.models.trade import TradePair


class MockBinanceFutureHttpClient:
    """
    A mock implementation of the BinanceFutureHttpClient for backtesting.
    It tracks a simulated account balance and records trades without making any actual network calls.
    """

    def __init__(self, initial_balance: float = 10000.0, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.available_balance = initial_balance
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

        # Simulating current state
        self.current_mark_price = 0.0

        # Track positions and orders
        self.open_positions: list[Position] = []
        self.order_history: list[Order] = []
        self.trade_history = []  # For PnL tracking

    def set_current_price(self, price: float):
        """Used by the Backtest Runner to update the mock exchange's price as time advances."""
        self.current_mark_price = price

    def get_account_balance(self, asset: str = "USDT") -> AccountInformation:
        """Mock implementation of get_account_balance."""
        return AccountInformation(
            asset=asset,
            balance=self.balance,
            cross_wallet_balance=self.balance,
            cross_un_pnl=0.0,  # Could be calculated dynamically based on open positions and current_mark_price
            available_balance=self.available_balance,
            max_withdraw_amount=self.available_balance,
            margin_available=True
        )

    def get_open_orders(self, symbol: TradePair) -> list[Position]:
        """Mock implementation of get_open_orders."""
        # For simplicity in testing, we might not track pending limit orders, just instant market executions.
        return self.open_positions

    def get_mark_price(self, symbol: TradePair) -> MarkPrice:
        """Mock implementation of get_mark_price."""
        return MarkPrice(
            symbol=symbol.ticker + symbol.quote,
            mark_price=self.current_mark_price,
            index_price=self.current_mark_price,
            estimated_settle_price=self.current_mark_price,
            last_funding_rate=0.0,
            next_funding_time=0,
            interest_rate=0.0,
            time=0
        )

    def order(self, order: Order) -> dict:
        """
        Mock implementation of order.
        Simulates an instant market execution.
        """
        self.order_history.append(order)

        # Calculate fees based on the notional size of the trade
        # notional_size = order.ticker_size * order.entry_price
        # Note: Since the real TradeManager calculates order.quote_size based on leverage,
        # we'll use quote_size directly if available, or calculate it.
        notional_size = order.ticker_size * order.entry_price

        # Assuming market orders (Taker fee)
        fee = notional_size * self.taker_fee

        # Determine if this is an exit or a new position
        is_exit = order.meta_data.get("exit", False)
        is_reverse = order.meta_data.get("reverse", False)

        if is_exit:
            # We are closing a position. Realized PnL should be calculated.
            # In a full backtester, we'd calculate exact PnL here based on entry vs exit price.
            # For now, we update balance based on the bot's calculated PnL.
            pnl_rate = order.meta_data.get("pnl_rate", 0.0)

            # The notional value actually traded relative to leverage
            # If I had $100, 10x leverage, my position size is $1000.
            # A 1% price move ($10) is a 10% move on my margin.
            pnl_amount = (notional_size / order.leverage) * (pnl_rate * order.leverage)

            # Update balance
            self.balance += pnl_amount - fee
            self.available_balance = self.balance

            self.logger.info(f"[MOCK_EXECUTION] EXIT. PnL: {pnl_amount:.2f}, Fee: {fee:.2f}, New Balance: {self.balance:.2f}")
            self.trade_history.append({"type": "EXIT", "pnl": pnl_amount, "fee": fee, "balance": self.balance})

        else:
            # We are opening a new position (or reversing into a new one)
            # Deduct the fee from balance
            self.balance -= fee

            # Deduct the margin used from available balance
            margin_used = notional_size / order.leverage
            self.available_balance -= margin_used

            self.logger.info(f"[MOCK_EXECUTION] ENTRY ({order.side_str}). Margin Used: {margin_used:.2f}, Fee: {fee:.2f}, Balance: {self.balance:.2f}")
            self.trade_history.append({"type": "ENTRY", "side": order.side_str, "fee": fee, "balance": self.balance})

        return {"status": "FILLED", "orderId": len(self.order_history), "price": order.entry_price, "qty": order.ticker_size}
