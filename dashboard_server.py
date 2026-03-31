import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-red: #f00;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.8);
        }

        body {
            margin: 0;
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Share Tech Mono', monospace;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        /* CRT Effect */
        body::after {
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

        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px currentColor;
            margin-top: 0;
        }

        h1 {
            text-align: center;
            color: var(--neon-blue);
            font-size: 2.5em;
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            position: relative;
            z-index: 3;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.2) inset, 0 0 10px rgba(0, 255, 0, 0.3);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green));
            animation: scanline 3s linear infinite;
        }

        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }

        .panel.trinity {
            border-color: var(--neon-pink);
            color: var(--neon-pink);
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.2) inset, 0 0 10px rgba(255, 0, 255, 0.3);
        }

        .panel.market {
            border-color: var(--neon-blue);
            color: var(--neon-blue);
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2) inset, 0 0 10px rgba(0, 255, 255, 0.3);
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            margin-right: 10px;
            animation: blink 1.5s infinite alternate;
        }

        .status-indicator.offline {
            background-color: var(--neon-red);
            box-shadow: 0 0 10px var(--neon-red);
        }

        @keyframes blink {
            0% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .team-card, .proto-card, .metric-card {
            margin-bottom: 15px;
            padding: 10px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(0,0,0,0.5);
            transition: all 0.3s ease;
        }

        .team-card:hover, .proto-card:hover, .metric-card:hover {
            transform: scale(1.02);
            background: rgba(255,255,255,0.1);
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9em;
        }

        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            text-shadow: 0 0 5px currentColor;
        }
        
        .blink-text {
            animation: text-blink 2s infinite;
        }
        
        @keyframes text-blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0.5; }
        }

    </style>
</head>
<body>
    <h1><span class="status-indicator"></span>NUVOLA ORBITAL COMMAND 🛰️</h1>
    
    <div style="text-align: center; margin-bottom: 20px; padding: 10px; background: rgba(255, 0, 255, 0.1); border: 1px solid var(--neon-pink); color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); font-size: 1.2em; border-radius: 5px;">
        <span class="status-indicator" style="background:var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></span> ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="team-card">
                <h3>🐺 SQUADRA_ALPHA <span style="float:right; font-size: 0.6em" class="blink-text">[ ENGAGED ]</span></h3>
                <p>> Ruolo: Scalper su Binance</p>
                <p>> Latenza: 14ms</p>
                <p>> PnL (24h): <span style="color:var(--neon-green)">+1.24%</span></p>
            </div>
            
            <div class="team-card">
                <h3>🦅 SQUADRA_DELTA <span style="float:right; font-size: 0.6em" class="blink-text">[ ENGAGED ]</span></h3>
                <p>> Ruolo: Order Flow Analysis</p>
                <p>> Segnali attivi: 3 (Long: BTC, ETH | Short: SOL)</p>
                <p>> Win Rate: 68.5%</p>
            </div>
            
            <div class="team-card">
                <h3>🐍 SQUADRA_GAMMA <span style="float:right; font-size: 0.6em" class="blink-text">[ STANDBY ]</span></h3>
                <p>> Ruolo: Pairs Trading su Bitget</p>
                <p>> Spread target: >0.5%</p>
                <p>> Coppie monitorate: 14</p>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <p style="font-size: 0.8em; text-align: center; border-bottom: 1px dashed currentColor; padding-bottom: 10px;">> BACKGROUND PROCESSES ONLINE &lt;</p>
            
            <div class="proto-card">
                <h3>🕴️ Lo Strozzino</h3>
                <p>> Task: Funding Arbitrage</p>
                <p>> Status: <span class="status-indicator" style="background:var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></span> <span class="blink-text">ESTRANDO RENDIMENTO...</span></p>
                <p>> APR Corrente: 18.4%</p>
            </div>
            
            <div class="proto-card">
                <h3>🧮 Il Contabile</h3>
                <p>> Task: DCA Engine</p>
                <p>> Status: <span class="status-indicator" style="background:var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></span> ACCUMULO ATTIVO</p>
                <p>> Prossimo acquisto: 04:12:05</p>
            </div>
            
            <div class="proto-card">
                <h3>🛡️ L'Angelo Custode</h3>
                <p>> Task: MEV Arbitrum Protection</p>
                <p>> Status: <span class="status-indicator" style="background:var(--neon-pink); box-shadow: 0 0 10px var(--neon-pink);"></span> SCANSIONE MEMPOOL...</p>
                <p>> Tx salvate (30d): 14</p>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market">
            <h2>📡 METRICHE DI MERCATO</h2>
            
            <div class="metric-card">
                <h3>👁️ The Oracle (Binance Sentiment)</h3>
                <div class="metric-grid">
                    <div>
                        <p>Global Sentiment</p>
                        <p class="metric-value" style="color:var(--neon-green)">BULLISH</p>
                    </div>
                    <div>
                        <p>Fear & Greed</p>
                        <p class="metric-value">72</p>
                    </div>
                    <div>
                        <p>Long/Short Ratio</p>
                        <p class="metric-value">1.45</p>
                    </div>
                    <div>
                        <p>Volatility Idx</p>
                        <p class="metric-value" style="color:var(--neon-red)">ELEVATA</p>
                    </div>
                </div>
            </div>
            
            <div class="metric-card">
                <h3>🐋 Whale Tracker</h3>
                <p style="font-size: 0.8em; margin-bottom: 10px;">> ULTIMI MOVIMENTI RILEVATI</p>
                <div style="font-family: monospace; font-size: 0.85em;">
                    <p>[16:54:12] ALERT: 1,500 BTC -> Coinbase</p>
                    <p>[16:50:05] INFO: 12,000 ETH -> Unknown Wallet</p>
                    <p>[16:42:33] ALERT: 50M USDT -> Binance</p>
                    <p>[16:30:10] INFO: 400 BTC withdrawn da Bitfinex</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Aggiunge un po' di dinamicità alle metriche
        setInterval(() => {
            const ratios = [1.45, 1.46, 1.44, 1.47, 1.43];
            const r = ratios[Math.floor(Math.random() * ratios.length)];
            document.querySelectorAll('.metric-value')[2].innerText = r;
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_CONTENT)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=False)
