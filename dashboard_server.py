from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ea;
            --neon-green: #39ff14;
            --dark-bg: #050510;
            --panel-bg: rgba(0, 20, 40, 0.6);
        }

        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
        }

        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: fixed;
            top: 0;
            left: 0;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,243,255,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.3;
            animation: scan 6s linear infinite;
        }

        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100vh; }
        }

        h1 {
            text-align: center;
            text-transform: uppercase;
            font-size: 2.5em;
            color: #fff;
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            letter-spacing: 5px;
            margin-bottom: 40px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            box-shadow: 0 10px 10px -10px rgba(0, 243, 255, 0.5);
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .card {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            padding: 25px;
            border-radius: 8px;
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.1), 0 0 20px rgba(0, 243, 255, 0.15);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 50%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent);
            transform: skewX(-20deg);
            animation: shine 8s infinite;
        }

        @keyframes shine {
            0% { left: -100%; }
            20% { left: 200%; }
            100% { left: 200%; }
        }

        .card:hover {
            transform: translateY(-5px);
            box-shadow: inset 0 0 20px rgba(0, 243, 255, 0.2), 0 0 30px rgba(0, 243, 255, 0.4);
            border-color: #fff;
        }

        .card h2 {
            border-bottom: 1px solid var(--neon-pink);
            padding-bottom: 10px;
            margin-top: 0;
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
            font-size: 1.5em;
            display: flex;
            align-items: center;
        }

        ul {
            list-style-type: none;
            padding: 0;
            margin: 0;
        }

        li {
            margin: 15px 0;
            font-size: 1.15em;
            display: flex;
            align-items: center;
            border-left: 2px solid transparent;
            padding-left: 10px;
            transition: border-color 0.2s;
        }

        li:hover {
            border-color: var(--neon-green);
            background: rgba(57, 255, 20, 0.05);
        }

        .emoji {
            font-size: 1.3em;
            margin-right: 15px;
            filter: drop-shadow(0 0 5px rgba(255,255,255,0.3));
        }

        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            margin-left: auto;
            animation: pulse 2s infinite;
        }

        .status-active {
            color: #ffb300;
            text-shadow: 0 0 5px #ffb300;
            margin-left: auto;
        }

        .status-alert {
            color: #ff003c;
            text-shadow: 0 0 8px #ff003c;
            margin-left: auto;
            animation: blink 1s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
        }

        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0; }
        }

        .metric-value {
            color: #fff;
            margin-left: 10px;
            font-weight: bold;
        }

        /* Glitch effect on header */
        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: '🛰️ NUVOLA ORBITAL COMMAND 🛰️';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--dark-bg);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -2px 0 red;
            clip: rect(24px, 550px, 90px, 0);
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -2px 0 blue;
            clip: rect(85px, 550px, 140px, 0);
            animation: glitch-anim 2.5s infinite linear alternate-reverse;
        }

        @keyframes glitch-anim {
            0% { clip: rect(10px, 9999px, 86px, 0); }
            5% { clip: rect(69px, 9999px, 11px, 0); }
            10% { clip: rect(32px, 9999px, 93px, 0); }
            15% { clip: rect(84px, 9999px, 47px, 0); }
            20% { clip: rect(12px, 9999px, 76px, 0); }
            25% { clip: rect(98px, 9999px, 23px, 0); }
            30% { clip: rect(45px, 9999px, 67px, 0); }
            100% { clip: rect(45px, 9999px, 67px, 0); }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    
    <h1 class="glitch">🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    
    <div style="text-align: center; margin-bottom: 30px; font-size: 1.2em; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="card">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span class="emoji">🐺</span> 
                    <strong>SQUADRA_ALPHA</strong> <span style="font-size:0.8em; color:#aaa; margin-left:5px;">(Scalper Binance)</span>
                    <span class="status-online">[ONLINE]</span>
                    <span class="metric-value">PnL: <span style="color: var(--neon-green)">+$412.80</span></span>
                </li>
                <li>
                    <span class="emoji">🌊</span> 
                    <strong>SQUADRA_DELTA</strong> <span style="font-size:0.8em; color:#aaa; margin-left:5px;">(Order Flow)</span>
                    <span class="status-online">[ONLINE]</span>
                    <span class="metric-value">Vol: 8.4M</span>
                </li>
                <li>
                    <span class="emoji">⚖️</span> 
                    <strong>SQUADRA_GAMMA</strong> <span style="font-size:0.8em; color:#aaa; margin-left:5px;">(Pairs Trading Bitget)</span>
                    <span class="status-active">[DEPLOYED]</span>
                    <span class="metric-value">Spread: 0.12%</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="card">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <span class="emoji">🦈</span> 
                    <strong>Lo Strozzino</strong> <span style="font-size:0.8em; color:#aaa; margin-left:5px;">(Funding Arb)</span>
                    <span class="status-online">[RUNNING]</span>
                    <span class="metric-value">APR: 21.4%</span>
                </li>
                <li>
                    <span class="emoji">🧮</span> 
                    <strong>Il Contabile</strong> <span style="font-size:0.8em; color:#aaa; margin-left:5px;">(DCA)</span>
                    <span class="status-online">[ACTIVE]</span>
                    <span class="metric-value">Next Buy: 2h 45m</span>
                </li>
                <li>
                    <span class="emoji">🛡️</span> 
                    <strong>L'Angelo Custode</strong> <span style="font-size:0.8em; color:#aaa; margin-left:5px;">(MEV Arbitrum)</span>
                    <span class="status-active">[HUNTING]</span>
                    <span class="metric-value">Mempool Scan: OK</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="card">
            <h2>📊 METRICHE DI MERCATO</h2>
            <ul>
                <li>
                    <span class="emoji">👁️‍🗨️</span> 
                    <strong>The Oracle</strong> <span style="font-size:0.8em; color:#aaa; margin-left:5px;">(Binance Sentiment)</span>
                    <span style="color: #ffb300; margin-left:auto; text-shadow: 0 0 5px #ffb300;">[BULLISH - 78%]</span>
                </li>
                <li>
                    <span class="emoji">🐋</span> 
                    <strong>Whale Tracker</strong>
                    <span class="status-alert">[ALERT]</span>
                    <span class="metric-value">12,000 ETH -> Kraken</span>
                </li>
                <li>
                    <span class="emoji">⚡</span> 
                    <strong>System Latency</strong>
                    <span style="margin-left:auto; color:var(--neon-blue);">[NOMINAL]</span>
                    <span class="metric-value">12ms (Frankfurt)</span>
                </li>
            </ul>
        </div>
    </div>
    
    <script>
        // Randomly update numbers to make the dashboard feel "alive"
        setInterval(() => {
            const spreadEl = document.querySelectorAll('.metric-value')[2];
            const newSpread = (0.10 + Math.random() * 0.05).toFixed(2);
            spreadEl.innerHTML = `Spread: ${newSpread}%`;
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
