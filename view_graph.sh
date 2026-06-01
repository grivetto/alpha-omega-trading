#!/bin/bash
PORT=8000

# Rileva IP locale/remoto
IP=$(hostname -I | awk '{print $1}')
if [ -z "$IP" ]; then
    IP="127.0.0.1"
fi

echo "=================================================="
echo " 🌌 SERVIZIO DI VISUALIZZAZIONE GRAFO GRAPHIFY"
echo "=================================================="
echo "Avvio del server HTTP sulla cartella: graphify-out"
echo "Porta: $PORT"
echo ""
echo "Puoi accedere alla mappa interattiva da questi link:"
echo "👉 Locale (se sul server):  http://localhost:$PORT"
echo "👉 Remoto (dal tuo browser): http://$IP:$PORT"
echo "=================================================="
echo "Premi CTRL+C per fermare il server."
echo ""

python3 -m http.server --directory graphify-out $PORT
