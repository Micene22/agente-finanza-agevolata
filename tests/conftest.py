"""Configurazione comune dei test.

agente.py crea il modello Gemini all'import: qui imposto valori finti, cosi' i test girano
anche senza .env (es. su GitHub Actions). Nessun test chiama davvero l'API.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("GOOGLE_API_KEY", "chiave-finta-per-i-test")
os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-flash")
