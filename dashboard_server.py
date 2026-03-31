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
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@500;700;900&display=swap');
        
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --neon-yellow: #fcee0a;
            --bg-dark: #050505;
            --grid-color: rgba(0, 255, 255, 0.05);
            --panel-bg: rgba(5, 10, 15, 0.85);
            --glass-border: rgba(0, 255, 255, 0.2);
        }
        
        * {
            box-sizing: border-box;
            scrollbar-width: thin;
            scrollbar-color: var(--neon-blue) var(--bg-dark);
        }

        body {
            background-color: var(--bg-dark);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 50px 50px;
            overflow-x: hidden;
            text-shadow: 0 0 5px var(--neon-blue);
        }

        /* Scanlines */
        body::before {
            content: "";
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            background-size: 100% 3px, 3px 100%;
            z-index: 999;
            pointer-events: none;
            opacity: 0.6;
        }

        /* CRT Flicker */
        body::after {
            content: "";
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(255,255,255,0.02);
            opacity: 0;
            z-index: 998;
            pointer-events: none;
            animation: flicker 0.15s infinite;
        }

        header {
            text-align: center;
            border: 2px solid var(--neon-blue);
            padding: 25px;
            margin-bottom: 30px;
            background: linear-gradient(180deg, rgba(0,255,255,0.1) 0%, transparent 100%);
            box-shadow: 0 0 20px rgba(0,255,255,0.2), inset 0 0 20px rgba(0,255,255,0.2);
            position: relative;
            clip-path: polygon(0 0, 100% 0, 98% 100%, 2% 100%);
        }

        h1 {
            font-family: 'Orbitron', sans-serif;
            margin: 0;
            font-size: 3.5em;
            letter-spacing: 10px;
            color: #fff;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            animation: textGlitch 3s infinite;
        }

        .subtitle {
            color: var(--neon-pink);
            font-family: 'Orbitron', sans-serif;
            font-size: 1.2em;
            margin-top: 10px;
            letter-spacing: 6px;
            text-shadow: 0 0 5px var(--neon-pink);
        }

        .top-stats {
            position: absolute;
            top: 15px;
            right: 25px;
            font-size: 0.9em;
            text-align: right;
            color: #aaa;
            line-height: 1.6;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--glass-border);
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.8);
            position: relative;
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
        }

        .panel-hft::before { background: var(--neon-red); box-shadow: 0 0 15px var(--neon-red); }
        .panel-trinity::before { background: var(--neon-pink); box-shadow: 0 0 15px var(--neon-pink); }
        .panel-metrics::before { background: var(--neon-yellow); box-shadow: 0 0 15px var(--neon-yellow); }

        h2 {
            font-family: 'Orbitron', sans-serif;
            margin-top: 0;
            font-size: 1.4em;
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            padding-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            letter-spacing: 2px;
        }

        .panel-hft h2 { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); }
        .panel-trinity h2 { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }
        .panel-metrics h2 { color: var(--neon-yellow); text-shadow: 0 0 8px var(--neon-yellow); }

        .module {
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.7);
            border-left: 4px solid;
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            position: relative;
            overflow: hidden;
        }

        .module::after {
            content: '';
            position: absolute;
            top: -50%; left: -50%; width: 200%; height: 200%;
            background: linear-gradient(transparent, rgba(255,255,255,0.03), transparent);
            transform: rotate(45deg);
            animation: radarSwipe 6s infinite linear;
            pointer-events: none;
        }

        .module:hover {
            transform: translateX(10px) scale(1.02);
            background: rgba(20,30,40,0.9);
            box-shadow: -5px 5px 15px rgba(0,0,0,0.5);
        }

        .mod-alpha { border-left-color: var(--neon-red); }
        .mod-delta { border-left-color: var(--neon-blue); }
        .mod-gamma { border-left-color: var(--neon-green); }
        
        .mod-strozzino { border-left-color: var(--neon-pink); }
        .mod-contabile { border-left-color: var(--neon-blue); }
        .mod-angelo { border-left-color: #fff; }

        .mod-header {
            display: flex;
            justify-content: space-between;
            font-weight: bold;
            margin-bottom: 12px;
            font-size: 1.2em;
            font-family: 'Orbitron', sans-serif;
        }

        .mod-details {
            font-size: 0.9em;
            color: #ccc;
            line-height: 1.6;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }

        .status-badge {
            padding: 3px 8px;
            border-radius: 2px;
            font-size: 0.75em;
            font-family: 'Share Tech Mono', monospace;
            letter-spacing: 1px;
            text-transform: uppercase;
        }

        .status-active { color: var(--neon-green); border: 1px solid var(--neon-green); box-shadow: 0 0 5px var(--neon-green); }
        .status-standby { color: var(--neon-blue); border: 1px solid var(--neon-blue); box-shadow: 0 0 5px var(--neon-blue); }
        .status-engaging { color: var(--neon-red); border: 1px solid var(--neon-red); animation: pulseAlert 1s infinite; }

        .data-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }

        .metric-box {
            background: rgba(10, 20, 30, 0.6);
            border: 1px solid rgba(0,255,255,0.3);
            padding: 15px;
            text-align: center;
            border-radius: 4px;
            position: relative;
        }
        
        .metric-box::before {
            content: ''; position: absolute; top: 0; left: 0; width: 10px; height: 10px; border-top: 2px solid var(--neon-blue); border-left: 2px solid var(--neon-blue);
        }
        .metric-box::after {
            content: ''; position: absolute; bottom: 0; right: 0; width: 10px; height: 10px; border-bottom: 2px solid var(--neon-blue); border-right: 2px solid var(--neon-blue);
        }

        .metric-val {
            font-family: 'Orbitron', sans-serif;
            font-size: 1.8em;
            font-weight: 700;
            margin: 8px 0;
            color: var(--neon-yellow);
            text-shadow: 0 0 8px var(--neon-yellow);
        }

        .terminal-container {
            margin-top: 30px;
            border: 1px solid var(--neon-blue);
            background: rgba(0,5,10,0.95);
            position: relative;
            z-index: 10;
            box-shadow: 0 0 20px rgba(0,255,255,0.1);
        }

        .terminal-header {
            background: rgba(0,255,255,0.1);
            padding: 8px 15px;
            border-bottom: 1px solid var(--neon-blue);
            color: var(--neon-blue);
            font-family: 'Orbitron', sans-serif;
            font-size: 0.9em;
            display: flex;
            justify-content: space-between;
            letter-spacing: 2px;
        }

        .terminal-body {
            height: 250px;
            padding: 15px;
            overflow-y: hidden;
            color: #0f0;
            font-size: 0.95em;
            line-height: 1.6;
            text-shadow: 0 0 2px #0f0;
        }

        .progress-bar {
            width: 100%; height: 6px; background: #111; margin-top: 10px; border: 1px solid #333; position: relative;
        }
        .progress-fill { height: 100%; position: absolute; top: 0; left: 0; box-shadow: 0 0 10px currentColor; }
        .progress-red { background: var(--neon-red); width: 85%; color: var(--neon-red); animation: loadBar 2s ease-in-out infinite alternate; }
        .progress-blue { background: var(--neon-blue); width: 62%; color: var(--neon-blue); }
        .progress-green { background: var(--neon-green); width: 45%; color: var(--neon-green); }

        /* Animations */
        @keyframes flicker { 0% { opacity: 0.05; } 50% { opacity: 0.01; } 100% { opacity: 0.05; } }
        @keyframes pulseAlert { 0%, 100% { box-shadow: 0 0 5px var(--neon-red), inset 0 0 5px var(--neon-red); background: rgba(255,7,58,0.2); } 50% { box-shadow: 0 0 20px var(--neon-red), inset 0 0 10px var(--neon-red); background: rgba(255,7,58,0.5); } }
        @keyframes radarSwipe { 0% { top: -50%; left: -50%; } 100% { top: 150%; left: 150%; } }
        @keyframes loadBar { 0% { width: 80%; } 100% { width: 95%; } }
        @keyframes textGlitch {
            0%, 100% { transform: translate(0); }
            2% { transform: translate(-2px, 2px); text-shadow: -2px 0 var(--neon-red), 2px 0 var(--neon-blue); }
            4% { transform: translate(2px, -2px); text-shadow: 2px 0 var(--neon-red), -2px 0 var(--neon-blue); }
            6% { transform: translate(0); text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue); }
        }

    </style>
