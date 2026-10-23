"""Strumenti (tools) che l'agente puo' chiamare.

Progetto dimostrativo: i bandi sono inventati, non e' una consulenza reale.
"""
from datetime import date

from langchain_core.tools import tool

from dati_finti import BANDI

AGENDA = []  # agenda finta dei promemoria (in fase 2 diventera' un database)


@tool
def cerca_bandi(regione: str, dimensione: str, settore: str) -> list[dict]:
    """Trova i bandi aperti compatibili con il profilo di un'impresa.

    Args:
        regione: regione della sede, per esempio "Sicilia".
        dimensione: "micro", "piccola", "media" o "grande".
        settore: settore di attivita', per esempio "commercio", "manifattura", "servizi".
    """
    compatibili = []
    for codice, bando in BANDI.items():
        giorni_rimasti = (bando["scadenza"] - date.today()).days

        if giorni_rimasti < 0:
            continue  # scaduto: passo al bando successivo
        if "tutte" not in bando["regioni"] and regione.capitalize() not in bando["regioni"]:
            continue
        if dimensione.lower() not in bando["dimensioni"]:
            continue
        if settore.lower() in bando["settori_esclusi"]:
            continue

        compatibili.append({
            "bando_id": codice,
            "nome": bando["nome"],
            "percentuale": bando["percentuale"],
            "massimale": bando["massimale"],
            "spesa_minima": bando["spesa_minima"],
            "giorni_alla_scadenza": giorni_rimasti,
            "urgente": giorni_rimasti <= 15,
        })
    return compatibili


@tool
def calcola_contributo(bando_id: str, spesa: float) -> dict:
    """Calcola il contributo a fondo perduto che un'impresa puo' ottenere da un bando.

    Args:
        bando_id: codice del bando, per esempio "DIGI-PMI".
        spesa: spesa prevista dall'impresa per il progetto, in euro.
    """
    # 1. Il bando esiste? (l'LLM potrebbe inventarsi un codice)
    if bando_id not in BANDI:
        return {"errore": f"bando {bando_id} non trovato"}

    bando = BANDI[bando_id]

    # 1.1 Il bando è scaduto?
    if bando["scadenza"] < date.today():
        return {
            "ammissibile": False,
            "motivo": f"bando scaduto il {bando['scadenza']}",
        }

    # 2. La spesa raggiunge il minimo richiesto?
    if spesa < bando["spesa_minima"]:
        return {
            "ammissibile": False,
            "motivo": f"spesa minima richiesta: {bando['spesa_minima']} euro",
        }

    # 3. Contributo = percentuale della spesa, ma mai oltre il massimale
    contributo = spesa * bando["percentuale"] / 100
    contributo = min(contributo, bando["massimale"])
    return {
        "ammissibile": True,
        "contributo": round(contributo, 2),
        "percentuale": bando["percentuale"],
        "massimale_applicato": contributo == bando["massimale"],
    }


@tool
def crea_promemoria(azienda: str, bando_id: str, nota: str) -> dict:
    """Registra nell'agenda dello studio un promemoria per seguire la pratica di un'impresa.

    Args:
        azienda: nome dell'impresa cliente.
        bando_id: codice del bando, per esempio "DIGI-PMI".
        nota: cosa ricordarsi di fare, per esempio "raccogliere i preventivi".
    """
    if bando_id not in BANDI:
        return {"errore": f"bando {bando_id} non trovato"}

    bando = BANDI[bando_id]
    promemoria = {
        "id": f"PR-{len(AGENDA) + 1}",
        "azienda": azienda,
        "bando_id": bando_id,
        "nota": nota,
        "scadenza": str(bando["scadenza"]),
    }

    AGENDA.append(promemoria)
    return {"creato": True, "promemoria": promemoria}
