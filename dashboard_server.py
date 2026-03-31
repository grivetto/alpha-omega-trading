from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root { 
            --neon-green: #39ff14; 
            --neon-blue: #00ffff; 
            --neon-purple: #bc13fe; 
            --neon-red: #ff073a;
            --bg: #030303; 
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body { 
            background-color: var(--bg); 
            color: var(--neon-green); 
            font-family: 'Courier New', Courier, monospace; 
            margin: 0; 
            padding: 20px; 
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
        }
        h1, h2, h3 { 
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green); 
            text-transform: uppercase; 
            margin-top: 0;
        }
        .neon-blue { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue), 0 0 15px var(--neon-blue); }
        .neon-purple { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple), 0 0 15px var(--neon-purple); }
        .neon-red { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red), 0 0 15px var(--neon-red); }
        
        .container { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); 
            gap: 25px; 
            max-width: 1400px; 
            margin: 0 auto; 
        }
        .panel { 
            border: 1px solid var(--neon-green); 
            padding: 20px; 
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.1), 0 0 10px rgba(57, 255, 20, 0.2); 
            background: var(--panel-bg); 
            position: relative; 
            backdrop-filter: blur(5px);
        }
        .panel::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            border: 1px solid transparent;
            box-shadow: 0 0 8px inset var(--neon-green);
            pointer-events: none;
        }
        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 5px;
            background: rgba(57, 255, 20, 0.3);
            opacity: 0.6;
            animation: scan 4s linear infinite;
            pointer-events: none;
            z-index: 100;
        }
        @keyframes scan { 0% { top: -10px; } 100% { top: 100%; } }
        
        .glitch { animation: glitch 2.5s infinite; }
        @keyframes glitch { 
            0% { opacity: 1; text-shadow: 2px 0 var(--neon-red), -2px 0 var(--neon-blue); } 
            2% { opacity: 0.8; transform: translate(-2px, 2px); } 
            4% { opacity: 1; transform: translate(0); text-shadow: none; }
            100% { opacity: 1; }
        }
        
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.95em; }
        th, td { border-bottom: 1px solid rgba(57, 255, 20, 0.3); padding: 10px; text-align: left; }
        th { color: var(--neon-blue); text-shadow: none; font-weight: bold; }
        tr:hover { background: rgba(57, 255, 20, 0.1); }
        
        .status-online { color: var(--neon-green); animation: pulse 2s infinite; font-weight: bold; }
        .status-standby { color: #ffaa00; text-shadow: 0 0 5px #ffaa00; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        
        .header { text-align: center; margin-bottom: 40px; border-bottom: 2px solid var(--neon-purple); padding-bottom: 20px; }
        .header h1 { font-size: 3em; margin-bottom: 5px; }
        
        .log-box { 
            font-size: 0.85em; 
            height: 150px; 
            overflow: hidden; 
            color: #ccc; 
            background: #000; 
            padding: 10px; 
            border: 1px solid #333;
        }
        .log-entry { margin-bottom: 5px; }
        .log-time { color: var(--neon-blue); }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <div class="header">
        <h1 class="neon-purple">🛰️ ORBITAL COMMAND // NUVOLA</h1>
        <p class="glitch neon-green">SYSTEM ONLINE // TERMINAL SECURED // ALGO-TRADING MATRIX ACTIVE</p>
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 class="neon-blue">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr><th>Squadra</th><th>Target / Strategia</th><th>Status</th></tr>
                <tr>
                    <td>[🐺] SQUADRA_ALPHA</td>
                    <td>Binance / Scalper Quant</td>
                    <td class="status-online">🟢 ENGAGED</td>
                </tr>
                <tr>
                    <td>[🦅] SQUADRA_DELTA</td>
                    <td>Global / Order Flow Analysis</td>
                    <td class="status-online">🟢 ENGAGED</td>
                </tr>
                <tr>
                    <td>[🐍] SQUADRA_GAMMA</td>
                    <td>Bitget / Pairs Trading Arb</td>
                    <td class="status-online">🟢 ENGAGED</td>
                </tr>
            </table>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="neon-purple">🔺 PROTOCOLLO TRINITY</h2>
            <div style="margin-bottom: 15px; font-weight: bold; color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); border-bottom: 1px solid var(--neon-green); padding-bottom: 5px;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <table>
                <tr><th>Agente Autonomo</th><th>Specializzazione</th><th>Background Task</th></tr>
                <tr>
                    <td>🕴️ Lo Strozzino</td>
                    <td>Funding Rate Arbitrage</td>
                    <td class="status-online">⚡ ONLINE</td>
                </tr>
                <tr>
                    <td>🧮 Il Contabile</td>
                    <td>Smart DCA & Rebalancing</td>
                    <td class="status-online">⚡ ONLINE</td>
                </tr>
                <tr>
                    <td>🛡️ L'Angelo Custode</td>
                    <td>MEV Arbitrum Protection</td>
                    <td class="status-online">⚡ ONLINE</td>
                </tr>
            </table>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ THE ORACLE // MARKET METRICS</h2>
            <table>
                <tr><th>Sensore</th><th>Lettura Corrente</th><th>Direzione</th></tr>
                <tr>
                    <td>Binance Sentiment</td>
                    <td>72.4 [Greed]</td>
                    <td class="neon-green">▲ RIALZISTA</td>
                </tr>
                <tr>
                    <td>Whale Tracker</td>
                    <td>+3,150 BTC Net Inflow (24h)</td>
                    <td class="neon-purple">⚠️ ANOMALIA</td>
                </tr>
                <tr>
                    <td>Orderbook Imbalance</td>
                    <td>68% Bids (Top 10 CEX)</td>
                    <td class="neon-green">▲ PRESSIONE ACQUISTO</td>
                </tr>
                <tr>
                    <td>VIX-Crypto</td>
                    <td>Elevata (Eventi Macro)</td>
                    <td class="neon-red">⚡ VOLATILITÀ</td>
                </tr>
            </table>
        </div>
        
        <!-- SYSTEM LOGS -->
        <div class="panel">
            <h2 class="neon-blue">📝 SYSTEM LOGS & TELEMETRY</h2>
            <div class="log-box" id="logBox">
                <div class="log-entry"><span class="log-time">[07:28:45]</span> <span class="neon-green">[SYS]</span> Inizializzazione protocolli orbitali completata.</div>
                <div class="log-entry"><span class="log-time">[07:28:48]</span> <span class="neon-blue">[SQUADRA_ALPHA]</span> Scalper agent posizionato su BTC/USDT.</div>
                <div class="log-entry"><span class="log-time">[07:28:52]</span> <span class="neon-purple">[TRINITY]</span> Lo Strozzino rileva spread anomalo +0.025% su Bybit.</div>
                <div class="log-entry"><span class="log-time">[07:29:01]</span> <span class="neon-red">[ORACLE]</span> Rilevato spike di volumi su ETH/USDT. Monitoraggio in corso.</div>
                <div class="log-entry"><span class="log-time">[07:29:15]</span> <span class="neon-green">[SYS]</span> Latenza websocket: 14ms. All systems nominal.</div>
            </div>
        </div>
    </div>
    
    <script>
        // Effetto scorrimento log finto
        const logs = [
            "[SQUADRA_DELTA] Aggiornamento heatmap order flow completato.",
            "[TRINITY] Il Contabile ha eseguito check portafoglio DCA.",
            "[ORACLE] Nuovo tweet di rilevanza macroeconomica scansionato.",
            "[SQUADRA_GAMMA] Pair trading ZRO/USDT vs W/USDT spread: 1.2%.",
            "[SYS] Ottimizzazione memoria DB vettoriale in corso..."
        ];
        
        setInterval(() => {
            const logBox = document.getElementById('logBox');
            const now = new Date();
            const timeStr = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;
            const randomLog = logs[Math.floor(Math.random() * logs.length)];
            
            const newEntry = document.createElement('div');
            newEntry.className = 'log-entry';
            newEntry.innerHTML = `<span class="log-time">${timeStr}</span> ${randomLog}`;
            
            logBox.appendChild(newEntry);
            if (logBox.children.length > 8) {
                logBox.removeChild(logBox.firstChild);
            }
            logBox.scrollTop = logBox.scrollHeight;
        }, 8000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esegue sulla porta 5000 (o un'altra porta standard per le dashboard)
    app.run(host='0.0.0.0', port=5000, debug=False)
