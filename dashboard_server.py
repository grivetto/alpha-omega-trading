import os
import signal
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND [NUVOLA CORE]</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --neon-yellow: #ffff00;
            --bg-dark: #020202;
            --grid-color: rgba(57, 255, 20, 0.1);
            --panel-bg: rgba(5, 10, 5, 0.85);
        }
        
        * {
            box-sizing: border-box;
            scrollbar-width: thin;
            scrollbar-color: var(--neon-green) var(--bg-dark);
        }

        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 15px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            overflow-x: hidden;
            text-shadow: 0 0 3px var(--neon-green);
        }

        /* Scanline effect */
        body::after {
            content: " ";
            display: block;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        header {
            text-align: center;
            border: 2px solid var(--neon-green);
            padding: 20px;
            margin-bottom: 20px;
            background: linear-gradient(90deg, transparent, rgba(57, 255, 20, 0.1), transparent);
            box-shadow: inset 0 0 20px rgba(57,255,20,0.2), 0 0 15px rgba(57,255,20,0.4);
            position: relative;
        }

        h1 {
            margin: 0;
            font-size: 3em;
            letter-spacing: 8px;
            animation: glitch 4s infinite;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
        }

        .subtitle {
            color: var(--neon-blue);
            font-size: 1.2em;
            margin-top: 10px;
            letter-spacing: 4px;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 1;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid #333;
            border-top: 3px solid;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.5);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.8), transparent);
            opacity: 0.5;
        }

        .panel-hft { border-top-color: var(--neon-red); box-shadow: inset 0 0 20px rgba(255, 7, 58, 0.1); }
        .panel-trinity { border-top-color: var(--neon-pink); box-shadow: inset 0 0 20px rgba(255, 0, 255, 0.1); }
        .panel-metrics { border-top-color: var(--neon-blue); box-shadow: inset 0 0 20px rgba(0, 255, 255, 0.1); }

        h2 {
            margin-top: 0;
            font-size: 1.5em;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel-hft h2 { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }
        .panel-trinity h2 { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
        .panel-metrics h2 { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); }

        .module {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0,0,0,0.6);
            border-left: 3px solid;
            transition: all 0.2s;
        }

        .module:hover {
            transform: translateX(5px);
            background: rgba(20,20,20,0.8);
        }

        .mod-alpha { border-left-color: var(--neon-red); }
        .mod-delta { border-left-color: var(--neon-yellow); }
        .mod-gamma { border-left-color: var(--neon-blue); }
        
        .mod-strozzino { border-left-color: var(--neon-pink); }
        .mod-contabile { border-left-color: var(--neon-green); }
        .mod-angelo { border-left-color: #fff; }

        .mod-header {
            display: flex;
            justify-content: space-between;
            font-weight: bold;
            margin-bottom: 8px;
            font-size: 1.1em;
        }

        .mod-details {
            font-size: 0.85em;
            color: #aaa;
            line-height: 1.4;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 5px;
        }

        .status-badge {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.8em;
            animation: pulse 2s infinite;
            background: rgba(0,0,0,0.8);
        }

        .status-active { color: var(--neon-green); border: 1px solid var(--neon-green); }
        .status-standby { color: var(--neon-yellow); border: 1px solid var(--neon-yellow); animation: none; }
        .status-engaging { color: var(--neon-red); border: 1px solid var(--neon-red); animation: blink 0.5s infinite; }

        .data-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .metric-box {
            background: rgba(0, 0, 0, 0.8);
            border: 1px solid #444;
            padding: 10px;
            text-align: center;
        }

        .metric-val {
            font-size: 1.8em;
            font-weight: bold;
            margin: 5px 0;
            color: var(--neon-green);
        }

        .terminal-container {
            margin-top: 25px;
            border: 1px solid #333;
            background: rgba(0,0,0,0.9);
            position: relative;
            z-index: 1;
        }

        .terminal-header {
            background: #111;
            padding: 5px 10px;
            border-bottom: 1px solid #333;
            color: #888;
            font-size: 0.9em;
            display: flex;
            justify-content: space-between;
        }

        .terminal-body {
            height: 200px;
            padding: 10px;
            overflow-y: hidden;
            color: #0f0;
            font-size: 0.9em;
            line-height: 1.5;
        }

        @keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(57,255,20,0.4); } 70% { box-shadow: 0 0 0 5px rgba(57,255,20,0); } 100% { box-shadow: 0 0 0 0 rgba(57,255,20,0); } }
        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 rgba(255,0,0,0.75), -0.05em -0.025em 0 rgba(0,255,0,0.75), -0.025em 0.05em 0 rgba(0,0,255,0.75); }
            14% { text-shadow: 0.05em 0 0 rgba(255,0,0,0.75), -0.05em -0.025em 0 rgba(0,255,0,0.75), -0.025em 0.05em 0 rgba(0,0,255,0.75); }
            15% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,0.75), 0.025em 0.025em 0 rgba(0,255,0,0.75), -0.05em -0.05em 0 rgba(0,0,255,0.75); }
            49% { text-shadow: -0.05em -0.025em 0 rgba(255,0,0,0.75), 0.025em 0.025em 0 rgba(0,255,0,0.75), -0.05em -0.05em 0 rgba(0,0,255,0.75); }
            50% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,0.75), 0.05em 0 0 rgba(0,255,0,0.75), 0 -0.05em 0 rgba(0,0,255,0.75); }
            99% { text-shadow: 0.025em 0.05em 0 rgba(255,0,0,0.75), 0.05em 0 0 rgba(0,255,0,0.75), 0 -0.05em 0 rgba(0,0,255,0.75); }
            100% { text-shadow: -0.025em 0 0 rgba(255,0,0,0.75), -0.025em -0.025em 0 rgba(0,255,0,0.75), -0.025em -0.05em 0 rgba(0,0,255,0.75); }
        }

        .progress-bar {
            width: 100%;
            height: 4px;
            background: #222;
            margin-top: 5px;
            border-radius: 2px;
            overflow: hidden;
        }
        .progress-fill { height: 100%; background: var(--neon-green); width: 68%; }
        .progress-red { background: var(--neon-red); width: 85%; }
        .progress-blue { background: var(--neon-blue); width: 42%; }

    </style>
