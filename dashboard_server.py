from flask import Flask, render_template_string
import os
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA 🌌 ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@500;700;900&display=swap');
        
        :root {
            --bg-base: #050508;
            --neon-green: #00ffcc;
            --neon-red: #ff003c;
            --neon-purple: #b800e6;
            --neon-blue: #0088ff;
            --neon-yellow: #fcee0a;
            --grid-color: rgba(0, 255, 204, 0.05);
        }
        
        * { box-sizing: border-box; }

        body {
            background-color: var(--bg-base);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 204, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 204, 0.03) 1px, transparent 1px);
            background-size: 40px 40px;
            text-transform: uppercase;
        }

        /* CRT Overlay & Scanlines */
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.2) 50%, rgba(0,0,0,0.2));
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 9999;
        }

        .crt-flicker {
            animation: flicker 0.15s infinite;
        }
        @keyframes flicker {
            0% { opacity: 0.95; }
            50% { opacity: 1; }
            100% { opacity: 0.98; }
        }

        /* Header */
        header {
            text-align: center;
            margin-bottom: 30px;
            position: relative;
        }

        h1 {
            font-family: 'Orbitron', sans-serif;
            font-size: 3.5rem;
            font-weight: 900;
            color: #fff;
            margin: 0;
            letter-spacing: 5px;
            text-shadow: 
                0 0 5px #fff,
                0 0 10px #fff,
                0 0 20px var(--neon-green),
                0 0 40px var(--neon-green),
                0 0 80px var(--neon-green);
        }

        .subtitle {
            font-size: 1.2rem;
            color: var(--neon-yellow);
            text-shadow: 0 0 10px var(--neon-yellow);
            margin-top: 10px;
            letter-spacing: 2px;
        }

        .sys-status {
            display: inline-block;
            margin-top: 15px;
            padding: 5px 15px;
            border: 1px solid var(--neon-blue);
            background: rgba(0, 136, 255, 0.1);
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
            border-radius: 3px;
        }

        /* Layout Grid */
        .dashboard {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 25px;
            max-width: 1800px;
            margin: 0 auto;
        }
        @media (max-width: 1200px) {
            .dashboard { grid-template-columns: 1fr 1fr; }
        }
        @media (max-width: 800px) {
            .dashboard { grid-template-columns: 1fr; }
        }

        /* Panels */
        .panel {
            background: rgba(5, 5, 8, 0.85);
            border: 1px solid var(--neon-green);
            position: relative;
            backdrop-filter: blur(10px);
            box-shadow: 
                inset 0 0 30px rgba(0, 255, 204, 0.05), 
                0 0 20px rgba(0, 255, 204, 0.1);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .panel-header {
            background: rgba(0, 255, 204, 0.1);
            padding: 15px 20px;
            border-bottom: 1px solid var(--neon-green);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green);
            margin: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .panel-content {
            padding: 20px;
            flex-grow: 1;
        }

        /* Theme Variants */
        .panel.red { border-color: var(--neon-red); box-shadow: inset 0 0 30px rgba(255, 0, 60, 0.05), 0 0 20px rgba(255, 0, 60, 0.1); }
        .panel.red .panel-header { background: rgba(255, 0, 60, 0.1); border-bottom-color: var(--neon-red); }
        .panel.red .panel-title { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); }

        .panel.purple { border-color: var(--neon-purple); box-shadow: inset 0 0 30px rgba(184, 0, 230, 0.05), 0 0 20px rgba(184, 0, 230, 0.1); }
        .panel.purple .panel-header { background: rgba(184, 0, 230, 0.1); border-bottom-color: var(--neon-purple); }
        .panel.purple .panel-title { color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); }

        .panel.blue { border-color: var(--neon-blue); box-shadow: inset 0 0 30px rgba(0, 136, 255, 0.05), 0 0 20px rgba(0, 136, 255, 0.1); }
        .panel.blue .panel-header { background: rgba(0, 136, 255, 0.1); border-bottom-color: var(--neon-blue); }
        .panel.blue .panel-title { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); }

        /* Status Indicator / Radar */
        .radar-box {
            width: 30px; height: 30px;
            border-radius: 50%;
            border: 1px dashed currentColor;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .radar-box::before {
            content: '';
            position: absolute;
            width: 50%; height: 50%;
            background: currentColor;
            border-radius: 50%;
            box-shadow: 0 0 10px currentColor;
            animation: pulse-dot 1.5s infinite alternate;
        }
        .radar-box::after {
            content: '';
            position: absolute;
            width: 100%; height: 100%;
            border-radius: 50%;
            border: 2px solid currentColor;
            border-top-color: transparent;
            animation: spin 2s linear infinite;
        }
        
        @keyframes spin { 100% { transform: rotate(360deg); } }
        @keyframes pulse-dot { 0% { opacity: 0.3; transform: scale(0.8); } 100% { opacity: 1; transform: scale(1.2); } }

        /* Items Lists */
        .agent-list {
            list-style: none; padding: 0; margin: 0;
            display: flex; flex-direction: column; gap: 15px;
        }

        .agent-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 15px;
            position: relative;
            transition: all 0.3s ease;
        }
        
        .agent-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 4px; height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }
        .panel.red .agent-card::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        .panel.purple .agent-card::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }

        .agent-card:hover {
            background: rgba(255, 255, 255, 0.05);
            transform: translateX(5px);
            border-color: rgba(255, 255, 255, 0.3);
        }

        .agent-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 10px;
            font-size: 1.2rem; font-weight: bold;
        }

        .agent-name { color: #fff; letter-spacing: 1px; }

        .status-badge {
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 2px;
            background: rgba(0, 255, 204, 0.2);
            color: var(--neon-green);
            border: 1px solid var(--neon-green);
            animation: blink 2s infinite;
        }
        .panel.red .status-badge { background: rgba(255, 0, 60, 0.2); color: var(--neon-red); border-color: var(--neon-red); }
        .panel.purple .status-badge { background: rgba(184, 0, 230, 0.2); color: var(--neon-purple); border-color: var(--neon-purple); }

        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }

        .agent-details {
            font-size: 0.9rem; color: #ccc;
            display: grid; grid-template-columns: auto 1fr; gap: 5px 15px;
        }
        .agent-details span.label { color: rgba(255,255,255,0.5); }
        .agent-details span.val { color: var(--neon-green); }
        .panel.red .agent-details span.val { color: var(--neon-red); }
        .panel.purple .agent-details span.val { color: var(--neon-purple); }

        /* Market Grid */
        .market-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 15px;
            margin-bottom: 20px;
        }
        .market-box {
            border: 1px solid rgba(0, 136, 255, 0.3);
            background: rgba(0, 136, 255, 0.05);
            padding: 15px; text-align: center;
            position: relative;
            overflow: hidden;
        }
        .market-box::after {
            content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
            background: linear-gradient(to right, transparent, rgba(255,255,255,0.1), transparent);
            transform: rotate(45deg) translateY(-100%);
            animation: sweep 4s infinite linear;
        }
        @keyframes sweep { 0% { transform: rotate(45deg) translateY(-100%); } 100% { transform: rotate(45deg) translateY(100%); } }

        .market-box .label { font-size: 0.85rem; color: rgba(0, 136, 255, 0.8); margin-bottom: 8px; }
        .market-box .value { font-family: 'Orbitron', sans-serif; font-size: 1.5rem; color: #fff; text-shadow: 0 0 10px var(--neon-blue); }
        .market-box.alert .value { color: var(--neon-red); text-shadow: 0 0 15px var(--neon-red); animation: pulse-text 1s infinite alternate; }

        @keyframes pulse-text { 0% { opacity: 0.7; transform: scale(0.98); } 100% { opacity: 1; transform: scale(1.02); } }

        /* Terminal Logs */
        .terminal-container {
            border: 1px solid var(--neon-blue);
            background: rgba(0, 0, 0, 0.6);
            padding: 15px;
            height: 250px;
            overflow: hidden;
            position: relative;
            box-shadow: inset 0 0 15px rgba(0, 136, 255, 0.1);
        }
        .terminal-container::before {
            content: 'LIVE FEED // COMMS';
            position: absolute; top: 0; left: 0; background: var(--neon-blue); color: #000;
            font-size: 0.7rem; padding: 2px 8px; font-weight: bold;
        }
        .terminal-content {
            margin-top: 15px;
            display: flex; flex-direction: column; justify-content: flex-end; height: 100%;
        }
        .log-entry {
            font-size: 0.85rem; margin-bottom: 5px; color: #aaa;
            animation: type-in 0.3s ease-out forwards;
        }
        .log-entry .timestamp { color: var(--neon-blue); margin-right: 10px; }
        .log-entry.critical { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .log-entry.success { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        
        @keyframes type-in { 0% { opacity: 0; transform: translateY(10px); } 100% { opacity: 1; transform: translateY(0); } }

    </style>
</head>
<body class="crt-flicker">
    <div class="scanlines"></div>

    <header>
        <h1>🌌 NUVOLA</h1>
        <div class="subtitle">--- ORBITAL COMMAND CENTER ---</div>
        <div class="sys-status">
            [ UPLINK SECURE ] 📡 <span id="clock">00:00:00</span> UTC // AES-256 GCM ENCRYPTED
        </div>
        <div style="margin-top: 15px; font-size: 1.2rem; color: #00ffcc; text-shadow: 0 0 10px #00ffcc; font-weight: bold; border: 1px solid #00ffcc; display: inline-block; padding: 5px 15px; background: rgba(0, 255, 204, 0.1);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </header>

    <div class="dashboard">

        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel red">
            <div class="panel-header">
                <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
                <div class="radar-box" style="color: var(--neon-red);"></div>
            </div>
            <div class="panel-content">
                <ul class="agent-list">
                    <li class="agent-card">
                        <div class="agent-header">
                            <span class="agent-name">🐺 SQUADRA_ALPHA</span>
                            <span class="status-badge">ENGAGED</span>
                        </div>
                        <div class="agent-details">
                            <span class="label">STRATEGY:</span> <span class="val">High-Frequency Scalper</span>
                            <span class="label">TARGET:</span> <span class="val">Binance Spot (BTC/USDT)</span>
                            <span class="label">LATENCY:</span> <span class="val">14ms [DIRECT CONNECT]</span>
                            <span class="label">WINRATE:</span> <span class="val">71.4% (Last 1H)</span>
                        </div>
                    </li>
                    <li class="agent-card">
                        <div class="agent-header">
                            <span class="agent-name">🦅 SQUADRA_DELTA</span>
                            <span class="status-badge">MONITORING</span>
                        </div>
                        <div class="agent-details">
                            <span class="label">STRATEGY:</span> <span class="val">Order Flow / Imbalance</span>
                            <span class="label">TARGET:</span> <span class="val">CME & Deribit Options</span>
                            <span class="label">VOLUME:</span> <span class="val">$4.2M Notional</span>
                            <span class="label">STATUS:</span> <span class="val">Awaiting Liquidity Spike</span>
                        </div>
                    </li>
                    <li class="agent-card">
                        <div class="agent-header">
                            <span class="agent-name">🐍 SQUADRA_GAMMA</span>
                            <span class="status-badge">ARBITRAGE</span>
                        </div>
                        <div class="agent-details">
                            <span class="label">STRATEGY:</span> <span class="val">Statistical Pairs Trading</span>
                            <span class="label">TARGET:</span> <span class="val">Bitget Futures (SOL/ETH)</span>
                            <span class="label">SPREAD:</span> <span class="val">0.08% [WIDENING]</span>
                            <span class="label">LEVERAGE:</span> <span class="val">25x</span>
                        </div>
                    </li>
                </ul>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <div class="panel-header">
                <h2 class="panel-title">🔺 PROTOCOLLO TRINITY</h2>
                <div class="radar-box" style="color: var(--neon-purple);"></div>
            </div>
            <div class="panel-content">
                <ul class="agent-list">
                    <li class="agent-card">
                        <div class="agent-header">
                            <span class="agent-name">🦇 LO STROZZINO</span>
                            <span class="status-badge">HARVESTING</span>
                        </div>
                        <div class="agent-details">
                            <span class="label">ROLE:</span> <span class="val">Funding Rate Arbitrage</span>
                            <span class="label">VECTOR:</span> <span class="val">Perpetual Swaps (Cross-Ex)</span>
                            <span class="label">EST. YIELD:</span> <span class="val">+24.8% APY</span>
                            <span class="label">EXPOSURE:</span> <span class="val">DELTA-NEUTRAL</span>
                        </div>
                    </li>
                    <li class="agent-card">
                        <div class="agent-header">
                            <span class="agent-name">🧮 IL CONTABILE</span>
                            <span class="status-badge">BACKGROUND</span>
                        </div>
                        <div class="agent-details">
                            <span class="label">ROLE:</span> <span class="val">Smart DCA & Rebalancing</span>
                            <span class="label">VAULT:</span> <span class="val">Cold Storage Multi-Sig</span>
                            <span class="label">ASSETS:</span> <span class="val">BTC, ETH, SOL</span>
                            <span class="label">NEXT BUY:</span> <span class="val">T-Minus 02:45:10</span>
                        </div>
                    </li>
                    <li class="agent-card">
                        <div class="agent-header">
                            <span class="agent-name">🛡️ L'ANGELO CUSTODE</span>
                            <span class="status-badge">DEFENDING</span>
                        </div>
                        <div class="agent-details">
                            <span class="label">ROLE:</span> <span class="val">MEV Sniper & Protection</span>
                            <span class="label">NETWORK:</span> <span class="val">Arbitrum One RPC</span>
                            <span class="label">TX SENT:</span> <span class="val">3,892</span>
                            <span class="label">BLOCKS:</span> <span class="val">142 WON</span>
                        </div>
                    </li>
                </ul>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel blue">
            <div class="panel-header">
                <h2 class="panel-title">📡 METRICHE GLOBAL</h2>
                <div class="radar-box" style="color: var(--neon-blue);"></div>
            </div>
            <div class="panel-content">
                <div class="market-grid">
                    <div class="market-box">
                        <div class="label">👁️ THE ORACLE (BINANCE)</div>
                        <div class="value" style="color: #00ffcc; text-shadow: 0 0 10px #00ffcc;">BULLISH 89%</div>
                    </div>
                    <div class="market-box alert">
                        <div class="label">🐋 WHALE TRACKER</div>
                        <div class="value">CRITICAL MOVEMENT</div>
                    </div>
                    <div class="market-box">
                        <div class="label">📊 LIQUIDITY INDEX</div>
                        <div class="value">DEEP</div>
                    </div>
                    <div class="market-box">
                        <div class="label">💻 ORBITAL CORE LOAD</div>
                        <div class="value">18.4%</div>
                    </div>
                </div>

                <div class="terminal-container">
                    <div class="terminal-content" id="terminal">
                        <!-- Logs injected via JS -->
                    </div>
                </div>
            </div>
        </div>

    </div>

    <script>
        // Clock
        setInterval(() => {
            const now = new Date();
            document.getElementById('clock').innerText = now.toISOString().replace('T', ' ').substr(0, 19);
        }, 1000);

        // Terminal Logs
        const logs = [
            { t: "[WHALE_TRACKER]", m: "12,000 ETH transferred to Kraken (Tx: 0x8f2...)", c: "critical" },
            { t: "[THE_ORACLE]", m: "RSI Bearish Divergence negated on 1H BTC/USDT", c: "success" },
            { t: "[TRINITY_SYS]", m: "Il Contabile successfully balanced ETH holding", c: "success" },
            { t: "[ANGELO_CUSTODE]", m: "MEV Sandwich attack blocked. Saved: $450", c: "success" },
            { t: "[HFT_ALPHA]", m: "Executed 15 trades in 2.4s. PnL: +$12.50", c: "" },
            { t: "[HFT_GAMMA]", m: "Spread target hit. Entering Short SOL / Long ETH", c: "" },
            { t: "[WHALE_TRACKER]", m: "Tether Treasury minted 1B USDT", c: "critical" },
            { t: "[STROZZINO]", m: "Funding rate spike detected on Bybit. Re-allocating.", c: "" },
            { t: "[SYSTEM]", m: "Ping to Binance API: 11ms. Connection stable.", c: "" },
            { t: "[HFT_DELTA]", m: "Order book spoofing detected. Adjusting bids.", c: "critical" }
        ];

        const terminal = document.getElementById('terminal');
        
        function addLog() {
            const entry = logs[Math.floor(Math.random() * logs.length)];
            const div = document.createElement('div');
            div.className = 'log-entry ' + entry.c;
            
            const time = new Date().toISOString().substr(11, 8);
            div.innerHTML = `<span class="timestamp">[${time}]</span> <strong>${entry.t}</strong> ${entry.m}`;
            
            terminal.appendChild(div);
            
            if (terminal.childElementCount > 8) {
                terminal.removeChild(terminal.firstChild);
            }
        }

        // Initial logs
        for(let i=0; i<6; i++) { setTimeout(addLog, i * 200); }
        // Random new logs
        setInterval(addLog, 2500 + Math.random() * 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Porta esplicita per evitare conflitti e bind a tutte le interfacce
    app.run(host='0.0.0.0', port=5000)
