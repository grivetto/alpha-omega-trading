import os
from flask import Flask, render_template_string
import logging

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command // KINETIC FRAMEWORK</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-cyan: #00ffff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --neon-yellow: #fdfd96;
            --bg-dark: #050505;
            --bg-panel: rgba(10, 20, 15, 0.85);
            --grid-color: rgba(57, 255, 20, 0.1);
        }
        
        @font-face {
            font-family: 'Terminus';
            src: local('Courier New'), monospace;
        }

        body {
            background-color: var(--bg-dark);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-green);
            font-family: 'Terminus', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }

        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        .crt-flicker {
            animation: crt-flicker 0.15s infinite;
        }

        @keyframes crt-flicker {
            0% { opacity: 0.95; }
            100% { opacity: 1; }
        }

        h1 {
            color: var(--neon-cyan);
            text-align: center;
            font-size: 2.5rem;
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan), 0 0 30px var(--neon-cyan);
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            margin-bottom: 5px;
            text-transform: uppercase;
        }
        
        .subtitle {
            text-align: center;
            color: var(--neon-purple);
            font-size: 1.2rem;
            text-shadow: 0 0 10px var(--neon-purple);
            margin-bottom: 40px;
            letter-spacing: 2px;
        }

        .sys-status {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-bottom: 30px;
            font-weight: bold;
            font-size: 1.1rem;
            background: rgba(0,0,0,0.6);
            padding: 10px;
            border: 1px dashed var(--neon-green);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 30px;
            max-width: 1600px;
            margin: 0 auto;
            position: relative;
            z-index: 10;
        }

        .panel {
            background-color: var(--bg-panel);
            border: 1px solid var(--neon-green);
            box-shadow: inset 0 0 20px rgba(57, 255, 20, 0.1), 0 0 15px rgba(57, 255, 20, 0.3);
            border-radius: 4px;
            padding: 25px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: inset 0 0 30px rgba(57, 255, 20, 0.2), 0 0 25px rgba(57, 255, 20, 0.6);
            border-color: var(--neon-cyan);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-cyan), transparent);
            animation: scanline 3s linear infinite;
        }

        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }

        h2 {
            font-size: 1.5rem;
            color: var(--neon-green);
            text-shadow: 0 0 8px var(--neon-green);
            border-bottom: 1px dashed rgba(57, 255, 20, 0.5);
            padding-bottom: 10px;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        ul { list-style: none; padding: 0; margin: 0; }
        
        li {
            margin: 20px 0;
            padding: 15px;
            background: rgba(0, 0, 0, 0.4);
            border-left: 3px solid var(--neon-cyan);
            border-radius: 0 4px 4px 0;
            position: relative;
        }
        
        .team-name {
            font-size: 1.2rem;
            font-weight: bold;
            color: #fff;
            text-shadow: 0 0 5px #fff;
        }

        .status { font-weight: bold; float: right; }
        .status.online { color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); }
        .status.standby { color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow); }
        .status.active { color: var(--neon-cyan); text-shadow: 0 0 10px var(--neon-cyan); animation: pulse 2s infinite; }
        .status.alert { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); animation: blink 1s infinite; }

        .metrics {
            margin-top: 10px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px;
            font-size: 0.85rem;
            color: #aaa;
        }
        
        .metrics span { color: var(--neon-cyan); }

        .data-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 20px;
        }

        .data-box {
            border: 1px solid rgba(0, 255, 255, 0.3);
            background: rgba(0, 255, 255, 0.05);
            padding: 15px;
            text-align: center;
            border-radius: 3px;
        }

        .data-box .label {
            font-size: 0.8rem;
            color: #888;
            margin-bottom: 5px;
            text-transform: uppercase;
        }

        .data-box .value {
            font-size: 1.4rem;
            font-weight: bold;
            color: var(--neon-cyan);
            text-shadow: 0 0 8px var(--neon-cyan);
        }

        .terminal {
            background: #000;
            border: 1px solid #333;
            padding: 15px;
            font-size: 0.8rem;
            height: 150px;
            overflow-y: hidden;
            color: #aaa;
            margin-top: 20px;
            position: relative;
        }
        
        .terminal::after {
            content: '_';
            animation: blink 1s infinite;
        }

        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        @keyframes pulse { 0% { opacity: 0.7; } 50% { opacity: 1; text-shadow: 0 0 20px var(--neon-cyan); } 100% { opacity: 0.7; } }

        .footer {
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            color: #444;
            font-size: 0.9rem;
            border-top: 1px solid #222;
        }
    </style>
