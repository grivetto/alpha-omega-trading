from flask import Flask, render_template_string
import threading
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | Nuvola Dashboard</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-purple: #bc13fe;
            --neon-red: #ff003c;
            --bg-dark: #050505;
            --panel-bg: rgba(10, 20, 30, 0.8);
            --border-glow: 0 0 10px rgba(0, 255, 255, 0.5);
        }
        
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        body {
            background-color: var(--bg-dark);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 255, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 20px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
            animation: pulse-blue 2s infinite;
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: var(--border-glow);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            animation: scanline 3s linear infinite;
        }

        .squad-green { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .squad-purple { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); }
        .squad-red { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: blink 1s infinite alternate;
        }

        .data-row {
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            border-bottom: 1px dashed rgba(0, 255, 255, 0.3);
            padding-bottom: 5px;
        }

        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        @keyframes blink {
            from { opacity: 0.4; }
            to { opacity: 1; }
        }

        @keyframes pulse-blue {
            0%, 100% { text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue); }
            50% { text-shadow: 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue); }
        }
        
        .marquee {
            width: 100%;
            overflow: hidden;
            white-space: nowrap;
            box-sizing: border-box;
            border-top: 1px solid var(--neon-green);
            border-bottom: 1px solid var(--neon-green);
            color: var(--neon-green);
            padding: 5px 0;
            margin-top: 30px;
            text-shadow: 0 0 5px var(--neon-green);
        }
        
        .marquee span {
            display: inline-block;
            padding-left: 100%;
            animation: scroll-left 15s linear infinite;
        }

        @keyframes scroll-left {
            0% { transform: translate(0, 0); }
            100% { transform: translate(-100%, 0); }
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <h3>NUVOLA DASHBOARD // QUANTITATIVE CONTROL CENTER</h3>
        <p>SYSTEM STATUS: <span class="squad-green">ONLINE</span> | UPLINK: SECURE</p>
        <p><span class="squad-purple">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span></p>
    </div>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 class="squad-red">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="data-row">
                <span><span class="status-indicator"></span> SQUADRA_ALPHA</span>
                <span>(Scalper su Binance)</span>
            </div>
            <div class="data-row">
                <span>> APY Stima: <span class="squad-green">+42.5%</span></span>
                <span>Latenza: 12ms</span>
            </div>

            <div class="data-row" style="margin-top: 20px;">
                <span><span class="status-indicator"></span> SQUADRA_DELTA</span>
                <span>(Order Flow)</span>
            </div>
            <div class="data-row">
                <span>> Rateo di Fuoco: 350 ord/min</span>
                <span>Latenza: 18ms</span>
            </div>

            <div class="data-row" style="margin-top: 20px;">
                <span><span class="status-indicator"></span> SQUADRA_GAMMA</span>
                <span>(Pairs Trading Bitget)</span>
            </div>
            <div class="data-row">
                <span>> Spread Divergence: <span class="squad-purple">0.84%</span></span>
                <span>Latenza: 21ms</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="squad-purple">🔺 PROTOCOLLO TRINITY</h2>
            <p><i>Agenti Silenti Operativi in Background</i></p>

            <div class="data-row">
                <span><span class="status-indicator"></span> 🕵️ Lo Strozzino</span>
                <span>(Funding Arb)</span>
            </div>
            <div class="data-row">
                <span>> Tasso Medio: <span class="squad-green">0.03% / 8h</span></span>
                <span>Target: Bybit/Binance</span>
            </div>

            <div class="data-row" style="margin-top: 20px;">
                <span><span class="status-indicator"></span> 🧮 Il Contabile</span>
                <span>(DCA Dinamico)</span>
            </div>
            <div class="data-row">
                <span>> Accumulo: Attivo su BTC/ETH</span>
                <span>Fondi Allocati: 64%</span>
            </div>

            <div class="data-row" style="margin-top: 20px;">
                <span><span class="status-indicator"></span> 👼 L'Angelo Custode</span>
                <span>(MEV Arbitrum)</span>
            </div>
            <div class="data-row">
                <span>> TX Front-runnate: 14 (Oggi)</span>
                <span>Gas Salvato: 0.15 ETH</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2 class="squad-green">📊 METRICHE DI MERCATO</h2>
            
            <div class="data-row">
                <span>👁️ THE ORACLE (Binance Sentiment)</span>
                <span class="squad-green">BULLISH [78/100]</span>
            </div>
            <div class="data-row">
                <span>Long/Short Ratio:</span>
                <span>1.45 (Dominanza Long)</span>
            </div>
            <div class="data-row">
                <span>Open Interest (BTC):</span>
                <span>$18.4B [▲ IN AUMENTO]</span>
            </div>

            <div class="data-row" style="margin-top: 20px;">
                <span>🐳 WHALE TRACKER</span>
                <span class="squad-red">ALLERTA</span>
            </div>
            <div class="data-row">
                <span>Ultimo Movimento:</span>
                <span>4,500 BTC -> Coinbase</span>
            </div>
            <div class="data-row">
                <span>Liquidità in Bid:</span>
                <span>Sottile (-12% vol)</span>
            </div>
        </div>
        
    </div>

    <div class="marquee">
        <span>> LOG TRASMISSIONE: [SQUADRA_ALPHA] Eseguito scalp +0.12% su SOL/USDT | [L'Angelo Custode] Arbitraggio DEX completato su Uniswap V3 | [Lo Strozzino] Posizione Short aperta su XRP per funding rate anomalo | THE ORACLE: Rilevata anomalia volumetrica su altcoin mid-cap... </span>
    </div>

    <script>
        // Simulazione di dati in tempo reale
        setInterval(() => {
            const latencies = document.querySelectorAll('.data-row span:nth-child(2)');
            latencies.forEach(el => {
                if(el.innerText.includes('ms')) {
                    const base = parseInt(el.innerText);
                    const var_ = Math.floor(Math.random() * 5) - 2;
                    el.innerText = `Latenza: ${Math.max(5, base + var_)}ms`;
                }
            });
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Avvia Flask app su 0.0.0.0 porta 5000 (o 8080)
    app.run(host='0.0.0.0', port=5000)
