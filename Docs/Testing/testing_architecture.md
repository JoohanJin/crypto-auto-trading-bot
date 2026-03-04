# Testing Architecture & Strategy

> Last updated: 2026-03-04

The testing suite for `AutoCryptoTrading` is built on a modern **Pytest** foundation. It is designed to be blazingly fast for local development while providing comprehensive end-to-end verification during Continuous Integration (CI).

## Framework Overview

We utilize `pytest` combined with standard `unittest.TestCase` classes. This allows us to leverage Pytest's powerful fixture and marker system while maintaining backward compatibility with legacy test structures.

### Test Categories (Pytest Markers)

Tests are strictly categorized using `@pytest.mark` decorators defined in `pyproject.toml`. This allows us to run specific subsets of tests depending on the environment.

| Marker | Description | Expected Execution Time | CI Stage |
| :--- | :--- | :--- | :--- |
| **`unit`** | Default label for tests with zero external dependencies. Network, file I/O, and time are heavily mocked. | < 5 seconds (Total) | Runs on every commit |
| **`integration`** | Tests that require actual network connectivity to public exchange endpoints (Binance/MEXC) or test complex inter-thread queuing. | 30 - 60 seconds | Runs on PRs / Nightly |
| **`slow`** | Tests that intentionally invoke `time.sleep()` to verify timeout loops, reconnections, or window-based data pruning. | Varies | Runs on PRs / Nightly |

---

## 1. Unit Testing Layer (Service & Logic)

The unit testing layer isolates specific components and tests their exact mathematical or structural outputs without spinning up the entire bot.

### Broker Gateways (Service Layer)
We test the `HttpGateway` and `WebSocketGateway` classes for both Binance and MEXC. These tests verify the core security and formatting requirements of the exchanges without actually sending packets over the internet.
- **HMAC SHA256 / Ed25519 Signing:** Verifies that API secrets correctly hash timestamps and payloads according to exchange documentation.
- **Payload Routing:** Ensures that incoming JSON strings are correctly parsed, mapped to internal DTOs (`Ticker`, `OrderBook`), and dispatched to the correct callback function.
- *Files:* `test_binance_http_gateway.py`, `test_binance_ws_gateway.py`, `test_mexc_http_gateway.py`, `test_mexc_ws_gateway.py`

### Trading Brain (WSDC Logic)
The `TradeManager` is tested heavily using mock data injections.
- **Threshold Integrity:** Verifies that the `min_history_density`, `consensus_short_term`, and `consensus_struct` variables properly restrict `TradeState` transitions (e.g., ensuring the bot stays `HOLD` during whipsaws).
- **Position State Reversals:** Verifies that `_construct_new_order` correctly calculates dynamic position sizes (closing old + opening new) when `TradeState.REVERSE_BUY` or `REVERSE_SELL` is triggered.
- *Files:* `test_trade_manager.py`, `test_strategy_pipeline.py`

---

## 2. Integration Testing Layer

Integration tests verify that the multi-threaded queues and network sockets behave correctly in a live environment. These tests connect to the public internet.

- **WebSocket Interface:** Connects to actual Binance and MEXC live feeds for 15 seconds, subscribes to the `BTCUSDT` ticker, and ensures `Ticker` objects are successfully populated and retrieved.
- **Pipeline Data Flow:** Simulates live data hitting the `WebSocketInterface`, flowing through the `DataCollector` (appending to the DataFrame), being picked up by the `DataProcessor`, and finally popping out of the `PipelineController`.
- *Files:* `test_websocket_interface.py`, `test_dm_output.py`

---

## Running the Tests Locally

It is highly recommended to run the **Unit Suite** locally before every commit.

```bash
# Activate your virtual environment
source .venv/bin/activate

# Run ONLY the fast unit tests (skip network/slow tests)
pytest -m "not integration" -v

# Run the FULL suite (Unit + Integration)
pytest -v

# Run tests with Coverage Report
pytest --cov=src -m "not integration"
```

## CI/CD Integration

The testing suite is fully integrated into GitHub Actions (`.github/workflows/ci.yml`). The CI pipeline is separated into parallel jobs:
1. **Static Analysis:** `flake8` and `mypy` ensure formatting and type safety.
2. **Fast Unit Tests:** Runs the mocked unit suite (`pytest -m "not integration"`).
3. **Integration Tests:** Runs the network suite to verify exchange APIs haven't broken.
