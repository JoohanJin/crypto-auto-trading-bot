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
        from src.backtesting.time_manager import MockTimeManager
        return AccountInformation(
            timestamp=MockTimeManager.generate_timestamp(),
            source="BACKTEST_MOCK",
            id="BACKTEST_ID",
            asset=asset,
            balance=self.balance,
            unrealized_pnl=0.0,
            available_balance=self.available_balance,
        )

    def get_open_orders(self, symbol: TradePair) -> list[Position]:
        """Mock implementation of get_open_orders."""
        # For simplicity in testing, we might not track pending limit orders, just instant market executions.
        return self.open_positions

    def get_mark_price(self, symbol: TradePair) -> MarkPrice:
        """Mock implementation of get_mark_price."""
        from src.backtesting.time_manager import MockTimeManager
        return MarkPrice(
            timestamp=MockTimeManager.generate_timestamp(),
            source="BACKTEST_MOCK",
            ticker=symbol,
            mark_price=self.current_mark_price
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

        elif is_reverse:
            # REVERSE = atomically close old position + open new base position.
            # Order notional is 2x (old_size + new_size). We need to:
            #   1. Return the old position's margin to available_balance
            #   2. Charge fee on full 2x notional
            #   3. Deduct the new (base) position's margin
            base_ticker = order.meta_data.get("base_ticker_size", order.ticker_size / 2)
            old_ticker = order.ticker_size - base_ticker
            old_margin = old_ticker * order.entry_price / order.leverage
            new_margin = base_ticker * order.entry_price / order.leverage

            self.balance -= fee
            self.available_balance += old_margin   # release old margin
            self.available_balance -= new_margin   # lock new margin
            self.available_balance -= fee

            self.logger.info(
                f"[MOCK_EXECUTION] REVERSE ({order.side_str}). "
                f"Old Margin Released: {old_margin:.2f}, New Margin: {new_margin:.2f}, "
                f"Fee: {fee:.2f}, Balance: {self.balance:.2f}"
            )
            self.trade_history.append({"type": "REVERSE", "side": order.side_str, "fee": fee, "balance": self.balance})

        else:
            # NEW position: deduct fee + margin
            margin_used = notional_size / order.leverage
            self.balance -= fee
            self.available_balance -= margin_used
            self.available_balance -= fee

            self.logger.info(f"[MOCK_EXECUTION] ENTRY ({order.side_str}). Margin Used: {margin_used:.2f}, Fee: {fee:.2f}, Balance: {self.balance:.2f}")
            self.trade_history.append({"type": "ENTRY", "side": order.side_str, "fee": fee, "balance": self.balance})

        return {"status": "FILLED", "orderId": len(self.order_history), "price": order.entry_price, "qty": order.ticker_size}
