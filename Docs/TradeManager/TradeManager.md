# TradeManager

> Last updated: 2026-02-16

`TradeManager` is the central trading orchestration component. It consumes signals from the signal pipeline, accumulates a conviction score, makes trade decisions, constructs orders, and dispatches them to Binance Futures via REST API.

---

## Architecture Overview

```
SignalPipeline ──pop()──▶ _thread_get_signal ──score+=delta──▶ trade_score
                                                                   │
                                                              (shared int)
                                                                   │
                          _thread_decide_trade ◀──read + decay─────┘
                                │
                          _decide_trade(score)
                                │
                     ┌──────────┼───────────────────┐
                     ▼          ▼                    ▼
                   HOLD    NEW/REVERSE/EXIT    (cooldown?)
                  (noop)        │                skip tick
                                ▼
                        _construct_new_order()
                                │
                        _format_trade_message()
                                │
                        _make_order()  ──▶  Binance API
                                │
                        _update_position()
                                │
                        telegram_bot.send_text()
```

Two daemon threads run in an infinite loop:

| Thread                | Role                                                                                                                  |
| --------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `Thread-Get-Signal`   | Pops signals from the pipeline, validates freshness, maps to score delta, and atomically adds to `trade_score`.       |
| `Thread-Decide-Trade` | Every 250ms: decays score, evaluates `_decide_trade()`, enforces cooldown, executes trade if triggered, resets score. |

Thread safety is managed with two locks:

- `trade_score_lock` — guards `trade_score` reads/writes.
- `lock_current_position` — guards `current_position` reads/writes.

---

## TradeState Machine

`TradeState` is an `IntFlag` enum representing all possible trade decisions.

| State          | Value | Condition                                        | Effect                  |
| -------------- | ----- | ------------------------------------------------ | ----------------------- |
| `HOLD`         | 1     | Default / score within thresholds                | No action               |
| `NEW_BUY`      | 2     | No position, `score > threshold`                 | Open long               |
| `NEW_SELL`     | 4     | No position, `score < -threshold`                | Open short              |
| `REVERSE_BUY`  | 8     | Short position, `score > threshold/2`            | Close short + open long |
| `REVERSE_SELL` | 16    | Long position, `score < -threshold/2`            | Close long + open short |
| `EXIT`         | 32    | Position held, score moderately against position | Close position, go flat |

### Decision Priority

When a position exists, decisions are evaluated in this order:

1. **REVERSE** — checked first (strong opposing signal)
2. **EXIT** — checked second (moderate opposing signal, not strong enough for REVERSE)
3. **HOLD** — fallback

When no position exists:

1. **NEW_BUY** or **NEW_SELL** — if score exceeds ±threshold
2. **HOLD** — fallback

### Threshold Hierarchy

Given `score_threshold = 2000`:

| Decision                       | Threshold                |
| ------------------------------ | ------------------------ |
| `NEW_BUY` / `NEW_SELL`         | `±2000` (full threshold) |
| `REVERSE_BUY` / `REVERSE_SELL` | `±1000` (threshold / 2)  |
| `EXIT`                         | `±500` (threshold / 4)   |

---

## Score System

### Accumulation

Signals arrive from the pipeline via `_thread_get_signal`. Each signal is mapped to a score delta by `ScoreMapper.map()` and atomically added:

```python
self.trade_score += self._calculate_signal_score_delta(signal_data)
```

Positive deltas indicate bullish conviction; negative deltas indicate bearish conviction.

### Decay

Every tick (250ms), the score is multiplied by `score_decay_rate` (default `0.995`):

```python
self.trade_score = int(self.trade_score * self.score_decay_rate)
```

This ensures stale conviction naturally drains away. Without fresh signals reinforcing the score, it decays toward zero:

| Elapsed Time     | Remaining Score (from 2000) |
| ---------------- | --------------------------- |
| 1s (4 ticks)     | ~1960                       |
| 10s (40 ticks)   | ~1637                       |
| 35s (~140 ticks) | ~990 (halved)               |

