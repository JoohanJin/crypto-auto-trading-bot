# TradeManager & Application Logging Tags Reference

## Overview

This document defines the standardized logging format and tags used throughout the AutoCryptoTrading project. All log messages follow a consistent structure for easy parsing, filtering, and monitoring across all modules (TradeManager, SystemManager, and Application).

---

## Log Levels & Usage Guidelines

| Level        | Usage                                               | When to Use                                           |
| ------------ | --------------------------------------------------- | ----------------------------------------------------- |
| **DEBUG**    | Detailed diagnostic info                            | Internal state inspection (rarely used)               |
| **INFO**     | General informational messages                      | Initialization, periodic stats, successful operations |
| **WARNING**  | Warning messages for potentially harmful situations | Retries, invalid data received, degraded performance  |
| **ERROR**    | Error messages for serious problems                 | Function failures, exceptions, recoverable errors     |
| **CRITICAL** | Critical messages for very serious errors           | Fatal errors, system shutdown, unrecoverable states   |

---

## Tag Directory

### 1. Initialization & Lifecycle

| Tag                      | Log Level | Purpose                                               | Format                                              |
| ------------------------ | --------- | ----------------------------------------------------- | --------------------------------------------------- |
| `[INIT_COMPLETE]`        | INFO      | TradeManager initialization complete with config      | `Ready \| Pair: X/Y \| Leverage: Z \| Threshold: N` |
| `[SYSTEM_INIT_COMPLETE]` | INFO      | SystemManager initialization complete with components | `Ready \| Components: N \| Status: operational`     |
| `[SYSTEM_INIT_ERROR]`    | CRITICAL  | SystemManager initialization failed                   | `Initialization failed \| Error: ErrorType: msg`    |
| `[SYSTEM_START]`         | INFO      | System starting main event loop                       | `Starting main event loop`                          |
| `[SYSTEM_SHUTDOWN]`      | WARNING   | System shutdown initiated (graceful or forced)        | `User interrupt signal received \| Action: exiting` |
| `[SYSTEM_RUNTIME_ERROR]` | CRITICAL  | Critical error during system runtime                  | `Runtime error \| Error: ErrorType: msg`            |
| `[SHUTDOWN]`             | INFO      | TradeManager shutdown/cleanup initiated               | `Cleanup initiated \| Threads: N \| Score: N`       |

### 2. Thread Management

| Tag              | Log Level | Purpose                     | Format                                       |
| ---------------- | --------- | --------------------------- | -------------------------------------------- |
| `[THREAD_START]` | INFO      | Thread successfully started | `ThreadName \| Status: running`              |
| `[THREAD_STOP]`  | INFO      | Thread successfully stopped | `ThreadName \| Status: stopped`              |
| `[THREAD_ERROR]` | ERROR     | Thread failed to start      | `ThreadName failed \| Error: ErrorType: msg` |

### 3. Trade Decision & Execution

| Tag                            | Log Level | Purpose                              | Format                                           |
| ------------------------------ | --------- | ------------------------------------ | ------------------------------------------------ |
| `[TRADE_DECISION_ERROR]`       | ERROR     | Error in trade decision logic        | `Failed \| Score: N \| Error: ErrorType: msg`    |
| `[TRADE_DECISION_CHECK_ERROR]` | ERROR     | Error checking position before trade | `Position check failed \| Error: ErrorType: msg` |
| `[TRADE_EXECUTION_ERROR]`      | ERROR     | Error executing a trade order        | `Trade: State \| Error: ErrorType: msg`          |

### 4. Order Management

| Tag                          | Log Level | Purpose                         | Format                                                |
| ---------------------------- | --------- | ------------------------------- | ----------------------------------------------------- |
| `[ORDER_CONSTRUCTION_ERROR]` | CRITICAL  | Error building Order object     | `Trade: State \| Error: ErrorType: msg`               |
| `[ORDER_REGISTRATION_ERROR]` | CRITICAL  | Error registering/storing order | `Type: BUY/SELL \| Price: N \| Error: ErrorType: msg` |

### 5. Signal Processing

| Tag              | Log Level | Purpose                               | Format                                     |
| ---------------- | --------- | ------------------------------------- | ------------------------------------------ |
| `[SIGNAL_STATS]` | INFO      | Periodic signal processing statistics | `Score: N \| Signal Processed`             |
| `[SIGNAL_ERROR]` | ERROR     | Error fetching/processing signals     | `Failed to fetch \| Error: ErrorType: msg` |

### 6. Data Fetching & Validation

