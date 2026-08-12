echo "== HOST =="
hostname; whoami; uptime; uname -a
echo "== DENARO SERVICES =="
systemctl list-units --all 'denaro*' --no-pager 2>/dev/null | head -20
echo "== ACTIVE =="
for s in $(systemctl list-unit-files 'denaro*' --no-legend 2>/dev/null | awk '{print $1}'); do echo "$s: $(systemctl is-active $s 2>/dev/null)"; done
echo "== SERVICE DEFINITIONS =="
for s in $(systemctl list-unit-files 'denaro*' --no-legend 2>/dev/null | awk '{print $1}'); do echo "--- $s ---"; systemctl cat $s 2>/dev/null | grep -E "ExecStart|WorkingDirectory|EnvironmentFile|User="; done
echo "== PROCESSES =="
ps aux | grep -E "python.*(main|denaro)" | grep -v grep
echo "== CODE DIR =="
ls -la ~/denaro 2>/dev/null | head -40
echo "== GIT =="
cd ~/denaro 2>/dev/null && git rev-parse --abbrev-ref HEAD 2>/dev/null && git log --oneline -5 2>/dev/null && echo "--- status ---" && git status --short 2>/dev/null | head -20
echo "== PYTHON =="
~/denaro/venv/bin/python --version 2>/dev/null || python3 --version
echo "== ENV KEYS (masked) =="
if [ -f ~/denaro/.env ]; then
  while IFS='=' read -r k v; do
    case "$k" in
      KRAKEN_API|KRAKEN_SECRET|OKX_API|OKX_SECRET|OKX_API_KEY|OKX_API_SECRET|MEXC_API|MEXC_SECRET|BYBIT_API|BYBIT_SECRET|TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID)
        [ -n "$v" ] && echo "$k=SET(${v:0:6}...)" || echo "$k=EMPTY";;
    esac
  done < ~/denaro/.env
else
  echo "NO .env"
fi
echo "== HEALTH =="
curl -s -m 5 http://127.0.0.1:8909/health 2>/dev/null || echo "health endpoint not reachable"
echo ""
