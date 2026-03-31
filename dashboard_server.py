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
            --neon-blue: #00ffff;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --neon-yellow: #fcee0a;
            --neon-orange: #ffaa00;
            --bg-dark: #020202;
            --grid-color: rgba(0, 255, 255, 0.08);
            --panel-bg: rgba(5, 10, 15, 0.9);
            --glass-border: rgba(0, 255, 255, 0.3);
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
            background-size: 40px 40px;
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
            opacity: 0.7;
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
            animation: flicker 0.12s infinite;
        }

        header {
            text-align: center;
            border: 2px solid var(--neon-blue);
            padding: 25px;
            margin-bottom: 30px;
            background: linear-gradient(180deg, rgba(0,255,255,0.15) 0%, transparent 100%);
            box-shadow: 0 0 30px rgba(0,255,255,0.3), inset 0 0 20px rgba(0,255,255,0.2);
            position: relative;
            clip-path: polygon(0 0, 100% 0, 98% 100%, 2% 100%);
        }

        h1 {
            font-family: 'Orbitron', sans-serif;
            margin: 0;
            font-size: 3.8em;
            letter-spacing: 12px;
            color: #fff;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue), 0 0 80px var(--neon-blue);
            animation: textGlitch 4s infinite;
        }

        .subtitle {
            color: var(--neon-pink);
            font-family: 'Orbitron', sans-serif;
            font-size: 1.3em;
            margin-top: 10px;
            letter-spacing: 8px;
            text-shadow: 0 0 10px var(--neon-pink);
        }

        .top-stats {
            position: absolute;
            top: 15px;
            right: 25px;
            font-size: 0.9em;
            text-align: right;
            color: #ccc;
            line-height: 1.6;
            background: rgba(0, 0, 0, 0.6);
            padding: 10px;
            border: 1px solid var(--glass-border);
            box-shadow: 0 0 10px rgba(0,255,255,0.2);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
            gap: 30px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--glass-border);
            padding: 25px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.9), inset 0 0 20px rgba(0,255,255,0.05);
            position: relative;
            backdrop-filter: blur(10px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 4px;
        }

        .panel-hft::before { background: var(--neon-red); box-shadow: 0 0 20px var(--neon-red); }
        .panel-hft { border-color: rgba(255, 7, 58, 0.4); }
        
        .panel-trinity::before { background: var(--neon-pink); box-shadow: 0 0 20px var(--neon-pink); }
        .panel-trinity { border-color: rgba(255, 0, 255, 0.4); }
        
        .panel-metrics::before { background: var(--neon-yellow); box-shadow: 0 0 20px var(--neon-yellow); }
        .panel-metrics { border-color: rgba(252, 238, 10, 0.4); }

        h2 {
            font-family: 'Orbitron', sans-serif;
            margin-top: 0;
            font-size: 1.5em;
            border-bottom: 2px dashed rgba(255,255,255,0.3);
            padding-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            letter-spacing: 3px;
            text-transform: uppercase;
        }

        .panel-hft h2 { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); }
        .panel-trinity h2 { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }
        .panel-metrics h2 { color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow); }

        .module {
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.8);
            border: 1px solid rgba(255,255,255,0.1);
            border-left: 5px solid;
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            position: relative;
            overflow: hidden;
        }

        .module::after {
            content: '';
            position: absolute;
            top: -50%; left: -50%; width: 200%; height: 200%;
            background: linear-gradient(transparent, rgba(255,255,255,0.05), transparent);
            transform: rotate(45deg);
            animation: radarSwipe 4s infinite linear;
            pointer-events: none;
        }

        .module:hover {
            transform: translateX(12px) scale(1.03);
            background: rgba(20,30,40,0.95);
            box-shadow: -8px 8px 20px rgba(0,0,0,0.7), 0 0 15px currentColor;
            z-index: 100;
        }

        .mod-alpha { border-left-color: var(--neon-red); color: var(--neon-red); }
        .mod-delta { border-left-color: var(--neon-orange); color: var(--neon-orange); }
        .mod-gamma { border-left-color: var(--neon-green); color: var(--neon-green); }
        
        .mod-strozzino { border-left-color: var(--neon-pink); color: var(--neon-pink); }
        .mod-contabile { border-left-color: var(--neon-blue); color: var(--neon-blue); }
        .mod-angelo { border-left-color: #ffffff; color: #ffffff; }

        .mod-header {
            display: flex;
            justify-content: space-between;
            font-weight: bold;
            margin-bottom: 12px;
            font-size: 1.3em;
            font-family: 'Orbitron', sans-serif;
            text-shadow: 0 0 8px currentColor;
        }

        .mod-details {
            font-size: 0.95em;
            color: #d0d0d0;
            line-height: 1.7;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .status-badge {
            padding: 4px 10px;
            border-radius: 3px;
            font-size: 0.75em;
            font-family: 'Share Tech Mono', monospace;
            letter-spacing: 2px;
            text-transform: uppercase;
            font-weight: bold;
        }

        .status-active { color: var(--neon-green); border: 1px solid var(--neon-green); box-shadow: 0 0 8px var(--neon-green), inset 0 0 5px var(--neon-green); }
        .status-standby { color: var(--neon-blue); border: 1px solid var(--neon-blue); box-shadow: 0 0 8px var(--neon-blue); }
        .status-engaging { color: var(--neon-red); border: 1px solid var(--neon-red); animation: pulseAlert 0.8s infinite; }
        .status-harvesting { color: var(--neon-pink); border: 1px solid var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink); animation: pulseAlertPink 1.5s infinite; }

        .data-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }

        .metric-box {
            background: rgba(10, 20, 30, 0.8);
            border: 1px solid rgba(0,255,255,0.4);
            padding: 15px;
            text-align: center;
            border-radius: 4px;
            position: relative;
            box-shadow: inset 0 0 10px rgba(0,255,255,0.1);
        }
        
        .metric-box::before {
            content: ''; position: absolute; top: -1px; left: -1px; width: 12px; height: 12px; border-top: 2px solid var(--neon-blue); border-left: 2px solid var(--neon-blue);
        }
        .metric-box::after {
            content: ''; position: absolute; bottom: -1px; right: -1px; width: 12px; height: 12px; border-bottom: 2px solid var(--neon-blue); border-right: 2px solid var(--neon-blue);
        }

        .metric-val {
            font-family: 'Orbitron', sans-serif;
            font-size: 2em;
            font-weight: 900;
            margin: 10px 0;
            color: var(--neon-yellow);
            text-shadow: 0 0 10px var(--neon-yellow), 0 0 20px var(--neon-yellow);
        }

        .terminal-container {
            margin-top: 30px;
            border: 2px solid var(--neon-blue);
            background: rgba(0,5,10,0.98);
            position: relative;
            z-index: 10;
            box-shadow: 0 0 30px rgba(0,255,255,0.15), inset 0 0 20px rgba(0,255,255,0.05);
        }

        .terminal-header {
            background: rgba(0,255,255,0.15);
            padding: 10px 20px;
            border-bottom: 2px solid var(--neon-blue);
            color: var(--neon-blue);
            font-family: 'Orbitron', sans-serif;
            font-size: 1em;
            display: flex;
            justify-content: space-between;
            letter-spacing: 3px;
            text-shadow: 0 0 5px var(--neon-blue);
        }

        .terminal-body {
            height: 300px;
            padding: 20px;
            overflow-y: hidden;
            color: #0f0;
            font-size: 1.05em;
            line-height: 1.7;
            text-shadow: 0 0 3px #0f0;
        }

        .progress-bar {
            width: 100%; height: 8px; background: #111; margin-top: 15px; border: 1px solid #333; position: relative;
        }
        .progress-fill { height: 100%; position: absolute; top: 0; left: 0; box-shadow: 0 0 12px currentColor; }
        .progress-red { background: var(--neon-red); width: 88%; color: var(--neon-red); animation: loadBar 1.5s ease-in-out infinite alternate; }
        .progress-orange { background: var(--neon-orange); width: 75%; color: var(--neon-orange); animation: loadBarMid 2s ease-in-out infinite alternate;}
        .progress-green { background: var(--neon-green); width: 45%; color: var(--neon-green); animation: loadBarSlow 3s ease-in-out infinite alternate;}

        /* Animations */
        @keyframes flicker { 0% { opacity: 0.05; } 50% { opacity: 0.01; } 100% { opacity: 0.05; } }
        @keyframes pulseAlert { 0%, 100% { box-shadow: 0 0 8px var(--neon-red), inset 0 0 8px var(--neon-red); background: rgba(255,7,58,0.25); } 50% { box-shadow: 0 0 25px var(--neon-red), inset 0 0 15px var(--neon-red); background: rgba(255,7,58,0.6); } }
        @keyframes pulseAlertPink { 0%, 100% { box-shadow: 0 0 8px var(--neon-pink); background: rgba(255,0,255,0.1); } 50% { box-shadow: 0 0 20px var(--neon-pink); background: rgba(255,0,255,0.4); } }
        @keyframes radarSwipe { 0% { top: -50%; left: -50%; } 100% { top: 150%; left: 150%; } }
        @keyframes loadBar { 0% { width: 80%; } 100% { width: 98%; } }
        @keyframes loadBarMid { 0% { width: 65%; } 100% { width: 85%; } }
        @keyframes loadBarSlow { 0% { width: 40%; } 100% { width: 50%; } }
        @keyframes textGlitch {
            0%, 100% { transform: translate(0); }
            2% { transform: translate(-3px, 2px); text-shadow: -3px 0 var(--neon-red), 3px 0 var(--neon-blue); }
            4% { transform: translate(3px, -2px); text-shadow: 3px 0 var(--neon-red), -3px 0 var(--neon-blue); }
            6% { transform: translate(0); text-shadow: 0 0 15px var(--neon-blue), 0 0 30px var(--neon-blue); }
        }

    </style>
