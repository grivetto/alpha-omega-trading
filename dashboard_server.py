from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-align: center;
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header-glow {
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan), 0 0 15px var(--neon-cyan);
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2), inset 0 0 10px rgba(0, 255, 0, 0.1);
            padding: 15px;
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scanline 2s linear infinite;
        }
        @keyframes scanline {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .trinity { border-color: var(--neon-magenta); box-shadow: 0 0 10px rgba(255, 0, 255, 0.2); color: var(--neon-magenta); }
        .trinity h2 { text-shadow: 0 0 5px var(--neon-magenta); }
        
        .status-indicator {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: blink 1.5s infinite alternate;
        }
        @keyframes blink {
            0% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        .item-row { display: flex; justify-content: space-between; border-bottom: 1px dashed rgba(0,255,0,0.3); padding: 8px 0; }
        .trinity .item-row { border-bottom: 1px dashed rgba(255,0,255,0.3); }
        .data-value { font-weight: bold; }
        
        .glitch {
            animation: glitch 1s linear infinite;
        }
        @keyframes glitch {
            2%, 64% { transform: translate(2px,0) skew(0deg); }
            4%, 60% { transform: translate(-2px,0) skew(0deg); }
            62% { transform: translate(0,0) skew(5deg); }
        }
    </style>
</head>
<body>
    <h1 class="header-glow glitch">🛰️ ORBITAL COMMAND TERMINAL 🛰️</h1>
    <h3>SYS.VER: 9.4.2 // STATUS: <span style="color:var(--neon-green)">ONLINE</span></h3>
    <div style="text-align: center; margin-bottom: 20px;">
        <span style="color:var(--neon-magenta); border: 1px solid var(--neon-magenta); padding: 8px 15px; display: inline-block; box-shadow: 0 0 10px var(--neon-magenta); font-weight: bold; letter-spacing: 1px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="item-row">
                <span><div class="status-indicator"></div> 🐺 SQUADRA_ALPHA</span>
                <span class="data-value">BINANCE SCALPER [ACTIVE]</span>
            </div>
            <div class="item-row">
                <span><div class="status-indicator" style="animation-delay: 0.2s"></div> 🦅 SQUADRA_DELTA</span>
                <span class="data-value">ORDER FLOW [DEPLOYED]</span>
            </div>
            <div class="item-row">
                <span><div class="status-indicator" style="animation-delay: 0.4s"></div> 🐍 SQUADRA_GAMMA</span>
                <span class="data-value">BITGET PAIRS [HUNTING]</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="item-row">
                <span><div class="status-indicator" style="background:var(--neon-magenta); box-shadow: 0 0 8px var(--neon-magenta)"></div> 🕴️ Lo Strozzino</span>
                <span class="data-value">FUNDING ARB [SYNCED]</span>
            </div>
            <div class="item-row">
                <span><div class="status-indicator" style="background:var(--neon-magenta); box-shadow: 0 0 8px var(--neon-magenta); animation-delay: 0.3s"></div> 🧮 Il Contabile</span>
                <span class="data-value">DCA MATRIX [COMPUTING]</span>
            </div>
            <div class="item-row">
                <span><div class="status-indicator" style="background:var(--neon-magenta); box-shadow: 0 0 8px var(--neon-magenta); animation-delay: 0.6s"></div> 🛡️ L'Angelo Custode</span>
                <span class="data-value">ARBITRUM MEV [GUARDING]</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: 1 / -1; border-color: var(--neon-cyan);">
            <h2 style="color:var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan)">📊 METRICHE DI MERCATO GLOBALI</h2>
            <div style="display: flex; justify-content: space-around; text-align: center; margin-top: 20px;">
                <div>
                    <h4 style="color:var(--neon-cyan)">👁️ THE ORACLE (SENTIMENT)</h4>
                    <div class="data-value glitch" style="font-size: 2em; color:var(--neon-green)">EXTREME GREED</div>
                    <div>BINANCE AGGREGATED</div>
                </div>
                <div>
                    <h4 style="color:var(--neon-cyan)">🐋 WHALE TRACKER</h4>
                    <div class="data-value" style="font-size: 2em; color:var(--neon-magenta)">+42,069 BTC</div>
                    <div>LAST 24H INFLOW</div>
                </div>
                <div>
                    <h4 style="color:var(--neon-cyan)">⚡ SYSTEM LOAD</h4>
                    <div class="data-value" style="font-size: 2em; color:var(--neon-green)">12.4%</div>
                    <div>QUANT CORE CPU</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            const load = (Math.random() * 15 + 5).toFixed(1);
            document.querySelectorAll('.data-value')[8].innerText = load + '%';
        }, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
