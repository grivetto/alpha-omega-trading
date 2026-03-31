from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --dark-bg: #050505;
            --panel-bg: rgba(10, 10, 10, 0.85);
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 8px currentColor, 0 0 15px currentColor;
        }
        h1 { 
            color: var(--neon-blue); 
            text-align: center; 
            border-bottom: 3px double var(--neon-blue); 
            padding-bottom: 15px; 
            letter-spacing: 4px;
        }
        h2 { 
            color: var(--neon-pink); 
            border-bottom: 1px dashed var(--neon-pink); 
            font-size: 1.2em;
            padding-bottom: 5px;
        }
        
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 25px;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.15);
            padding: 20px;
            border-radius: 4px;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(5px);
        }
        
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 15px var(--neon-green);
            animation: scanline 4s linear infinite;
            opacity: 0.7;
        }
        
        @keyframes scanline {
            0% { transform: translateY(-100px); }
            100% { transform: translateY(500px); }
        }
        
        .status-online { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); animation: blink 2s infinite; font-weight: bold; }
        .status-active { color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue); font-weight: bold; }
        .status-warning { color: #ffeb3b; text-shadow: 0 0 8px #ffeb3b; font-weight: bold; }
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.9em; }
        th, td { border: 1px solid rgba(57, 255, 20, 0.2); padding: 10px; text-align: left; }
        th { background: rgba(57, 255, 20, 0.1); color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        tr:hover { background: rgba(57, 255, 20, 0.05); }
        
        .list-item {
            margin: 15px 0;
            padding: 10px;
            border-left: 3px solid var(--neon-pink);
            background: rgba(255, 0, 255, 0.05);
        }

        .metric-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-top: 15px; }
        .metric-box { 
            border: 1px solid rgba(0, 255, 255, 0.4); 
            padding: 15px; 
            text-align: center; 
            background: rgba(0, 255, 255, 0.05);
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.1); 
        }
        .metric-title { font-size: 0.85em; opacity: 0.8; letter-spacing: 1px; }
        .metric-value { 
            font-size: 1.8em; 
            font-weight: bold; 
            margin-top: 8px; 
            color: var(--neon-blue); 
            text-shadow: 0 0 10px var(--neon-blue); 
        }
        .metric-value.critical { color: var(--neon-pink); text-shadow: 0 0 10px var(--neon-pink); }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            font-size: 0.8em;
            opacity: 0.7;
            letter-spacing: 2px;
            border-top: 1px solid rgba(57, 255, 20, 0.3);
            padding-top: 20px;
        }
    </style>
</head>
<body>
    <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    
    <div style="text-align: center; margin-bottom: 25px; font-size: 1.3em; border: 1px solid var(--neon-green); padding: 12px; background: rgba(57, 255, 20, 0.1); box-shadow: 0 0 15px rgba(57, 255, 20, 0.2); border-radius: 4px;">
        <span class="status-online">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr><th>SQUADRA</th><th>TARGET</th><th>STATO</th><th>P&L (24h)</th></tr>
                <tr><td>🐺 SQUADRA_ALPHA</td><td>Binance Scalper</td><td><span class="status-online">ENGAGED</span></td><td class="status-active">+4.2%</td></tr>
                <tr><td>🦅 SQUADRA_DELTA</td><td>Order Flow</td><td><span class="status-online">MONITORING</span></td><td class="status-active">+1.8%</td></tr>
                <tr><td>🐍 SQUADRA_GAMMA</td><td>Bitget Pairs</td><td><span class="status-online">ARBITRAGE</span></td><td class="status-active">+2.5%</td></tr>
            </table>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <div class="list-item">
                🕴️ <b>Lo Strozzino</b> (Funding Arb)<br>
                <span class="status-online">[ONLINE - BACKGROUND]</span> | APY Attuale: <span class="status-active">18.4%</span>
            </div>
            <div class="list-item">
                🧮 <b>Il Contabile</b> (DCA)<br>
                <span class="status-online">[ONLINE - BACKGROUND]</span> | Accumulo attivo: BTC/ETH
            </div>
            <div class="list-item">
                👼 <b>L'Angelo Custode</b> (MEV Arbitrum)<br>
                <span class="status-online">[ONLINE - BACKGROUND]</span> | Protezione Frontrun attiva
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2;">
            <h2>📊 METRICHE DI MERCATO (ORACLE & WHALE TRACKER)</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div class="metric-title">👁️ THE ORACLE (BINANCE SENTIMENT)</div>
                    <div class="metric-value">BULLISH [78%]</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">🐋 WHALE TRACKER (NETFLOW 1H)</div>
                    <div class="metric-value status-warning">-1,450 BTC</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">⚡ VOLATILITÀ SISTEMA</div>
                    <div class="metric-value critical">ELEVATA [CRITICAL]</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">🛡️ LIQUIDITÀ SCUDO</div>
                    <div class="metric-value status-online">1.2M USDT</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        [ SYSTEM.UPTIME: 99.99% ] | [ SECURE.CONNECTION: TRUE ] | [ ALL.SYSTEMS.NOMINAL ]
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
