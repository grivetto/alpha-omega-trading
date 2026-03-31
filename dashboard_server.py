from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --dark-bg: #050505;
            --panel-bg: rgba(0, 255, 0, 0.03);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            text-transform: uppercase;
            overflow-x: hidden;
        }
        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            letter-spacing: 2px;
        }
        h2 {
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
            margin-top: 0;
            font-size: 1.2em;
            border-bottom: 1px dashed #333;
            padding-bottom: 10px;
        }
        h3 {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-top: 30px;
        }
        .panel {
            border: 1px solid var(--neon-green);
            padding: 20px;
            background: var(--panel-bg);
            box-shadow: inset 0 0 15px rgba(0,255,0,0.1), 0 0 10px rgba(0,255,0,0.2);
            position: relative;
            overflow: hidden;
            border-radius: 4px;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: -100%;
            left: -100%;
            width: 300%;
            height: 300%;
            background: linear-gradient(0deg, transparent, rgba(0,255,0,0.05), transparent);
            animation: scanline 6s linear infinite;
            pointer-events: none;
        }
        @keyframes scanline {
            0% { transform: translateY(-50%); }
            100% { transform: translateY(50%); }
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); font-weight: bold; }
        .status-warning { color: #ff0; text-shadow: 0 0 5px #ff0; font-weight: bold; }
        .status-offline { color: #f00; text-shadow: 0 0 5px #f00; font-weight: bold; }
        .status-hunting { color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); font-weight: bold; }
        
        ul { list-style-type: none; padding: 0; margin: 0; }
        li { margin-bottom: 15px; background: rgba(0,0,0,0.5); padding: 10px; border-left: 3px solid var(--neon-green); }
        li strong { font-size: 1.1em; }
        small { display: block; margin-top: 5px; color: #888; font-size: 0.9em; }
        
        .blink { animation: blinker 1.5s linear infinite; }
        .fast-blink { animation: blinker 0.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        
        .grid-full { grid-column: span 2; }
        .metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        
        .sys-info {
            display: flex;
            justify-content: space-between;
            background: #111;
            padding: 10px;
            border: 1px solid #333;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND <span class="blink">_</span></h1>
    
    <div class="sys-info">
        <span>SYSTEM: <span class="status-online">ONLINE</span></span>
        <span>UPLINK: <span class="status-online">SECURE</span></span>
        <span>LOCATION: NUVOLA</span>
        <span>NODE: ALPHA-7</span>
        <span id="clock">00:00:00</span>
    </div>
    
    <div style="text-align: center; border: 1px dashed var(--neon-blue); padding: 10px; margin-bottom: 20px; background: rgba(0, 255, 255, 0.05);">
        <span style="font-size: 1.2em; font-weight: bold; color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> [Binance Scalper] 
                    <span style="float:right;" class="status-online">ACTIVE 🟢</span>
                    <small id="alpha-metrics">Pnl/Day: +1.24% | Latency: 12ms</small>
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> [Order Flow] 
                    <span style="float:right;" class="status-online">ACTIVE 🟢</span>
                    <small>Imbalance detected. Accumulating bid side...</small>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> [Bitget Pairs] 
                    <span style="float:right;" class="status-warning">STANDBY 🟡</span>
                    <small>Awaiting divergence threshold (Z-Score > 2.5)</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>LO STROZZINO</strong> [Funding Arb] 
                    <span style="float:right;" class="status-online">DEPLOYED 🟢</span>
                    <small>Net APR: +24.5% (Short Perps, Long Spot)</small>
                </li>
                <li>
                    <strong>IL CONTABILE</strong> [DCA] 
                    <span style="float:right;" class="status-online">RUNNING 🟢</span>
                    <small id="dca-timer">Next BTC buy in: 04h 12m 30s</small>
                </li>
                <li>
                    <strong>L'ANGELO CUSTODE</strong> [MEV Arbitrum] 
                    <span style="float:right;" class="status-hunting fast-blink">HUNTING 🟣</span>
                    <small>Scanning mempool for sandwich opportunities...</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel grid-full">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metrics-grid">
                <div style="background: rgba(0,255,255,0.05); padding: 15px; border: 1px solid var(--neon-blue);">
                    <h3>🔮 THE ORACLE (Binance Sentiment)</h3>
                    <p>Current Bias: <span class="status-online">BULLISH (68%)</span></p>
                    <p>Orderbook Depth: <span class="status-warning">ASYMMETRIC (Ask Heavy)</span></p>
                    <p>Vol. Spike Detected: <span class="status-offline blink">FALSE</span></p>
                </div>
                <div style="background: rgba(255,0,255,0.05); padding: 15px; border: 1px solid var(--neon-pink);">
                    <h3>🐋 WHALE TRACKER</h3>
                    <p>Large TX Alert: <span class="status-offline">1,500 BTC to Coinbase</span></p>
                    <p>Tether Treasury: <span class="status-online">Minted 1B USDT</span></p>
                    <p>Exchange Netflow: <span class="status-online">-12,450 BTC (Outflow)</span></p>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Clock
        setInterval(() => {
            const now = new Date();
            document.getElementById('clock').innerText = now.toISOString().split('T')[1].split('.')[0] + " UTC";
        }, 1000);

        // Simulate live HFT metrics
        setInterval(() => {
            const latency = Math.floor(Math.random() * 15) + 5;
            const pnl = (1.2 + Math.random() * 0.1).toFixed(3);
            document.getElementById('alpha-metrics').innerText = `Pnl/Day: +${pnl}% | Latency: ${latency}ms | Ops/sec: ${Math.floor(Math.random()*50)+10}`;
        }, 800);
        
        // Simulate countdown for DCA
        let dcaSeconds = 15150; // 4h 12m 30s
        setInterval(() => {
            dcaSeconds--;
            const h = Math.floor(dcaSeconds / 3600);
            const m = Math.floor((dcaSeconds % 3600) / 60);
            const s = dcaSeconds % 60;
            document.getElementById('dca-timer').innerText = `Next BTC buy in: ${h.toString().padStart(2, '0')}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s`;
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Riavvia su porta 5000 in tutte le interfacce per la rete locale / tailscale
    app.run(host='0.0.0.0', port=5000, debug=False)