Setting `score_decay_rate = 1.0` disables decay entirely.

### Reset

After any trade (NEW, REVERSE, or EXIT), the score resets to **0**:

```python
self.trade_score = 0
```

This forces the next trade decision to be based entirely on fresh signals rather than carrying directional bias from the previous position.

---

## Trade Cooldown

A minimum delay of `trade_cooldown_ms` (default `30,000ms` = 30s) is enforced between consecutive trades:

```python
if self.generate_timestamp() - self.last_trade_timestamp < self.trade_cooldown_ms:
    continue  # skip this tick
```

**Rationale**: Prevents rapid cycling (e.g., NEW → EXIT → NEW → EXIT) that would bleed trading fees and amplify noise/whipsaw losses. During the cooldown window, **decay continues operating**, so if the triggering signal was noise, the score drains before the window expires.

The initial `last_trade_timestamp = 0` ensures the very first trade is never blocked by the cooldown.

---

## Order Construction

`_construct_new_order(buy_or_sell)` builds an `Order` dataclass differently based on trade type:

### NEW_BUY / NEW_SELL

| Field         | Value                                                 |
| ------------- | ----------------------------------------------------- |
| `side`        | Matches trade direction                               |
| `ticker_size` | `(leverage × available_quote × trade_weight) / price` |
| `quote_size`  | `available_quote × trade_weight`                      |
| `tp_price`    | `price × (1 ± tp_rate / leverage)`                    |
| `sl_price`    | `price × (1 ∓ sl_rate / leverage)`                    |
| `meta_data`   | `{}`                                                  |

### REVERSE_BUY / REVERSE_SELL

| Field         | Value                                                               |
| ------------- | ------------------------------------------------------------------- |
| `side`        | Opposite of current position                                        |
| `ticker_size` | `current_position.ticker_size + base_ticker` (2x order to exchange) |
| `quote_size`  | `current_position.quote_size + base_quote`                          |
| `tp_price`    | Same formula as NEW                                                 |
| `sl_price`    | Same formula as NEW                                                 |
| `meta_data`   | `{reverse: True, base_ticker_size, base_quote_size}`                |

The **actual new position** stored in `PositionState` uses the base size, not the 2x order size. This prevents exponential position growth on consecutive reverses.

### EXIT

| Field         | Value                                     |
| ------------- | ----------------------------------------- |
| `side`        | Opposite of current position (close-only) |
| `ticker_size` | `current_position.ticker_size`            |
| `quote_size`  | `current_position.quote_size`             |
| `tp_price`    | `0.0` (no TP — going flat)                |
| `sl_price`    | `0.0` (no SL — going flat)                |
| `meta_data`   | `{exit: True, pnl_rate: float}`           |

`pnl_rate` is an approximation:

- Long: `(mark_price - entry_price) / entry_price`
- Short: `(entry_price - mark_price) / entry_price`

---

## Position Tracking

`PositionState` is a mutable dataclass that tracks the **actual position** held, separate from order sizes sent to the exchange:

```python
@dataclass
class PositionState:
    side: int          # Side.BUY (1) or Side.SELL (2)
    ticker_size: float # actual position qty
    quote_size: float  # actual position value
    entry_price: float
    timestamp: int     # epoch ms
```

`_update_position(order, trade_action)` updates `current_position` after every trade:

| Action                         | Result                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------- |
| `NEW_BUY` / `NEW_SELL`         | `current_position = PositionState(...)` using full order size                |
| `REVERSE_BUY` / `REVERSE_SELL` | `current_position = PositionState(...)` using **base** size from `meta_data` |
| `EXIT`                         | `current_position = None`                                                    |

---

## Telegram Notifications

Every executed trade sends a message via `CustomTelegramBot.send_text()`:

**NEW order:**