</head>
<body class="crt-flicker">

    <h1>🛰️ ORBITAL COMMAND</h1>
    <div class="subtitle">NUVOLA // ADVANCED KINETIC FRAMEWORK</div>

    <div class="sys-status" style="margin-bottom: 15px;">
        <span>[ CORE: <span class="status online">STABLE</span> ]</span>
        <span>[ UPLINK: <span class="status active">SECURE-TLS</span> ]</span>
        <span>[ LATENCY: <span class="status active">8ms</span> ]</span>
        <span>[ THREAT LEVEL: <span class="status online">ZERO</span> ]</span>
    </div>

    <div class="sys-status" style="color: var(--neon-cyan); border-color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan);">
        <span>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="container">
        
        <!-- SEZIONE 1: SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span class="team-name">🐺 SQUADRA_ALPHA</span>
                    <span class="status online">[ ONLINE ]</span>
                    <div style="color: #888; font-size: 0.85rem; margin-top: 5px;">> Binance Scalper Engine</div>
                    <div class="metrics">
                        <div>Win Rate: <span>68.4%</span></div>
                        <div>Trades/Hr: <span>142</span></div>
                        <div>24h PnL: <span style="color: var(--neon-green)">+$842.50</span></div>
                        <div>Drawdown: <span style="color: var(--neon-yellow)">-1.2%</span></div>
                    </div>
                </li>
                <li>
                    <span class="team-name">🌊 SQUADRA_DELTA</span>
                    <span class="status standby">[ STANDBY ]</span>
                    <div style="color: #888; font-size: 0.85rem; margin-top: 5px;">> Order Flow Analyzer</div>
                    <div class="metrics">
                        <div>Status: <span style="color: var(--neon-yellow)">Awaiting Sweeps</span></div>
                        <div>Depth: <span>Analyzed</span></div>
                        <div>Target: <span>Liquidity Voids</span></div>
                        <div>Imbalance: <span style="color: var(--neon-cyan)">Detected</span></div>
                    </div>
                </li>
                <li>
                    <span class="team-name">⚖️ SQUADRA_GAMMA</span>
                    <span class="status online">[ ONLINE ]</span>
                    <div style="color: #888; font-size: 0.85rem; margin-top: 5px;">> Bitget Pairs Trading</div>
                    <div class="metrics">
                        <div>Z-Score: <span>+2.14</span></div>
                        <div>Exposure: <span>Delta Neutral</span></div>
                        <div>Leg 1: <span>LONG BTC</span></div>
                        <div>Leg 2: <span style="color: var(--neon-red)">SHORT ETH</span></div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <p style="color: #aaa; font-size: 0.85rem; border-bottom: 1px solid #333; padding-bottom: 10px;">
                > BACKGROUND DAEMONS ONLINE. OVERSEEING ASSET PRESERVATION.
            </p>
            <ul>
                <li style="border-left-color: var(--neon-purple);">
                    <span class="team-name">🩸 LO STROZZINO</span>
                    <span class="status active">[ EXTRACTING ]</span>
                    <div style="color: #888; font-size: 0.85rem; margin-top: 5px;">> Funding Rate Arbitrage</div>
                    <div class="metrics">
                        <div>Yield: <span style="color: var(--neon-purple)">+18.4% APY</span></div>
                        <div>Hedged: <span>100%</span></div>
                        <div>Delta: <span>0.04%</span></div>
                        <div>Capital: <span>$24,000</span></div>
                    </div>
                </li>
                <li style="border-left-color: var(--neon-yellow);">
                    <span class="team-name">🧮 IL CONTABILE</span>
                    <span class="status online">[ ACCUMULATING ]</span>
                    <div style="color: #888; font-size: 0.85rem; margin-top: 5px;">> DCA & Rebalancing</div>
                    <div class="metrics">
                        <div>Asset: <span>BTC</span></div>
                        <div>Avg Entry: <span>$62,450</span></div>
                        <div>Next Buy: <span style="color: var(--neon-yellow)">In 14h 22m</span></div>
                        <div>Slippage: <span>0.01%</span></div>
                    </div>
                </li>
                <li style="border-left-color: var(--neon-green);">
                    <span class="team-name">🦇 L'ANGELO CUSTODE</span>
                    <span class="status active">[ PATROLLING ]</span>
                    <div style="color: #888; font-size: 0.85rem; margin-top: 5px;">> Arbitrum MEV & Flashloans</div>
                    <div class="metrics">
                        <div>Blocks Checked: <span>1,432,109</span></div>
                        <div>Gas Sent: <span>0.4 ETH</span></div>
                        <div>Flash Exec: <span>3</span></div>
                        <div>Profit: <span style="color: var(--neon-green)">+1.2 ETH</span></div>
                    </div>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            
            <div style="margin-bottom: 15px; padding: 10px; background: rgba(255,0,60,0.1); border: 1px solid var(--neon-red);">
                <div style="font-weight: bold; color: var(--neon-red); margin-bottom: 5px;">🐳 WHALE TRACKER ALERTS:</div>
                <div class="status alert" style="float:none; font-size: 0.9rem;">
                    [!!] 5,200 BTC -> BINANCE (HOT WALLET)
                </div>
                <div style="color: #888; font-size: 0.8rem; margin-top: 3px;">Time: T-4 Mins | Risk: HIGH</div>
            </div>

            <div style="margin-bottom: 15px; padding: 10px; background: rgba(0,255,255,0.1); border: 1px solid var(--neon-cyan);">
                <div style="font-weight: bold; color: var(--neon-cyan); margin-bottom: 5px;">🔮 THE ORACLE (Sentiment):</div>
                <div style="font-size: 1.2rem; font-weight: bold; text-shadow: 0 0 5px var(--neon-cyan);">GREED (78/100)</div>
                <div style="color: #888; font-size: 0.8rem; margin-top: 3px;">Social Vol: +14% | Funding Bias: LONG</div>
            </div>

            <div class="data-grid">
                <div class="data-box">
                    <div class="label">BTC/USDT</div>
                    <div class="value" style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">68,432.10</div>
                </div>
                <div class="data-box">
                    <div class="label">ETH/USDT</div>
                    <div class="value" style="color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red);">3,541.20</div>
                </div>
                <div class="data-box">
                    <div class="label">VOLATILITY (VIX)</div>
                    <div class="value">HIGH</div>
                </div>
                <div class="data-box">
                    <div class="label">GLOBAL LIQ</div>
                    <div class="value">$2.42T</div>
                </div>
            </div>

            <div class="terminal" id="term-output">
                > Initializing quant models...<br>
                > Connecting to Binance FIX API... OK<br>
                > Loading neural weights for SQUADRA_ALPHA... Done<br>
                > The Oracle: Scanning Twitter/X sentiment...<br>
                > L'Angelo Custode: Pending mempool txs (Arbitrum)...<br>
                > Listening for websocket stream...
            </div>
            <script>
                const term = document.getElementById('term-output');
                const msgs = [
                    "> Market maker detected on orderbook (Depth 5)",
                    "> SQUADRA_ALPHA executing scalp LONG (0.5 BTC)",
                    "> Il Contabile: Balance check OK",
                    "> Lo Strozzino: Funding rate shifted, recalculating delta",
                    "> Whale Tracker: 10,000 ETH moved off Coinbase",
                    "> SQUADRA_GAMMA: Spread expanding, entering position"
                ];
                setInterval(() => {
                    const msg = msgs[Math.floor(Math.random() * msgs.length)];
                    term.innerHTML += '<br>' + msg;
                    term.scrollTop = term.scrollHeight;
                }, 3000);
            </script>
        </div>

    </div>

    <div class="footer">
        // NUVOLA ORBITAL COMMAND v4.2.0 // AUTHORIZED PERSONNEL ONLY // ENCRYPTED CONNECTION //
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)