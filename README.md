# 🚀 AutoCryptoTrading System

An automated, multi-container algorithmic cryptocurrency trading system built for real-time market data ingestion, high-speed limit orderbook calculations, strategy execution, and historical data persistence.

---

## 🏗️ Architecture Overview

The system is structured as a multi-container microservice architecture composed of dedicated Docker components:

```
AutoCryptoTrading (Root Orchestrator)
│
├── 🤖 bot/          -> Python Trading Bot (Strategy execution, exchanges, signals)
├── ⚡ orderbook/    -> C++ Orderbook Engine (High-performance depth builder & L2/L3 calculations)
└── 🗄️ db/           -> TimescaleDB / PostgreSQL (Time-series tick/candle & trade persistence)
```

---

## 📁 Repository & Component Breakdown

| Component | Language / Stack | Git Repository | Role & Responsibilities |
| :--- | :--- | :--- | :--- |
| **`bot/`** | Python 3.10 | Submodule / Sub-repo | Connects to exchanges (Binance, MEXC), runs technical analysis (WSDC strategy), manages trades. |
| **`orderbook/`** | C++17 / CMake | Submodule / Sub-repo | High-throughput limit order book engine for fast orderbook matching and depth snapshots. |
| **`db/`** | TimescaleDB (PostgreSQL 15) | Submodule / Sub-repo | Stores market tick data, OHLCV candles, strategy logs, and executed trade records. |

---

## ⚡ Getting Started

### Prerequisites
- [Docker](https://www.docker.com/) & Docker Compose
- [Git](https://git-scm.com/)

### 1. Environment Configuration
Copy the template environment file:
```bash
cp .env.example .env
```

### 2. Launch System Containers
To build and launch all containers in detached mode:
```bash
docker-compose up -d --build
```

### 3. Check Container Status
```bash
docker-compose ps
```

### 4. View Component Logs
- **All logs:** `docker-compose logs -f`
- **Bot component:** `docker-compose logs -f bot`
- **Orderbook engine:** `docker-compose logs -f orderbook`
- **Database:** `docker-compose logs -f db`

---

## 🛠️ Submodule & Development Management

Each service directory (`bot/`, `orderbook/`, `db/`) functions as an independent module with its own Git system.

```bash
# Check status across root & submodules
git status

# Push or pull changes within individual components
cd bot && git status
```

