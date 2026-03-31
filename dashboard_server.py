from flask import Flask, render_template_string
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --bg-color: #050505;
            --text-color: #e0e0e0;
            --neon-blue: #00f3ff;
            --neon-red: #ff003c;
            --neon-green: #39ff14;
            --neon-purple: #bc13fe;
            --panel-bg: rgba(10, 10, 15, 0.8);
            --border-glow: 0 0 10px rgba(0, 243, 255, 0.5);
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 15px var(--neon-blue);
            text-align: center;
            margin-bottom: 40px;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: var(--border-glow);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scan 3s linear infinite;
        }
        @keyframes scan {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        h2 {
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 10px;
        }
        .squad-alpha h2 { color: var(--neon-red); border-color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); }
        .squad-alpha { border-color: var(--neon-red); box-shadow: 0 0 10px rgba(255, 0, 60, 0.5); }
        .protocol-trinity h2 { color: var(--neon-purple); border-color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); }
        .protocol-trinity { border-color: var(--neon-purple); box-shadow: 0 0 10px rgba(188, 19, 254, 0.5); }
        .market-metrics h2 { color: var(--neon-green); border-color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); }
        .market-metrics { border-color: var(--neon-green); box-shadow: 0 0 10px rgba(57, 255, 20, 0.5); grid-column: 1 / -1; }
        
        .status-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            padding: 5px;
            background: rgba(255,255,255,0.05);
        }
        .status-online { color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green); }
        .status-standby { color: #ffa500; font-weight: bold; text-shadow: 0 0 5px #ffa500; }
        .status-active { color: var(--neon-red); font-weight: bold; text-shadow: 0 0 5px var(--neon-red); animation: pulse 1.5s infinite; }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .grid-data {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            text-align: center;
        }
        .data-box {
            border: 1px solid rgba(57, 255, 20, 0.3);
            padding: 10px;
            background: rgba(0,0,0,0.5);
        }
        .data-value {
            font-size: 1.5em;
            color: var(--neon-green);
            margin-top: 5px;
        }
        .blink { animation: blinker 2s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
    </style>
</head>
<body>
    <h1><span class="blink">🔴</span> ORBITAL COMMAND - NUVOLA DASHBOARD <span class="blink">🔴</span></h1>
    
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple); border: 1px solid var(--neon-purple); padding: 10px; background: rgba(188, 19, 254, 0.1);">
        <span class="blink">⚙️</span> PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) <span class="blink">⚙️</span>
    </div>
    
    <div class="container">
        <!-- ASSAULT SQUADS -->
        <div class="panel squad-alpha">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item">
                <span>🐺 SQUADRA_ALPHA (Scalper su Binance)</span>
                <span class="status-active">ENGAGED</span>
            </div>
            <div class="status-item">
                <span>🌊 SQUADRA_DELTA (Order Flow)</span>
                <span class="status-online">MONITORING</span>
            </div>
            <div class="status-item">
                <span>⚖️ SQUADRA_GAMMA (Pairs Trading su Bitget)</span>
                <span class="status-standby">STANDBY</span>
            </div>
        </div>

        <!-- PROTOCOL TRINITY -->
        <div class="panel protocol-trinity">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div class="status-item">
                <span>🦇 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">ONLINE</span>
            </div>
            <div class="status-item">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="status-online">ONLINE</span>
            </div>
            <div class="status-item">
                <span>👼 L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status-online">SHIELDING</span>
            </div>
        </div>

        <!-- MARKET METRICS -->
        <div class="panel market-metrics">
            <h2>📊 METRICHE DI MERCATO - THE ORACLE & WHALE TRACKER</h2>
            <div class="grid-data">
                <div class="data-box">
                    <div>BTC/USDT</div>
                    <div class="data-value">$68,420.50</div>
                </div>
                <div class="data-box">
                    <div>BINANCE SENTIMENT</div>
                    <div class="data-value" style="color: var(--neon-red);">EXTREME GREED</div>
                </div>
                <div class="data-box">
                    <div>WHALE ALERT</div>
                    <div class="data-value">5,000 BTC MOVED</div>
                </div>
                <div class="data-box">
                    <div>ARB GAS FEE</div>
                    <div class="data-value">0.01 GWEI</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Fake dynamic updates for realism
        setInterval(() => {
            const btcBox = document.querySelectorAll('.data-value')[0];
            let current = parseFloat(btcBox.innerText.replace(/[$,]/g, ''));
            let change = (Math.random() - 0.5) * 50;
            btcBox.innerText = '$' + (current + change).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
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