```
Trade Signal: BUY
Entry Price: 97500.0
Amount: 200.0 USDT or 0.021 BTC
Take Profit: 99450.0
Stop Loss: 96525.0
It is the new order.
```

**REVERSE order:**

```
Trade Signal: BUY
Entry Price: 97500.0
Amount: 400.0 USDT or 0.041 BTC
Take Profit: 99450.0
Stop Loss: 96525.0
It is the reverse order.
```

**EXIT order:**

```
Trade Signal: EXIT (SELL to close)
Close Price: 98000.0
Amount: 200.0 USDT or 0.021 BTC
Approx Profit: 0.51% (x10 leverage: 5.13%)
It is an EXIT order.
```

---

## Network Resilience

All broker API calls (`_get_account_info`, `_get_open_orders`, `_get_mark_price`) use `_fetch_with_retry()`:

- Retries **indefinitely** with exponential backoff
- Validates response type before accepting
- Logs each retry attempt with delay info

---

## Constructor Parameters

| Parameter                    | Type                         | Default           | Description                                        |
| ---------------------------- | ---------------------------- | ----------------- | -------------------------------------------------- |
| `signal_pipeline_controller` | `PipelineController[Signal]` | required          | Signal source                                      |
| `http_interface`             | `HttpInterface`              | required          | HTTP abstraction (future use)                      |
| `binance_future_client`      | `BinanceFutureHttpClient`    | required          | Binance Futures API client                         |
| `delta_mapper`               | `ScoreMapper`                | required          | Maps signals to score deltas                       |
| `telegram_bot`               | `CustomTelegramBot`          | required          | Notification channel                               |
| `trade_pair`                 | `TradePair`                  | `BTC/USDT`        | Trading pair                                       |
| `leverage`                   | `int`                        | `10`              | Leverage multiplier                                |
| `trade_weight`               | `float`                      | `0.1`             | Fraction of balance per trade (10%)                |
| `take_profit_rate`           | `float`                      | `0.2`             | TP distance from entry (20%)                       |
| `stop_loss_rate`             | `float`                      | `0.2`             | SL distance from entry (20%)                       |
| `score_threashold`           | `int`                        | `2000`            | Score required for NEW trade                       |
| `score_trend_management`     | `int`                        | `200`             | Legacy bias score (unused after reset-to-0 change) |
| `score_decay_rate`           | `float`                      | `0.995`           | Per-tick decay factor                              |
| `trade_cooldown_ms`          | `int`                        | `30000`           | Minimum ms between trades                          |
| `name`                       | `str`                        | `"TRADE_MANAGER"` | Instance identifier for logging                    |

---

## Test Coverage

80 unit tests across 11 test classes (`test/test_trade_manager.py`):

| Test Class                      | Count | Coverage                                                                  |
| ------------------------------- | ----- | ------------------------------------------------------------------------- |
| `TestDecideTrade`               | 14    | All TradeState transitions including EXIT boundaries and REVERSE priority |
| `TestConstructNewOrder`         | 12    | NEW, REVERSE, EXIT order construction, P/L calculation, edge cases        |
| `TestFormatTradeMessage`        | 6     | NEW, REVERSE, EXIT message formatting                                     |
| `TestExecuteTrade`              | 5     | Full execution flow, position updates, EXIT clears position               |
| `TestUpdatePosition`            | 7     | NEW sets position, REVERSE uses base size, EXIT clears                    |
| `TestGetTargetPrices`           | 4     | Long/short TP/SL formula                                                  |
| `TestTradeSizing`               | 5     | Quote amt, ticker amt formula and rounding                                |
| `TestVerifySignal`              | 3     | Timestamp freshness validation                                            |
| `TestCalculateSignalScoreDelta` | 7     | Score delta mapping                                                       |
| `TestScoreDecay`                | 6     | Decay arithmetic, zero stability, disable with rate=1.0                   |
| `TestTradeCooldown`             | 5     | Cooldown enforcement, initial state, window boundaries                    |
