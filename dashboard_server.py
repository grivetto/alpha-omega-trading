from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola: Orbital Command</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-green: #39ff14;
            --neon-yellow: #fdf500;
            --neon-red: #ff003c;
            --dark-bg: #030305;
            --panel-bg: rgba(0, 20, 30, 0.6);
            --scanline: rgba(0, 243, 255, 0.1);
        }

        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--dark-bg);
            background-image: 
                linear-gradient(var(--scanline) 1px, transparent 1px),
                linear-gradient(90deg, var(--scanline) 1px, transparent 1px);
            background-size: 20px 20px;
            color: var(--neon-blue);
            font-family: 'Share Tech Mono', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            text-transform: uppercase;
            overflow-x: hidden;
        }

        body::after {
            content: " ";
            display: block;
            position: fixed;
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
            margin-top: 0;
            letter-spacing: 2px;
        }

        h1 {
            color: var(--neon-pink);
            text-shadow: 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink), 0 0 40px var(--neon-pink);
            font-size: 2.5em;
            text-align: center;
            border-bottom: 2px solid var(--neon-pink);
            padding-bottom: 10px;
            margin-bottom: 5px;
        }

        h2 {
            color: var(--neon-yellow);
            text-shadow: 0 0 5px var(--neon-yellow), 0 0 10px var(--neon-yellow);
            border-bottom: 1px dashed var(--neon-yellow);
            padding-bottom: 5px;
            font-size: 1.5em;
        }

        .subtitle {
            text-align: center;
            color: var(--neon-green);
            font-size: 1.2em;
            margin-bottom: 30px;
            text-shadow: 0 0 5px var(--neon-green);
            animation: blink 2s infinite;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            position: relative;
            z-index: 10;
        }

        .grid-main {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }

        @media (max-width: 1024px) {
            .grid-main {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 10px rgba(0, 243, 255, 0.2) inset, 0 0 15px rgba(0, 243, 255, 0.3);
            padding: 20px;
            border-radius: 4px;
            position: relative;
            backdrop-filter: blur(4px);
            margin-bottom: 20px;
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.4) inset, 0 0 25px rgba(0, 243, 255, 0.6);
            border-color: #fff;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            width: 20px;
            height: 20px;
            border-top: 2px solid var(--neon-blue);
            border-left: 2px solid var(--neon-blue);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: -2px;
            right: -2px;
            width: 20px;
            height: 20px;
            border-bottom: 2px solid var(--neon-blue);
            border-right: 2px solid var(--neon-blue);
        }

        .panel-trinity {
            border-color: var(--neon-pink);
            box-shadow: 0 0 10px rgba(255, 0, 255, 0.2) inset, 0 0 15px rgba(255, 0, 255, 0.3);
        }
        .panel-trinity:hover {
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.4) inset, 0 0 25px rgba(255, 0, 255, 0.6);
        }
        .panel-trinity::before, .panel-trinity::after { border-color: var(--neon-pink); }
        .panel-trinity h2 { color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink), 0 0 10px var(--neon-pink); border-color: var(--neon-pink); }

        .panel-metrics {
            border-color: var(--neon-green);
            box-shadow: 0 0 10px rgba(57, 255, 20, 0.2) inset, 0 0 15px rgba(57, 255, 20, 0.3);
        }
        .panel-metrics:hover {
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.4) inset, 0 0 25px rgba(57, 255, 20, 0.6);
        }
        .panel-metrics::before, .panel-metrics::after { border-color: var(--neon-green); }
        .panel-metrics h2 { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green); border-color: var(--neon-green); }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.9em;
        }

        th, td {
            border-bottom: 1px solid rgba(0, 243, 255, 0.3);
            padding: 12px;
            text-align: left;
        }

        th {
            color: var(--neon-yellow);
            font-weight: normal;
            background: rgba(253, 245, 0, 0.1);
        }

        tr:hover {
            background: rgba(0, 243, 255, 0.1);
        }

        .status-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 2px;
            font-size: 0.8em;
            font-weight: bold;
            text-shadow: none;
        }

        .bg-online { background: rgba(57, 255, 20, 0.2); color: var(--neon-green); border: 1px solid var(--neon-green); box-shadow: 0 0 8px var(--neon-green); }
        .bg-warning { background: rgba(253, 245, 0, 0.2); color: var(--neon-yellow); border: 1px solid var(--neon-yellow); box-shadow: 0 0 8px var(--neon-yellow); }
        .bg-danger { background: rgba(255, 0, 60, 0.2); color: var(--neon-red); border: 1px solid var(--neon-red); box-shadow: 0 0 8px var(--neon-red); }

        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px dashed rgba(57, 255, 20, 0.3);
        }

        .metric-value {
            font-size: 1.2em;
            font-weight: bold;
            color: #fff;
            text-shadow: 0 0 5px #fff;
        }

        .progress-container {
            width: 100%;
            height: 12px;
            background: rgba(0,0,0,0.5);
            border: 1px solid var(--neon-blue);
            margin-top: 5px;
            position: relative;
            overflow: hidden;
        }

        .progress-bar {
            height: 100%;
            background: var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue);
            position: relative;
        }
        
        .progress-bar::after {
            content: '';
            position: absolute;
            top: 0; left: 0; bottom: 0; right: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
            animation: slide 2s infinite;
        }

        .pulse { animation: pulse 2s infinite; }
        .blink { animation: blink 1s infinite; }
        .fast-blink { animation: blink 0.3s infinite; }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }

        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0; }
        }

        @keyframes slide {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .terminal-text {
            color: #aaa;
            font-size: 0.85em;
            margin-top: 15px;
            padding: 10px;
            background: rgba(0,0,0,0.8);
            border-left: 3px solid var(--neon-pink);
            height: 120px;
            overflow-y: hidden;
            position: relative;
        }
        
        .typewriter p {
            overflow: hidden;
            white-space: nowrap;
            margin: 0 0 5px 0;
            animation: typing 3s steps(40, end);
        }

        @keyframes typing {
            from { width: 0 }
            to { width: 100% }
        }
        
        .hud-overlay {
            position: fixed;
            top: 20px;
            right: 20px;
            font-size: 0.7em;
            color: rgba(255,255,255,0.5);
            text-align: right;
            z-index: 100;
        }
    </style>
</head>
<body>
    <div class="hud-overlay">
        SYS.REQ: OK<br>
        UPLINK: SECURE<br>
        LATENCY: 14ms<br>
        <span class="blink" style="color:var(--neon-red)">REC</span>
    </div>

    <div class="container">
        <h1>[ 🛰️ ORBITAL COMMAND ]</h1>
        <div class="subtitle">&gt;&gt; UPLINK ESTABLISHED :: NUVOLA CORE SYSTEM ONLINE &lt;&lt;</div>

        <div style="text-align: center; margin-bottom: 25px; font-size: 1.3em; color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink); border: 1px dashed var(--neon-pink); padding: 12px; background: rgba(255,0,255,0.05);" class="pulse">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>

        <div class="grid-main">
            <!-- Left Column: Assault Squads & Terminal -->
            <div class="col-left">
                <div class="panel">
                    <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>UNITÀ TATTICA</th>
                                <th>SPECIALIZZAZIONE</th>
                                <th>TARGET/VETTORE</th>
                                <th>STATO</th>
                                <th>ROE (24H)</th>
                                <th>PING</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><span style="color:var(--neon-blue)">[ALPHA]</span> 🦅</td>
                                <td>SCALPING ALTA FREQUENZA</td>
                                <td>BINANCE_FUTURES</td>
                                <td><span class="status-badge bg-online pulse">ENGAGED</span></td>
                                <td style="color: var(--neon-green)">+2.45%</td>
                                <td>12ms</td>
                            </tr>
                            <tr>
                                <td><span style="color:var(--neon-blue)">[DELTA]</span> 🦈</td>
                                <td>ORDER FLOW / IMBALANCE</td>
                                <td>DERIBIT+BINANCE</td>
                                <td><span class="status-badge bg-online pulse">ENGAGED</span></td>
                                <td style="color: var(--neon-green)">+1.12%</td>
                                <td>24ms</td>
                            </tr>
                            <tr>
                                <td><span style="color:var(--neon-blue)">[GAMMA]</span> ⚖️</td>
                                <td>PAIRS TRADING (STATARB)</td>
                                <td>BITGET</td>
                                <td><span class="status-badge bg-warning">STANDBY</span></td>
                                <td style="color: var(--neon-yellow)">+0.85%</td>
                                <td>45ms</td>
                            </tr>
                        </tbody>
                    </table>

                    <div style="margin-top: 25px;">
                        <span style="font-size:0.8em; color:var(--neon-blue)">ALLOCAZIONE MUNIZIONI (CAPITALE):</span>
                        <div class="progress-container">
                            <div class="progress-bar" style="width: 78%;"></div>
                        </div>
                        <div style="text-align:right; font-size:0.7em; margin-top:3px;">UTILIZZO: 78% | RISERVA: 22%</div>
                    </div>
                </div>

                <div class="panel panel-trinity">
                    <h2>🛡️ PROTOCOLLO TRINITY: PROCESSI DEMONIACI</h2>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 15px;">
                        
                        <div style="background: rgba(255,0,255,0.1); border: 1px solid var(--neon-pink); padding: 10px; border-radius: 3px; text-align: center;">
                            <div style="font-size: 2em; margin-bottom: 10px;">💸</div>
                            <div style="font-weight: bold; color: #fff; margin-bottom: 5px;">LO STROZZINO</div>
                            <div style="font-size: 0.7em; color: #aaa; margin-bottom: 10px;">[FUNDING ARB]</div>
                            <span class="status-badge bg-online">ACTIVE IN BG</span>
                        </div>

                        <div style="background: rgba(255,0,255,0.1); border: 1px solid var(--neon-pink); padding: 10px; border-radius: 3px; text-align: center;">
                            <div style="font-size: 2em; margin-bottom: 10px;">🧮</div>
                            <div style="font-weight: bold; color: #fff; margin-bottom: 5px;">IL CONTABILE</div>
                            <div style="font-size: 0.7em; color: #aaa; margin-bottom: 10px;">[SMART DCA]</div>
                            <span class="status-badge bg-online">ACTIVE IN BG</span>
                        </div>

                        <div style="background: rgba(255,0,255,0.1); border: 1px solid var(--neon-pink); padding: 10px; border-radius: 3px; text-align: center;">
                            <div style="font-size: 2em; margin-bottom: 10px;">👼</div>
                            <div style="font-weight: bold; color: #fff; margin-bottom: 5px;">L'ANGELO CUSTODE</div>
                            <div style="font-size: 0.7em; color: #aaa; margin-bottom: 10px;">[MEV ARBITRUM]</div>
                            <span class="status-badge bg-online">ACTIVE IN BG</span>
                        </div>
                    </div>
                    <div class="terminal-text typewriter" style="margin-top: 20px;">
                        <p>&gt; Initializing TRINITY background hooks...</p>
                        <p>&gt; Lo_Strozzino.exe: Monitoring perp-spot spread... OK.</p>
                        <p>&gt; Il_Contabile.exe: Accumulation threshold met. Executing TWAP... OK.</p>
                        <p>&gt; Angelo_Custode.exe: Mempool scanning active. Front-run protection ON.</p>
                        <p class="blink" style="color: var(--neon-pink);">&gt; _</p>
                    </div>
                </div>
            </div>

            <!-- Right Column: Metrics & Sensors -->
            <div class="col-right">
                <div class="panel panel-metrics">
                    <h2>📊 SENSORI & METRICHE</h2>
                    
                    <div class="metric-row">
                        <div>
                            <span style="font-size: 1.2em;">🔮</span> <strong>THE ORACLE</strong><br>
                            <span style="font-size: 0.7em; color: #aaa;">[BINANCE SENTIMENT]</span>
                        </div>
                        <div style="text-align: right;">
                            <span class="metric-value" style="color: var(--neon-green)">BULLISH</span><br>
                            <span style="font-size: 0.8em;">L/S RATIO: 1.45</span>
                        </div>
                    </div>

                    <div class="metric-row" style="background: rgba(255,0,60,0.1); border-color: var(--neon-red); padding: 10px; border-radius: 3px;">
                        <div>
                            <span style="font-size: 1.2em;">🐋</span> <strong>WHALE TRACKER</strong><br>
                            <span style="font-size: 0.7em; color: #aaa;">[ON-CHAIN FLOWS]</span>
                        </div>
                        <div style="text-align: right;">
                            <span class="status-badge bg-danger fast-blink">INFLOW ALERT</span><br>
                            <span style="font-size: 0.8em; color: var(--neon-red)">+5,000 BTC (COINBASE)</span>
                        </div>
                    </div>

                    <div class="metric-row">
                        <div>
                            <span style="font-size: 1.2em;">📡</span> <strong>VIX CRYPTO</strong><br>
                            <span style="font-size: 0.7em; color: #aaa;">[IMPLIED VOLATILITY]</span>
                        </div>
                        <div style="text-align: right;">
                            <span class="metric-value" style="color: var(--neon-yellow)">45.2</span><br>
                            <span style="font-size: 0.8em;">STATO: ELEVATA</span>
                        </div>
                    </div>

                    <div class="metric-row" style="border-bottom: none;">
                        <div>
                            <span style="font-size: 1.2em;">⛓️</span> <strong>GAS GWEI</strong><br>
                            <span style="font-size: 0.7em; color: #aaa;">[ETH MAINNET]</span>
                        </div>
                        <div style="text-align: right;">
                            <span class="metric-value">12.4</span><br>
                            <span style="font-size: 0.8em; color: var(--neon-green)">BASSO</span>
                        </div>
                    </div>

                    <div style="margin-top: 20px; border-top: 1px solid var(--neon-green); padding-top: 15px;">
                        <span style="font-size:0.8em; color:var(--neon-green)">CARICO CPU DEL SISTEMA:</span>
                        <div class="progress-container" style="border-color: var(--neon-green);">
                            <div class="progress-bar" style="width: 42%; background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green);"></div>
                        </div>
                        <div style="text-align:right; font-size:0.7em; margin-top:3px;">LOAD: 42% | TEMP: 65°C</div>
                    </div>
                </div>

                <div class="panel" style="text-align: center; border-color: #fff;">
                    <h3 style="color: #fff; text-shadow: 0 0 10px #fff; margin-bottom: 5px;">KILL SWITCH</h3>
                    <p style="font-size: 0.7em; color: #aaa; margin-top: 0; margin-bottom: 15px;">EMERGENCY LIQUIDATION PROTOCOL</p>
                    <button style="
                        background: rgba(255,0,60,0.2); 
                        border: 2px solid var(--neon-red); 
                        color: var(--neon-red); 
                        padding: 15px 30px; 
                        font-family: inherit; 
                        font-size: 1.2em; 
                        font-weight: bold; 
                        cursor: pointer; 
                        box-shadow: 0 0 15px var(--neon-red) inset;
                        border-radius: 5px;
                        transition: 0.2s;
                    " onmouseover="this.style.background='var(--neon-red)'; this.style.color='#fff';" onmouseout="this.style.background='rgba(255,0,60,0.2)'; this.style.color='var(--neon-red)';">
                        ☠️ ABORT ALL OPERATIONS
                    </button>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Disabling reloader if running in background
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)