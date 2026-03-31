from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola: Orbital Command</title>
    <style>
        body {
            background-color: #050510;
            color: #00ffcc;
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
        }
        h1, h2, h3 {
            color: #ff00ff;
            text-shadow: 0 0 10px #ff00ff, 0 0 20px #ff00ff;
            letter-spacing: 2px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            border: 1px solid #00ffcc;
            box-shadow: 0 0 15px #00ffcc inset, 0 0 15px #00ffcc;
            padding: 20px;
            margin-bottom: 20px;
            background: rgba(0, 255, 204, 0.05);
            border-radius: 5px;
            backdrop-filter: blur(5px);
        }
        .pulse {
            animation: pulse-animation 3s infinite;
        }
        @keyframes pulse-animation {
            0% { box-shadow: 0 0 15px #00ffcc inset, 0 0 15px #00ffcc; }
            50% { box-shadow: 0 0 30px #00ffcc inset, 0 0 30px #00ffcc; }
            100% { box-shadow: 0 0 15px #00ffcc inset, 0 0 15px #00ffcc; }
        }
        .status-online {
            color: #00ff00;
            text-shadow: 0 0 5px #00ff00;
            animation: blinker 1.5s linear infinite;
            font-weight: bold;
        }
        @keyframes blinker {
            50% { opacity: 0.5; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid #00ffcc;
            padding: 12px;
            text-align: left;
        }
        th {
            background-color: rgba(0, 255, 204, 0.2);
            color: #fff;
            text-shadow: 0 0 5px #fff;
        }
        .trinity-panel {
            border-color: #ff00ff;
            box-shadow: 0 0 15px #ff00ff inset, 0 0 15px #ff00ff;
            background: rgba(255, 0, 255, 0.05);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        ul { list-style-type: none; padding-left: 0; }
        li { margin-bottom: 10px; border-bottom: 1px dashed rgba(0, 255, 204, 0.3); padding-bottom: 5px;}
    </style>
</head>
<body>
    <div class="container">
        <h1 align="center">🛰️ ORBITAL COMMAND: NUVOLA 🛰️</h1>
        <p align="center" class="status-online">&gt;&gt; SYSTEM ONLINE - SECURE UPLINK ESTABLISHED &lt;&lt;</p>
        
        <div class="panel" style="text-align: center; border-color: #ffaa00; box-shadow: 0 0 15px #ffaa00 inset, 0 0 15px #ffaa00; background: rgba(255, 170, 0, 0.05); padding: 10px;">
            <h3 style="margin: 0; color: #ffaa00; text-shadow: 0 0 10px #ffaa00;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
        </div>
        
        <div class="panel pulse">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT) ⚔️</h2>
            <table>
                <tr>
                    <th>Unità Tattica</th>
                    <th>Specializzazione</th>
                    <th>Vettore d'Attacco</th>
                    <th>Stato Operativo</th>
                    <th>ROE (24h)</th>
                </tr>
                <tr>
                    <td>⚡ SQUADRA_ALPHA</td>
                    <td>Scalping Alta Frequenza</td>
                    <td>Binance API</td>
                    <td class="status-online">ACTIVE</td>
                    <td style="color: #00ff00;">+2.45%</td>
                </tr>
                <tr>
                    <td>🌊 SQUADRA_DELTA</td>
                    <td>Order Flow / Imbalance</td>
                    <td>Deribit / Binance</td>
                    <td class="status-online">ACTIVE</td>
                    <td style="color: #00ff00;">+1.12%</td>
                </tr>
                <tr>
                    <td>⚖️ SQUADRA_GAMMA</td>
                    <td>Pairs Trading (StatArb)</td>
                    <td>Bitget</td>
                    <td class="status-online">ACTIVE</td>
                    <td style="color: #00ff00;">+0.85%</td>
                </tr>
            </table>
        </div>

        <div class="grid">
            <div class="panel trinity-panel">
                <h2>🛡️ PROTOCOLLO TRINITY 🛡️</h2>
                <p>Processi Demoniaci [Background Ops]:</p>
                <ul>
                    <li>💸 <strong>Lo Strozzino:</strong> [Funding Rate Arb] &raquo; <span class="status-online">ONLINE</span></li>
                    <li>🧮 <strong>Il Contabile:</strong> [Smart DCA Protocol] &raquo; <span class="status-online">ONLINE</span></li>
                    <li>👼 <strong>L'Angelo Custode:</strong> [MEV Protection / Arbitrum] &raquo; <span class="status-online">ONLINE</span></li>
                </ul>
                <p style="font-size: 0.8em; color: #ff00ff; text-align: center; margin-top: 20px;">
                    [!] SORVEGLIANZA CAPITALE ATTIVA. PROTEZIONE DOWNSIDE INGAGGIATA.
                </p>
            </div>

            <div class="panel">
                <h2>📊 METRICHE DI MERCATO 📊</h2>
                <p>Feed Dati Telemetrici (Real-Time):</p>
                <ul>
                    <li>🔮 <strong>The Oracle (Binance):</strong> BULLISH [L/S Ratio: 1.45]</li>
                    <li>🐋 <strong>Whale Tracker:</strong> <span style="color: #ff3333; font-weight: bold; animation: blinker 1s infinite;">ALERT</span> - 5000 BTC INFLOW (Coinbase)</li>
                    <li>📡 <strong>VIX Crypto:</strong> 45.2 (ELEVATA)</li>
                </ul>
                <p style="margin-bottom: 2px; font-size: 0.8em;">CARICO CPU / ESECUZIONE:</p>
                <div style="width: 100%; height: 15px; background: #111; border: 1px solid #00ffcc;">
                    <div style="width: 82%; height: 100%; background: #00ffcc; box-shadow: 0 0 10px #00ffcc;"></div>
                </div>
                <p style="font-size: 0.7em; text-align: right; margin-top: 5px;">LOAD: 82%</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Disabling reloader if running in background
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
