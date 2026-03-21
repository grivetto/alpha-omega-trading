#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

load_dotenv('/root/.openclaw/workspace/.env.telegram')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

msg = """📩 *Nota su Whatsapp e WhatsApp Bot*

Caro Sergio (Capitan Bot all'ascolto!),
Ti avviso che ho preparato la fattura da **320 EUR** per De Felice con data **20/03/2026** come richiesto.
Tuttavia il mio servizio di connessione WhatsApp aziendale risulta *disconnesso (Errore 401)* e necessita di essere ri-sincronizzato inquadrando un QR code, per cui per ora **non sono riuscito** a farla partire dal mio numero verso il suo 3711741209.

Per non farti perdere tempo, ti lascio qui sotto il testo pronto: copialo o clicca il link e inviagliela al volo dal tuo cellulare mentre vai a prendere la piccola Lucrezia!

--- TESTO ---
Gentile De Felice,
Le invio la fattura relativa alle prestazioni effettuate.
Importo: 320,00 EUR
Data: 20/03/2026
Cordiali saluti, Sergio Grivetto
---

👉 *Oppure clicca questo link per aprirgli la chat Whatsapp in automatico:*
https://api.whatsapp.com/send?phone=393711741209&text=Gentile%20De%20Felice%2C%0ALe%20invio%20la%20fattura%20relativa%20alle%20prestazioni%20effettuate.%0AImporto%3A%20320%2C00%20EUR%0AData%3A%2020/03/2026%0ACordiali%20saluti%2C%20Sergio%20Grivetto

🤖 Un abbraccio e corri per le 15:30! Ci sentiamo quando rientri. Ciao da Cappy / Capitan Bot!
"""

url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'})
print("sent")