| Tag                     | Log Level | Purpose                              | Format                                                                 |
| ----------------------- | --------- | ------------------------------------ | ---------------------------------------------------------------------- |
| `[SUCCESS]`             | INFO      | Network call succeeded after retries | `call_name() \| Attempt: N \| Response Type: Type`                     |
| `[INVALID_RESPONSE]`    | WARNING   | Network response has invalid type    | `call_name() \| Attempt: N \| Expected: X \| Got: Y \| Next Retry: Ns` |
| `[RETRY]`               | WARNING   | Network call failed, retrying        | `call_name() \| Attempt: N \| Error: ErrorType: msg \| Next Retry: Ns` |
| `[PRICE_FETCH_ERROR]`   | CRITICAL  | Cannot fetch current market price    | `Mark price unavailable \| Error: ErrorType: msg`                      |
| `[BALANCE_FETCH_ERROR]` | CRITICAL  | Cannot fetch account balance         | `Quote: USDT \| Error: ErrorType: msg`                                 |
| `[QUANTITY_CALC_ERROR]` | CRITICAL  | Cannot calculate trade quantity      | `Ticker: X \| Price: N \| Error: ErrorType: msg`                       |

### 7. System Manager Specific (SystemManager.py)

| Tag                     | Log Level | Purpose                                 | Format                                                   |
| ----------------------- | --------- | --------------------------------------- | -------------------------------------------------------- |
| `[COMPONENT_INIT]`      | INFO      | Individual component initialization     | `ComponentName initialized \| Status: active/ready`      |
| `[SERVICE_INIT]`        | INFO      | Service interface initialization        | `ServiceName initialized`                                |
| `[SERVICE_CLIENT_INIT]` | INFO      | Service client creation success         | `ClientName created`                                     |
| `[SERVICE_INTERFACE]`   | INFO      | Service interface summary               | `InterfaceName \| Clients registered: N`                 |
| `[SERVICE_INIT_ERROR]`  | CRITICAL  | Service or client initialization failed | `ServiceName/ClientName failed \| Error: ErrorType: msg` |
| `[CREDENTIAL_ERROR]`    | CRITICAL  | Missing or invalid credentials          | `Service \| Missing: fields or Error: ErrorType: msg`    |
| `[TELEGRAM_INIT_ERROR]` | CRITICAL  | Telegram bot initialization failed      | `Credentials missing or Error: ErrorType: msg`           |

### 8. Application Entry Point (main.py)

| Tag                    | Log Level | Purpose                           | Format                                                     |
| ---------------------- | --------- | --------------------------------- | ---------------------------------------------------------- |
| `[APP_START]`          | INFO      | Application startup initiated     | `Application starting \| Loading configuration`            |
| `[APP_INIT_COMPLETE]`  | INFO      | Application initialized and ready | `Application initialized \| Status: ready`                 |
| `[APP_LOOP_START]`     | INFO      | Main event loop starting          | `Entering main event loop`                                 |
| `[APP_SHUTDOWN]`       | WARNING   | Application graceful shutdown     | `User interrupt received \| Action: graceful shutdown`     |
| `[MAIN_RUNTIME_ERROR]` | CRITICAL  | Runtime error in main function    | `RuntimeError \| Error: RuntimeError: msg`                 |
| `[APP_STARTUP_ERROR]`  | CRITICAL  | Unexpected error during startup   | `Unexpected error during startup \| Error: ErrorType: msg` |

### 9. Broker Specific (src/brokers/**)

| Tag                 | Log Level | Purpose                             | Format                                           |
| ------------------- | --------- | ----------------------------------- | ------------------------------------------------ |
| `[BROKER_ERROR]`    | CRITICAL  | API error from the broker           | `Broker \| Status: N \| Error: msg`              |
| `[WS_OPEN]`         | INFO      | WebSocket connection opened         | `Broker \| URL: X \| Status: opened`             |
| `[WS_CLOSE]`        | WARNING   | WebSocket connection closed         | `Broker \| Status: N \| Reason: msg`             |
| `[WS_AUTH_SUCCESS]` | INFO      | WebSocket authentication successful | `Broker \| Status: authenticated`                |
| `[WS_AUTH_ERROR]`   | CRITICAL  | WebSocket authentication failed     | `Broker \| Error: ErrorType: msg`                |
| `[WS_RECONNECT]`    | WARNING   | WebSocket reconnection attempt      | `Broker \| Attempt: N \| Next Retry: Ns`         |
| `[WS_SUBSCRIBE]`    | INFO      | WebSocket subscription success      | `Broker \| Topic: X \| Status: subscribed`       |
| `[WS_UNSUBSCRIBE]`  | INFO      | WebSocket unsubscription success    | `Broker \| Topic: X \| Status: unsubscribed`     |
| `[WS_PING_PONG]`    | DEBUG     | WebSocket heartbeat activity        | `Broker \| Type: PING/PONG \| Status: success`   |

