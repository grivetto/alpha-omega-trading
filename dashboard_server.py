from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        :root {
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --neon-green: #39ff14;
            --neon-red: #ff3131;
            --neon-yellow: #fffb00;
            --bg-color: #030303;
            --panel-bg: rgba(5, 5, 10, 0.9);
            --font-main: 'Share Tech Mono', monospace;
            --grid-color: rgba(0, 255, 255, 0.05);
        }

        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-blue);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 40px 40px;
            background-position: center center;
            overflow-x: hidden;
        }

        /* Scanline effect */
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

        h1, h2, h3, h4 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }

        .header-container {
            text-align: center;
            margin-bottom: 30px;
            position: relative;
            z-index: 10;
        }

        h1 {
            color: var(--neon-pink);
            font-size: 3em;
            text-shadow: 0 0 5px var(--neon-pink), 0 0 10px var(--neon-pink), 0 0 20px var(--neon-pink), 0 0 40px var(--neon-pink);
            margin-bottom: 5px;
            animation: glitch 3s infinite;
        }

        .header-sub {
            color: var(--neon-yellow);
            font-size: 1.2em;
            text-shadow: 0 0 5px var(--neon-yellow);
            animation: blinker 1.5s linear infinite;
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 20px;
            position: relative;
            z-index: 10;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2), inset 0 0 20px rgba(0, 255, 255, 0.05);
            padding: 20px;
            border-radius: 2px;
            position: relative;
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            border: 2px solid transparent;
            z-index: -1;
            animation: border-glow 4s linear infinite;
        }

        .panel-hft { grid-column: span 6; border-color: var(--neon-red); }
        .panel-hft h2 { color: var(--neon-red); text-shadow: 0 0 10px var(--neon-red); border-bottom: 1px solid var(--neon-red); padding-bottom: 10px; }
        
        .panel-trinity { grid-column: span 6; border-color: var(--neon-blue); }
        .panel-trinity h2 { color: var(--neon-blue); text-shadow: 0 0 10px var(--neon-blue); border-bottom: 1px solid var(--neon-blue); padding-bottom: 10px; }
        
        .panel-market { grid-column: span 12; border-color: var(--neon-green); }
        .panel-market h2 { color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); border-bottom: 1px solid var(--neon-green); padding-bottom: 10px; }

        .unit {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 15px;
            margin-bottom: 15px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s;
        }

        .unit:hover {
            background: rgba(255, 255, 255, 0.08);
            transform: scale(1.01);
        }

        .unit-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 1.2em;
            font-weight: bold;
        }

        .status-badge {
            padding: 3px 8px;
            border-radius: 2px;
            font-size: 0.8em;
            text-shadow: none;
            color: #000;
            animation: pulse 2s infinite;
        }

        .status-active { background-color: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }
        .status-standby { background-color: var(--neon-yellow); box-shadow: 0 0 10px var(--neon-yellow); }
        .status-deploying { background-color: var(--neon-blue); box-shadow: 0 0 10px var(--neon-blue); }
        
        .unit-details {
            font-size: 0.9em;
            color: #ccc;
            display: flex;
            justify-content: space-between;
            border-top: 1px dashed rgba(255, 255, 255, 0.2);
            padding-top: 10px;
        }

        .log-window {
            background: #000;
            border: 1px solid #333;
            color: var(--neon-blue);
            padding: 10px;
            font-size: 0.85em;
            height: 120px;
            overflow-y: hidden;
            position: relative;
        }

        .log-window::after {
            content: '';
            position: absolute;
            bottom: 0; left: 0; right: 0; height: 30px;
            background: linear-gradient(transparent, #000);
        }

        .log-line { margin-bottom: 5px; opacity: 0; animation: typeWriter 0.1s forwards; }
        .log-line:nth-child(1) { animation-delay: 0.5s; }
        .log-line:nth-child(2) { animation-delay: 1.2s; }
        .log-line:nth-child(3) { animation-delay: 2.1s; }
        .log-line:nth-child(4) { animation-delay: 3.3s; }
        .log-line:nth-child(5) { animation-delay: 4.0s; }
        .log-line:nth-child(6) { animation-delay: 4.8s; }

        .metric-cards {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }

        .card {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid var(--neon-green);
            padding: 15px;
            text-align: center;
        }

        .card-value {
            font-size: 2em;
            font-weight: bold;
            color: var(--neon-green);
            text-shadow: 0 0 10px var(--neon-green);
            margin: 10px 0;
        }

        .alert-text { color: var(--neon-red); }
        .info-text { color: var(--neon-blue); }
        .warn-text { color: var(--neon-yellow); }

        @keyframes glitch {
            0% { transform: translate(0) }
            20% { transform: translate(-2px, 2px) }
            40% { transform: translate(-2px, -2px) }
            60% { transform: translate(2px, 2px) }
            80% { transform: translate(2px, -2px) }
            100% { transform: translate(0) }
        }

        @keyframes blinker {
            50% { opacity: 0.5; }
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(57, 255, 20, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(57, 255, 20, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(57, 255, 20, 0); }
        }

        @keyframes typeWriter {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }

        /* Responsive */
        @media (max-width: 1200px) {
            .panel-hft, .panel-trinity { grid-column: span 12; }
            .metric-cards { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="header-container">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <div class="header-sub">>>> SECURE UPLINK ESTABLISHED // NUVOLA MAINFRAME ONLINE <<<</div>
        <div style="margin-top: 20px; padding: 10px 20px; border: 1px solid var(--neon-green); background: rgba(57, 255, 20, 0.1); color: var(--neon-green); font-size: 1.2em; text-shadow: 0 0 5px var(--neon-green); display: inline-block; font-weight: bold; animation: pulse 2s infinite;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="grid-container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel panel-hft">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="unit" style="border-left: 3px solid var(--neon-red);">
                <div class="unit-header">
                    <span style="color: var(--neon-red);">SQUADRA_ALPHA 🐺</span>
                    <span class="status-badge status-active">ENGAGED</span>
                </div>
                <div class="unit-details">
                    <span>Target: Binance [Scalper]</span>
                    <span>Win Rate: <b style="color:var(--neon-green)">68.4%</b></span>
                    <span>Ping: 12ms</span>
                </div>
            </div>

            <div class="unit" style="border-left: 3px solid var(--neon-red);">
                <div class="unit-header">
                    <span style="color: var(--neon-red);">SQUADRA_DELTA 🦅</span>
                    <span class="status-badge status-active">ENGAGED</span>
                </div>
                <div class="unit-details">
                    <span>Target: Order Flow [Aggregator]</span>
                    <span>Volume: <b style="color:var(--neon-blue)">1.2M USDT/h</b></span>
                    <span>Ping: 8ms</span>
                </div>
            </div>

            <div class="unit" style="border-left: 3px solid var(--neon-yellow);">
                <div class="unit-header">
                    <span style="color: var(--neon-yellow);">SQUADRA_GAMMA 🐍</span>
                    <span class="status-badge status-standby">STANDBY</span>
                </div>
                <div class="unit-details">
                    <span>Target: Bitget [Pairs Trading]</span>
                    <span>Status: Awaiting Spread > 0.5%</span>
                    <span>Ping: 15ms</span>
                </div>
            </div>

            <div class="log-window">
                <div class="log-line">> [ALPHA] Executing limit orders on BTC/USDT...</div>
                <div class="log-line">> [ALPHA] Fill confirmed. PNL +$142.50.</div>
                <div class="log-line">> [DELTA] Detecting heavy spoofing on ETH orderbook.</div>
                <div class="log-line">> [DELTA] Recalibrating resistance thresholds...</div>
                <div class="log-line">> [GAMMA] Monitoring SOL/BNB correlation matrix.</div>
                <div class="log-line">> [SYS] HFT modules operating at peak efficiency.</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-trinity">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            
            <div class="unit" style="border-left: 3px solid var(--neon-blue);">
                <div class="unit-header">
                    <span style="color: var(--neon-blue);">LO STROZZINO 🕴️</span>
                    <span class="status-badge status-deploying" style="background:var(--neon-blue);">BACKGROUND</span>
                </div>
                <div class="unit-details">
                    <span>Role: Funding Arb [Perpetuals]</span>
                    <span>Target APR: <b style="color:var(--neon-green)">18.4%</b></span>
                    <span>Capital: Deployed</span>
                </div>
            </div>

            <div class="unit" style="border-left: 3px solid var(--neon-blue);">
                <div class="unit-header">
                    <span style="color: var(--neon-blue);">IL CONTABILE 🧮</span>
                    <span class="status-badge status-deploying" style="background:var(--neon-blue);">BACKGROUND</span>
                </div>
                <div class="unit-details">
                    <span>Role: DCA Engine [Spot]</span>
                    <span>Next execution: <b>04h 12m 45s</b></span>
                    <span>Asset: BTC/ETH</span>
                </div>
            </div>

            <div class="unit" style="border-left: 3px solid var(--neon-blue);">
                <div class="unit-header">
                    <span style="color: var(--neon-blue);">L'ANGELO CUSTODE 🛡️</span>
                    <span class="status-badge status-active">GUARDING</span>
                </div>
                <div class="unit-details">
                    <span>Role: MEV Protection [Arbitrum]</span>
                    <span>Status: Tx Pool Scanning</span>
                    <span>Saved Gas: 0.15 ETH</span>
                </div>
            </div>

            <div class="log-window" style="border-color: var(--neon-blue); color: var(--neon-blue);">
                <div class="log-line">> [TRINITY] Initialization sequence complete.</div>
                <div class="log-line">> [STROZZINO] Hedging short positions on Bybit.</div>
                <div class="log-line">> [CONTABILE] Ledger synchronized. Funds secured.</div>
                <div class="log-line">> [ANGELO] Block #19842211 scanned. No sandwich attacks detected.</div>
                <div class="log-line">> [TRINITY] All background protocols functioning normally.</div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-market">
            <h2>📊 METRICHE DI MERCATO</h2>
            
            <div class="metric-cards">
                <div class="card">
                    <div style="font-size: 0.9em; color: #888;">FEAR & GREED INDEX</div>
                    <div class="card-value">72</div>
                    <div style="color: var(--neon-green);">GREED</div>
                </div>
                <div class="card">
                    <div style="font-size: 0.9em; color: #888;">ORDERBOOK IMBALANCE</div>
                    <div class="card-value">+14%</div>
                    <div style="color: var(--neon-green);">BID HEAVY</div>
                </div>
                <div class="card">
                    <div style="font-size: 0.9em; color: #888;">AI PREDICTION (1H)</div>
                    <div class="card-value" style="font-size: 1.5em; margin-top: 15px;">BULLISH</div>
                    <div style="color: var(--neon-blue);">Confidence: 82%</div>
                </div>
                <div class="card">
                    <div style="font-size: 0.9em; color: #888;">MARKET VOLATILITY</div>
                    <div class="card-value" style="font-size: 1.5em; margin-top: 15px; color: var(--neon-yellow); text-shadow: 0 0 10px var(--neon-yellow);">MODERATE</div>
                    <div style="color: var(--neon-yellow);">VIX: 18.5</div>
                </div>
            </div>

            <div style="display: flex; gap: 20px;">
                <div style="flex: 1; border: 1px solid #333; padding: 15px; background: rgba(0,0,0,0.6);">
                    <h3 style="color: var(--neon-blue); border-bottom: 1px dashed #333; padding-bottom: 5px;">👁️ THE ORACLE (Sentiment Data)</h3>
                    <div class="log-line info-text">> Scraping Crypto Twitter... [Done]</div>
                    <div class="log-line info-text">> Analyzing Reddit/r/CryptoCurrency... [Done]</div>
                    <div class="log-line warn-text">> Sentiment Shift: Retail FOMO increasing.</div>
                    <div class="log-line info-text">> Funding rates heavily positive on major alts.</div>
                </div>
                
                <div style="flex: 1; border: 1px solid #333; padding: 15px; background: rgba(0,0,0,0.6);">
                    <h3 style="color: var(--neon-pink); border-bottom: 1px dashed #333; padding-bottom: 5px;">🐋 WHALE TRACKER</h3>
                    <div class="log-line alert-text">[ALERT] 1,450 BTC transferred from Unknown to Coinbase.</div>
                    <div class="log-line alert-text">[ALERT] 40,000 ETH withdrawn from Binance.</div>
                    <div class="log-line info-text">[INFO] Accumulation detected on ARB (Wallet: 0x7a...4b).</div>
                    <div class="log-line info-text">[INFO] $50,000,000 USDC minted at Treasury.</div>
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
    app.run(host='0.0.0.0', port=5000, debug=False)
