from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND // TACTICAL DASHBOARD</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --neon-red: #ff003c;
            --neon-yellow: #ffb300;
            --dark-bg: #030305;
            --panel-bg: rgba(5, 15, 25, 0.85);
            --grid-line: rgba(0, 243, 255, 0.1);
        }

        * { box-sizing: border-box; }

        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 40px 40px;
            text-transform: uppercase;
        }

        /* CRT effects */
        body::before {
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

        .scanline {
            width: 100%;
            height: 15px;
            z-index: 9999;
            position: fixed;
            top: 0;
            left: 0;
            pointer-events: none;
            background: rgba(0, 243, 255, 0.3);
            opacity: 0.4;
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.5);
            animation: scan 4s linear infinite;
        }

        @keyframes scan {
            0% { top: -20px; }
            100% { top: 100vh; }
        }

        header {
            text-align: center;
            margin-bottom: 40px;
            position: relative;
            z-index: 10;
        }

        h1 {
            font-size: 3em;
            color: #fff;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            letter-spacing: 10px;
            margin: 0;
            border-bottom: 2px solid var(--neon-blue);
            display: inline-block;
            padding: 10px 40px;
            background: rgba(0, 243, 255, 0.05);
            box-shadow: 0 10px 10px -10px rgba(0, 243, 255, 0.5), inset 0 0 20px rgba(0, 243, 255, 0.1);
        }

        .subtitle {
            margin-top: 15px;
            font-size: 1.2em;
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green);
            letter-spacing: 3px;
            animation: pulse 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            max-width: 1600px;
            margin: 0 auto;
            position: relative;
            z-index: 10;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-left: 4px solid var(--neon-blue);
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 15px rgba(0, 243, 255, 0.2);
            position: relative;
        }
        
        .panel::before {
            content: '>';
            position: absolute;
            top: -12px;
            left: 10px;
            background: var(--dark-bg);
            padding: 0 5px;
            color: var(--neon-blue);
            font-size: 1.2em;
        }

        .panel.pink-theme {
            border-color: var(--neon-pink);
            border-left-color: var(--neon-pink);
            box-shadow: inset 0 0 15px rgba(255, 0, 234, 0.1), 0 0 15px rgba(255, 0, 234, 0.2);
        }
        .panel.pink-theme::before { color: var(--neon-pink); }
        .panel.pink-theme h2 { color: var(--neon-pink); border-bottom-color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); }

        .panel.green-theme {
            border-color: var(--neon-green);
            border-left-color: var(--neon-green);
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.1), 0 0 15px rgba(57, 255, 20, 0.2);
        }
        .panel.green-theme::before { color: var(--neon-green); }
        .panel.green-theme h2 { color: var(--neon-green); border-bottom-color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }

        h2 {
            margin-top: 0;
            padding-bottom: 10px;
            border-bottom: 1px dashed var(--neon-blue);
            font-size: 1.4em;
            display: flex;
            align-items: center;
            letter-spacing: 2px;
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
        }

        .data-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .data-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 10px;
            margin-bottom: 8px;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: 0.2s;
        }

        .data-item:hover {
            background: rgba(0, 243, 255, 0.1);
            border-color: var(--neon-blue);
        }

        .data-name {
            display: flex;
            align-items: center;
            font-weight: bold;
            font-size: 1.1em;
        }

        .emoji-icon {
            font-size: 1.4em;
            margin-right: 12px;
            filter: drop-shadow(0 0 4px rgba(255,255,255,0.4));
        }

        .data-sub {
            font-size: 0.75em;
            color: #888;
            margin-left: 8px;
            letter-spacing: 1px;
        }

        .status {
            font-weight: bold;
            font-size: 0.9em;
            padding: 2px 6px;
            border-radius: 2px;
        }
        .status.online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); border: 1px solid var(--neon-green); }
        .status.active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); border: 1px solid var(--neon-blue); }
        .status.hunting { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); border: 1px solid var(--neon-pink); animation: pulse 1.5s infinite; }
        .status.alert { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); border: 1px solid var(--neon-red); animation: blink 1s infinite; }

        .metric {
            text-align: right;
            font-size: 1.1em;
            color: #fff;
        }

        .metric span {
            display: block;
            font-size: 0.7em;
            color: var(--neon-blue);
            margin-top: 2px;
        }

        /* Fake Matrix / Terminal Grid */
        .terminal-grid {
            font-size: 0.8em;
            line-height: 1.4;
            color: #aaa;
            height: 180px;
            overflow: hidden;
            position: relative;
            background: #000;
            padding: 10px;
            border: 1px solid #333;
            width: 100%;
        }
        .terminal-grid::after {
            content: '';
            position: absolute;
            bottom: 0; left: 0; width: 100%; height: 40px;
            background: linear-gradient(transparent, #000);
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0; }
        }

        .glitch-text {
            position: relative;
        }
        .glitch-text::before, .glitch-text::after {
            content: attr(data-text);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--dark-bg);
        }
        .glitch-text::before {
            left: 2px;
            text-shadow: -2px 0 var(--neon-red);
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim 3s infinite linear alternate-reverse;
        }
        .glitch-text::after {
            left: -2px;
            text-shadow: -2px 0 var(--neon-blue);
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }

        @keyframes glitch-anim {
            0% { clip: rect(10px, 9999px, 86px, 0); }
            10% { clip: rect(32px, 9999px, 93px, 0); }
            20% { clip: rect(12px, 9999px, 76px, 0); }
            30% { clip: rect(45px, 9999px, 67px, 0); }
            100% { clip: rect(45px, 9999px, 67px, 0); }
        }
        
        .sys-log {
            font-family: monospace;
            color: var(--neon-green);
            font-size: 0.85em;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <header>
        <h1 class="glitch-text" data-text="🛰️ ORBITAL COMMAND 🛰️">🛰️ ORBITAL COMMAND 🛰️</h1>
        <div class="subtitle">>>> NUVOLA SYSTEM OVERRIDE ACTIVE <<<</div>
        <div style="margin-top: 15px; font-size: 1.5em; color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); font-weight: bold; border: 1px solid var(--neon-pink); display: inline-block; padding: 10px 20px; background: rgba(255, 0, 234, 0.1);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </header>

    <div class="container">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO <span style="color:#fff;font-size:0.6em;margin-left:10px;">[HFT DIVISION]</span></h2>
            <ul class="data-list">
                <li class="data-item">
                    <div class="data-name">
                        <span class="emoji-icon">🐺</span> SQUADRA_ALPHA
                        <span class="data-sub">SCALPER BINANCE</span>
                    </div>
                    <div class="status online">ENGAGED</div>
                    <div class="metric" style="color:var(--neon-green);">+$842.10<span>Realized PnL</span></div>
                </li>
                <li class="data-item">
                    <div class="data-name">
                        <span class="emoji-icon">🌊</span> SQUADRA_DELTA
                        <span class="data-sub">ORDER FLOW</span>
                    </div>
                    <div class="status active">STANDBY</div>
                    <div class="metric">12.4M<span>24h Volume</span></div>
                </li>
                <li class="data-item">
                    <div class="data-name">
                        <span class="emoji-icon">⚖️</span> SQUADRA_GAMMA
                        <span class="data-sub">PAIRS BITGET</span>
                    </div>
                    <div class="status hunting">ARBITRAGE</div>
                    <div class="metric">0.18%<span id="gamma-spread">Live Spread</span></div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel pink-theme">
            <h2>🔺 PROTOCOLLO TRINITY <span style="color:#fff;font-size:0.6em;margin-left:10px;">[BACKGROUND CORES]</span></h2>
            <ul class="data-list">
                <li class="data-item">
                    <div class="data-name">
                        <span class="emoji-icon">🦈</span> LO STROZZINO
                        <span class="data-sub">FUNDING ARB</span>
                    </div>
                    <div class="status online">YIELDING</div>
                    <div class="metric" style="color:var(--neon-pink);">28.4%<span>Current APR</span></div>
                </li>
                <li class="data-item">
                    <div class="data-name">
                        <span class="emoji-icon">🧮</span> IL CONTABILE
                        <span class="data-sub">SMART DCA</span>
                    </div>
                    <div class="status active">MONITORING</div>
                    <div class="metric">1h 12m<span>Next Execution</span></div>
                </li>
                <li class="data-item">
                    <div class="data-name">
                        <span class="emoji-icon">🛡️</span> L'ANGELO CUSTODE
                        <span class="data-sub">MEV ARBITRUM</span>
                    </div>
                    <div class="status hunting">SNIPING</div>
                    <div class="metric">0 Tx<span>Mempool Targets</span></div>
                </li>
            </ul>
            <div class="sys-log">> TRINITY DAEMONS RUNNING IN BACKGROUND [OK]</div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel green-theme">
            <h2>📊 METRICHE DI MERCATO <span style="color:#fff;font-size:0.6em;margin-left:10px;">[GLOBAL INTEL]</span></h2>
            <ul class="data-list">
                <li class="data-item">
                    <div class="data-name">
                        <span class="emoji-icon">👁️‍🗨️</span> THE ORACLE
                        <span class="data-sub">BINANCE SENTIMENT</span>
                    </div>
                    <div class="status online" style="color:var(--neon-yellow);border-color:var(--neon-yellow);text-shadow:0 0 5px var(--neon-yellow);">BULLISH</div>
                    <div class="metric" style="color:var(--neon-yellow);">82%<span>Confidence</span></div>
                </li>
                <li class="data-item" style="flex-direction:column; align-items:flex-start;">
                    <div style="display:flex; justify-content:space-between; width:100%; margin-bottom:10px;">
                        <div class="data-name">
                            <span class="emoji-icon">🐋</span> WHALE TRACKER
                            <span class="data-sub">ON-CHAIN RADAR</span>
                        </div>
                        <div class="status alert">ALERT</div>
                    </div>
                    <div class="terminal-grid" id="whale-term">
                        [SYS] Tracker initialized...<br>
                        [SCAN] Monitoring large Tx...<br>
                        <span style="color:var(--neon-red);">[WARN] 15,000 ETH moved to Coinbase</span><br>
                        [INFO] 4,200 BTC outflow from Binance<br>
                        [SCAN] Awaiting blocks...<br>
                    </div>
                </li>
            </ul>
        </div>

    </div>

    <script>
        // Animations
        setInterval(() => {
            const spreadEl = document.getElementById('gamma-spread');
            const spread = (0.15 + Math.random() * 0.08).toFixed(2);
            spreadEl.parentElement.innerHTML = `${spread}%<span id="gamma-spread">Live Spread</span>`;
        }, 2000);

        const terms = [
            "[SCAN] Analyzing mempool depths...",
            "[INFO] Suspicious wallet activity detected (0x8F2...A1b)",
            "[OK] Block finalized",
            "<span style='color:var(--neon-green);'>[BUY] 2M USDT swap on Uniswap V3</span>",
            "<span style='color:var(--neon-red);'>[SELL] 500 WBTC dumped on Binance</span>",
            "[SYS] Re-calibrating Oracle weights...",
            "[SCAN] No arbitrage opportunities found in block."
        ];
        
        const termEl = document.getElementById('whale-term');
        setInterval(() => {
            const newLog = terms[Math.floor(Math.random() * terms.length)];
            termEl.innerHTML += `${newLog}<br>`;
            termEl.scrollTop = termEl.scrollHeight;
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
