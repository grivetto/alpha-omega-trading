#!/usr/bin/env python3
"""Il mandato e' eseguibile: in live solo strategie con alpha misurato."""
from __future__ import annotations

from denaro.research.misurate import (ELIMINATE, MISURATE, NON_MISURATE,
                                      puo_girare_live)


def test_trend_puo_girare_live():
    ok, motivo = puo_girare_live("trend", "okx")
    assert ok, motivo


def test_paper_ammesso_sempre():
    for s in ("grid", "momentum", "meanrev", "adaptive", "irmr", "vagr"):
        ok, _ = puo_girare_live(s, "paper")
        assert ok, s


def test_strategie_eliminate_non_partono_live():
    for s in ELIMINATE:
        ok, motivo = puo_girare_live(s, "okx")
        assert not ok
        assert "ELIMINATA" in motivo


def test_policy_senza_motore_non_parte_live():
    for s in ("adaptive", "adaptive_vol_grid", "irmr", "vagr",
              "mincapture_grid", "flowgate_grid", "cycle_phase_grid",
              "asymvol_anchor", "circular", "pullback"):
        ok, motivo = puo_girare_live(s, "okx")
        assert not ok, s
        assert "MISURATA" in motivo or "sconosciuta" in motivo


def test_strategia_ignota_rifiutata():
    ok, motivo = puo_girare_live("strategia_inventata", "okx")
    assert not ok and "sconosciuta" in motivo


def test_registro_copre_il_dispatch_del_node():
    """Ogni strategia che il Node sa costruire ha un verdetto esplicito."""
    dispatch = {"grid", "momentum", "meanrev", "adaptive", "irmr", "vagr",
                "trend"}
    for s in dispatch:
        ok, _ = puo_girare_live(s, "okx")
        if not ok:
            assert s in ELIMINATE or s in NON_MISURATE, s
