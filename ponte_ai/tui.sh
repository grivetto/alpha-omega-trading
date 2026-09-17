#!/bin/bash
# TUI Hermes — comando che FUNZIONA su questa versione (v0.20.6).
# NOTA: --resume/--continue con nome sessione richiedono una sessione
# ESISTENTE (--create-if-missing non esiste in questa versione). Per una
# sessione dedicata: avvia e usa il session-id mostrato all'uscita:
#   hermes -c --resume <SESSION_ID>
# Il ciclo del Brain usa gia' una sessione separata (brain-sync) ogni 60 min.
export PATH="$HOME/.local/bin:$PATH"
exec hermes -c
