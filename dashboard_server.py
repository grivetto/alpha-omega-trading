from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🛰️</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-green: #39ff14;
            --neon-red: #ff3333;
            --dark-bg: #050505;
            --panel-bg: #0a0a0a;
            --border-color: #1a1a1a;
        }

        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 50% 50%, rgba(0, 243, 255, 0.05) 0%, transparent 50%),
                linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 100% 100%, 20px 20px, 20px 20px;
        }

        h1 {
            text-align: center;
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink);
            text-transform: uppercase;
            letter-spacing: 5px;
            margin-bottom: 5px;
        }

        .subtitle {
            text-align: center;
            color: var(--neon-blue);
            margin-bottom: 30px;
            font-size: 1.2em;
            text-shadow: 0 0 5px var(--neon-blue);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(10, 10, 10, 0.8);
            border: 1px solid var(--neon-blue);
            border-radius: 5px;
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 10px rgba(0, 243, 255, 0.2);
            position: relative;
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            background: linear-gradient(90deg, transparent, var(--neon-blue), transparent);
            box-shadow: 0 0 10px var(--neon-blue);
        }

        .panel.pink-accent { border-color: var(--neon-pink); }
        .panel.pink-accent::before { background: linear-gradient(90deg, transparent, var(--neon-pink), transparent); box-shadow: 0 0 10px var(--neon-pink); }
        .panel.green-accent { border-color: var(--neon-green); }
        .panel.green-accent::before { background: linear-gradient(90deg, transparent, var(--neon-green), transparent); box-shadow: 0 0 10px var(--neon-green); }

        h2 {
            border-bottom: 1px dashed currentcolor;
            padding-bottom: 10px;
            font-size: 1.4em;
            text-transform: uppercase;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .panel.pink-accent h2 { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); }
        .panel.green-accent h2 { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        h2 { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }

        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); }
        .status-offline { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .status-standby { color: #fdfd96; text-shadow: 0 0 5px #fdfd96; }

        .glitch {
            position: relative;
            animation: glitch 2s infinite;
        }

        @keyframes glitch {
            0% { transform: translate(0) }
            2% { transform: translate(-2px, 2px) }
            4% { transform: translate(-2px, -2px) }
            6% { transform: translate(2px, 2px) }
            8% { transform: translate(2px, -2px) }
            10% { transform: translate(0) }
            100% { transform: translate(0) }
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: rgba(0,0,0,0.5);
        }

        th, td {
            border: 1px solid rgba(0, 243, 255, 0.2);
            padding: 10px;
            text-align: left;
        }

        th { 
            color: var(--neon-pink); 
            background: rgba(255, 0, 255, 0.05);
            text-shadow: 0 0 2px var(--neon-pink);
        }

        ul { list-style-type: none; padding-left: 0; margin-top: 15px; }
        li { padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }

        .scanline {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(to bottom, transparent 50%, rgba(0,0,0,0.25) 51%);
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 9999;
        }
        
        .value-box {
            font-size: 1.5em;
            text-align: right;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1 class="glitch">ORBITAL COMMAND</h1>
    <div class="subtitle blink">/// SECURE UPLINK ESTABLISHED ///</div>
    <div style="text-align: center; color: var(--neon-green); margin-bottom: 20px; font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr><th>Unità Tattica</th><th>Zona Operativa</th><th>Stato</th></tr>
                <tr><td>🐺 SQUADRA_ALPHA</td><td>Binance (Scalper)</td><td class="status-online">ENGAGED [L/S]</td></tr>
                <tr><td>🦅 SQUADRA_DELTA</td><td>Order Flow</td><td class="status-online">MONITORING</td></tr>
                <tr><td>🐍 SQUADRA_GAMMA</td><td>Bitget (Pairs)</td><td class="status-standby">STANDBY</td></tr>
            </table>
            <div style="margin-top: 15px; font-size: 0.9em; color: #888;">> EXECUTION LATENCY: 14ms (OPTIMAL)</div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel pink-accent">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li><span class="status-online">●</span> <strong>Lo Strozzino</strong> <br><span style="color: #aaa; font-size: 0.9em;">(Funding Rate Arb)</span> <span style="float:right;" class="status-online">GHOST MODE</span></li>
                <li><span class="status-online">●</span> <strong>Il Contabile</strong> <br><span style="color: #aaa; font-size: 0.9em;">(Smart DCA)</span> <span style="float:right;" class="status-online">GHOST MODE</span></li>
                <li><span class="status-online">●</span> <strong>L'Angelo Custode</strong> <br><span style="color: #aaa; font-size: 0.9em;">(MEV Arbitrum Sniper)</span> <span style="float:right;" class="status-online">GHOST MODE</span></li>
            </ul>
            <p style="font-size: 0.8em; color: var(--neon-pink); border-top: 1px solid var(--border-color); padding-top: 10px; margin-top: 15px;">> ALL BACKGROUND PROTOCOLS ONLINE AND HIDDEN</p>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel green-accent">
            <h2>📊 METRICHE DI MERCATO</h2>
            <div style="margin-bottom: 15px; background: rgba(0,0,0,0.5); padding: 10px; border: 1px solid rgba(57, 255, 20, 0.2);">
                <p style="margin: 0 0 5px 0;">👁️ <strong>The Oracle (Binance Sentiment):</strong></p>
                <div class="value-box status-online" style="text-shadow: 0 0 10px var(--neon-green);">EXTREME GREED (82)</div>
            </div>
            
            <div style="margin-bottom: 15px; background: rgba(0,0,0,0.5); padding: 10px; border: 1px solid rgba(255, 51, 51, 0.2);">
                <p style="margin: 0 0 5px 0;">🐋 <strong>Whale Tracker (On-Chain):</strong></p>
                <div class="value-box blink status-offline" style="font-size: 1.1em; text-align: left;">ALERT: +15,000 BTC INFLOW (CEX)</div>
            </div>

            <table>
                <tr><th>Asset</th><th>Px (USD)</th><th>24h Δ</th></tr>
                <tr><td>BTC</td><td>$98,421.50</td><td class="status-online">+3.2%</td></tr>
                <tr><td>ETH</td><td>$4,015.30</td><td class="status-online">+1.9%</td></tr>
                <tr><td>SOL</td><td>$201.85</td><td class="status-offline">-0.4%</td></tr>
            </table>
        </div>
    </div>
    
    <script>
        // Simulate real-time metric updates
        setInterval(function() {
            let latency = Math.floor(Math.random() * 5) + 12;
            document.querySelector('.panel:nth-child(1) div').innerText = `> EXECUTION LATENCY: ${latency}ms (OPTIMAL)`;
        }, 3000);
        
        // Auto-refresh logic
        setTimeout(function(){
            window.location.reload(1);
        }, 60000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Orbital Command runs on 0.0.0.0:8000 by default in Nuvola setups
    app.run(host='0.0.0.0', port=8000)
