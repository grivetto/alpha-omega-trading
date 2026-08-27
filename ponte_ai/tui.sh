#!/bin/bash
# TUI Hermes in sessione DEDICATA "chat-sergio" (isolata da webchat :3080,
# gateway Telegram e ciclo del Brain "brain-sync" — niente lock collision).
# Uso su mc2:  hermes-tui   (alias in ~/.bashrc)  oppure  bash tui.sh
export PATH="$HOME/.local/bin:$PATH"
exec hermes -c --resume chat-sergio
