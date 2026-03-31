from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>NUVOLA // ORBITAL COMMAND</title>
    <style>
        :root {
            --bg: #0a0a0c;
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff3333;
            --panel-bg: rgba(16, 20, 25, 0.85);
            --border: #1a2a3a;
        }
        body {
            background-color: var(--bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 40px;
            background-image: 
                linear-gradient(0deg, transparent 24%, rgba(0, 243, 255, .03) 25%, rgba(0, 243, 255, .03) 26%, transparent 27%, transparent 74%, rgba(0, 243, 255, .03) 75%, rgba(0, 243, 255, .03) 76%, transparent 77%, transparent), 
                linear-gradient(90deg, transparent 24%, rgba(0, 243, 255, .03) 25%, rgba(0, 243, 255, .03) 26%, transparent 27%, transparent 74%, rgba(0, 243, 255, .03) 75%, rgba(0, 243, 255, .03) 76%, transparent 77%, transparent);
            background-size: 50px 50px;
        }
        h1 {
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue);
            text-align: center;
            letter-spacing: 4px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border);
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.1);
            padding: 20px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 2px;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
        }
        .panel-title {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            border-bottom: 1px dashed var(--border);
            padding-bottom: 10px;
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 1.2rem;
            text-transform: uppercase;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            border-bottom: 1px solid rgba(57, 255, 20, 0.2);
            padding-bottom: 5px;
            font-size: 1.1rem;
        }
        .status-label {
            color: #ddd;
        }
        .online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); font-weight: bold; }
        .offline { color: var(--neon-red); text-shadow: 0 0 8px var(--neon-red); font-weight: bold; }
        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }
        .blink {
            animation: blink 1s step-end infinite;
        }
        @keyframes blink {
            50% { opacity: 0; }
        }
        .data-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .data-box {
            border: 1px solid var(--neon-blue);
            padding: 15px;
            text-align: center;
            background: rgba(0, 243, 255, 0.05);
            box-shadow: inset 0 0 10px rgba(0, 243, 255, 0.1);
        }
        .data-label {
            font-size: 0.8rem;
            color: #aaa;
            margin-bottom: 5px;
            text-transform: uppercase;
        }
        .data-value {
            font-size: 1.5rem;
            color: var(--neon-blue);
            text-shadow: 0 0 8px var(--neon-blue);
            font-weight: bold;
        }
        .footer {
            margin-top: 40px; 
            text-align: center; 
            font-size: 0.9em; 
            color: #666;
            border-top: 1px dashed #333;
            padding-top: 20px;
        }
    </style>
</head>
<body>
    <h1><span class="blink">></span> NUVOLA // ORBITAL COMMAND TERMINAL <span class="blink"><</span></h1>
    
    <div style="text-align: center; margin-bottom: 30px; padding: 15px; border: 1px solid var(--neon-green); background: rgba(57, 255, 20, 0.1); box-shadow: 0 0 15px rgba(57, 255, 20, 0.2);">
        <h2 style="margin: 0; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h2>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 class="panel-title">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item">
                <span class="status-label">💥 [ALPHA] Scalper (Binance)</span>
                <span class="online pulse">ONLINE</span>
            </div>
            <div class="status-item">
                <span class="status-label">🌊 [DELTA] Order Flow</span>
                <span class="online pulse">ONLINE</span>
            </div>
            <div class="status-item">
                <span class="status-label">⚖️ [GAMMA] Pairs Trading (Bitget)</span>
                <span class="online pulse">ONLINE</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="panel-title">🛡️ PROTOCOLLO TRINITY</h2>
            <div class="status-item">
                <span class="status-label">🕴️ Lo Strozzino (Funding Arb)</span>
                <span class="online">ACTIVE</span>
            </div>
            <div class="status-item">
                <span class="status-label">🧮 Il Contabile (DCA)</span>
                <span class="online">ACTIVE</span>
            </div>
            <div class="status-item">
                <span class="status-label">👼 L'Angelo Custode (MEV)</span>
                <span class="online">ACTIVE</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="panel-title">📊 METRICHE DI MERCATO</h2>
            <div class="data-grid">
                <div class="data-box">
                    <div class="data-label">The Oracle (Sentiment)</div>
                    <div class="data-value pulse" style="color: var(--neon-green);">EXTREME GREED</div>
                </div>
                <div class="data-box">
                    <div class="data-label">Whale Tracker (Inflow)</div>
                    <div class="data-value">+$420.69M</div>
                </div>
                <div class="data-box">
                    <div class="data-label">System Latency</div>
                    <div class="data-value">12 ms</div>
                </div>
                <div class="data-box">
                    <div class="data-label">Uptime</div>
                    <div class="data-value">99.99%</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        SYSTEM: NUVOLA OS v4.2.0 | ENCRYPTION: AES-256-GCM | OVERRIDE: <span class="online blink">ENGAGED</span>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
