from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --bg-color: #050505;
            --neon-green: #00ff00;
            --neon-blue: #00f3ff;
            --neon-purple: #b026ff;
            --neon-red: #ff003c;
            --text-main: #e0e0e0;
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        h1 {
            text-align: center;
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 40px;
            animation: pulse 2s infinite;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(10, 10, 10, 0.8);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.2), inset 0 0 20px rgba(0, 243, 255, 0.05);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }

        .panel.red { border-color: var(--neon-red); }
        .panel.red::before { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }
        
        .panel.purple { border-color: var(--neon-purple); }
        .panel.purple::before { background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }

        h2 {
            margin-top: 0;
            font-size: 1.2rem;
            border-bottom: 1px dashed rgba(255,255,255,0.2);
            padding-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .panel.blue h2 { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .panel.red h2 { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .panel.purple h2 { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: blink 1s infinite alternate;
        }

        ul {
            list-style-type: none;
            padding: 0;
        }

        li {
            margin-bottom: 15px;
            background: rgba(0,0,0,0.4);
            padding: 10px;
            border-left: 3px solid #444;
            transition: all 0.3s ease;
        }
        
        li:hover {
            border-left-color: var(--neon-green);
            background: rgba(0, 255, 0, 0.05);
        }

        .metric {
            display: flex;
            justify-content: space-between;
            font-family: monospace;
            margin-top: 5px;
        }

        .value { color: var(--neon-green); font-weight: bold; }
        .value.negative { color: var(--neon-red); }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 10;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scanline 6s linear infinite;
        }

        @keyframes pulse {
            0% { opacity: 0.8; }
            50% { opacity: 1; }
            100% { opacity: 0.8; }
        }

        @keyframes blink {
            from { opacity: 0.4; }
            to { opacity: 1; }
        }

        @keyframes scanline {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(1000%); }
        }

        .grid-data {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .data-box {
            border: 1px solid #333;
            padding: 8px;
            text-align: center;
        }
        .data-box span {
            display: block;
            font-size: 0.8em;
            color: #888;
        }
        .data-box strong {
            font-size: 1.2em;
            color: var(--neon-blue);
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>⚡ ORBITAL COMMAND: NUVOLA ⚡</h1>
    
    <div style="text-align: center; margin-bottom: 30px; color: var(--neon-purple); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-purple);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel red">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT) <span class="status-indicator"></span></h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🐺 
                    <div class="metric"><span>Role:</span> <span>Scalper su Binance</span></div>
                    <div class="metric"><span>Status:</span> <span class="value">ENGAGED</span></div>
                    <div class="metric"><span>Latency:</span> <span>12ms</span></div>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🦅
                    <div class="metric"><span>Role:</span> <span>Order Flow</span></div>
                    <div class="metric"><span>Status:</span> <span class="value">HUNTING</span></div>
                    <div class="metric"><span>Win Rate:</span> <span>64.2%</span></div>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> 🦈
                    <div class="metric"><span>Role:</span> <span>Pairs Trading su Bitget</span></div>
                    <div class="metric"><span>Status:</span> <span class="value">CALIBRATING</span></div>
                    <div class="metric"><span>Exposure:</span> <span>$14,250</span></div>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <h2>🛡️ PROTOCOLLO TRINITY <span class="status-indicator"></span></h2>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> 🕴️
                    <div class="metric"><span>Engine:</span> <span>Funding Arb</span></div>
                    <div class="metric"><span>APR (Est):</span> <span class="value">18.4%</span></div>
                    <div class="metric"><span>Active Positions:</span> <span>4 (Delta Neutral)</span></div>
                </li>
                <li>
                    <strong>Il Contabile</strong> 🧮
                    <div class="metric"><span>Engine:</span> <span>Smart DCA</span></div>
                    <div class="metric"><span>Asset Focus:</span> <span>BTC, ETH, SOL</span></div>
                    <div class="metric"><span>Next Trigger:</span> <span>-4.5% drop</span></div>
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> 👼
                    <div class="metric"><span>Engine:</span> <span>MEV Arbitrum Protection</span></div>
                    <div class="metric"><span>Blocks Scanned:</span> <span>1,432,091</span></div>
                    <div class="metric"><span>Sandwich Avoided:</span> <span class="value">12</span></div>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel blue">
            <h2>📡 METRICHE DI MERCATO <span class="status-indicator"></span></h2>
            <p style="color: #888; font-size: 0.9em;">Sensors: The Oracle (Binance) & Whale Tracker</p>
            <div class="grid-data">
                <div class="data-box">
                    <span>BTC/USDT</span>
                    <strong>$98,421.50</strong>
                </div>
                <div class="data-box">
                    <span>ETH/USDT</span>
                    <strong>$3,142.80</strong>
                </div>
                <div class="data-box">
                    <span>Whale Net Flow</span>
                    <strong style="color: var(--neon-red)">-$42.1M</strong>
                </div>
                <div class="data-box">
                    <span>Global Sentiment</span>
                    <strong>GREED (78)</strong>
                </div>
                <div class="data-box">
                    <span>Vol. 24h</span>
                    <strong>$112.4B</strong>
                </div>
                <div class="data-box">
                    <span>Funding Rate</span>
                    <strong>+0.01%</strong>
                </div>
            </div>
            
            <div style="margin-top: 20px;">
                <strong>Recent Whale Alerts:</strong>
                <ul style="margin-top: 10px; font-size: 0.85em;">
                    <li>🚨 1000 BTC transferred to Coinbase</li>
                    <li>🔥 50,000 ETH withdrawn from Binance</li>
                    <li>⚠️ Suspicious DEX activity on Base</li>
                </ul>
            </div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 30px; font-size: 0.8em; color: #555;">
        [SYSTEM: ONLINE] [ENCRYPTION: AES-256] [NODES: SYNCED]
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
