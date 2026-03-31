from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        /* Scanlines */
        body::before {
            content: " ";
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }
        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 30px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            z-index: 10;
            position: relative;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.5);
            border-color: var(--neon-pink);
        }
        .panel h2 {
            margin-top: 0;
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 10px;
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            font-size: 1.2em;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 15px;
            line-height: 1.4;
        }
        .status-online {
            color: var(--neon-blue);
            font-weight: bold;
            animation: blink 2s infinite;
        }
        .status-active {
            color: var(--neon-green);
            font-weight: bold;
        }
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            color: #ddd;
        }
        th, td {
            border: 1px solid #333;
            padding: 8px;
            text-align: left;
            font-size: 0.9em;
        }
        th {
            background-color: #222;
            color: var(--neon-blue);
        }
        .emoji {
            font-size: 1.2em;
            margin-right: 5px;
        }
    </style>
</head>
<body>
    <h1>🌐 NUVOLA ORBITAL COMMAND 🌐</h1>
    <div style="text-align: center; margin-bottom: 30px; font-size: 1.5em; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span class="emoji">⚡</span> <strong>SQUADRA_ALPHA</strong><br>
                    <small>Binance Scalper Unit</small><br>
                    Status: <span class="status-active">[ ENGAGED - 15ms latency ]</span>
                </li>
                <li>
                    <span class="emoji">🌊</span> <strong>SQUADRA_DELTA</strong><br>
                    <small>Order Flow Dominator</small><br>
                    Status: <span class="status-active">[ READING TAPE ]</span>
                </li>
                <li>
                    <span class="emoji">⚖️</span> <strong>SQUADRA_GAMMA</strong><br>
                    <small>Bitget Pairs Trading</small><br>
                    Status: <span class="status-active">[ ARB SEARCHING ]</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <span class="emoji">🕴️</span> <strong>Lo Strozzino</strong> (Funding Arb)<br>
                    Status: <span class="status-online">[ ONLINE IN BACKGROUND ]</span><br>
                    <small>Yield ext: 14.2% APR</small>
                </li>
                <li>
                    <span class="emoji">💼</span> <strong>Il Contabile</strong> (DCA)<br>
                    Status: <span class="status-online">[ ONLINE IN BACKGROUND ]</span><br>
                    <small>Next buy in: 04:12:00</small>
                </li>
                <li>
                    <span class="emoji">👼</span> <strong>L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    Status: <span class="status-online">[ ONLINE IN BACKGROUND ]</span><br>
                    <small>Mempool monitoring: ACTIVE</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <p><span class="emoji">👁️</span> <strong>The Oracle (Binance Sentiment)</strong></p>
            <table>
                <tr><th>Asset</th><th>Sentiment</th><th>Confidence</th></tr>
                <tr><td>BTC/USDT</td><td style="color:#0f0;">BULLISH</td><td>87%</td></tr>
                <tr><td>ETH/USDT</td><td style="color:#0f0;">BULLISH</td><td>76%</td></tr>
                <tr><td>SOL/USDT</td><td style="color:#f00;">BEARISH</td><td>65%</td></tr>
            </table>
            
            <p style="margin-top:20px;"><span class="emoji">🐳</span> <strong>Whale Tracker</strong></p>
            <table>
                <tr><th>Time</th><th>Action</th><th>Vol</th></tr>
                <tr><td>-2m</td><td>BTC INFLOW</td><td>$14M</td></tr>
                <tr><td>-15m</td><td>ETH OUTFLOW</td><td>$5M</td></tr>
            </table>
        </div>

    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
