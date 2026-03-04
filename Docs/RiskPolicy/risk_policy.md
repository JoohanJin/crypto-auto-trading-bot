# AutoCryptoTrading Risk Management Policy

## 1. Governance & Context

### 1.1 Purpose
- Establish a repeatable framework that protects trading capital, preserves client trust, and keeps the automated system aligned with regulatory expectations.
- Ensure every trading module (`src/manager/data_collector_and_processor.py`, `src/manager/signal_generator.py`, `src/manager/trade_manager.py`) operates within clearly defined risk limits.
- Ensure every class and objects implemented should be designed under the strict software engineering concept. (SOLID)
  - Further refactoring is needed. Design Decision is still under-review for the next deployable version.

### 1.2 Scope & Boundaries
- Applies to all automated trading activities executed by the AutoCryptoTrading platform across futures markets supported in `src/binance/future.py`.
- Covers data ingestion, signal generation, execution, and supporting infrastructure (monitoring, logging, alerting).
- Excludes discretionary/manual trades; any manual override must be logged and reviewed in the next governance recap.

### 1.3 Roles & Responsibilities
- **Product Owner**: Approves strategic risk appetite, chairs governance reviews, signs off on major limit changes.
  - Need to be able to modify the strategy changes or modification.
    - Need to implement a separate class which can decide the strategy logic for fast phase changes in the trading strategy.
- **Risk Lead**:
  - Owns this policy,
  - maintains the risk register,
  - validates model changes affecting exposure or leverage.
- **Data Quality Lead** (`data_collector_and_processor.py`):
  - Ensures feed redundancy, 
  - monitors latency/outage metrics, 
  - escalates data anomalies.
- **Strategy Lead** (`signal_generator.py`):
  - Confirms strategy assumptions,
  - documents model risk,
  - proposes parameter updates subject to risk review.
- **Execution Lead** (`trade_manager.py`):
  - Implements position sizing,
  - leverage caps, and order throttles;
  - halts trading when limits breach.
- **DevOps/Infrastructure**:
  - Maintains deployment pipelines,
  - access control,
  - alerting,
  - disaster recovery for trading servics.

### 1.4 Reporting & Escalation
- Daily automated risk summary distributed to stakeholders covering exposure, P&L variance, limit breaches, and outstanding incidents.
- Immediate escalation to Risk Lead and Product Owner for:
  - Any hard limit breach (position cap, leverage ceiling, VaR tolerance).
  - Data feed outage > 5 minutes or repeated reconciliation mismatches.
  - Strategy behaving outside tested parameters (e.g., signal firing rate doubling).
- Monthly governance meeting to review risk metrics, incident post-mortems, and approve changes to controls.

### 1.5 Risk Appetite, Thresholds, & Criteria
- **Capital at Risk**:
  - Max 15% of deployable capital per position (trade_weight = 0.15);
  - Dynamic position sizing adjustments applied upon trend reversals.
  - Only one primary position (Long or Short) per time (Always-in-Market).
- **Leverage**:
  - Futures leverage hard limit 10x (Currently enforced in TradeManager);
  - any request above would be rejected under any circumstance.
- **Liquidity**:
  - Only trade pairs of BTC_USDT or BTC_USDC would be allowed;
  - Other trading pairs would be added in the future after risk validation.
- **Model Deviation**:
  - If live Sharpe drops 30% below backtest baseline over a rolling week,
  - trigger strategy review. (Under Review)
- **Operational Resilience**:
  - Recovery time objective (RTO) ≤ 15 minutes for trading infrastructure;
  - recovery point objective (RPO) ≤ 1 minute of trade data. (Under Review)

### 1.6 Documentation & Auditability
- Maintain all policy revisions in git with tagged releases.
- Persist governance meeting minutes, incident reports, and approval records in `/Docs/RiskPolicy/logs/`.
- All threshold changes must reference a ticket ID and include quantitative justification.

### 1.7 Testing Schema for CI/CD

---

## 2. Risk Categories

### 2.1 Operational (Software) Risks
- **Infrastructure Outage**: Cloud provider/Server downtime, container crashes, or deployment failures interrupt trading continuity.
- **Code Regression**: Uncaught bugs introduced via releases (e.g., flawed merge affecting `trade_manager.py` order flow).
- **Data Feed Failure**: Exchange API rate limits, schema changes, or malformed payloads compromise `data_collector_and_processor.py`.
- **Security Breach**: API key leakage, unauthorized access, or dependency vulnerabilities impacting confidentiality or availability.
- **Monitoring Blind Spots**: Alerting misconfigurations or log retention gaps prevent early issue detection.

### 2.2 Trading (Business Logic) Risks
- **Model Drift**: Forecast accuracy deterioration due to regime changes, degrading `signal_generator.py` outputs.
- **Execution Slippage**: Insufficient liquidity or adverse fills pushing real P&L outside modeled expectations.
- **Leverage/Exposure Breach**: Position sizing exceeding policy limits because of stale portfolio state or concurrency.
- **Correlation Concentration**: Multiple strategies piling into highly correlated assets, increasing portfolio drawdown risk.
- **Parameter Misconfiguration**: Incorrect risk inputs (stop levels, volatility multipliers) leading to outsized losses.
