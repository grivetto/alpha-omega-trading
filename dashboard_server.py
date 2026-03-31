from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA DASHBOARD</title>
    <style>
        :root {
            --bg-color: #050505;
            --neon-green: #00ff00;
            --neon-blue: #00ffff;
            --neon-purple: #ff00ff;
            --neon-red: #ff0033;
            --panel-bg: rgba(10, 20, 15, 0.8);
            --border-glow: 0 0 10px rgba(0, 255, 0, 0.5);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: 
                linear-gradient(rgba(0, 255, 0, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 255, 0, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            text-shadow: 0 0 5px var(--neon-green);
            margin-top: 0;
        }

        h1 {
            text-align: center;
            font-size: 2.5em;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 30px;
        }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-green);
            box-shadow: var(--border-glow);
            padding: 20px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            animation: scanline 3s linear infinite;
        }

        @keyframes scanline {
            0% { top: -5px; }
            100% { top: 100%; }
        }

        .status-indicator {
            display: inline-block;
            width: 10px; height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 8px var(--neon-green);
            margin-right: 10px;
            animation: blink 1.5s infinite alternate;
        }

        .status-red { background-color: var(--neon-red); box-shadow: 0 0 8px var(--neon-red); }
        .status-blue { background-color: var(--neon-blue); box-shadow: 0 0 8px var(--neon-blue); }
        .status-purple { background-color: var(--neon-purple); box-shadow: 0 0 8px var(--neon-purple); }

        @keyframes blink {
            from { opacity: 0.4; }
            to { opacity: 1; }
        }

        .team-item, .protocol-item {
            margin-bottom: 15px;
            padding: 10px;
            border: 1px dashed rgba(0,255,0,0.3);
            background: rgba(0,0,0,0.5);
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .metric-box {
            border: 1px solid var(--neon-blue);
            padding: 10px;
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 3px var(--neon-blue);
        }
        
        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            margin-top: 5px;
        }

        .log-terminal {
            font-size: 0.85em;
            height: 150px;
            overflow-y: hidden;
            border-top: 1px solid var(--neon-green);
            padding-top: 10px;
            margin-top: 15px;
            color: #88ff88;
        }

        .typing-effect {
            overflow: hidden;
            border-right: .15em solid var(--neon-green);
            white-space: nowrap;
            margin: 0;
            animation: typing 3s steps(40, end), blink-caret .75s step-end infinite;
        }

        @keyframes typing { from { width: 0 } to { width: 100% } }
        @keyframes blink-caret { from, to { border-color: transparent } 50% { border-color: var(--neon-green); } }

    </style>
</head>
<body>
    <h1><span class="status-indicator"></span> ORBITAL COMMAND <span style="font-size: 0.5em; color: #555;">v9.4.2</span></h1>
    
    <div class="container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel" style="border-color: var(--neon-blue); box-shadow: 0 0 10px rgba(0, 255, 255, 0.4);">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="team-item">
                <div style="display: flex; justify-content: space-between;">
                    <strong><span class="status-indicator status-blue"></span>SQUADRA_ALPHA</strong>
                    <span>[BINANCE]</span>
                </div>
                <div style="font-size: 0.8em; margin-top: 5px; color: #aaa;">Mode: Scalper | Latency: 12ms | PnL (24h): <span style="color:var(--neon-green)">+4.2%</span></div>
            </div>

            <div class="team-item">
                <div style="display: flex; justify-content: space-between;">
                    <strong><span class="status-indicator status-blue"></span>SQUADRA_DELTA</strong>
                    <span>[ORDER FLOW]</span>
                </div>
                <div style="font-size: 0.8em; margin-top: 5px; color: #aaa;">Mode: Imbalance Extractor | Blocks: 45/s | PnL (24h): <span style="color:var(--neon-green)">+1.8%</span></div>
            </div>

            <div class="team-item">
                <div style="display: flex; justify-content: space-between;">
                    <strong><span class="status-indicator status-purple"></span>SQUADRA_GAMMA</strong>
                    <span>[BITGET]</span>
                </div>
                <div style="font-size: 0.8em; margin-top: 5px; color: #aaa;">Mode: Pairs Trading | Spread: 0.15% | PnL (24h): <span style="color:var(--neon-green)">+2.1%</span></div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-purple); box-shadow: 0 0 10px rgba(255, 0, 255, 0.4);">
            <h2 style="color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple);">🛡️ PROTOCOLLO TRINITY</h2>
            
            <div style="text-align: center; margin-bottom: 15px; padding: 10px; border: 1px solid var(--neon-green); background-color: rgba(0, 255, 0, 0.1); color: var(--neon-green); font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>

            <div class="protocol-item">
                <strong><span class="status-indicator status-purple"></span>Lo Strozzino (Funding Arb)</strong>
                <p style="margin: 5px 0 0 0; font-size: 0.8em; color: #ccc;">Extracting yield across perp markets. Current APR: ~18.5%</p>
            </div>
            
            <div class="protocol-item">
                <strong><span class="status-indicator status-purple"></span>Il Contabile (DCA)</strong>
                <p style="margin: 5px 0 0 0; font-size: 0.8em; color: #ccc;">Strategic accumulation. Next execution in 04:12:00.</p>
            </div>
            
            <div class="protocol-item">
                <strong><span class="status-indicator status-purple"></span>L'Angelo Custode (MEV)</strong>
                <p style="margin: 5px 0 0 0; font-size: 0.8em; color: #ccc;">Arbitrum mempool watcher. Sandwich defense active.</p>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="border-color: var(--neon-red); box-shadow: 0 0 10px rgba(255, 0, 51, 0.4);">
            <h2 style="color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red);">📡 THE ORACLE / METRICS</h2>
            
            <div class="metric-grid">
                <div class="metric-box">
                    <div style="font-size: 0.7em;">BINANCE SENTIMENT</div>
                    <div class="metric-value" style="color: var(--neon-green);">BULLISH</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.7em;">WHALE TRACKER</div>
                    <div class="metric-value" style="color: var(--neon-red);">DISTRIB</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.7em;">VOLATILITY INDEX</div>
                    <div class="metric-value">64.2</div>
                </div>
                <div class="metric-box">
                    <div style="font-size: 0.7em;">GLOBAL LIQUIDITY</div>
                    <div class="metric-value">$42B</div>
                </div>
            </div>

            <div class="log-terminal" id="terminal">
                <div class="typing-effect">> Initializing Orbital Command...</div>
                <div>> Connecting to WebSocket feeds... OK</div>
                <div>> Syncing Squadra Alpha state... OK</div>
                <div style="color: var(--neon-red);">> WARNING: Minor latency spike on Bitget API</div>
                <div>> Funding arb opportunities detected: 3</div>
            </div>
        </div>
    </div>
    
    <script>
        const terminal = document.getElementById('terminal');
        const logs = [
            "> L'Angelo Custode intercepted pending tx 0x4f...",
            "> SQUADRA_DELTA executing block order...",
            "> The Oracle updated market state vector.",
            "> Rebalancing Lo Strozzino exposure...",
            "> Ping Arbitrum RPC: 18ms",
            "> System nominal."
        ];
        
        setInterval(() => {
            const newLog = document.createElement('div');
            newLog.innerText = logs[Math.floor(Math.random() * logs.length)];
            terminal.appendChild(newLog);
            if (terminal.childElementCount > 6) {
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
