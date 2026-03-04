# TradeManager

> Last updated: 2026-03-03

`TradeManager` is the central trading orchestration component, operating as the 'brain' of the bot. It utilizes the **Weighted Signal Density & Consensus (WSDC) model** to make high-frequency execution decisions, and dispatches them to Binance Futures via REST API.

---

## Architecture Overview

```
SignalPipeline ──pop()──▶ _thread_get_signal ──append()──▶ signal_history
                                                                   │
                                                              (shared deque)
                                                                   │
                          _thread_decide_trade ◀──read + prune─────┘
                                │
                          _analyze_signals()
                                │
                     ┌──────────┼───────────────────┐
                     ▼          ▼                    ▼
                   HOLD    NEW_BUY/SELL        REVERSE_BUY/SELL
                  (noop)        │                    │
                                ▼                    ▼
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
| `Thread-Get-Signal`   | Pops signals from the pipeline, validates freshness, and appends valid signals to `signal_history`.       |
| `Thread-Decide-Trade` | Evaluates `_analyze_signals()`, checks cooldowns, executes trades if consensus is reached across all timeframes. |

Thread safety is managed with two locks:
- `signal_history_lock` — guards `signal_history` reads/writes.
- `lock_current_position` — guards `current_position` reads/writes.

---

## WSDC Model (Weighted Signal Density & Consensus)

Instead of following single signals (which are often noisy in short timeframes), this manager looks for 'signal clusters' or 'bursts'. It assumes that a high density of signals in a short window represents a real market move.

The bot employs an **"Always-in-Market" (Trend Reversal Only)** strategy. It stays in a trade to ride out market noise (like liquidation wicks) and only flips positions when the consensus fully shifts. Panic Exits have been disabled to maximize profit per trade and minimize fee leakage.

### 1. The Three Time Windows
The `signal_history` is analyzed across three distinct timeframes:
- **Structural (10 minutes - `600,000 ms`)**: The "Titanium Backbone". Ensures the bot only trades when a massive, undeniable macro-trend is established.
- **Mid-Term (5 minutes - `300,000 ms`)**: The intermediate trend confirmation.
- **Short-Term / Momentum (2 minutes - `120,000 ms`)**: The "Hair Trigger". Looks for a sudden burst of momentum aligning with the structural trend to snipe the optimal entry point.

### 2. Signal Density
Before consensus is even calculated, a minimum number of signals must be present in the history windows to prove a real event is occurring (filtering out low-volume outlier signals).
- `min_history_density`: Minimum signals in the 10m window (Default: `10`).
- `min_short_term_density`: Minimum signals in the 2m window (Default: `2`).

### 3. Weighted Consensus (-1.0 to 1.0)
Signals are assigned weights based on their impact via `ScoreMapper` (e.g., `LONG_TERM_BUY = +5`, `SHORT_TERM_SELL = -3`). The bot calculates the net consensus across all three windows:
- **`+1.0`**: 100% agreement on BUY.
- **`-1.0`**: 100% agreement on SELL.

### 4. Optimal "Sweet Spot" Thresholds
Through rigorous vectorized backtesting (simulating OHLC 4x volatility), the following thresholds were mathematically proven to maximize **Profit per Trade**:
- `consensus_short_term_threshold`: `0.50` (50% Short-term agreement)
- `consensus_mid_term_threshold`: `0.50` (50% Mid-term agreement)
- `consensus_threshold` (Structural): `0.90` (90% Long-term agreement)

**Logic:** Wait patiently for an undeniable 10-minute wave (`0.90`), and immediately jump in (`0.50`) the moment momentum starts swinging in that direction.

---

## TradeState Machine

`TradeState` is an `IntFlag` enum representing all possible trade decisions.

| State          | Condition                                        | Effect                  |
| -------------- | ------------------------------------------------ | ----------------------- |
| `HOLD`         | Default / density too low / consensus unmet      | No action               |
| `NEW_BUY`      | No position, Buy consensus met on all 3 windows  | Open long               |
| `NEW_SELL`     | No position, Sell consensus met on all 3 windows | Open short              |
| `REVERSE_BUY`  | Short position, Buy consensus met on all windows | Close short + open long |
| `REVERSE_SELL` | Long position, Sell consensus met on all windows | Close long + open short |

*(Note: `EXIT` logic is preserved in code but safely bypassed to enforce the Trend-Reversal model).*

---

## Position Initialization & Tracking

`PositionState` is a mutable dataclass that tracks the actual position held:

```python
@dataclass
class PositionState:
    side: Side         # Side.BUY or Side.SELL
    ticker_size: float # actual position qty
    quote_size: float  # actual position value
    entry_price: float
    timestamp: int     # epoch ms
```

### Startup Recovery
When `TradeManager` initializes, it securely fetches the current active position from the Binance API (`get_current_position_state`) by validating that `float(positionAmt) != 0.0`. It automatically detects Long/Short states, resolving Binance's `"BOTH"` string ambiguity in One-Way mode via entry/break-even price math.

### Reversals & Dynamic Sizing
In a `REVERSE` action, the `_construct_new_order` function automatically calculates the new position size based on your *current* available balance, ensuring the `trade_weight` (e.g., 15%) scales correctly as the account grows or shrinks. The order size sent to the exchange is `current_position_size (to close) + new_base_size (to open)`.

---

## Trade Cooldown

A minimum delay of `trade_cooldown_ms` (default `30,000ms` = 30s) is enforced between consecutive trades:

```python
if self.generate_timestamp() - self.last_trade_timestamp < self.trade_cooldown_ms:
    continue  # skip this tick
```
Prevents rapid order spamming during extreme volatility spikes.

---

## Network Resilience

All broker API calls (`_get_account_info`, `_get_open_orders`, `_get_mark_price`) use a robust `_fetch_with_retry()` wrapper:
- Retries **indefinitely** with exponential backoff.
- Validates the expected class response type before accepting the payload.
- Logs each retry attempt with delay and error info.