</head>
<body>
    <header>
        <h1>🛰️ ORBITAL COMMAND</h1>
        <div class="subtitle">NUVOLA TACTICAL QUANTITATIVE DASHBOARD v3.0.0</div>
        <div style="margin-top: 15px; font-size: 1.2em; color: var(--neon-pink); font-weight: bold; border: 1px solid var(--neon-pink); display: inline-block; padding: 5px 15px; background: rgba(255,0,255,0.1); box-shadow: 0 0 10px rgba(255,0,255,0.3); text-shadow: 0 0 5px var(--neon-pink);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
        <div style="position: absolute; top: 10px; right: 20px; font-size: 0.8em; text-align: right; color: #888;">
            UPTIME: <span style="color:#fff" id="uptime">99:99:99</span><br>
            LATENCY: <span style="color:var(--neon-green)">12ms</span><br>
            DEFCON: <span style="color:var(--neon-yellow)">3</span>
        </div>
    </header>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel panel-hft">
            <h2>⚔️ SQUADRE D'ASSALTO <span style="font-size: 0.5em; color: #888;">[HFT CLUSTER]</span></h2>
            
            <div class="module mod-alpha">
                <div class="mod-header">
                    <span>🐺 SQUADRA_ALPHA</span>
                    <span class="status-badge status-engaging">ENGAGING</span>
                </div>
                <div style="color: #fff; margin-bottom: 5px;">STRAT: Scalper // TGT: Binance</div>
                <div class="mod-details">
                    <div>PAIR: BTC/USDT</div>
                    <div>FREQ: 450 msgs/s</div>
                    <div>WIN RATE: <span style="color: var(--neon-green)">68.4%</span></div>
                    <div>PNL (24h): <span style="color: var(--neon-green)">+$2,140.50</span></div>
                </div>
                <div class="progress-bar"><div class="progress-fill progress-red"></div></div>
            </div>

            <div class="module mod-delta">
                <div class="mod-header">
                    <span>🦅 SQUADRA_DELTA</span>
                    <span class="status-badge status-active">ONLINE</span>
                </div>
                <div style="color: #fff; margin-bottom: 5px;">STRAT: Order Flow // TGT: Deribit</div>
                <div class="mod-details">
                    <div>SKEW: 0.45 (BULL)</div>
                    <div>ABSORPTION: HIGH</div>
                    <div>OPEN POS: 2.5 BTC</div>
                    <div>LIQ DIST: 12%</div>
                </div>
                <div class="progress-bar"><div class="progress-fill" style="width: 75%;"></div></div>
            </div>

            <div class="module mod-gamma">
                <div class="mod-header">
                    <span>🦂 SQUADRA_GAMMA</span>
                    <span class="status-badge status-standby">STANDBY</span>
                </div>
                <div style="color: #fff; margin-bottom: 5px;">STRAT: Pairs Trading // TGT: Bitget</div>
                <div class="mod-details">
                    <div>PAIR: ETH/SOL</div>
                    <div>SPREAD: 0.0024</div>
                    <div>Z-SCORE: 1.8</div>
                    <div>ENTRY TGT: 2.0</div>
                </div>
                <div class="progress-bar"><div class="progress-fill progress-blue"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-trinity">
            <h2>🔺 PROTOCOLLO TRINITY <span style="font-size: 0.5em; color: #888;">[BACKGROUND OPS]</span></h2>
            
            <div class="module mod-strozzino">
                <div class="mod-header">
                    <span>🕴️ LO STROZZINO</span>
                    <span class="status-badge status-active">ACTIVE</span>
                </div>
                <div style="color: #fff; margin-bottom: 5px;">ROLE: Funding Arbitrage</div>
                <div class="mod-details">
                    <div>POS: SHORT PERP</div>
                    <div>HEDGE: LONG SPOT</div>
                    <div>YIELD: <span style="color: var(--neon-green)">14.2% APY</span></div>
                    <div>CAPITAL: $50,000</div>
                </div>
            </div>

            <div class="module mod-contabile">
                <div class="mod-header">
                    <span>🧮 IL CONTABILE</span>
                    <span class="status-badge status-active">ACTIVE</span>
                </div>
                <div style="color: #fff; margin-bottom: 5px;">ROLE: DCA Matrix & Rebalance</div>
                <div class="mod-details">
                    <div>ASSET: BTC</div>
                    <div>THRES: < $65,000</div>
                    <div>NEXT EXEC: 04:00 UTC</div>
                    <div>DRAWDOWN: 4.2%</div>
                </div>
            </div>

            <div class="module mod-angelo">
                <div class="mod-header">
                    <span>👼 L'ANGELO CUSTODE</span>
                    <span class="status-badge status-active">MONITORING</span>
                </div>
                <div style="color: #fff; margin-bottom: 5px;">ROLE: MEV & Flashloans // Arbitrum</div>
                <div class="mod-details">
                    <div>MEMPOOL: CLEAR</div>
                    <div>GAS GWEI: 12</div>
                    <div>OPPS: 0 DETECTED</div>
                    <div>LAST: -4 hrs ago</div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-metrics">
            <h2>📊 METRICHE DI MERCATO <span style="font-size: 0.5em; color: #888;">[GLOBAL INTEL]</span></h2>
            
            <div class="module">
                <div class="mod-header" style="color: var(--neon-yellow);">
                    <span>👁️ THE ORACLE</span>
                    <span>SENTIMENT ENGINE</span>
                </div>
                <div class="data-grid" style="margin-top: 10px;">
                    <div class="metric-box">
                        <div style="font-size: 0.8em; color: #888;">GLOBAL BIAS</div>
                        <div class="metric-val">BULL (72)</div>
                    </div>
                    <div class="metric-box">
                        <div style="font-size: 0.8em; color: #888;">ORDERBOOK PRESSURE</div>
                        <div class="metric-val" style="color: var(--neon-blue);">BIDS HEAVY</div>
                    </div>
                </div>
                <div style="font-size: 0.85em; color: #aaa; margin-top: 10px; text-align: center;">> HEATMAP: Massive buy wall @ $68,000</div>
            </div>

            <div class="module">
                <div class="mod-header" style="color: var(--neon-blue);">
                    <span>🐋 WHALE TRACKER</span>
                    <span class="status-badge status-engaging">ALERT</span>
                </div>
                <ul style="margin: 0; padding-left: 15px; font-size: 0.85em; color: #ccc;">
                    <li>[T-2m] 1,500 BTC -> Coinbase (tx:0x8F4...)</li>
                    <li>[T-12m] 50M USDT minted at Tether Treasury</li>
                    <li>[T-45m] 12,000 ETH withdrawn from Binance</li>
                </ul>
            </div>

            <div class="module">
                <div class="mod-header" style="color: var(--neon-red);">
                    <span>⚡ LIQUIDITY MAP</span>
                </div>
                <div class="mod-details">
                    <div>SHORT LIQ: $72,500</div>
                    <div>LONG LIQ: $64,200</div>
                    <div style="grid-column: span 2; color: var(--neon-yellow);">> CLUSTER DETECTED: HIGH VOLATILITY IMMINENT</div>
                </div>
            </div>
        </div>

    </div>

    <!-- TERMINALE DI COMANDO -->
    <div class="terminal-container">
        <div class="terminal-header">
            <span>TERMINAL // ROOT@ORBITAL-CMD</span>
            <span>SECURE CONNECTION</span>
        </div>
        <div class="terminal-body" id="term-output">
            [SYS] BOOT SEQUENCE INITIATED...<br>
            [SYS] CONNECTING TO EXCHANGE WEBSOCKETS (BINANCE, BYBIT, DERIBIT)... OK.<br>
            [SYS] LOADING ML WEIGHTS FOR ORDER FLOW PREDICTION... OK.<br>
            [TRINITY] PROTOCOLS SYNCHRONIZED AND RUNNING DETACHED.<br>
            [HFT] SQUADRE D'ASSALTO AWAITING ENGAGEMENT PARAMETERS...<br>
        </div>
    </div>

    <script>
        // Uptime counter
        let seconds = 0;
        setInterval(() => {
            seconds++;
            const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
            const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
            const s = String(seconds % 60).padStart(2, '0');
            document.getElementById('uptime').innerText = `${h}:${m}:${s}`;
        }, 1000);

        // Terminal simulation
        const term = document.getElementById('term-output');
        const logs = [
            "[ALPHA] Executing scalping sequence... ENTRY: 69420, EXIT: 69425 (PROFIT: +$4.20)",
            "[DELTA] Spot/Perp delta diverging. Skew increasing.",
            "[ORACLE] Parsing Twitter sentiment... Elon Musk tweet detected -> Neural net adjusting targets.",
            "[ANGELO] Mempool scan complete. No profitable flashloan routes.",
            "[CONTABILE] Depositing 0.05 BTC into cold storage vault.",
            "[WHALE] Alert: Large short position opened on Deribit (Size: 250 BTC)",
            "[SYS] Re-calibrating WebSocket latency... 11ms.",
            "[ALPHA] Order partially filled. Remaining: 0.15 BTC",
            "[STROZZINO] Funding rate shifted. Rebalancing hedge..."
        ];

        setInterval(() => {
            const rLog = logs[Math.floor(Math.random() * logs.length)];
            const time = new Date().toISOString().split('T')[1].split('.')[0];
            term.innerHTML += `[${time}] ${rLog}<br>`;
            if(term.innerHTML.split('<br>').length > 15) {
                term.innerHTML = term.innerHTML.substring(term.innerHTML.indexOf('<br>') + 4);
            }
            term.scrollTop = term.scrollHeight;
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Using specific port, making sure it restarts
    app.run(host='0.0.0.0', port=5000, debug=False)