---

## Usage Patterns

### Pattern 1: Info Logs (Initialization, Stats)

```python
self.logger.info(f"[TAG] Message | Key1: {value1} | Key2: {value2}")
```

**Example:**

```python
self.logger.info(
    f"[INIT_COMPLETE] Ready | Pair: {self.trade_pair.ticker}/{self.trade_pair.quote} | "
    f"Leverage: {self.leverage} | Threshold: {self.score_threshold}"
)
```

### Pattern 2: Error Logs (Non-critical Failures)

```python
self.logger.error(f"[TAG] Message | Error: {type(e).__name__}: {str(e)}")
```

**Example:**

```python
self.logger.error(f"[SIGNAL_ERROR] Failed to fetch | Error: {type(e).__name__}: {str(e)}")
```

### Pattern 3: Critical Logs (Fatal Errors)

```python
self.logger.critical(f"[TAG] Message | Error: {type(e).__name__}: {str(e)}")
```

**Example:**

```python
self.logger.critical(
    f"[ORDER_CONSTRUCTION_ERROR] Trade: {buy_or_sell.name} | Error: {type(e).__name__}: {str(e)}"
)
```

### Pattern 4: Warning Logs (Retries, Invalid Data)

```python
self.logger.warning(f"[TAG] Message | Attempt: {attempt} | Next Retry: {delay:.2f}s")
```

**Example:**

```python
self.logger.warning(
    f"[RETRY] _get_account_info() | Attempt: 2 | "
    f"Error: ConnectionError: timeout | Next Retry: 2.00s"
)
```

---

## Field Naming Conventions

### Global Conventions

| Field           | Format                    | Example                            | Notes                                           |
| --------------- | ------------------------- | ---------------------------------- | ----------------------------------------------- |
| `Pair`          | `TICKER/QUOTE`            | `BTC/USDT`                         | Use forward slash, uppercase                    |
| `Leverage`      | Integer                   | `10`                               | Reference field variable `self.leverage`        |
| `Threshold`     | Integer                   | `2000`                             | Reference field variable `self.score_threshold` |
| `Score`         | Integer (can be negative) | `-1500`                            | Current accumulation score                      |
| `Price`         | Float, 2 decimals         | `45000.50`                         | Use `round(val, 2)`                             |
| `Attempt`       | Positive integer          | `1`, `2`, `3`                      | Retry attempt number                            |
| `Error`         | `ErrorType: message`      | `RuntimeError: Connection timeout` | Always include exception type                   |
| `Status`        | Predefined values         | `running` \| `failed`              | Use lowercase                                   |
| `Type`          | Trade direction           | `BUY` \| `SELL`                    | Uppercase                                       |
| `Threads`       | Non-negative integer      | `2`                                | Total thread count                              |
| `Response Type` | Class name                | `AccountInformation`               | Use `type(obj).__name__`                        |

### TradeManager-Specific Conventions

| Field         | Format                    | Example                     | Notes                           |
| ------------- | ------------------------- | --------------------------- | ------------------------------- |
| `ThreadName`  | String from `thread.name` | `Thread-Get-Signal`         | Direct reference to thread name |
| `Trade State` | Enum name                 | `NEW_BUY` \| `REVERSE_SELL` | Use `trade_state.name`          |
| `Order Type`  | Direction                 | `BUY` \| `SELL`             | Use `order_type_str` or enum    |
| `Ticker`      | Symbol                    | `BTC`                       | Just the ticker, not full pair  |
| `Quote`       | Currency                  | `USDT`                      | Just the quote currency         |
| `Call Name`   | Function identifier       | `_get_account_info`         | Use actual method name          |

### SystemManager-Specific Conventions

| Field                | Format                              | Example                                                 | Notes                                  |
| -------------------- | ----------------------------------- | ------------------------------------------------------- | -------------------------------------- |
| `Components`         | Positive integer                    | `7`                                                     | Total number of initialized components |
| `Clients registered` | Positive integer                    | `2`                                                     | Count of registered service clients    |
| `Service Name`       | Pascal case or SCREAMING_SNAKE_CASE | `BinanceFutureHttpClient` \| `BINANCE_WEBSOCKET_CLIENT` | Exact client class/instance name       |
| `Broker`             | Uppercase                           | `Binance` \| `MEXC`                                     | Broker identifier                      |

### Application-Level Conventions

