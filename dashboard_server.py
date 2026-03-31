from flask import Flask, render_template_string
import os

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
            --bg-color: #050510;
            --neon-blue: #00f3ff;
            --neon-pink: #ff00c8;
            --neon-green: #39ff14;
            --neon-red: #ff073a;
            --panel-bg: rgba(10, 15, 30, 0.85);
            --border-color: rgba(0, 243, 255, 0.3);
            --font-main: 'Courier New', Courier, monospace;
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { text-shadow: 0 0 5px var(--neon-blue); }
            50% { text-shadow: 0 0 20px var(--neon-blue), 0 0 30px #fff; }
            100% { text-shadow: 0 0 5px var(--neon-blue); }
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.1);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scanline 3s linear infinite;
        }

        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 100%; }
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            margin-right: 10px;
            animation: blink 1s infinite alternate;
        }

        .status-offline {
            background-color: var(--neon-red);
            box-shadow: 0 0 10px var(--neon-red);
            animation: none;
        }

        @keyframes blink {
            from { opacity: 0.5; }
            to { opacity: 1; }
        }

        .team {
            margin-bottom: 15px;
            padding: 10px;
            border-left: 3px solid var(--neon-pink);
            background: rgba(255, 0, 200, 0.05);
        }

        .team-title {
            color: var(--neon-pink);
            font-weight: bold;
        }

        .protocol {
            margin-bottom: 15px;
            padding: 10px;
            border-left: 3px solid var(--neon-green);
            background: rgba(57, 255, 20, 0.05);
        }

        .protocol-title {
            color: var(--neon-green);
            font-weight: bold;
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .metric-box {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 10px;
            text-align: center;
        }

        .metric-value {
            font-size: 1.5em;
            color: var(--neon-blue);
            margin-top: 5px;
            text-shadow: 0 0 5px var(--neon-blue);
        }

        .log-terminal {
            background: #000;
            border: 1px solid var(--neon-blue);
            padding: 10px;
            height: 150px;
            overflow-y: hidden;
            font-size: 0.9em;
            color: #00ff00;
            margin-top: 20px;
        }

        .log-line { margin: 5px 0; }
        .glitch { animation: glitch 1s linear infinite; }

        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="glitch">🌐 ORBITAL COMMAND 🌐</h1>
        <h3>Sistema Tattico Quantitativo Nuvola // STATUS: <span style="color:var(--neon-green)">ONLINE</span></h3>
        <div style="margin-top: 10px; font-weight: bold; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); font-size: 1.2em;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="team">
                <div class="team-title"><span class="status-indicator"></span>SQUADRA_ALPHA (Scalper)</div>
                <div>Target: Binance [BTC/USDT, ETH/USDT]</div>
                <div>Status: High Frequency Mode. PnL (24h): +4.2%</div>
            </div>
            <div class="team">
                <div class="team-title"><span class="status-indicator"></span>SQUADRA_DELTA (Order Flow)</div>
                <div>Target: Cross-Exchange Futures</div>
                <div>Status: Absorbing Liquidity. PnL (24h): +1.8%</div>
            </div>
            <div class="team">
                <div class="team-title"><span class="status-indicator"></span>SQUADRA_GAMMA (Pairs Trading)</div>
                <div>Target: Bitget</div>
                <div>Status: Statistical Arbitrage Active. PnL (24h): +2.5%</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="protocol">
                <div class="protocol-title"><span class="status-indicator"></span>Lo Strozzino</div>
                <div>Ruolo: Funding Rate Arbitrage</div>
                <div>Operatività: Background Delta-Neutral (Yield: 18% APY)</div>
            </div>
            <div class="protocol">
                <div class="protocol-title"><span class="status-indicator"></span>Il Contabile</div>
                <div>Ruolo: Accumulo Dinamico DCA</div>
                <div>Operatività: Buy The Dip su Drawdown &gt; 5%</div>
            </div>
            <div class="protocol">
                <div class="protocol-title"><span class="status-indicator"></span>L'Angelo Custode</div>
                <div>Ruolo: MEV &amp; Sandwich Protection</div>
                <div>Operatività: Arbitrum Network Monitoring</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div>The Oracle (Binance Sentiment)</div>
                    <div class="metric-value">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div>Whale Tracker (Inflow/Outflow)</div>
                    <div class="metric-value" style="color:var(--neon-green)">+ $42.5M</div>
                </div>
                <div class="metric-box">
                    <div>Global VIX (Crypto)</div>
                    <div class="metric-value" style="color:var(--neon-red)">45.2</div>
                </div>
                <div class="metric-box">
                    <div>Liquidity Heatmap</div>
                    <div class="metric-value">DENSE</div>
                </div>
            </div>
            <div class="log-terminal">
                <div class="log-line">&gt; INIZIALIZZAZIONE SISTEMA... OK</div>
                <div class="log-line">&gt; CONNESSIONE WEBSOCKET BINANCE... STABILITA</div>
                <div class="log-line">&gt; SINC. NODI ARBITRUM... COMPLETATA</div>
                <div class="log-line">&gt; ANALISI SENTIMENT THE ORACLE... IN CORSO</div>
                <div class="log-line">&gt; ATTESA NUOVI BLOCCHI...</div>
            </div>
        </div>
    </div>

    <script>
        // Simulazione log terminale
        const terminal = document.querySelector('.log-terminal');
        const logs = [
            "&gt; ESECUZIONE ARBITRAGGIO SQUADRA_GAMMA...",
            "&gt; PROFITTO REGISTRATO: +$12.45",
            "&gt; AGGIORNAMENTO FUNDING RATE BITGET...",
            "&gt; LO STROZZINO: RIBILANCIAMENTO POSIZIONE",
            "&gt; WHALE ALERT: 500 BTC SPOSTATI SU BINANCE",
            "&gt; PREPARAZIONE SCUDO MEV ANGELO CUSTODE..."
        ];
        
        setInterval(() => {
            const line = document.createElement('div');
            line.className = 'log-line';
            line.textContent = logs[Math.floor(Math.random() * logs.length)];
            terminal.appendChild(line);
            if(terminal.children.length > 6) {
                terminal.removeChild(terminal.firstChild);
            }
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
