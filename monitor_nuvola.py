
import subprocess
import sys
import os

# Simulate error conditions
# Low EUR balance
EUR_BALANCE = 0.56
FLOOR_EUR = 35.0

# Telegram alert details (read from .env)
TELEGRAM_BOT_TOKEN = "8715854678:AAH3YJx2r0gqlmw"
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Telegram bot token or chat ID not set in environment.", file=sys.stderr)
        return False
    
    # Basic sanitization to prevent command injection or issues with special characters
    sanitized_message = message.replace('`', '').replace('$', '').replace('(', '').replace(')', '').replace(';', '').replace('\'', '').replace('"', '')
    
    try:
        subprocess.run([
            "python3", "/home/sergio/denaro/send_alert.py",
            sanitized_message,
            "Nuvola"
        ], check=True, capture_output=True, text=True)
        print(f"Sent Telegram alert: {sanitized_message}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error sending Telegram alert: {e.stderr}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("Error: send_alert.py not found. Ensure it's in /home/sergio/denaro/.", file=sys.stderr)
        return False


def monitor_nuvola():
    print(f"NUVOLA STATUS: ⚠️ Basso saldo EUR: {EUR_BALANCE:.2f}€")
    print(f"Saldo EUR: {EUR_BALANCE:.2f}€")
    print(f"Totale: 45.10€")
    print(f"Asset: 6")

    if EUR_BALANCE < FLOOR_EUR:
        alert_message = f"Low EUR balance on Nuvola: {EUR_BALANCE:.2f}€. Floor is {FLOOR_EUR}€."
        if send_telegram_alert(alert_message):
            sys.exit(0) # Exit code 0 indicates alert was sent for this condition
        else:
            sys.exit(2) # Exit code 2 for configuration/script error
    else:
        print("Nuvola balance is healthy.")
        sys.exit(0)

if __name__ == "__main__":
    # Set dummy environment variables for testing if not already set
    if not TELEGRAM_BOT_TOKEN:
        os.environ["TELEGRAM_BOT_TOKEN"] = "DUMMY_TOKEN"
    if not TELEGRAM_CHAT_ID:
        os.environ["TELEGRAM_CHAT_ID"] = "DUMMY_CHAT_ID"
        
    monitor_nuvola()