| Field           | Format             | Example                             | Notes                          |
| --------------- | ------------------ | ----------------------------------- | ------------------------------ |
| `Status`        | Predefined values  | `ready` \| `operational`            | Use lowercase status terms     |
| `Configuration` | Type of config     | `Loading environment configuration` | Briefly describe config action |
| `Action`        | Action description | `graceful shutdown`                 | Expected recovery action       |

---

## Examples by Tag

### [INIT_COMPLETE]

```python
self.logger.info(
    f"[INIT_COMPLETE] Ready | Pair: {self.trade_pair.ticker}/{self.trade_pair.quote} | "
    f"Leverage: {self.leverage} | Threshold: {self.score_threshold}"
)
```

### [SHUTDOWN]

```python
self.logger.info("[SHUTDOWN] Cleanup initiated | Threads: %d | Score: %d", len(self.threads), self.trade_score)
```

### [THREAD_START]

```python
self.logger.info(f"[THREAD_START] {thread.name} | Status: running")
```

### [SIGNAL_STATS]

```python
self.logger.info(f"[SIGNAL_STATS] Score: {self.trade_score} | Signal Processed")
```

### [SUCCESS] (Retry wrapper)

```python
self.logger.info(
    f"[SUCCESS] {call_name}() | Attempt: {attempt + 1} | "
    f"Response Type: {type(response).__name__}"
)
```

### [RETRY] (Infinite retry with backoff)

```python
self.logger.warning(
    f"[RETRY] {call_name}() | Attempt: {attempt + 1} | "
    f"Error: {type(e).__name__}: {str(e)} | "
    f"Next Retry: {delay:.2f}s"
)
```

### [TRADE_DECISION_ERROR]

```python
self.logger.error(f"[TRADE_DECISION_ERROR] Failed | Score: {score} | Error: {type(e).__name__}: {str(e)}")
```

### [COMPONENT_INIT] (SystemManager)

```python
self.logger.info("Component DataPipeline created | Status: active")
```

### [CREDENTIAL_ERROR] (SystemManager)

```python
self.logger.critical(
    "[CREDENTIAL_ERROR] Binance HTTP | Missing: API_KEY or SECRET_KEY"
)
```

### [SERVICE_CLIENT_INIT] (SystemManager)

```python
self.logger.info("[SERVICE_CLIENT_INIT] Binance Future HTTP Client created")
```

### [SERVICE_INTERFACE] (SystemManager)

```python
self.logger.info(f"[SERVICE_INTERFACE] WebSocket Interface | Clients registered: 2")
```

### [SYSTEM_INIT_COMPLETE] (SystemManager)

```python
self.logger.info("[SYSTEM_INIT_COMPLETE] Ready | Components: 7 | Status: operational")
```

### [SYSTEM_SHUTDOWN] (SystemManager)

```python
self.logger.warning("[SYSTEM_SHUTDOWN] User interrupt signal received | Action: exiting")
```

### [APP_START] (main.py)

```python
logger.info("[APP_START] Application starting | Loading environment configuration")
```

### [APP_INIT_COMPLETE] (main.py)

```python
logger.info("[APP_INIT_COMPLETE] Application initialized | Status: ready")
```

### [APP_LOOP_START] (main.py)

```python
logger.info("[APP_LOOP_START] Entering main event loop")
```

### [APP_SHUTDOWN] (main.py)

```python
logger.warning("[APP_SHUTDOWN] User interrupt received | Action: graceful shutdown")
```

### [APP_STARTUP_ERROR] (main.py)

````python
logger.critical(
    f"[APP_STARTUP_ERROR] Unexpected error during startup | Error: {type(e).__name__}: {str(e)}"
)

## Future Enhancements

### Migration to Custom Exceptions

These tags can be replaced with custom exception classes for production use:

