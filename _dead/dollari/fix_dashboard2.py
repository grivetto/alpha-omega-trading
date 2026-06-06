import re
with open('/home/sergio/denaro/dashboard_server.py', 'r') as f:
    content = f.read()

# Modifica il nome del patrimonio per la web dashboard
content = content.replace("💰 PATRIMONIO REALE", "💰 PATRIMONIO REALE (SOLO CAPITALE IN GIOCO)")
content = content.replace("💸 INCASSO MEDIO GIORNALIERO", "💸 DRAWDOWN STORICO (PER NOI AMICI)")

# Sostituisci il +0.00 dell'incasso medio con la formula vera
import json

def get_drawdown():
    try:
        with open("/home/sergio/denaro/total_usdt_cache.json", "r") as f:
            total = float(json.load(f).get('total_usdt', 0))
            return (total - 500.0) * 0.92
    except:
        return 0.0

# Questo replace è troppo statico se il codice genera la pagina dinamicamente
# Guardiamo come lo fa il server

