"""Denaro infrastructure layer — adattatori e servizi (I/O).

Regole del layer:
- implementa i contratti definiti in `domain`
- unico layer che tocca rete/file
- ogni componente e' iniettabile e testabile con fake
"""
