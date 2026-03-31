import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --bg-dark: #050505;
            --grid-color: #1a1a1a;
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            margin-bottom: 10px;
        }
        h1 {
            text-align: center;
            font-size: 2.5em;
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 15px;
            animation: flicker 3s infinite;
        }
        h2 { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        h3 { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .panel {
            background: rgba(0, 0, 0, 0.7);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: inset 0 0 10px rgba(57, 255, 20, 0.2), 0 0 10px rgba(57, 255, 20, 0.2);
            transition: all 0.3s;
        }
        .panel:hover {
            box-shadow: inset 0 0 20px rgba(57, 255, 20, 0.5), 0 0 20px rgba(57, 255, 20, 0.5);
            transform: scale(1.02);
        }
        .status-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            margin-right: 10px;
            animation: pulse 1.5s infinite;
        }
        .status-idle { background-color: yellow; box-shadow: 0 0 10px yellow; }
        .status-offline { background-color: red; box-shadow: 0 0 10px red; animation: none; }
        
        ul { list-style: none; padding: 0; }
        li { margin-bottom: 10px; padding-bottom: 5px; border-bottom: 1px dotted #333; }
        .data-row { display: flex; justify-content: space-between; }
        .value { font-weight: bold; color: #fff; text-shadow: 0 0 5px #fff; }
        
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(57, 255, 20, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(57, 255, 20, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(57, 255, 20, 0); }
        }
        @keyframes flicker {
            0%, 18%, 22%, 25%, 53%, 57%, 100% { text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green); opacity: 1; }
            20%, 24%, 55% { text-shadow: none; opacity: 0.5; }
        }
        .terminal {
            background: #000;
            border: 1px solid var(--neon-blue);
            height: 150px;
            overflow: hidden;
            font-size: 0.8em;
            padding: 10px;
            margin-top: 20px;
            color: var(--neon-blue);
            text-shadow: none;
        }
        .marquee { overflow: hidden; white-space: nowrap; box-sizing: border-box; }
        .marquee span { display: inline-block; padding-left: 100%; animation: marquee 15s linear infinite; }
        @keyframes marquee { 0% { transform: translate(0, 0); } 100% { transform: translate(-100%, 0); } }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>
    <div class="marquee"><span>[SYSTEM] ORBITAL COMMAND UPLINK ESTABLISHED ... ALL PROTOCOLS NOMINAL ... QUANTUM ENCRYPTION ACTIVE ...</span></div>
    
    <div style="text-align: center; margin-top: 20px; padding: 10px; border: 2px solid var(--neon-pink); background: rgba(255,0,255,0.1); font-size: 1.2em; text-shadow: 0 0 5px var(--neon-pink); color: var(--neon-pink);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <div class="data-row">
                        <span><span class="status-dot"></span> <b>SQUADRA_ALPHA</b> (Scalper)</span>
                        <span class="value">BINANCE</span>
                    </div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #888;">> TARGET: BTC/USDT | WIN RATE: 68.4% | PNL: +$1,420</div>
                </li>
                <li>
                    <div class="data-row">
                        <span><span class="status-dot"></span> <b>SQUADRA_DELTA</b> (Order Flow)</span>
                        <span class="value">DERIBIT</span>
                    </div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #888;">> IMBALANCE DETECTED | ABSORPTION: HIGH | SKEW: 0.45</div>
                </li>
                <li>
                    <div class="data-row">
                        <span><span class="status-dot status-idle"></span> <b>SQUADRA_GAMMA</b> (Pairs)</span>
                        <span class="value">BITGET</span>
                    </div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #888;">> PAIR: ETH/SOL | SPREAD: 0.0024 | WAITING FOR ENTRY...</div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-pink)">🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <div class="data-row">
                        <span><span class="status-dot"></span> <b>Lo Strozzino</b></span>
                        <span class="value">FUNDING ARB</span>
                    </div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #ccc;">> SHORT PERP @ 0.01% / LONG SPOT | YIELD: 14% APY</div>
                </li>
                <li>
                    <div class="data-row">
                        <span><span class="status-dot"></span> <b>Il Contabile</b></span>
                        <span class="value">DCA MATRIX</span>
                    </div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #ccc;">> ACCUMULATING BTC < $65K | NEXT BUY: 04:00 UTC</div>
                </li>
                <li>
                    <div class="data-row">
                        <span><span class="status-dot"></span> <b>L'Angelo Custode</b></span>
                        <span class="value">MEV ARBITRUM</span>
                    </div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #ccc;">> FLASHLOAN POOL MONITORING | MEMPOOL: CLEAR</div>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--neon-blue)">📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <div class="data-row">
                        <span>👁️ <b>THE ORACLE</b> (Sentiment)</span>
                        <span class="value" style="color: #0f0;">BULLISH (72)</span>
                    </div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #888;">> BINANCE ORDERBOOK HEATMAP: HEAVY BIDS @ 68,000</div>
                </li>
                <li>
                    <div class="data-row">
                        <span>🐋 <b>WHALE TRACKER</b></span>
                        <span class="value">ALERT</span>
                    </div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #888;">> 1,500 BTC MOVED TO COINBASE [TX: 0x8F4A...]</div>
                </li>
                <li>
                    <div class="data-row">
                        <span>⚡ <b>LIQUIDITY MAP</b></span>
                        <span class="value">UPPER</span>
                    </div>
                    <div style="font-size: 0.8em; margin-top: 5px; color: #888;">> MASSIVE LIQUIDATION CLUSTER AT 72,500</div>
                </li>
            </ul>
        </div>
    </div>
    
    <div class="terminal" id="terminal">
        > INITIALIZING CORE SYSTEMS...<br>
        > CONNECTING TO EXCHANGE WEBSOCKETS... [OK]<br>
        > HFT ENGINES ONLINE.<br>
        > AWAITING ORDERS...
    </div>

    <script>
        const terminal = document.getElementById('terminal');
        const messages = [
            "> EXECUTING ALPHA PROTOCOL...",
            "> NEW BLOCK MINED [HEIGHT: 837192]",
            "> ARBITRAGE OPPORTUNITY DETECTED [PROFIT: $12.50] - EXECUTING...",
            "> WHALE ALERT: 500 ETH BOUGHT ON BINANCE",
            "> SYNCING LEDGER STATE..."
        ];
        setInterval(() => {
            const msg = messages[Math.floor(Math.random() * messages.length)];
            terminal.innerHTML += `<br>${msg}`;
            terminal.scrollTop = terminal.scrollHeight;
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
