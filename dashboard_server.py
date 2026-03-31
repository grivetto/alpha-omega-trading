from flask import Flask, render_template_string
import threading

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>ORBITAL COMMAND | Nuvola</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --neon-blue: #0ff;
            --bg-color: #050505;
            --panel-bg: #111;
            --text-main: #e0e0e0;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid #333;
            padding: 15px;
            border-radius: 5px;
            box-shadow: inset 0 0 10px #000;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: 0 0 10px rgba(0,255,255,0.1);
            pointer-events: none;
        }
        .panel h2 {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            border-bottom: 1px dashed var(--neon-green);
            padding-bottom: 5px;
            font-size: 1.2em;
            margin-top: 0;
        }
        .status-online { color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green); animation: blink 2s infinite; }
        .status-active { color: var(--neon-blue); font-weight: bold; text-shadow: 0 0 5px var(--neon-blue); }
        .status-warning { color: yellow; font-weight: bold; }
        
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        
        ul { list-style-type: none; padding: 0; }
        li { margin-bottom: 10px; padding: 10px; background: rgba(255,255,255,0.05); border-left: 3px solid var(--neon-blue); font-size: 0.95em; }
        
        .metrics-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9em; }
        .metrics-table th, .metrics-table td { border: 1px solid #444; padding: 8px; text-align: center; }
        .metrics-table th { color: var(--neon-blue); }
        .metrics-table td.up { color: var(--neon-green); }
        .metrics-table td.down { color: var(--neon-red); }
        
        .glow { box-shadow: 0 0 8px rgba(0, 255, 255, 0.4); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>SISTEMA OPERATIVO QUANTITATIVO NUVOLA - TERMINALE CENTRALE</p>
        <div style="margin-top: 15px; padding: 10px; border: 1px solid var(--neon-green); display: inline-block; background: rgba(57, 255, 20, 0.1); border-radius: 5px;">
            <span class="status-online" style="font-size: 1.2em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
        </div>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel glow">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> (Scalper - Binance)<br>
                    Stato: <span class="status-online">ENGAGED</span> 🟢<br>
                    Target: BTC/USDT | PnL Oggi: +124.50 USDT
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> (Order Flow)<br>
                    Stato: <span class="status-active">SCANNING</span> 🔵<br>
                    Imbalance Detect: Attivo | Spoofing Alert: Nessuno
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> (Pairs Trading - Bitget)<br>
                    Stato: <span class="status-online">ARBITRATING</span> 🟢<br>
                    Pair: ETH/BTC | Z-Score: 2.4 (Mean Reversion Iniziata)
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel glow">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> (Funding Arb)<br>
                    Stato: <span class="status-online">YIELDING IN BACKGROUND</span> 💸<br>
                    Spread: 0.04% / 8h | Posizione: Long Spot / Short Perp
                </li>
                <li>
                    <strong>Il Contabile</strong> (DCA)<br>
                    Stato: <span class="status-active">ACCUMULATING IN BACKGROUND</span> 📊<br>
                    Asset: BTC, SOL | Prossimo acquisto: 14:00 UTC
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> (MEV - Arbitrum)<br>
                    Stato: <span class="status-warning">MONITORING MEMPOOL IN BACKGROUND</span> 🦇<br>
                    Flashloans: Pronti | Sandwich Opp: 0
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel glow">
            <h2>📡 METRICHE DI MERCATO</h2>
            <p><strong>The Oracle</strong> (Binance Sentiment): <span class="status-online">BULLISH (68%)</span></p>
            <p><strong>Whale Tracker</strong>: Rilevato transito 12,000 BTC</p>
            
            <table class="metrics-table">
                <tr><th>Asset</th><th>Prezzo</th><th>1H %</th></tr>
                <tr><td>BTC/USDT</td><td class="up">72,450.00</td><td class="up">+1.2%</td></tr>
                <tr><td>ETH/USDT</td><td class="up">3,850.20</td><td class="up">+0.8%</td></tr>
                <tr><td>SOL/USDT</td><td class="down">145.30</td><td class="down">-0.4%</td></tr>
            </table>
        </div>
    </div>
    
    <script>
        // Simulazione animazioni dati
        setInterval(() => {
            const elements = document.querySelectorAll('.up, .down');
            elements.forEach(el => {
                if(Math.random() > 0.7 && el.innerText.includes('%')) {
                    let val = parseFloat(el.innerText.replace('%', ''));
                    val += (Math.random() * 0.2 - 0.1);
                    el.innerText = (val >= 0 ? '+' : '') + val.toFixed(2) + '%';
                    el.className = val >= 0 ? 'up' : 'down';
                }
            });
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
