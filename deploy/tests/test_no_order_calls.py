#!/usr/bin/env python3
"""Guardie statiche del banco a secco: l'invio ordini e' ASSENTE da deploy/.

I token proibiti sono costruiti a runtime: nemmeno questo file li contiene in
chiaro, cosi' una ricerca nell'albero non trova falsi positivi.

Divieti che questi test difendono (docs/02 §5):
1. nessun percorso di codice che chiami l'invio di ordini — verificato qui;
2. niente segreti nel repo (example con soli placeholder);
3. unit systemd presentabili (placeholder noti, nessun residuo).
"""
from __future__ import annotations

import py_compile
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"

#: costruiti a pezzi: questo file non deve contenere i token in chiaro
FORBIDDEN = [
    "create" + "_" + "order",
    "create" + "Order",
    "place" + "_" + "order",
    "private" + "PostTrade",
    "private_post" + "_trade",
]

#: si cerca solo nel codice che gira: il banco e gli script.
#: deploy/tests/ si esclude (contiene le guardie stesse), templates/ sono unit.
SCAN_DIRS = [DEPLOY / "banco", DEPLOY / "scripts"]
SCAN_SUFFIXES = {".py", ".sh"}


def _file_da_scansionare():
    for d in SCAN_DIRS:
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix in SCAN_SUFFIXES:
                yield p


def test_nessun_token_di_invio_in_deploy():
    colpevoli = []
    for p in _file_da_scansionare():
        testo = p.read_text(encoding="utf-8", errors="replace")
        for tok in FORBIDDEN:
            if tok in testo:
                colpevoli.append(f"{p.relative_to(ROOT)}: {tok}")
    assert not colpevoli, "trovate chiamate di invio ordini: " + ", ".join(colpevoli)


def test_sintassi_bash_di_tutti_gli_script():
    for p in sorted((DEPLOY / "scripts").glob("*.sh")):
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        assert r.returncode == 0, f"{p.name}: {r.stderr}"


def test_modulo_compila_e_self_test_passa():
    modulo = DEPLOY / "banco" / "money_banco_secco.py"
    py_compile.compile(str(modulo), doraise=True)
    r = subprocess.run([sys.executable, str(modulo), "--self-test"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELF-TEST OK" in r.stdout


def test_template_con_placeholder_noti():
    for p in sorted((DEPLOY / "templates").iterdir()):
        testo = p.read_text(encoding="utf-8")
        for ph in set(re.findall(r"\{\{(\w+)\}\}", testo)):
            assert ph in {"PROJECT_ROOT", "BANCO_USER"}, \
                f"{p.name}: placeholder ignoto {ph}"


def test_env_example_senza_segreti_veri():
    ex = ROOT / "config" / ".env_banco.example"
    testo = ex.read_text(encoding="utf-8")
    for riga in testo.splitlines():
        r = riga.strip()
        if not r or r.startswith("#") or "=" not in r:
            continue
        chiave, _, valore = r.partition("=")
        if chiave.strip() in {"OKX_API_KEY", "OKX_API_SECRET", "OKX_PASSPHRASE"}:
            assert valore.strip() in {"", "cambiami", "DA_CREARE_DAL_PROPRIETARIO"}, \
                f"{chiave}: valore non placeholder — segreto nel repo?"


def test_gitignore_copre_env_e_versiona_example():
    righe = [r.strip() for r in
             (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()]
    assert ".env_*" in righe or "*.env_*" in righe, \
        "il pattern che copre i .env_* deve esistere"
    assert "!config/.env_banco.example" in righe, \
        "serve la negazione per versionare l'example senza versionare i segreti"


def test_config_banco_ha_i_campi_minimi():
    import yaml  # noqa: PLC0415 — dipendenza dei test, non del banco

    cfg = yaml.safe_load((ROOT / "config" / "node_banco.yaml").read_text(encoding="utf-8"))
    bots = cfg.get("bots") or []
    trovati = [b for b in bots if b.get("strategy") == "banco_secco"]
    assert trovati, "nessun bot strategy=banco_secco in node_banco.yaml"
    b = trovati[0]
    assert float(b["capital"]) > 0, "capitale dichiarato non positivo"
    assert 0 < float(b["frazione_per_posizione"]) <= 1, "frazione fuori range"
    assert b["symbol"], "symbol mancante"
