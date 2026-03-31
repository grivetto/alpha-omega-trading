from flask import Flask, render_template_string
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        body {
            background-color: #020204;
            color: #0ff;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 40px;
            overflow-x: hidden;
            background-image: linear-gradient(0deg, transparent 24%, rgba(0, 255, 255, 0.05) 25%, rgba(0, 255, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 255, 0.05) 75%, rgba(0, 255, 255, 0.05) 76%, transparent 77%, transparent), linear-gradient(90deg, transparent 24%, rgba(0, 255, 255, 0.05) 25%, rgba(0, 255, 255, 0.05) 26%, transparent 27%, transparent 74%, rgba(0, 255, 255, 0.05) 75%, rgba(0, 255, 255, 0.05) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1 {
            text-align: center;
            color: #f0f;
            text-shadow: 0 0 10px #f0f, 0 0 20px #f0f, 0 0 40px #f0f;
            text-transform: uppercase;
            letter-spacing: 8px;
            font-size: 3em;
            margin-bottom: 50px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: rgba(0, 10, 20, 0.85);
            border: 2px solid #0ff;
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.3) inset, 0 0 15px #0ff;
            padding: 25px;
            border-radius: 8px;
            position: relative;
            backdrop-filter: blur(5px);
        }
        .panel h2 {
            color: #0f0;
            text-shadow: 0 0 8px #0f0;
            border-bottom: 2px solid #0f0;
            padding-bottom: 10px;
            margin-top: 0;
            font-size: 1.5em;
            text-transform: uppercase;
        }
        .status {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            padding: 12px;
            background: rgba(0, 255, 0, 0.15);
            border-left: 4px solid #0f0;
            font-size: 1.1em;
            border-radius: 0 4px 4px 0;
            transition: all 0.3s ease;
        }
        .status:hover {
            background: rgba(0, 255, 0, 0.3);
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
        }
        .status.warning {
            background: rgba(255, 255, 0, 0.15);
            border-left-color: #ff0;
            color: #ff0;
            text-shadow: 0 0 5px #ff0;
        }
        .status.danger {
            background: rgba(255, 0, 0, 0.15);
            border-left-color: #f00;
            color: #f00;
            text-shadow: 0 0 5px #f00;
        }
        .metric-value {
            font-weight: bold;
            color: #fff;
            text-shadow: 0 0 8px #fff;
        }
        .value-green { color: #0f0; text-shadow: 0 0 8px #0f0; }
        .value-red { color: #f00; text-shadow: 0 0 8px #f00; }
        .value-cyan { color: #0ff; text-shadow: 0 0 8px #0ff; }

        @keyframes pulse {
            0% { opacity: 0.8; }
            50% { opacity: 1; text-shadow: 0 0 20px #f0f, 0 0 40px #f0f; }
            100% { opacity: 0.8; }
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
        .blink { animation: blink 1.5s infinite; }
        .fast-blink { animation: blink 0.5s infinite; }
        .scanline {
            width: 100%;
            height: 150px;
            z-index: 9999;
            position: fixed;
            left: 0;
            pointer-events: none;
            background: linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,255,255,0.1) 50%, rgba(0,0,0,0) 100%);
            animation: scan 8s linear infinite;
        }
        @keyframes scan {
            0% { top: -200px; }
            100% { top: 100%; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1><span class="fast-blink">🔴</span> NUVOLA ORBITAL COMMAND <span class="fast-blink">🔴</span></h1>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status">
                <span>🐺 SQUADRA_ALPHA <span style="font-size:0.8em; opacity:0.7;">[Binance Scalp]</span></span>
                <span class="metric-value value-green">ENGAGED</span>
            </div>
            <div class="status warning">
                <span>⚡ SQUADRA_DELTA <span style="font-size:0.8em; opacity:0.7;">[Order Flow]</span></span>
                <span class="metric-value">RECALIBRATING</span>
            </div>
            <div class="status">
                <span>⚖️ SQUADRA_GAMMA <span style="font-size:0.8em; opacity:0.7;">[Bitget Pairs]</span></span>
                <span class="metric-value value-cyan blink">DEPLOYED</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: #f0f; box-shadow: 0 0 20px rgba(255, 0, 255, 0.3) inset, 0 0 15px #f0f;">
            <h2 style="color: #f0f; border-bottom-color: #f0f; text-shadow: 0 0 8px #f0f;">🔺 PROTOCOLLO TRINITY</h2>
            <div style="text-align: center; color: #0f0; font-weight: bold; margin-bottom: 15px; text-shadow: 0 0 8px #0f0;" class="blink">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="status" style="border-left-color: #f0f; background: rgba(255, 0, 255, 0.1);">
                <span style="color:#f0f;">🦇 Lo Strozzino <span style="font-size:0.8em; opacity:0.7;">[Funding Arb]</span></span>
                <span class="metric-value blink">ONLINE</span>
            </div>
            <div class="status" style="border-left-color: #f0f; background: rgba(255, 0, 255, 0.1);">
                <span style="color:#f0f;">🧮 Il Contabile <span style="font-size:0.8em; opacity:0.7;">[DCA Matrix]</span></span>
                <span class="metric-value">ONLINE</span>
            </div>
            <div class="status" style="border-left-color: #f0f; background: rgba(255, 0, 255, 0.1);">
                <span style="color:#f0f;">🛡️ L'Angelo Custode <span style="font-size:0.8em; opacity:0.7;">[MEV Arbitrum]</span></span>
                <span class="metric-value">ONLINE</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📡 METRICHE DI MERCATO</h2>
            <div class="status">
                <span>👁️ The Oracle <span style="font-size:0.8em; opacity:0.7;">[Binance Sent]</span></span>
                <span class="metric-value value-green">BULLISH [{{ oracle_prob }}%]</span>
            </div>
            <div class="status danger">
                <span>🐳 Whale Tracker <span style="font-size:0.8em; opacity:0.7;">[On-Chain]</span></span>
                <span class="metric-value value-red blink">DETECTED {{ whale_vol }} BTC</span>
            </div>
            <div class="status">
                <span>⏱️ Orbital Latency</span>
                <span class="metric-value value-cyan">{{ latency }}ms</span>
            </div>
        </div>
    </div>
    <script>
        // Fake dynamic updates without full reload for cyberpunk feel
        setInterval(() => {
            let latencies = document.querySelectorAll('.value-cyan');
            latencies.forEach(l => {
                if (l.innerText.includes('ms')) {
                    let base = parseInt(l.innerText);
                    let jitter = Math.floor(Math.random() * 5) - 2;
                    let newVal = Math.max(2, base + jitter);
                    l.innerText = newVal + 'ms';
                }
            });
        }, 1500);
        
        setInterval(() => {
            location.reload();
        }, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    oracle_prob = random.randint(75, 96)
    whale_vol = random.randint(450, 2100)
    latency = random.randint(4, 18)
    return render_template_string(HTML_TEMPLATE, oracle_prob=oracle_prob, whale_vol=whale_vol, latency=latency)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