</head>
<body>
    <header>
        <h1>🚀 ORBITAL COMMAND</h1>
        <div class="subtitle">► NUVOLA TACTICAL QUANTITATIVE ENGINE v5.0.0-RC1 ◄</div>
        <div style="margin-top: 25px; font-size: 1.3em; color: var(--neon-green); font-weight: bold; border: 2px solid var(--neon-green); display: inline-block; padding: 10px 30px; background: rgba(57,255,20,0.15); box-shadow: 0 0 20px rgba(57,255,20,0.4), inset 0 0 10px rgba(57,255,20,0.2); text-shadow: 0 0 8px var(--neon-green); letter-spacing: 3px; border-radius: 4px;">
            <span style="animation: flicker 2s infinite;">[✓] CORE SYSTEMS NOMINAL</span><br>
            <span style="color: var(--neon-pink); font-size: 0.9em; text-shadow: 0 0 8px var(--neon-pink); letter-spacing: 2px;">⚡ PROTOCOLLO TRINITY: ONLINE & DETACHED</span><br>
            <div style="margin-top: 15px; border: 1px solid var(--neon-yellow); padding: 5px; background: rgba(252, 238, 10, 0.1); color: var(--neon-yellow); font-size: 0.85em; text-shadow: 0 0 5px var(--neon-yellow);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
        </div>
        <div class="top-stats">
            UPTIME: <span style="color:#fff; font-family:'Orbitron', sans-serif; font-size: 1.1em; text-shadow: 0 0 5px #fff;" id="uptime">00:00:00</span><br>
            NET LATENCY: <span style="color:var(--neon-green); font-weight:bold; text-shadow: 0 0 5px var(--neon-green);">4ms (FIBER)</span><br>
            CLUSTER TEMP: <span style="color:var(--neon-orange); text-shadow: 0 0 5px var(--neon-orange);">44°C</span><br>
            THREAT LEVEL: <span style="color:var(--neon-red); text-shadow: 0 0 5px var(--neon-red); font-weight: bold; animation: pulseAlert 2s infinite;">DEFCON 3</span>
        </div>
    </header>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel panel-hft">
            <h2>⚔️ SQUADRE D'ASSALTO <span style="font-size: 0.45em; color: var(--neon-red); border: 1px solid var(--neon-red); padding: 3px 8px; box-shadow: 0 0 5px var(--neon-red);">HFT CLUSTER ACTIVE</span></h2>
            
            <div class="module mod-alpha">
                <div class="mod-header">
                    <span>🐺 SQUADRA_ALPHA</span>
                    <span class="status-badge status-engaging">ENGAGING</span>
                </div>
                <div style="color: #fff; margin-bottom: 10px; font-weight: bold; border-bottom: 1px solid rgba(255,7,58,0.5); padding-bottom: 6px; letter-spacing: 1px;">STRAT: SCALPER // TGT: BINANCE L2</div>
                <div class="mod-details">
                    <div>ASSET: <span style="color: #fff">BTC/USDT</span></div>
                    <div>FREQ: <span style="color: var(--neon-yellow)">1,250 msg/s</span></div>
                    <div>WIN RATE: <span style="color: var(--neon-green); font-weight: bold; font-size: 1.1em;">74.8%</span></div>
                    <div>PNL (24h): <span style="color: var(--neon-green); font-weight: bold; font-size: 1.1em;">+$4,890.50</span></div>
                </div>
                <div class="progress-bar"><div class="progress-fill progress-red"></div></div>
            </div>

            <div class="module mod-delta">
                <div class="mod-header">
                    <span>🦅 SQUADRA_DELTA</span>
                    <span class="status-badge status-active" style="color: var(--neon-orange); border-color: var(--neon-orange); box-shadow: 0 0 8px var(--neon-orange);">ONLINE</span>
                </div>
                <div style="color: #fff; margin-bottom: 10px; font-weight: bold; border-bottom: 1px solid rgba(255,170,0,0.5); padding-bottom: 6px; letter-spacing: 1px;">STRAT: ORDER FLOW // TGT: DERIBIT</div>
                <div class="mod-details">
                    <div>SKEW: <span style="color: var(--neon-green)">0.75 (BULL)</span></div>
                    <div>ABSORPTION: <span style="color: var(--neon-red)">SEVERE</span></div>
                    <div>OPEN POS: <span style="color: #fff">8.5 BTC</span></div>
                    <div>LIQ DIST: <span style="color: var(--neon-yellow)">12%</span></div>
                </div>
                <div class="progress-bar"><div class="progress-fill progress-orange"></div></div>
            </div>

            <div class="module mod-gamma">
                <div class="mod-header">
                    <span>🦂 SQUADRA_GAMMA</span>
                    <span class="status-badge status-standby">STANDBY</span>
                </div>
                <div style="color: #fff; margin-bottom: 10px; font-weight: bold; border-bottom: 1px solid rgba(57,255,20,0.5); padding-bottom: 6px; letter-spacing: 1px;">STRAT: PAIRS TRD // TGT: BITGET</div>
                <div class="mod-details">
                    <div>PAIR: <span style="color: #fff">ETH/SOL</span></div>
                    <div>SPREAD: <span style="color: var(--neon-yellow)">0.0034</span></div>
                    <div>Z-SCORE: <span style="color: var(--neon-blue)">1.85</span></div>
                    <div>ENTRY TGT: <span style="color: var(--neon-blue)">2.00</span></div>
                </div>
                <div class="progress-bar"><div class="progress-fill progress-green"></div></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-trinity">
            <h2>🔺 PROTOCOLLO TRINITY <span style="font-size: 0.45em; color: var(--neon-pink); border: 1px solid var(--neon-pink); padding: 3px 8px; box-shadow: 0 0 5px var(--neon-pink);">BACKGROUND DAEMONS</span></h2>
            
            <div class="module mod-strozzino">
                <div class="mod-header">
                    <span>🕴️ LO STROZZINO</span>
                    <span class="status-badge status-harvesting">HARVESTING</span>
                </div>
                <div style="color: #fff; margin-bottom: 10px; font-weight: bold; border-bottom: 1px solid rgba(255,0,255,0.5); padding-bottom: 6px; letter-spacing: 1px;">ROLE: FUNDING ARBITRAGE (DELTA NEUTRAL)</div>
                <div class="mod-details">
                    <div>POS: <span style="color: var(--neon-red)">SHORT PERP</span></div>
                    <div>HEDGE: <span style="color: var(--neon-green)">LONG SPOT</span></div>
                    <div>YIELD: <span style="color: var(--neon-green); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-green);">22.4% APY</span></div>
                    <div>CAPITAL ALLOC: <span style="color: #fff">$150,000</span></div>
                </div>
            </div>

            <div class="module mod-contabile">
                <div class="mod-header">
                    <span>🧮 IL CONTABILE</span>
                    <span class="status-badge status-active">EXECUTING</span>
                </div>
                <div style="color: #fff; margin-bottom: 10px; font-weight: bold; border-bottom: 1px solid rgba(0,255,255,0.5); padding-bottom: 6px; letter-spacing: 1px;">ROLE: DCA MATRIX & REBALANCE</div>
                <div class="mod-details">
                    <div>ASSET: <span style="color: #fff">BTC/ETH/SOL</span></div>
                    <div>MATRIX: <span style="color: var(--neon-blue)">DYNAMIC K-MEANS</span></div>
                    <div>NEXT EXEC: <span style="color: var(--neon-yellow)">08:00 UTC</span></div>
                    <div>DRAWDOWN: <span style="color: var(--neon-green); font-weight: bold;">0.8%</span></div>
                </div>
            </div>

            <div class="module mod-angelo">
                <div class="mod-header">
                    <span>👼 L'ANGELO CUSTODE</span>
                    <span class="status-badge status-active" style="color: #fff; border-color: #fff; box-shadow: 0 0 10px #fff;">PATROLLING</span>
                </div>
                <div style="color: #fff; margin-bottom: 10px; font-weight: bold; border-bottom: 1px solid rgba(255,255,255,0.5); padding-bottom: 6px; letter-spacing: 1px;">ROLE: MEV & FLASHLOAN // ARBITRUM L2</div>
                <div class="mod-details">
                    <div>MEMPOOL: <span style="color: var(--neon-green)">MONITORING</span></div>
                    <div>GAS GWEI: <span style="color: var(--neon-yellow)">12</span></div>
                    <div>OPPS: <span style="color: var(--neon-orange); font-weight: bold; font-size: 1.1em; animation: pulseAlert 1s infinite;">2 DETECTED</span></div>
                    <div>LAST PROFIT: <span style="color: #fff">45 mins ago</span></div>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-metrics">
            <h2>📊 METRICHE GLOBALI <span style="font-size: 0.45em; color: var(--neon-yellow); border: 1px solid var(--neon-yellow); padding: 3px 8px; box-shadow: 0 0 5px var(--neon-yellow);">MARKET INTEL</span></h2>
            
            <div class="module" style="border-left-color: var(--neon-yellow);">
                <div class="mod-header">
                    <span style="color: var(--neon-yellow);">👁️ THE ORACLE</span>
                    <span class="status-badge status-active">SYNCED</span>
                </div>
                <div style="color: #fff; margin-bottom: 10px; font-size: 0.9em; border-bottom: 1px solid rgba(252,238,10,0.5); padding-bottom: 6px; letter-spacing: 1px;">AI SENTIMENT ENGINE (BINANCE DATAFEED)</div>
                <div class="data-grid">
                    <div class="metric-box">
                        <div style="font-size: 0.75em; color: var(--neon-blue); letter-spacing: 2px;">GLOBAL BIAS</div>
                        <div class="metric-val">BULL <span style="font-size: 0.6em;">(88)</span></div>
                    </div>
                    <div class="metric-box">
                        <div style="font-size: 0.75em; color: var(--neon-blue); letter-spacing: 2px;">ORDERBOOK MASS</div>
                        <div class="metric-val" style="color: var(--neon-green);">+5.8K <span style="font-size: 0.6em; color: #fff;">BTC</span></div>
                    </div>
                </div>
                <div style="font-size: 0.9em; color: var(--neon-bg-dark); background-color: var(--neon-yellow); font-weight: bold; margin-top: 15px; text-align: center; padding: 8px; border: 2px dashed #000; box-shadow: 0 0 15px var(--neon-yellow); animation: pulseAlertPink 2s infinite;">
                    [!] HEATMAP ALERT: Massive buy wall @ $70,000
                </div>
            </div>

            <div class="module" style="border-left-color: var(--neon-blue);">
                <div class="mod-header">
                    <span style="color: var(--neon-blue);">🐋 WHALE TRACKER</span>
                    <span class="status-badge status-engaging" style="color: var(--neon-blue); border-color: var(--neon-blue); animation: none; box-shadow: 0 0 10px var(--neon-blue);">TRACKING</span>
                </div>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.95em; color: #ddd; line-height: 1.9; list-style-type: square; font-family: 'Share Tech Mono', monospace;">
                    <li><span style="color: var(--neon-red); font-weight: bold;">[T-1m]</span> 3,200 BTC ➔ Coinbase <span style="color: #666;">(tx:0x8F9...)</span></li>
                    <li><span style="color: var(--neon-green); font-weight: bold;">[T-5m]</span> 250M USDT minted at Tether Treas.</li>
                    <li><span style="color: var(--neon-blue); font-weight: bold;">[T-14m]</span> 22,000 ETH withdrawn from Binance</li>
                    <li><span style="color: var(--neon-orange); font-weight: bold;">[T-30m]</span> 1,000 WBTC burned on Ethereum</li>
                </ul>
            </div>

            <div class="module" style="border-left-color: var(--neon-red); background: rgba(255,0,0,0.08);">
                <div class="mod-header">
                    <span style="color: var(--neon-red);">⚡ LIQUIDITY MAP</span>
                </div>
                <div class="mod-details" style="font-size: 1.1em;">
                    <div style="border: 1px solid rgba(255,7,58,0.5); padding: 10px; text-align: center; background: rgba(0,0,0,0.5);">
                        <div style="font-size: 0.8em; color: #aaa; margin-bottom: 5px;">SHORT LIQ</div>
                        <span style="color:var(--neon-yellow); font-weight:bold; font-size:1.4em; text-shadow: 0 0 8px var(--neon-yellow);">$74,500</span>
                    </div>
                    <div style="border: 1px solid rgba(255,7,58,0.5); padding: 10px; text-align: center; background: rgba(0,0,0,0.5);">
                        <div style="font-size: 0.8em; color: #aaa; margin-bottom: 5px;">LONG LIQ</div>
                        <span style="color:var(--neon-red); font-weight:bold; font-size:1.4em; text-shadow: 0 0 8px var(--neon-red);">$68,200</span>
                    </div>
                    <div style="grid-column: span 2; color: #fff; background: var(--neon-red); font-weight: bold; text-align: center; margin-top: 10px; padding: 8px; animation: textGlitch 2s infinite; box-shadow: 0 0 20px var(--neon-red);">
                        ► CLUSTER DETECTED: VOLATILITY SPIKE IMMINENT ◄
                    </div>
                </div>
            </div>
        </div>

    </div>

    <!-- TERMINALE DI COMANDO -->
    <div class="terminal-container">
        <div class="terminal-header">
            <span>>_ ROOT@ORBITAL-CMD // TACTICAL OVERVIEW & LOGS</span>
            <span style="color: var(--neon-green); font-weight: bold; animation: flicker 3s infinite;">ENCRYPTED TIE-LINE [SECURE]</span>
        </div>
        <div class="terminal-body" id="term-output">
            <span style="color: #888;">[SYS] INITIATING SECURE BOOT SEQUENCE v5.0...</span><br>
            <span style="color: #888;">[SYS] ESTABLISHING WSS CONNECTIONS [BINANCE, BYBIT, DERIBIT, OKX]...</span> <span style="color: var(--neon-green);">OK.</span><br>
            <span style="color: #888;">[SYS] LOADING NEURAL WEIGHTS FOR ORDER FLOW PREDICTION...</span> <span style="color: var(--neon-green);">OK.</span><br>
            <span style="color: var(--neon-pink);">[TRINITY] PROTOCOLS SYNCHRONIZED AND RUNNING DETACHED IN BACKGROUND.</span><br>
            <span style="color: var(--neon-red);">[HFT] SQUADRE D'ASSALTO AWAITING ENGAGEMENT PARAMETERS...</span><br>
            <span style="color: var(--neon-blue);">[SYS] DASHBOARD RENDERED WITH ENHANCED TACTICAL OVERLAYS.</span><br>
        </div>
    </div>

    <script>
        // Uptime counter
        let seconds = 12450;
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
            "<span style='color: var(--neon-red); font-weight: bold;'>[ALPHA]</span> Executing scalping sequence... ENTRY: 70050, EXIT: 70065 (PROFIT: <span style='color: var(--neon-green);'>+$15.50</span>)",
            "<span style='color: var(--neon-orange); font-weight: bold;'>[DELTA]</span> Spot/Perp delta diverging. Skew increasing rapidly. Preparing to hedge.",
            "<span style='color: var(--neon-yellow); font-weight: bold;'>[ORACLE]</span> Parsing X sentiment... Institutional accumulation detected -> Neural net adjusting targets.",
            "<span style='color: #fff; font-weight: bold;'>[ANGELO]</span> Mempool scan complete. Flashloan opportunity detected. Routing via Uniswap V3...",
            "<span style='color: var(--neon-blue); font-weight: bold;'>[CONTABILE]</span> Depositing 0.25 BTC into cold storage vault. Rebalancing complete.",
            "<span style='color: var(--neon-blue); font-weight: bold;'>[WHALE]</span> Alert: Massive short position opened on Deribit (Size: 850 BTC)",
            "<span style='color: #888; font-weight: bold;'>[SYS]</span> Re-calibrating WebSocket latency... 4ms.",
            "<span style='color: var(--neon-red); font-weight: bold;'>[ALPHA]</span> Order partially filled. Remaining: 0.15 BTC",
            "<span style='color: var(--neon-pink); font-weight: bold;'>[STROZZINO]</span> Funding rate shifted on Bybit. Rebalancing hedge...",
            "<span style='color: var(--neon-green); font-weight: bold;'>[GAMMA]</span> Z-Score hit 2.1. Entering pairs trade ETH/SOL. Size: 50 ETH.",
            "<span style='color: #888; font-weight: bold;'>[SYS]</span> Garbage collection complete. Memory optimal."
        ];

        setInterval(() => {
            const rLog = logs[Math.floor(Math.random() * logs.length)];
            const time = new Date().toISOString().split('T')[1].split('.')[0];
            term.innerHTML += `<span style="color:#666;">[${time}]</span> ${rLog}<br>`;
            if(term.innerHTML.split('<br>').length > 22) {
                term.innerHTML = term.innerHTML.substring(term.innerHTML.indexOf('<br>') + 4);
            }
            term.scrollTop = term.scrollHeight;
        }, 1200);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
