from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND [NUVOLA]</title>
    <style>
        :root {
            --neon-blue: #0ff;
            --neon-red: #f00;
            --neon-green: #0f0;
            --neon-purple: #b0f;
            --dark-bg: #050505;
            --grid-color: rgba(0, 255, 255, 0.1);
        }
        
        body {
            background-color: var(--dark-bg);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2 {
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 5px;
        }
        
        h1 {
            text-align: center;
            font-size: 2.5em;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 10px;
            box-shadow: 0 10px 10px -10px var(--neon-blue);
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(0, 20, 20, 0.8);
            border: 1px solid var(--neon-blue);
            padding: 20px;
            border-radius: 5px;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.2), 0 0 15px rgba(0, 255, 255, 0.2);
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 50%;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-blue));
            animation: scanline 3s linear infinite;
        }

        @keyframes scanline {
            0% { left: -100%; }
            100% { left: 200%; }
        }

        .status {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 0.8em;
            text-transform: uppercase;
        }

        .status.online {
            color: var(--neon-green);
            border: 1px solid var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            box-shadow: 0 0 5px rgba(0, 255, 0, 0.3);
            animation: pulse-green 2s infinite;
        }
        
        .status.standby {
            color: var(--neon-purple);
            border: 1px solid var(--neon-purple);
            text-shadow: 0 0 5px var(--neon-purple);
            box-shadow: 0 0 5px rgba(187, 0, 255, 0.3);
        }

        @keyframes pulse-green {
            0% { box-shadow: 0 0 5px rgba(0, 255, 0, 0.3); }
            50% { box-shadow: 0 0 15px rgba(0, 255, 0, 0.6); }
            100% { box-shadow: 0 0 5px rgba(0, 255, 0, 0.3); }
        }

        ul {
            list-style-type: none;
            padding: 0;
        }

        li {
            margin-bottom: 15px;
            border-left: 2px solid rgba(0, 255, 255, 0.5);
            padding-left: 10px;
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .metric-box {
            background: rgba(0, 0, 0, 0.5);
            border: 1px dashed var(--neon-blue);
            padding: 10px;
            text-align: center;
        }

        .metric-value {
            font-size: 1.5em;
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
        }
        
        .metric-label {
            font-size: 0.7em;
            color: #aaa;
            text-transform: uppercase;
        }

        .blink {
            animation: blinker 1s linear infinite;
        }

        @keyframes blinker {
            50% { opacity: 0; }
        }

        .log-window {
            height: 150px;
            overflow-y: auto;
            background: rgba(0,0,0,0.8);
            border: 1px solid #333;
            padding: 10px;
            font-size: 0.8em;
            color: #888;
            margin-top: 20px;
            scrollbar-width: thin;
            scrollbar-color: var(--neon-blue) #111;
        }

        .log-window p {
            margin: 2px 0;
        }

        .log-window .timestamp {
            color: #555;
            margin-right: 10px;
        }
        
        .log-window .highlight {
            color: var(--neon-blue);
        }

        .sys-info {
            position: fixed;
            bottom: 10px;
            right: 10px;
            font-size: 0.7em;
            color: rgba(0, 255, 255, 0.5);
            pointer-events: none;
        }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND [NUVOLA] <span class="blink">_</span></h1>
    <div style="text-align: center; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); font-size: 1.2em; margin-bottom: 20px; font-weight: bold; border: 1px dashed var(--neon-green); padding: 10px; background: rgba(0, 255, 0, 0.1);">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <p style="font-size: 0.8em; color: #888; border-bottom: 1px solid #333; padding-bottom: 5px;">TACTICAL DEPLOYMENT STATUS</p>
            <ul>
                <li>
                    <strong>🐺 SQUADRA_ALPHA</strong> <span class="status online">ENGAGED</span>
                    <div style="font-size: 0.8em; color: #ccc; margin-top: 5px;">Role: Scalper [Binance]</div>
                    <div style="font-size: 0.8em; color: var(--neon-green);">Latency: 12ms | Hit Rate: 68%</div>
                </li>
                <li>
                    <strong>⚡ SQUADRA_DELTA</strong> <span class="status standby">STANDBY</span>
                    <div style="font-size: 0.8em; color: #ccc; margin-top: 5px;">Role: Order Flow Analysis</div>
                    <div style="font-size: 0.8em; color: var(--neon-purple);">Awaiting Liquidity Clusters</div>
                </li>
                <li>
                    <strong>⚖️ SQUADRA_GAMMA</strong> <span class="status online">ENGAGED</span>
                    <div style="font-size: 0.8em; color: #ccc; margin-top: 5px;">Role: Pairs Trading [Bitget]</div>
                    <div style="font-size: 0.8em; color: var(--neon-green);">Spread: 0.15% | Vol: $450K</div>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-purple); box-shadow: inset 0 0 15px rgba(187, 0, 255, 0.2), 0 0 15px rgba(187, 0, 255, 0.2);">
            <h2 style="color: var(--neon-purple); text-shadow: 0 0 10px var(--neon-purple);">🔺 PROTOCOLLO TRINITY</h2>
            <p style="font-size: 0.8em; color: #888; border-bottom: 1px solid #333; padding-bottom: 5px;">BACKGROUND OPS OVERSEERS</p>
            <ul>
                <li>
                    <strong>🕴️ Lo Strozzino</strong> <span class="status online" style="color: var(--neon-purple); border-color: var(--neon-purple); box-shadow: 0 0 5px rgba(187, 0, 255, 0.5); text-shadow: 0 0 5px var(--neon-purple);">ACTIVE</span>
                    <div style="font-size: 0.8em; color: #ccc; margin-top: 5px;">Funding Arb Collector</div>
                    <div style="font-size: 0.8em; color: #aaa;">Yielding: ~14% APY</div>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> <span class="status online" style="color: var(--neon-purple); border-color: var(--neon-purple); box-shadow: 0 0 5px rgba(187, 0, 255, 0.5); text-shadow: 0 0 5px var(--neon-purple);">ACTIVE</span>
                    <div style="font-size: 0.8em; color: #ccc; margin-top: 5px;">Strategic DCA Engine</div>
                    <div style="font-size: 0.8em; color: #aaa;">Accumulation: BTC, ETH, SOL</div>
                </li>
                <li>
                    <strong>🛡️ L'Angelo Custode</strong> <span class="status online" style="color: var(--neon-purple); border-color: var(--neon-purple); box-shadow: 0 0 5px rgba(187, 0, 255, 0.5); text-shadow: 0 0 5px var(--neon-purple);">ACTIVE</span>
                    <div style="font-size: 0.8em; color: #ccc; margin-top: 5px;">MEV Protection & Sniping [Arbitrum]</div>
                    <div style="font-size: 0.8em; color: #aaa;">Mempool Scanned: 1450 tx/s</div>
                </li>
            </ul>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <p style="font-size: 0.8em; color: #888; border-bottom: 1px solid #333; padding-bottom: 5px;">GLOBAL INTELLIGENCE NETWORK</p>
            
            <div class="metric-grid">
                <div class="metric-box">
                    <div class="metric-label">The Oracle (Binance Sentiment)</div>
                    <div class="metric-value">BULLISH 67%</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Whale Tracker (Inflows 24h)</div>
                    <div class="metric-value">+$1.4B</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Global Volatility Index</div>
                    <div class="metric-value" style="color: #ffaa00;">HIGH 42.1</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Liquidations (1H)</div>
                    <div class="metric-value" style="color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red);">$45.2M</div>
                </div>
            </div>

            <div class="log-window" id="terminal">
                <p><span class="timestamp">[SYS]</span> Initializing Orbital Command...</p>
                <p><span class="timestamp">[SYS]</span> Connecting to exchange APIs (Binance, Bitget, OKX)...</p>
                <p><span class="timestamp">[SYS]</span> Link established. Latency: 14ms.</p>
                <p><span class="timestamp">[OPS]</span> <span class="highlight">SQUADRA_ALPHA:</span> Executed BUY 1.5 BTC @ $64,210</p>
                <p><span class="timestamp">[TRN]</span> <span class="highlight">L'Angelo Custode:</span> Blocked front-running attempt on ARB.</p>
                <p><span class="timestamp">[INT]</span> <span class="highlight">The Oracle:</span> Detecting unusual options volume on ETH.</p>
            </div>
        </div>
    </div>

    <div class="sys-info">
        SYS_VER: 4.2.1-QUANT | KERNEL: NUVOLA-CUSTOM | ENCRYPTION: AES-256-GCM
    </div>

    <script>
        // Fake terminal log animation
        const logs = [
            "[OPS] SQUADRA_ALPHA: Taking profit at $64,280 (+0.11%)",
            "[TRN] Lo Strozzino: Collecting funding fees ($4.21)",
            "[INT] Whale Tracker: Large stablecoin mint detected (Tether 50M)",
            "[OPS] SQUADRA_GAMMA: Adjusting spread dynamically.",
            "[SYS] Re-calibrating risk parameters...",
            "[TRN] Il Contabile: Executing DCA tier 2 for BTC."
        ];
        
        const terminal = document.getElementById('terminal');
        
        function addLog() {
            const now = new Date();
            const timeStr = now.toTimeString().split(' ')[0] + '.' + now.getMilliseconds().toString().padStart(3, '0');
            const logEntry = logs[Math.floor(Math.random() * logs.length)];
            
            const p = document.createElement('p');
            p.innerHTML = `<span class="timestamp">[${timeStr}]</span> ${logEntry.replace(/(SQUADRA_[A-Z]+|Lo Strozzino|Il Contabile|L'Angelo Custode|The Oracle|Whale Tracker)/, '<span class="highlight">$1</span>')}`;
            
            terminal.appendChild(p);
            terminal.scrollTop = terminal.scrollHeight;
            
            setTimeout(addLog, Math.random() * 3000 + 1000);
        }
        
        setTimeout(addLog, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Esegue su 0.0.0.0 porta 5000 in locale per Nuvola
    app.run(host='0.0.0.0', port=5000, debug=False)
