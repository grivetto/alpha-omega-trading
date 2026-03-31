from flask import Flask, render_template_string
import logging

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | Nuvola Dashboard</title>
    <style>
        :root {
            --bg-color: #050510;
            --primary: #0ff;
            --secondary: #f0f;
            --success: #0f0;
            --warning: #ff0;
            --danger: #f00;
            --panel-bg: rgba(0, 20, 40, 0.8);
            --grid-line: rgba(0, 255, 255, 0.1);
        }
        body {
            background-color: var(--bg-color);
            color: var(--primary);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 30px 30px;
            text-transform: uppercase;
        }
        h1, h2, h3 {
            text-shadow: 0 0 10px var(--primary);
            margin-top: 0;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--primary);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2), inset 0 0 20px rgba(0, 255, 255, 0.1);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: var(--primary);
            box-shadow: 0 0 10px var(--primary);
            animation: scanline 2s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateY(-100%); opacity: 0; }
            50% { opacity: 1; }
            100% { transform: translateY(1000%); opacity: 0; }
        }
        .header {
            grid-column: 1 / -1;
            text-align: center;
            border-bottom: 2px solid var(--secondary);
            padding-bottom: 20px;
            margin-bottom: 20px;
            text-shadow: 0 0 15px var(--secondary);
            color: var(--secondary);
        }
        .status-online { color: var(--success); text-shadow: 0 0 5px var(--success); font-weight: bold; }
        .status-offline { color: var(--danger); text-shadow: 0 0 5px var(--danger); font-weight: bold; }
        .status-standby { color: var(--warning); text-shadow: 0 0 5px var(--warning); font-weight: bold; }
        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; border-bottom: 1px dashed rgba(0, 255, 255, 0.3); padding-bottom: 10px; }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid rgba(0, 255, 255, 0.3); padding: 10px; text-align: left; }
        th { background: rgba(0, 255, 255, 0.1); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p class="blink">/// NUVOLA SYSTEM ONLINE /// SECURE UPLINK ESTABLISHED ///</p>
        <p style="color: var(--warning); font-size: 1.2em; border: 1px solid var(--warning); display: inline-block; padding: 5px 15px; border-radius: 3px;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </p>
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>[SQUADRA_ALPHA]</strong> - Scalper su Binance 
                    <span style="float:right" class="status-online">⚡ ENGAGED</span><br>
                    <small style="color:#aaa;">Target: BTC/USDT | Latency: 12ms | PNL: +0.42% (1h)</small>
                </li>
                <li>
                    <strong>[SQUADRA_DELTA]</strong> - Order Flow 
                    <span style="float:right" class="status-online">⚡ ENGAGED</span><br>
                    <small style="color:#aaa;">Target: ETH/USDT | Volume Spike Detected | Active Orders: 14</small>
                </li>
                <li>
                    <strong>[SQUADRA_GAMMA]</strong> - Pairs Trading su Bitget 
                    <span style="float:right" class="status-standby">⏳ STANDBY</span><br>
                    <small style="color:#aaa;">Target: SOL/AVAX | Spread: 0.15% (Target: 0.25%)</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>🕴️ Lo Strozzino</strong> (Funding Arb)
                    <span style="float:right" class="status-online">🟢 ONLINE [BACKGROUND]</span><br>
                    <small style="color:#aaa;">Monitoring 42 perpetual markets. Delta neutral.</small>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> (DCA)
                    <span style="float:right" class="status-online">🟢 ONLINE [BACKGROUND]</span><br>
                    <small style="color:#aaa;">Next execution in 4h 12m. Accumulating BTC.</small>
                </li>
                <li>
                    <strong>👼 L'Angelo Custode</strong> (MEV Arbitrum)
                    <span style="float:right" class="status-online">🟢 ONLINE [BACKGROUND]</span><br>
                    <small style="color:#aaa;">Mempool scanning active. Flashbots connected.</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>📊 METRICHE DI MERCATO: THE ORACLE & WHALE TRACKER</h2>
            <table>
                <tr>
                    <th>DATA SOURCE</th>
                    <th>METRIC</th>
                    <th>VALUE</th>
                    <th>SIGNAL</th>
                </tr>
                <tr>
                    <td>👁️ THE ORACLE (Binance Sentiment)</td>
                    <td>Long/Short Ratio (Top Traders)</td>
                    <td>1.45</td>
                    <td class="status-online">BULLISH</td>
                </tr>
                <tr>
                    <td>👁️ THE ORACLE</td>
                    <td>Taker Buy/Sell Volume</td>
                    <td>52.3% Buy</td>
                    <td class="status-online">WEAK BUY</td>
                </tr>
                <tr>
                    <td>🐳 WHALE TRACKER</td>
                    <td>Large Transactions (>100 BTC)</td>
                    <td>12 in last 1H</td>
                    <td class="status-standby">NEUTRAL / ACCUMULATION</td>
                </tr>
                <tr>
                    <td>🐳 WHALE TRACKER</td>
                    <td>Exchange Netflow</td>
                    <td>-4,500 BTC</td>
                    <td class="status-online">STRONG BULLISH</td>
                </tr>
            </table>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 30px; font-size: 0.8em; color: rgba(0,255,255,0.5);">
        [ NUVOLA KERNEL V4.2.0 ] // ALL SYSTEMS NOMINAL // [ AUTO-REFRESH EVERY 30S ]
    </div>
    <script>
        setTimeout(() => { window.location.reload(); }, 30000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
