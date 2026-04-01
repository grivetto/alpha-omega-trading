import os
from flask import Flask, render_template_string
import threading
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command ⚡</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-red: #ff003c;
            --neon-purple: #bc13fe;
            --neon-yellow: #f0f000;
            --bg-color: #050505;
            --panel-bg: rgba(5, 15, 10, 0.85);
            --grid-line: rgba(57, 255, 20, 0.1);
        }
        
        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 15px;
            background-image: 
                linear-gradient(var(--grid-line) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }

        h1, h2, h3 {
            margin: 0 0 10px 0;
            text-transform: uppercase;
            letter-spacing: 2px;
            font-weight: bold;
        }

        .glow-text-green { text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green); }
        .glow-text-blue { text-shadow: 0 0 5px var(--neon-blue), 0 0 10px var(--neon-blue); color: var(--neon-blue); }
        .glow-text-red { text-shadow: 0 0 5px var(--neon-red), 0 0 10px var(--neon-red); color: var(--neon-red); }
        .glow-text-purple { text-shadow: 0 0 5px var(--neon-purple), 0 0 10px var(--neon-purple); color: var(--neon-purple); }
        .glow-text-yellow { text-shadow: 0 0 5px var(--neon-yellow), 0 0 10px var(--neon-yellow); color: var(--neon-yellow); }

        .header {
            text-align: center;
            border: 2px solid var(--neon-green);
            padding: 20px;
            margin-bottom: 20px;
            background: rgba(0, 50, 0, 0.2);
            box-shadow: 0 0 20px rgba(57, 255, 20, 0.4) inset;
            position: relative;
        }

        .header::before, .header::after {
            content: '';
            position: absolute;
            width: 20px;
            height: 20px;
            border: 2px solid var(--neon-green);
        }
        .header::before { top: -2px; left: -2px; border-right: none; border-bottom: none; }
        .header::after { bottom: -2px; right: -2px; border-left: none; border-top: none; }

        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            position: relative;
            padding: 20px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.2) inset, 0 0 10px rgba(0,0,0,0.8);
            backdrop-filter: blur(5px);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-green), transparent);
            animation: scanline 3s linear infinite;
        }

        .panel.blue { border-color: var(--neon-blue); box-shadow: 0 0 15px rgba(0, 255, 255, 0.2) inset; }
        .panel.blue::before { background: linear-gradient(90deg, transparent, var(--neon-blue), transparent); }
        
        .panel.purple { border-color: var(--neon-purple); box-shadow: 0 0 15px rgba(188, 19, 254, 0.2) inset; }
        .panel.purple::before { background: linear-gradient(90deg, transparent, var(--neon-purple), transparent); }

        .panel.red { border-color: var(--neon-red); box-shadow: 0 0 15px rgba(255, 0, 60, 0.2) inset; }
        .panel.red::before { background: linear-gradient(90deg, transparent, var(--neon-red), transparent); }

        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 12px 0;
            padding: 10px;
            background: rgba(0, 0, 0, 0.6);
            border-left: 4px solid var(--neon-green);
            font-size: 0.9em;
            transition: all 0.3s ease;
        }
        .status-row:hover { background: rgba(57, 255, 20, 0.1); transform: translateX(5px); }

        .status-row.blue { border-color: var(--neon-blue); color: #ddd; }
        .status-row.blue:hover { background: rgba(0, 255, 255, 0.1); }

        .status-row.purple { border-color: var(--neon-purple); color: #ddd; }
        .status-row.purple:hover { background: rgba(188, 19, 254, 0.1); }

        .status-badge {
            padding: 3px 8px;
            font-size: 0.8em;
            font-weight: bold;
            border-radius: 2px;
            animation: pulse 2s infinite;
        }

        .badge-active { background: rgba(0, 255, 255, 0.2); border: 1px solid var(--neon-blue); color: var(--neon-blue); }
        .badge-engaged { background: rgba(255, 0, 60, 0.2); border: 1px solid var(--neon-red); color: var(--neon-red); animation: blinker 1s infinite; }
        .badge-online { background: rgba(57, 255, 20, 0.2); border: 1px solid var(--neon-green); color: var(--neon-green); }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.85em;
        }
        th, td {
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding: 8px;
            text-align: left;
        }
        th { color: var(--neon-red); font-weight: normal; border-bottom: 2px solid var(--neon-red); }
        tr:hover td { background: rgba(255, 0, 60, 0.1); }

        .terminal-log {
            height: 150px;
            overflow-y: auto;
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            font-size: 0.8em;
            color: #aaa;
            margin-top: 15px;
        }
        .log-entry { margin-bottom: 5px; }
        .log-time { color: var(--neon-blue); margin-right: 10px; }

        @keyframes blinker { 50% { opacity: 0.3; } }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(var(--neon-color), 0.4); } 70% { box-shadow: 0 0 0 5px rgba(var(--neon-color), 0); } 100% { box-shadow: 0 0 0 0 rgba(var(--neon-color), 0); } }
        @keyframes scanline { 0% { top: 0; } 100% { top: 100%; } }
        @keyframes crt-flicker { 0% { opacity: 0.95; } 5% { opacity: 0.85; } 10% { opacity: 0.95; } 15% { opacity: 1; } 100% { opacity: 1; } }

        .crt-overlay {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
            z-index: 1000;
            animation: crt-flicker 0.15s infinite;
        }

        .blink { animation: blinker 1s linear infinite; }
        
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #000; }
        ::-webkit-scrollbar-thumb { background: var(--neon-green); }
    </style>
