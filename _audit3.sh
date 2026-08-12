echo "== FLEET PID ENV (masked keys) =="
FPID=$(pgrep -f "alpha_omega.fleet.coordinator" | head -1)
echo "fleet pid=$FPID"
if [ -n "$FPID" ]; then
  tr '\0' '\n' < /proc/$FPID/environ 2>/dev/null | grep -iE "^(KRAKEN|OKX|MEXC|BYBIT)" | sed -E 's/=(.{6}).*/=\1.../'
  echo "--- cmdline ---"
  tr '\0' ' ' < /proc/$FPID/cmdline 2>/dev/null; echo
  echo "--- cwd ---"
  readlink /proc/$FPID/cwd 2>/dev/null
fi
echo "== SRC.MAIN identity =="
SPID=$(pgrep -f "python -m src.main" | head -1)
echo "src.main pid=$SPID"
if [ -n "$SPID" ]; then
  readlink /proc/$SPID/cwd 2>/dev/null
  tr '\0' ' ' < /proc/$SPID/cmdline 2>/dev/null; echo
fi
echo "== FLEET CONFIG =="
cat /home/sergio/denaro/config/fleet_config_nuvola.json 2>/dev/null | head -50
cat /home/marco/denaro/config/fleet_config_marcodg1.json 2>/dev/null | head -50
echo "== DENARO-MEXC CRASH LOG =="
sudo journalctl -u denaro-mexc-marcodg1.service -n 15 --no-pager 2>/dev/null
sudo journalctl -u denaro-mexc-nuvola.service -n 5 --no-pager 2>/dev/null
echo "== VENV CCTX =="
ls /home/sergio/denaro/venv/bin/python* 2>/dev/null; /home/sergio/denaro/venv/bin/python -c "import ccxt; print('ccxt', ccxt.__version__)" 2>/dev/null
ls /home/marco/denaro/venv/bin/python* 2>/dev/null; /home/marco/denaro/venv/bin/python -c "import ccxt; print('ccxt', ccxt.__version__)" 2>/dev/null