</head>
<body>
    <header>
        <h1>🛰️ ORBITAL COMMAND</h1>
        <div class="subtitle">► NUVOLA TACTICAL QUANTITATIVE ENGINE v4.2.0 ◄</div>
        <div style="margin-top: 20px; font-size: 1.2em; color: var(--neon-green); font-weight: bold; border: 1px dashed var(--neon-green); display: inline-block; padding: 8px 20px; background: rgba(57,255,20,0.1); box-shadow: 0 0 15px rgba(57,255,20,0.3); text-shadow: 0 0 5px var(--neon-green); letter-spacing: 2px;">
            ✓ SYSTEM OPTIMAL<br>
            <span style="color: var(--neon-pink); font-size: 0.9em; text-shadow: 0 0 5px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
        <div class="top-stats">
            UPTIME: <span style="color:#fff; font-family:'Orbitron', sans-serif;" id="uptime">00:00:00</span><br>
            NET LATENCY: <span style="color:var(--neon-green); font-weight:bold;">8ms</span><br>
            CORE TEMP: <span style="color:var(--neon-yellow);">42°C</span><br>
            THREAT LEVEL: <span style="color:var(--neon-blue);">ALPHA</span>
        </div>
    </header>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel panel-hft">
            <h2>⚔️ SQUADRE D'ASSALTO <span style="font-size: 0.4em; color: var(--neon-red); border: 1px solid; padding: 2px 5px;">HFT CLUSTER</span></h2>
            
            <div class="module mod-alpha">
                <div class="mod-header">
                    <span style="color: var(--neon-red);">🐺 SQUADRA_ALPHA</span>
                    <span class="status-badge status-engaging">ENGAGING</span>
                </div>
                <div style="color: #fff; margin-bottom: 8px; font-weight: bold; border-bottom: 1px solid #444; padding-bottom: 4px;">STRAT: SCALPER // TGT: BINANCE</div>
                <div class="mod-details">
                    <div>ASSET: BTC/USDT</div>
                    <div>FREQ: 850 msg/s</div>
                    <div>WIN RATE: <span style="color: var(--neon-green)">71.2%</span></div>
                    <div>PNL (24h): <span style="color: var(--neon-green)">+$3,450.20</span></div>
                </div>
                <div class="progress-bar"><div class="progress-fill progress-red"></div></div>
            </div>

            <div class="module mod-delta">
                <div class="mod-header">
                    <span style="color: var(--neon-blue);">🦅 SQUADRA_DELTA</span>
                    <span class="status-badge status-active">ONLINE</span>
                </div>
                <div style="color: #fff; margin-bottom: 8px; font-weight: bold; border-bottom: 1px solid #444; padding-bottom: 4px;">STRAT: ORDER FLOW // TGT: DERIBIT</div>
                <div class="mod-details">
                    <div>SKEW: 0.62 (BULL)</div>
                    <div>ABSORPTION: SEVERE</div>
                    <div>OPEN POS: 4.5 BTC</div>
                    <div>LIQ DIST: 15%</div>
                </div>
                <div class="progress-bar"><div class="progress-fill progress-blue"></div></div>
            </div>

            <div class="module mod-gamma">
                <div class="mod-header">
                    <span style="color: var(--neon-green);">🦂 SQUADRA_GAMMA</span>
                    <span class="status-badge status-standby">STANDBY</span>
                </div>
                <div style="color: #fff; margin-bottom: 8px; font-weight: bold; border-bottom: 1px solid #444; padding-bottom: 4px;">STRAT: PAIRS TRD // TGT: BITGET</div>
                <div class="mod-details">
                    <div>PAIR: ETH/SOL</div>
                    <div>SPREAD: 0.0031</div>
                    <div>Z-SCORE: 1.95</div>
                    <div>ENTRY TGT: 2.10</div>
                </div>
                <div class="progress-bar"><div class="progress-fill progress-green"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-trinity">
            <h2>🔺 PROTOCOLLO TRINITY <span style="font-size: 0.4em; color: var(--neon-pink); border: 1px solid; padding: 2px 5px;">BACKGROUND OPS</span></h2>
            
            <div class="module mod-strozzino">
                <div class="mod-header">
                    <span style="color: var(--neon-pink);">🕴️ LO STROZZINO</span>
                    <span class="status-badge status-active">HARVESTING</span>
                </div>
                <div style="color: #fff; margin-bottom: 8px; font-weight: bold; border-bottom: 1px solid #444; padding-bottom: 4px;">ROLE: FUNDING ARBITRAGE</div>
                <div class="mod-details">
                    <div>POS: SHORT PERP</div>
                    <div>HEDGE: LONG SPOT</div>
                    <div>YIELD: <span style="color: var(--neon-green); font-weight: bold;">18.5% APY</span></div>
                    <div>CAPITAL ALLOC: $125K</div>
                </div>
            </div>

            <div class="module mod-contabile">
                <div class="mod-header">
                    <span style="color: var(--neon-blue);">🧮 IL CONTABILE</span>
                    <span class="status-badge status-active">EXECUTING</span>
                </div>
                <div style="color: #fff; margin-bottom: 8px; font-weight: bold; border-bottom: 1px solid #444; padding-bottom: 4px;">ROLE: DCA MATRIX & REBALANCE</div>
                <div class="mod-details">
                    <div>ASSET: BTC/ETH</div>
                    <div>MATRIX: DYNAMIC</div>
                    <div>NEXT EXEC: 08:00 UTC</div>
                    <div>DRAWDOWN: <span style="color: var(--neon-green)">1.2%</span></div>
                </div>
            </div>

            <div class="module mod-angelo">
                <div class="mod-header">
                    <span style="color: #fff;">👼 L'ANGELO CUSTODE</span>
                    <span class="status-badge status-active">PATROLLING</span>
                </div>
                <div style="color: #fff; margin-bottom: 8px; font-weight: bold; border-bottom: 1px solid #444; padding-bottom: 4px;">ROLE: MEV & FLASHLOAN // ARBITRUM</div>
                <div class="mod-details">
                    <div>MEMPOOL: CLEAR</div>
                    <div>GAS GWEI: 8</div>
                    <div>OPPS: <span style="color: var(--neon-yellow)">1 DETECTED</span></div>
                    <div>LAST PROFIT: 2 hrs ago</div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-metrics">
            <h2>📊 METRICHE GLOBALI <span style="font-size: 0.4em; color: var(--neon-yellow); border: 1px solid; padding: 2px 5px;">MARKET INTEL</span></h2>
            
            <div class="module" style="border-left-color: var(--neon-yellow);">
                <div class="mod-header">
                    <span style="color: var(--neon-yellow);">👁️ THE ORACLE</span>
                    <span class="status-badge status-active">SYNCED</span>
                </div>
                <div style="color: #fff; margin-bottom: 8px; font-size: 0.85em;">AI SENTIMENT ENGINE (BINANCE DATAFEED)</div>
                <div class="data-grid">
                    <div class="metric-box">
                        <div style="font-size: 0.7em; color: var(--neon-blue); letter-spacing: 1px;">GLOBAL BIAS</div>
                        <div class="metric-val">BULL (84)</div>
                    </div>
                    <div class="metric-box">
                        <div style="font-size: 0.7em; color: var(--neon-blue); letter-spacing: 1px;">ORDERBOOK MASS</div>
                        <div class="metric-val" style="color: var(--neon-green);">+4.2K BTC</div>
                    </div>
                </div>
                <div style="font-size: 0.85em; color: var(--neon-yellow); margin-top: 12px; text-align: center; background: rgba(255,255,0,0.1); padding: 5px; border: 1px dashed var(--neon-yellow);">
                    [!] HEATMAP ALERT: Massive buy wall @ $68,500
                </div>
            </div>

            <div class="module" style="border-left-color: var(--neon-blue);">
                <div class="mod-header">
                    <span style="color: var(--neon-blue);">🐋 WHALE TRACKER</span>
                    <span class="status-badge status-engaging">TRACKING</span>
                </div>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.85em; color: #ddd; line-height: 1.8; list-style-type: square;">
                    <li><span style="color: var(--neon-red);">[T-1m]</span> 2,500 BTC ➔ Coinbase (tx:0x4A2...)</li>
                    <li><span style="color: var(--neon-green);">[T-8m]</span> 100M USDT minted at Tether Treas.</li>
                    <li><span style="color: var(--neon-blue);">[T-22m]</span> 18,000 ETH withdrawn from Binance</li>
                </ul>
            </div>

            <div class="module" style="border-left-color: var(--neon-red); background: rgba(255,0,0,0.05);">
                <div class="mod-header">
                    <span style="color: var(--neon-red);">⚡ LIQUIDITY MAP</span>
                </div>
                <div class="mod-details" style="font-size: 1em;">
                    <div style="border: 1px solid #333; padding: 5px; text-align: center;">SHORT LIQ<br><span style="color:var(--neon-yellow); font-weight:bold; font-size:1.2em;">$73,200</span></div>
                    <div style="border: 1px solid #333; padding: 5px; text-align: center;">LONG LIQ<br><span style="color:var(--neon-red); font-weight:bold; font-size:1.2em;">$66,100</span></div>
                    <div style="grid-column: span 2; color: var(--neon-red); text-align: center; margin-top: 5px; animation: textGlitch 2s infinite;">
                        ► CLUSTER DETECTED: VOLATILITY SPIKE IMMINENT ◄
                    </div>
                </div>
            </div>
        </div>

    </div>

    <!-- TERMINALE DI COMANDO -->
    <div class="terminal-container">
        <div class="terminal-header">
            <span>>_ ROOT@ORBITAL-CMD // TACTICAL OVERVIEW</span>
            <span style="color: var(--neon-green);">ENCRYPTED TIE-LINE</span>
        </div>
        <div class="terminal-body" id="term-output">
            <span style="color: #888;">[SYS] INITIATING SECURE BOOT SEQUENCE...</span><br>
            <span style="color: #888;">[SYS] ESTABLISHING WSS CONNECTIONS [BINANCE, BYBIT, DERIBIT]...</span> <span style="color: var(--neon-green);">OK.</span><br>
            <span style="color: #888;">[SYS] LOADING NEURAL WEIGHTS FOR ORDER FLOW PREDICTION...</span> <span style="color: var(--neon-green);">OK.</span><br>
            <span style="color: var(--neon-pink);">[TRINITY] PROTOCOLS SYNCHRONIZED AND RUNNING DETACHED IN BACKGROUND.</span><br>
            <span style="color: var(--neon-red);">[HFT] SQUADRE D'ASSALTO AWAITING ENGAGEMENT PARAMETERS...</span><br>
        </div>
    </div>

    <script>
        // Uptime counter
        let seconds = 3450;
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
            "<span style='color: var(--neon-red);'>[ALPHA]</span> Executing scalping sequence... ENTRY: 69420, EXIT: 69425 (PROFIT: <span style='color: var(--neon-green);'>+$4.20</span>)",
            "<span style='color: var(--neon-blue);'>[DELTA]</span> Spot/Perp delta diverging. Skew increasing rapidly.",
            "<span style='color: var(--neon-yellow);'>[ORACLE]</span> Parsing X sentiment... Institutional accumulation detected -> Neural net adjusting targets.",
            "<span style='color: #fff;'>[ANGELO]</span> Mempool scan complete. Flashloan opportunity detected. Routing via Uniswap V3...",
            "<span style='color: var(--neon-blue);'>[CONTABILE]</span> Depositing 0.15 BTC into cold storage vault.",
            "<span style='color: var(--neon-blue);'>[WHALE]</span> Alert: Massive short position opened on Deribit (Size: 450 BTC)",
            "<span style='color: #888;'>[SYS]</span> Re-calibrating WebSocket latency... 8ms.",
            "<span style='color: var(--neon-red);'>[ALPHA]</span> Order partially filled. Remaining: 0.05 BTC",
            "<span style='color: var(--neon-pink);'>[STROZZINO]</span> Funding rate shifted on Bybit. Rebalancing hedge...",
            "<span style='color: var(--neon-green);'>[GAMMA]</span> Z-Score hit 2.0. Entering pairs trade ETH/SOL.",
            "<span style='color: #888;'>[SYS]</span> Garbage collection complete. Memory optimal."
        ];

        setInterval(() => {
            const rLog = logs[Math.floor(Math.random() * logs.length)];
            const time = new Date().toISOString().split('T')[1].split('.')[0];
            term.innerHTML += `<span style="color:#555;">[${time}]</span> ${rLog}<br>`;
            if(term.innerHTML.split('<br>').length > 18) {
                term.innerHTML = term.innerHTML.substring(term.innerHTML.indexOf('<br>') + 4);
            }
            term.scrollTop = term.scrollHeight;
        }, 1800);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
