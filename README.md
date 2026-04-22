# 🚀 DENARO: Autonomous Trading Infrastructure

DENARO is a distributed, self-healing trading system designed for survival, protection, and professional growth. It transitions from simple bot execution to a closed-loop autonomous architecture.

## 🏗 Architecture

The system is distributed across three specialized nodes:

### 1. NUVOLA (Control & Execution Node)
*   **Role**: The "Brain" and main trading hub.
*   **Core Components**:
    *   **Grid Bot v3**: High-frequency, self-healing grid strategy with adaptive order sizing.
    *   **Optimization Agent (`optimizer.py`)**: Analyzes real-time volatility (ATR) and dynamically adjusts grid spreads to maximize profit.
    *   **Stability Guardian (`guardian_v3.py`)**: Monitors bot health and ensures zero-downtime execution.
    *   **Infrastructure**: Systemd-managed services for automatic recovery and centralized logging.

### 2. MC2 (Development & Heavy-Lift Node)
*   **Role**: Physical server (16GB RAM) used for strategy development, backtesting, and heavy computation.
*   **Purpose**: Sandbox for testing new algorithms before deploying them to the cloud nodes.

### 3. MARCODG1 (Auxiliary Execution Node)
*   **Role**: Backup node and dedicated grid execution.
*   **Focus**: Stability and redundant trading capacity.

## 🧠 Autonomous Loop (The Learning Cycle)

The system operates on a continuous feedback loop:
`TRADING` $\rightarrow$ `ANALYSIS` $\rightarrow$ `OPTIMIZATION` $\rightarrow$ `REDEPLOYMENT`

1.  **Execution**: Bots place orders based on the current `grid_config.json`.
2.  **Analysis**: The `optimizer` analyzes the last 24h of price action and calculates the optimal spread.
3.  **Optimization**: Parameters are updated automatically in the config file.
4.  **Reload**: Bots detect config changes and adapt their grid in real-time without stopping.

## 🛡 Safety & Survival
*   **Circuit Breaker**: Integrated loss limits to prevent catastrophic drawdowns.
*   **Adaptive Sizing**: Order sizes are calculated based on available balance to prevent "Insufficient Funds" errors.
*   **Self-Healing**: Automatic synchronization of open orders on startup to prevent duplicate positions.

---
*Developed by Sergio - Focused on survival, protection, and professional intelligence.*
