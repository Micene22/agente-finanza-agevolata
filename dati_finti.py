"""Bandi INVENTATI per la demo. Nomi, importi e scadenze non sono reali.

In fase 2 la ricerca nei testi dei bandi diventera' un RAG su documenti pubblici;
questo elenco serve agli strumenti deterministici (requisiti e calcoli).
"""
from datetime import date, timedelta

OGGI = date.today()  # scadenze relative a oggi: la demo funziona in qualsiasi giorno

BANDI = {
    "DIGI-PMI": {
        "nome": "Voucher Digitalizzazione PMI (inventato)",
        "regioni": ["tutte"],
        "dimensioni": ["micro", "piccola", "media"],
        "settori_esclusi": ["agricoltura"],
        "percentuale": 50,          # % della spesa coperta
        "massimale": 10_000,        # contributo massimo in euro
        "spesa_minima": 3_000,
        "scadenza": OGGI + timedelta(days=10),   # urgente
    },
    "GREEN-SUD": {
        "nome": "Fondo Transizione Verde Sud (inventato)",
        "regioni": ["Sicilia", "Calabria", "Campania", "Puglia", "Basilicata", "Sardegna"],
        "dimensioni": ["micro", "piccola"],
        "settori_esclusi": [],
        "percentuale": 40,
        "massimale": 50_000,
        "spesa_minima": 10_000,
        "scadenza": OGGI + timedelta(days=150),
    },
    "START-INNOVA": {
        "nome": "Contributo Startup Innovative (inventato)",
        "regioni": ["tutte"],
        "dimensioni": ["micro"],
        "settori_esclusi": ["commercio"],
        "percentuale": 70,
        "massimale": 30_000,
        "spesa_minima": 5_000,
        "scadenza": OGGI + timedelta(days=90),
    },
}