```python
class TradeManagerException(Exception):
    """Base exception for TradeManager"""
    pass

class ThreadError(TradeManagerException):
    """Thread failed to start"""
    pass

class OrderConstructionError(TradeManagerException):
    """Error building order"""
    pass

# Usage:
try:
    ...
except Exception as e:
    self.logger.error("[THREAD_ERROR] %s failed", thread.name, exc_info=True)
    raise ThreadError(f"Cannot start {thread.name}") from e
````

### Structured Logging

Consider migrating to structured logging libraries (e.g., `structlog`, `python-json-logger`) for JSON-formatted logs:

```json
{
  "timestamp": "2026-02-15T10:30:45.123Z",
  "level": "ERROR",
  "tag": "THREAD_ERROR",
  "thread_name": "Thread-Get-Signal",
  "error_type": "RuntimeError",
  "error_message": "Cannot acquire lock",
  "context": {
    "instance_name": "TRADE_MANAGER",
    "pair": "BTC/USDT"
  }
}
```

---

## Checklist for Adding New Tags

When adding a new log tag:

- [ ] Choose appropriate log level (INFO, WARNING, ERROR, CRITICAL)
- [ ] Define clear, descriptive tag name (PascalCase, max 20 chars)
- [ ] Document the purpose/context
- [ ] Provide example format with placeholder fields
- [ ] Add to relevant section (Initialization, Thread, Trade, Data, etc.)
- [ ] Include example code snippet
- [ ] Update field conventions if new fields are introduced

---

### 9. Broker Specific (src/brokers/**)

| Tag                 | Log Level | Purpose                             | Format                                           |
| ------------------- | --------- | ----------------------------------- | ------------------------------------------------ |
| `[BROKER_ERROR]`    | CRITICAL  | API error from the broker           | `Broker \| Status: N \| Error: msg`              |
| `[WS_OPEN]`         | INFO      | WebSocket connection opened         | `Broker \| URL: X \| Status: opened`             |
| `[WS_CLOSE]`        | WARNING   | WebSocket connection closed         | `Broker \| Status: N \| Reason: msg`             |
| `[WS_AUTH_SUCCESS]` | INFO      | WebSocket authentication successful | `Broker \| Status: authenticated`                |
| `[WS_AUTH_ERROR]`   | CRITICAL  | WebSocket authentication failed     | `Broker \| Error: ErrorType: msg`                |
| `[WS_RECONNECT]`    | WARNING   | WebSocket reconnection attempt      | `Broker \| Attempt: N \| Next Retry: Ns`         |
| `[WS_SUBSCRIBE]`    | INFO      | WebSocket subscription success      | `Broker \| Topic: X \| Status: subscribed`       |
| `[WS_UNSUBSCRIBE]`  | INFO      | WebSocket unsubscription success    | `Broker \| Topic: X \| Status: unsubscribed`     |
| `[WS_PING_PONG]`    | DEBUG     | WebSocket heartbeat activity        | `Broker \| Type: PING/PONG \| Status: success`   |

---

### 10. Data Management Specific (src/data/**)

| Tag                 | Log Level | Purpose                             | Format                                              |
| ------------------- | --------- | ----------------------------------- | --------------------------------------------------- |
| `[DATA_INIT]`       | INFO      | Data component initialization       | `ComponentName \| Status: ready`                    |
| `[DATA_CLEANUP]`    | INFO      | DataFrame maintenance (resizing)    | `Action: resized \| Rows: N \| Cleaned: N`          |
| `[DATA_ERROR]`      | ERROR     | Error in data collection/processing | `MethodName \| Error: ErrorType: msg`               |
| `[DATA_SAVE_ERROR]` | ERROR     | Error during data persistence       | `Persistence failed \| Error: ErrorType: msg`       |
| `[DATA_STATS]`      | INFO      | Data processing statistics          | `Type: IndexType \| Timestamp: N \| Status: pushed` |

---

### 11. Integrations Specific (src/integrations/**)

| Tag                  | Log Level | Purpose                             | Format                                              |
| -------------------- | --------- | ----------------------------------- | --------------------------------------------------- |
| `[INTEGRATION_INIT]` | INFO      | Integration component initialization| `ComponentName \| Status: ready`                    |
| `[MSG_SEND]`         | INFO      | External message sent success       | `Platform: X \| Status: sent`                       |
| `[MSG_ERROR]`         | ERROR     | External message delivery failed    | `Platform: X \| Error: ErrorType: msg`              |

---

### 12. Strategy Specific (src/strategy/**)

| Tag                  | Log Level | Purpose                             | Format                                              |
| -------------------- | --------- | ----------------------------------- | --------------------------------------------------- |
| `[STRATEGY_INIT]`    | INFO      | Strategy component initialization   | `ComponentName \| Status: ready`                    |
| `[STRATEGY_LOAD]`    | INFO      | Strategy configuration loaded       | `Count: N \| Source: Path`                          |
| `[SIGNAL_GEN]`       | INFO      | Signal generation event             | `Strategy: Name \| Signal: Type \| Status: success` |
| `[STRATEGY_ERROR]`   | ERROR     | Strategy execution/logic error       | `MethodName \| Error: ErrorType: msg`               |

---

## References


- **Logging Module**: `src/infrastructure/logging/set_logger.py`
- **TradeManager**: `src/trading/trade_manager.py`
- **SystemManager**: `src/infrastructure/system_manager.py`
- **Application Entry Point**: `src/main.py`
- **Configuration**: See top of `trade_manager.py` for inline reference table