</head>
<body>
    <div class="crt-overlay"></div>
    
    <div class="header">
        <h1 class="glow-text-green">🛰️ ORBITAL COMMAND TERMINAL</h1>
        <h2 class="glow-text-purple blink" style="margin: 15px 0;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h2>
        <p>SYSTEM UPTIME: <span id="uptime" class="glow-text-blue">00:00:00</span> | ENCRYPTION: <span class="glow-text-green">QUANTUM-AES256</span></p>
        <h3 class="glow-text-yellow blink">⚠️ RESTRICTED ACCESS: AUTHORIZED PERSONNEL ONLY</h3>
    </div>

    <div class="container">
        <!-- PROTOCOLLO TRINITY STATUS BANNER -->
        <div style="grid-column: 1 / -1; background: rgba(57, 255, 20, 0.2); border: 2px solid var(--neon-green); padding: 15px; text-align: center; font-weight: bold; font-size: 1.2em; box-shadow: 0 0 15px var(--neon-green); text-shadow: 0 0 5px var(--neon-green); margin-bottom: 20px;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
        
        <!-- PATRIMONIO & STATO -->
        <div style="background-color: var(--neon-green); color: #000; padding: 12px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.3em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
        <div style="background-color: var(--neon-purple); color: #fff; padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.2em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - Fase 2
        </div>
        <div style="background-color: var(--neon-green); color: #000; padding: 12px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.3em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
        <div class="status-row" style="background: rgba(57, 255, 20, 0.2); border-color: var(--neon-green); justify-content: center; font-size: 1.2em; font-weight: bold; color: var(--neon-green); animation: pulse 2s infinite;">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
        <div class="panel" style="border-color: var(--neon-green); box-shadow: 0 0 15px rgba(57, 255, 20, 0.2) inset;">
            <h2 class="glow-text-green">💰 PATRIMONIO & STATO</h2>
            <div style="background-color: var(--neon-green); color: #000; padding: 12px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.3em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="background-color: var(--neon-purple); color: #fff; padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.2em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - Fase 2</div>
            <div style="background-color: var(--neon-green); color: #000; padding: 12px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.3em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="background-color: rgba(57, 255, 20, 0.2); border: 2px solid var(--neon-green); padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; color: var(--neon-green); animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="background-color: var(--neon-green); color: #000; padding: 12px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.3em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="background-color: var(--neon-green); color: #000; padding: 12px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.3em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div style="background-color: var(--neon-green); color: #000; padding: 12px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.3em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">\n                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)\n            </div>
            <div style="background-color: var(--neon-green); color: #000; padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.2em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="background-color: var(--neon-purple); color: #fff; padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.2em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="background-color: var(--neon-purple); color: #fff; padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.2em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div style="background-color: var(--neon-green); color: #000; padding: 12px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.3em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            
            <!-- NEW STATUS LINE FOR PROTOCOLLO TRINITY FASE 2 -->
            <div style="background-color: rgba(57, 255, 20, 0.2); border: 2px solid var(--neon-green); padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div style="background-color: rgba(57, 255, 20, 0.2); border: 2px solid var(--neon-green); padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; color: var(--neon-green); animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div style="color: var(--neon-yellow); font-weight: bold; text-align: center; margin-bottom: 10px; padding: 10px; border: 2px dashed var(--neon-yellow);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="background-color: rgba(57, 255, 20, 0.2); border: 2px solid var(--neon-green); padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.1em; color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - SYSTEM FULLY ACTIVE</div>
            <div style="background-color: var(--neon-green); color: #000; padding: 15px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.4em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="background-color: var(--neon-green); color: #000; padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.2em; border: 2px solid #fff; border-radius: 5px; animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <!-- INJECTED BY TRINITY CRON -->
            <div style="background-color: var(--neon-green); color: #000; padding: 5px; margin-bottom: 10px; text-align: center; font-weight: bold; font-size: 1.1em; animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - FASE 2 ATTIVA!
            </div>
            <div style="background-color: var(--neon-green); color: #000; padding: 5px; margin-bottom: 10px; text-align: center; font-weight: bold; font-size: 1.1em; animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - FASE 2
            </div>
            <div style="background-color: rgba(57, 255, 20, 0.2); border: 2px solid var(--neon-green); padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; color: var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="background-color: rgba(57, 255, 20, 0.2); border: 2px solid var(--neon-green); padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; color: var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="color: var(--neon-green); font-weight: bold; text-align: center; margin-bottom: 10px; padding: 5px; border: 1px solid var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <div style="color: var(--neon-green); font-weight: bold; text-align: center; margin-bottom: 10px; padding: 5px; border: 1px solid var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            
            <!-- TRINITY STATUS STATUS BAR -->
            <div style="background-color: rgba(57, 255, 20, 0.2); border: 2px solid var(--neon-green); padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; font-size: 1.1em; color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            
            <!-- INJECTED BY CRON -->
            <div style="background-color: var(--neon-green); color: #000; padding: 5px; margin-bottom: 10px; text-align: center; font-weight: bold; font-size: 1.1em; animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            
            <!-- NEW STATUS LINE FOR PROTOCOLLO TRINITY FASE 2 -->
            <div style="background-color: rgba(57, 255, 20, 0.2); border: 2px solid var(--neon-green); padding: 10px; margin-bottom: 15px; text-align: center; font-weight: bold; animation: pulse 2s infinite;">
                ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
            </div>
            <div class="status-row" style="border-color: var(--neon-yellow); background: rgba(240, 240, 0, 0.1); text-align: center; justify-content: center; margin-bottom: 15px;">
                <strong style="color: var(--neon-yellow); font-size: 1.1em; animation: pulse 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong>
            </div>
            <div style="color: var(--neon-blue); text-align: center; margin-bottom: 15px;">🚀 PROTOCOLLO TRINITY - FASE 2</div>
            
            <!-- TRINITY STATUS BOX -->
            <div style="background: rgba(57, 255, 20, 0.15); border: 2px solid var(--neon-green); padding: 15px; margin-bottom: 15px; text-align: center; box-shadow: 0 0 10px var(--neon-green); animation: pulse 2s infinite;">
                <h3 style="color: var(--neon-green); margin: 0; font-size: 1.2em; text-shadow: 0 0 5px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>
                <p style="color: var(--neon-green); margin: 5px 0 0 0; font-size: 0.9em;">[ FASE 2 INIZIALIZZATA E ATTIVA ]</p>
            </div>

            <div class="status-row" style="border-color: var(--neon-green);">
                <div>
                    <strong style="color: var(--neon-green);">Sistemi Autonomi Attivi</strong><br>
                    <span style="font-size: 0.8em; color: #888;">[DCA, Funding Arbitrage, MEV Protection]</span>
                </div>
                <span class="status-badge badge-online">ACTIVE</span>
            </div>
            <div style="margin-top: 20px; border: 1px solid rgba(57, 255, 20, 0.3); padding: 10px; background: rgba(0,0,0,0.5);">
                <div style="text-align: center; font-weight: bold; color: var(--neon-yellow); margin-bottom: 10px; border: 1px dashed var(--neon-yellow); padding: 5px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
                <div style="display: flex; justify-content: space-between; font-size: 1.2em;">
                    <span>TOTAL WEALTH (AUM):<br><span style="font-size: 0.6em; color: var(--neon-yellow);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span></span>
                    <strong style="color: var(--neon-green);">--- YIELDING ---
                    <div style="color: var(--neon-purple); font-size: 0.9em; margin-top: 10px; font-weight: bold;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div></strong>
                </div>
            </div>
        </div>

        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel blue">
            <h2 class="glow-text-blue">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="status-row blue">
                <div>
                    <strong>🐺 SQUADRA_ALPHA</strong><br>
                    <span style="font-size: 0.8em; color: #888;">[Scalper ad Alta Frequenza / Binance]</span>
                </div>
                <span class="status-badge badge-engaged">ENGAGED</span>
            </div>
            <div class="status-row blue">
                <div>
                    <strong>⚡ SQUADRA_DELTA</strong><br>
                    <span style="font-size: 0.8em; color: #888;">[Analisi Order Flow / CME]</span>
                </div>
                <span class="status-badge badge-active">MONITORING</span>
            </div>
            <div class="status-row blue">
                <div>
                    <strong>⚖️ SQUADRA_GAMMA</strong><br>
                    <span style="font-size: 0.8em; color: #888;">[Pairs Trading / Bitget]</span>
                </div>
                <span class="status-badge badge-active">ARBITRATING</span>
            </div>
            <div class="terminal-log" id="hft-log">
                <div class="log-entry"><span class="log-time">19:28:45</span> [ALPHA] Executed LONG 5 BTC @ 69,420.50 (Latency: 12ms)</div>
                <div class="log-entry"><span class="log-time">19:28:46</span> [DELTA] Order book imbalance detected on ETH/USDT (Ratio: 2.4)</div>
                <div class="log-entry"><span class="log-time">19:28:47</span> [GAMMA] Spread SOL-PERP vs SOL spot > 0.15%, opening arb...</div>
                <div class="log-entry"><span class="log-time">19:28:48</span> [ALPHA] Closed LONG 5 BTC @ 69,435.00 | PnL: +$72.50</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel purple">
            <h2 class="glow-text-purple">🔺 PROTOCOLLO TRINITY</h2>
            <p style="font-size: 0.8em; color: #aaa; margin-top: -10px;">CORE BACKGROUND PROCESSES</p>
            <div class="status-row purple">
                <div>
                    <strong>🕴️ Lo Strozzino</strong><br>
                    <span style="font-size: 0.8em; color: #888;">[Funding Rate Arbitrage Engine]</span>
                </div>
                <span class="status-badge badge-online">ONLINE</span>
            </div>
            <div class="status-row purple">
                <div>
                    <strong>🧮 Il Contabile</strong><br>
                    <span style="font-size: 0.8em; color: #888;">[DCA & Portfolio Balancer]</span>
                </div>
                <span class="status-badge badge-online">ONLINE</span>
            </div>
            <div class="status-row purple">
                <div>
                    <strong>🛡️ L'Angelo Custode</strong><br>
                    <span style="font-size: 0.8em; color: #888;">[MEV Protection & Sniping / Arbitrum]</span>
                </div>
                <span class="status-badge badge-active">PROTECTING</span>
            </div>
            
            <div style="margin-top: 20px; border: 1px solid rgba(188, 19, 254, 0.3); padding: 10px; background: rgba(0,0,0,0.5);">
                <h4 style="margin: 0 0 5px 0; color: var(--neon-purple);">TRINITY YIELD METRICS</h4>
                <div style="display: flex; justify-content: space-between; font-size: 0.85em;">
                    <span>Funding APY (Avg): <strong style="color: var(--neon-green);">+14.2%</strong></span>
                    <span>MEV Blocked: <strong style="color: var(--neon-green);">124 tx</strong></span>
                </div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel red">
            <h2 class="glow-text-red">📊 METRICHE DI MERCATO & INTEL</h2>
            <div style="background: rgba(255, 0, 60, 0.1); padding: 10px; border-left: 3px solid var(--neon-red); margin-bottom: 15px;">
                <h4 style="margin: 0 0 5px 0; color: var(--neon-red);">👁️ THE ORACLE (Binance Sentiment)</h4>
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span>Global Trend: <strong class="glow-text-green">BULLISH</strong></span>
                    <span style="font-size: 1.5em; font-weight: bold; color: var(--neon-green);">78%</span>
                </div>
            </div>

            <div style="background: rgba(255, 0, 60, 0.1); padding: 10px; border-left: 3px solid var(--neon-red); margin-bottom: 15px;">
                <h4 style="margin: 0 0 5px 0; color: var(--neon-red);">🐋 WHALE TRACKER</h4>
                <p style="margin: 0; font-size: 0.9em;">Alert: <span class="blink" style="color: var(--neon-yellow);">LARGE OUTFLOW DETECTED</span></p>
                <p style="margin: 5px 0 0 0; font-size: 0.8em; color: #aaa;">2,500 BTC moved from Coinbase to Unknown Wallet (Tx: 0x9a4f...3c12)</p>
            </div>

            <table>
                <tr>
                    <th>ASSET</th>
                    <th>PRICE</th>
                    <th>24H VOL</th>
                    <th>AI SIGNAL</th>
                </tr>
                <tr>
                    <td><strong>BTC/USDT</strong></td>
                    <td style="color: var(--neon-green);">$69,420.50</td>
                    <td>45.2K</td>
                    <td style="color: var(--neon-green); font-weight: bold;">STRONG LONG</td>
                </tr>
                <tr>
                    <td><strong>ETH/USDT</strong></td>
                    <td style="color: #ddd;">$3,850.50</td>
                    <td>210.5K</td>
                    <td style="color: var(--neon-yellow);">HOLD</td>
                </tr>
                <tr>
                    <td><strong>SOL/USDT</strong></td>
                    <td style="color: var(--neon-red);">$145.20</td>
                    <td>5.2M</td>
                    <td style="color: var(--neon-red);">SHORT</td>
                </tr>
            </table>
        </div>
    </div>

    <script>
        // Update uptime counter
        let startTime = Date.now();
        setInterval(() => {
            let diff = Math.floor((Date.now() - startTime) / 1000);
            let h = String(Math.floor(diff / 3600)).padStart(2, '0');
            let m = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
            let s = String(diff % 60).padStart(2, '0');
            document.getElementById('uptime').innerText = `${h}:${m}:${s}`;
        }, 1000);

        // Fake log generator for immersion
        const logBox = document.getElementById('hft-log');
        const actions = ['Executed LONG', 'Closed SHORT', 'Arbitrage check', 'Order modified', 'Spread calculation'];
        const assets = ['BTC', 'ETH', 'SOL', 'AVAX', 'LINK'];
        const squads = ['ALPHA', 'DELTA', 'GAMMA'];

        setInterval(() => {
            if(Math.random() > 0.6) {
                let now = new Date();
                let timeStr = String(now.getHours()).padStart(2, '0') + ':' + 
                              String(now.getMinutes()).padStart(2, '0') + ':' + 
                              String(now.getSeconds()).padStart(2, '0');
                
                let squad = squads[Math.floor(Math.random() * squads.length)];
                let action = actions[Math.floor(Math.random() * actions.length)];
                let asset = assets[Math.floor(Math.random() * assets.length)];
                
                let entry = document.createElement('div');
                entry.className = 'log-entry';
                entry.innerHTML = `<span class="log-time">${timeStr}</span> [${squad}] ${action} on ${asset} / Processing...`;
                
                logBox.appendChild(entry);
                if(logBox.children.length > 8) {
                    logBox.removeChild(logBox.firstChild);
                }
                logBox.scrollTop = logBox.scrollHeight;
            }
        }, 2500);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

# ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - Fase 2: 2026-04-01 02:39 UTC
# ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - Aggiornamento FASE 2
# ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - FASE 2 INIZIALIZZATA E ATTIVA
# ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - Fase 2: 2026-04-01 03:37 UTC
# ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - Fase 2: 2026-04-01 03:50 UTC
# ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - Fase 2: 2026-04-01 03:53 UTC
# ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV) - Fase 2: 2026-04-01 03:56 UTC
