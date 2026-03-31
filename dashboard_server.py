from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - Nuvola Terminal</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-red: #ff073a;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 5px var(--neon-green), inset 0 0 5px var(--neon-green); }
            50% { box-shadow: 0 0 15px var(--neon-green), inset 0 0 15px var(--neon-green); }
            100% { box-shadow: 0 0 5px var(--neon-green), inset 0 0 5px var(--neon-green); }
        }

        @keyframes glitch {
            0% { transform: translate(0) }
            20% { transform: translate(-2px, 2px) }
            40% { transform: translate(-2px, -2px) }
            60% { transform: translate(2px, 2px) }
            80% { transform: translate(2px, -2px) }
            100% { transform: translate(0) }
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            padding: 20px;
            border-radius: 5px;
            box-shadow: inset 0 0 10px rgba(57, 255, 20, 0.2);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
        }

        .panel h2 {
            margin-top: 0;
            font-size: 1.2em;
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .panel.critical h2 {
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }

        .status-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            border-bottom: 1px dashed rgba(57, 255, 20, 0.3);
            padding-bottom: 5px;
        }

        .status-item span.label {
            font-weight: bold;
        }

        .status-item span.value {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            animation: pulse 2s infinite;
        }

        .table-grid {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.9em;
        }

        .table-grid th, .table-grid td {
            border: 1px solid rgba(57, 255, 20, 0.3);
            padding: 8px;
            text-align: left;
        }

        .table-grid th {
            color: var(--neon-blue);
        }

        .online { color: var(--neon-green); }
        .offline { color: var(--neon-red); }
        .standby { color: #ffb400; }
        
        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 0.8em;
            color: rgba(57, 255, 20, 0.5);
        }
    </style>
</head>
<body>

    <h1>🛰️ ORBITAL COMMAND TERMINAL</h1>

    <div style="text-align: center; margin-top: 20px; color: var(--neon-green); font-weight: bold; font-size: 1.2em; text-shadow: 0 0 10px var(--neon-green); border: 1px solid var(--neon-green); padding: 10px; border-radius: 5px; background-color: var(--panel-bg); box-shadow: inset 0 0 10px rgba(57, 255, 20, 0.2);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="dashboard-grid">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-item">
                <span class="label">🦅 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="value"><div class="status-indicator"></div> ENGAGED</span>
            </div>
            <div class="status-item">
                <span class="label">⚡ SQUADRA_DELTA (Order Flow)</span>
                <span class="value"><div class="status-indicator"></div> ACTIVE</span>
            </div>
            <div class="status-item">
                <span class="label">🐺 SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="value"><div class="status-indicator"></div> DEPLOYED</span>
            </div>
            <p style="font-size: 0.8em; color: var(--neon-blue);">> Executing tactical micro-trades at high frequency...</p>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="status-item">
                <span class="label">🕴️ Lo Strozzino (Funding Arb)</span>
                <span class="value online">[ ONLINE ]</span>
            </div>
            <div class="status-item">
                <span class="label">🧮 Il Contabile (DCA Engine)</span>
                <span class="value online">[ ONLINE ]</span>
            </div>
            <div class="status-item">
                <span class="label">🛡️ L'Angelo Custode (MEV Arb)</span>
                <span class="value online">[ ONLINE ]</span>
            </div>
            <p style="font-size: 0.8em; color: var(--neon-blue);">> Background strategic operations running optimally...</p>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO & ORacoli</h2>
            <div class="status-item">
                <span class="label">👁️ The Oracle (Binance Sentiment)</span>
                <span class="value" style="color: var(--neon-green);">BULLISH (78%)</span>
            </div>
            <div class="status-item">
                <span class="label">🐋 Whale Tracker</span>
                <span class="value" style="color: var(--neon-pink);">LARGE INFLOW DETECTED</span>
            </div>
            
            <table class="table-grid">
                <tr>
                    <th>ASSET</th>
                    <th>SIGNAL</th>
                    <th>VOLATILITY</th>
                </tr>
                <tr>
                    <td>BTC/USDT</td>
                    <td class="online">LONG</td>
                    <td>HIGH</td>
                </tr>
                <tr>
                    <td>ETH/USDT</td>
                    <td class="standby">HOLD</td>
                    <td>MED</td>
                </tr>
                <tr>
                    <td>SOL/USDT</td>
                    <td class="online">LONG</td>
                    <td>EXTREME</td>
                </tr>
            </table>
        </div>

        <!-- SYSTEM CORE -->
        <div class="panel critical">
            <h2>⚙️ SYSTEM CORE</h2>
            <div class="status-item">
                <span class="label">Memory Usage</span>
                <span class="value">42.8%</span>
            </div>
            <div class="status-item">
                <span class="label">Network Latency</span>
                <span class="value">12ms</span>
            </div>
            <div class="status-item">
                <span class="label">API Rate Limits</span>
                <span class="value">Nominal</span>
            </div>
            <p style="font-size: 0.8em; color: var(--neon-red);">> ALL SYSTEMS GREEN. AWAITING NEW DIRECTIVES.</p>
        </div>

    </div>

    <div class="footer">
        Orbital Command - Nuvola V2.0 | SECURE CONNECTION ESTABLISHED
    </div>

</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
