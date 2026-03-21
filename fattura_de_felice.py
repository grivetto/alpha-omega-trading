import urllib.parse
import os

phone = "393711741209"  # Numero whatsapp che aveva lasciato (3711741209)
message = """Gentile De Felice,

Come da accordi, le invio il proforma della fattura relativa alle prestazioni effettuate.
Importo totale: 320,00 EUR
Data: 20/03/2026

Resto a disposizione per qualsiasi chiarimento.

Cordiali saluti,
Sergio Grivetto"""

encoded = urllib.parse.quote(message)
url = f"https://api.whatsapp.com/send?phone={phone}&text={encoded}"
print("URL per l'invio WhatsApp:", url)
