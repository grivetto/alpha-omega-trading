import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND - TACTICAL UPLINK</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --neon-yellow: #fcee0a;
            --bg-dark: #020202;
            --panel-bg: rgba(10, 10, 12, 0.85);
            --grid-line: rgba(57, 255, 20, 0.1);
        }
        
        @font-face {
            font-family: 'Cyber';
            src: local('Courier New');
        }

        body {
            background-color: var(--bg-dark);
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-green);
            font-family: 'Cyber', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            text-shadow: 0 0 5px var(--neon-green);
        }

        /* Scanline Overlay */
        body::before {
            content: " ";
            display: block;
            position: fixed;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 999;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }

        .header {
            text-align: center;
            border: 2px solid var(--neon-blue);
            background: rgba(0, 243, 255, 0.05);
            padding: 20px;
            margin-bottom: 30px;
            color: var(--neon-blue);
            box-shadow: 0 0 15px var(--neon-blue) inset, 0 0 20px var(--neon-blue);
            position: relative;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 5px;
            animation: glitch 2s linear infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 2px solid;
            border-radius: 4px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(5px);
        }

        /* SQUADRE D'ASSALTO (HFT) */
        .panel.hft {
            border-color: var(--neon-red);
            box-shadow: 0 0 15px var(--neon-red) inset, 0 0 10px var(--neon-red);
            color: var(--neon-red);
        }
        .panel.hft h2 { color: #fff; text-shadow: 0 0 10px var(--neon-red); border-bottom: 1px solid var(--neon-red); padding-bottom: 5px;}

        /* PROTOCOLLO TRINITY */
        .panel.trinity {
            border-color: var(--neon-purple);
            box-shadow: 0 0 15px var(--neon-purple) inset, 0 0 10px var(--neon-purple);
            color: var(--neon-purple);
        }
        .panel.trinity h2 { color: #fff; text-shadow: 0 0 10px var(--neon-purple); border-bottom: 1px solid var(--neon-purple); padding-bottom: 5px;}

        /* METRICHE DI MERCATO */
        .panel.market {
            border-color: var(--neon-yellow);
            box-shadow: 0 0 15px var(--neon-yellow) inset, 0 0 10px var(--neon-yellow);
            color: var(--neon-yellow);
        }
        .panel.market h2 { color: #fff; text-shadow: 0 0 10px var(--neon-yellow); border-bottom: 1px solid var(--neon-yellow); padding-bottom: 5px;}

        .status-dot {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .status-dot.active {
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            animation: pulse 1.5s infinite;
        }
        .status-dot.standby {
            background-color: var(--neon-yellow);
            box-shadow: 0 0 10px var(--neon-yellow);
            animation: pulse 2s infinite;
        }

        .unit {
            border-left: 3px solid;
            padding-left: 15px;
            margin-bottom: 20px;
            background: rgba(255,255,255,0.02);
            padding-top: 5px;
            padding-bottom: 5px;
        }
        .unit:last-child { margin-bottom: 0; }
        
        .hft .unit { border-color: var(--neon-red); }
        .trinity .unit { border-color: var(--neon-purple); }

        .unit-title {
            font-size: 1.2em;
            font-weight: bold;
            display: flex;
            align-items: center;
            color: #fff;
        }

        .unit-details {
            font-size: 0.9em;
            margin-top: 5px;
            opacity: 0.9;
        }

        .grid-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }
        .stat-box {
            border: 1px solid rgba(255,255,255,0.2);
            padding: 10px;
            text-align: center;
            background: rgba(0,0,0,0.5);
        }
        .stat-box.oracle { border-color: var(--neon-blue); box-shadow: 0 0 5px var(--neon-blue) inset; }
        .stat-box.whale { border-color: var(--neon-yellow); box-shadow: 0 0 5px var(--neon-yellow) inset; }
        
        .stat-value {
            font-size: 1.4em;
            font-weight: bold;
            margin-top: 5px;
            color: #fff;
        }

        /* Animations */
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }

        .terminal-scroll {
            height: 100px;
            overflow-y: hidden;
            border-top: 1px dashed rgba(255,255,255,0.3);
            margin-top: 15px;
            padding-top: 10px;
            font-size: 0.8em;
            color: var(--neon-green);
        }
        
        .log-line {
            margin-bottom: 3px;
        }

    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND UPLINK 🛰️</h1>
        <p style="color: #fff;">[ CONNECTION SECURED - ENCRYPTION LEVEL: QUANTUM ]</p>
        <p style="color: var(--neon-purple); font-weight: bold; text-shadow: 0 0 10px var(--neon-purple);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
        <p><span class="status-dot active"></span> SYSTEM CORE: <strong>NOMINAL</strong> | LATENCY: <strong>12ms</strong></p>
    </div>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel hft">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="unit">
                <div class="unit-title"><span class="status-dot active"></span> SQUADRA_ALPHA 🐺</div>
                <div class="unit-details">
                    > TARGET: Binance Scalping<br>
                    > STRATEGY: High-Frequency Momentum<br>
                    > STATUS: <span style="color:var(--neon-green)">ENGAGING TARGETS</span> (482 TX/hr)
                </div>
            </div>

            <div class="unit">
                <div class="unit-title"><span class="status-dot active"></span> SQUADRA_DELTA 🦂</div>
                <div class="unit-details">
                    > TARGET: Global Order Flow<br>
                    > STRATEGY: Spread Arbitrage<br>
                    > STATUS: <span style="color:var(--neon-yellow)">MONITORING LIQUIDITY</span>
                </div>
            </div>

            <div class="unit">
                <div class="unit-title"><span class="status-dot active"></span> SQUADRA_GAMMA 🦅</div>
                <div class="unit-details">
                    > TARGET: Bitget Pairs Trading<br>
                    > STRATEGY: Statistical Cointegration<br>
                    > STATUS: <span style="color:var(--neon-green)">BALANCING PORTFOLIO</span>
                </div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            
            <div class="unit">
                <div class="unit-title"><span class="status-dot active"></span> LO STROZZINO 🧛‍♂️</div>
                <div class="unit-details">
                    > ROLE: Perpetual Funding Arb<br>
                    > EXPOSURE: Delta Neutral<br>
                    > YIELD: <span style="color:var(--neon-green)">+18.4% APY</span>
                </div>
            </div>

            <div class="unit">
                <div class="unit-title"><span class="status-dot active"></span> IL CONTABILE 🧮</div>
                <div class="unit-details">
                    > ROLE: Algorithmic DCA<br>
                    > ACCUMULATION: BTC/ETH/SOL<br>
                    > STATUS: <span style="color:var(--neon-green)">STEADY DEPLOYMENT</span>
                </div>
            </div>

            <div class="unit">
                <div class="unit-title"><span class="status-dot active"></span> L'ANGELO CUSTODE 🛡️</div>
                <div class="unit-details">
                    > ROLE: MEV Arbitrum Protection<br>
                    > VECTOR: Front-running Defense<br>
                    > STATUS: <span style="color:var(--neon-green)">SHIELD ACTIVE</span>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market">
            <h2>📊 METRICHE DI MERCATO</h2>
            
            <div class="grid-stats">
                <div class="stat-box oracle">
                    <div style="color:var(--neon-blue)">👁️ THE ORACLE</div>
                    <div style="font-size:0.7em; color:#aaa">Binance Sentiment</div>
                    <div class="stat-value" style="text-shadow: 0 0 10px var(--neon-blue);">BULLISH (82%)</div>
                </div>
                <div class="stat-box whale">
                    <div style="color:var(--neon-yellow)">🐋 WHALE TRACKER</div>
                    <div style="font-size:0.7em; color:#aaa">Large TX Monitor</div>
                    <div class="stat-value" style="text-shadow: 0 0 10px var(--neon-yellow);">DETECTED ⚠️</div>
                </div>
                <div class="stat-box" style="border-color: var(--neon-red);">
                    <div style="color:var(--neon-red)">⚡ VOLATILITY</div>
                    <div style="font-size:0.7em; color:#aaa">Market Turbulence</div>
                    <div class="stat-value" style="text-shadow: 0 0 10px var(--neon-red);">EXTREME</div>
                </div>
                <div class="stat-box" style="border-color: var(--neon-green);">
                    <div style="color:var(--neon-green)">🌐 GWEI LEVEL</div>
                    <div style="font-size:0.7em; color:#aaa">Network Load</div>
                    <div class="stat-value" style="text-shadow: 0 0 10px var(--neon-green);">14 (LOW)</div>
                </div>
            </div>

            <div class="terminal-scroll" id="term">
                <!-- JS Will populate -->
            </div>
        </div>

    </div>

    <script>
        const termLogs = [
            "[SYS] Re-calibrating Arbitrum RPC endpoints...",
            "[SQUADRA_ALPHA] Executed BUY order BTC/USDT @ Market",
            "[STROZZINO] Funding rate shifted. Re-hedging Short ETH...",
            "[ORACLE] Sentiment spike detected on Socials",
            "[WHALE] 1,500 BTC moved to Coinbase Prime",
            "[ANGELO] MEV Sandwich attempt blocked. Saved 0.04 ETH",
            "[SYS] Network ping 12ms. Stable.",
            "[CONTABILE] Scheduled DCA execution in 14 mins...",
            "[SQUADRA_GAMMA] Mean reversion triggered on SOL/ADA"
        ];
        
        const termEl = document.getElementById('term');
        
        function addLog() {
            const line = document.createElement('div');
            line.className = 'log-line';
            const time = new Date().toLocaleTimeString('en-US', { hour12: false });
            line.innerHTML = `> [${time}] ${termLogs[Math.floor(Math.random() * termLogs.length)]}`;
            termEl.prepend(line);
            
            if (termEl.children.length > 5) {
                termEl.removeChild(termEl.lastChild);
            }
        }

        setInterval(addLog, 2500);
        addLog(); addLog(); addLog();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
