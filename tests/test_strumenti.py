"""Test degli strumenti deterministici: requisiti, calcoli e promemoria (nessuna chiamata all'LLM)."""
from datetime import date, timedelta

import pytest

import strumenti
from dati_finti import BANDI
from strumenti import calcola_contributo, cerca_bandi, crea_promemoria


@pytest.fixture(autouse=True)
def agenda_vuota():
    strumenti.AGENDA.clear()
    yield
    strumenti.AGENDA.clear()


# --- calcola_contributo -------------------------------------------------------
def test_contributo_percentuale_della_spesa():
    # DIGI-PMI: 50% della spesa, massimale 10.000
    risultato = calcola_contributo.invoke({"bando_id": "DIGI-PMI", "spesa": 8000})
    assert risultato == {"ammissibile": True, "contributo": 4000.0, "percentuale": 50,
                         "massimale_applicato": False}


def test_contributo_non_supera_il_massimale():
    risultato = calcola_contributo.invoke({"bando_id": "DIGI-PMI", "spesa": 50_000})
    assert risultato["contributo"] == 10_000
    assert risultato["massimale_applicato"] is True


def test_spesa_sotto_il_minimo_non_ammissibile():
    risultato = calcola_contributo.invoke({"bando_id": "GREEN-SUD", "spesa": 5_000})
    assert risultato["ammissibile"] is False
    assert "spesa minima" in risultato["motivo"]


def test_bando_inesistente_restituisce_errore():
    # l'LLM potrebbe inventarsi un codice: lo strumento deve rifiutarlo
    risultato = calcola_contributo.invoke({"bando_id": "NON-ESISTE", "spesa": 10_000})
    assert "errore" in risultato


def test_bando_scaduto_non_ammissibile(monkeypatch):
    scaduto = dict(BANDI["DIGI-PMI"], scadenza=date.today() - timedelta(days=1))
    monkeypatch.setitem(BANDI, "DIGI-PMI", scaduto)
    risultato = calcola_contributo.invoke({"bando_id": "DIGI-PMI", "spesa": 8000})
    assert risultato["ammissibile"] is False
    assert "scaduto" in risultato["motivo"]


# --- cerca_bandi --------------------------------------------------------------
def codici(risultati):
    return {b["bando_id"] for b in risultati}


def test_micro_impresa_siciliana_dei_servizi_trova_tutti_i_bandi():
    risultati = cerca_bandi.invoke({"regione": "sicilia", "dimensione": "micro", "settore": "servizi"})
    assert codici(risultati) == {"DIGI-PMI", "GREEN-SUD", "START-INNOVA"}


def test_filtro_per_regione():
    # GREEN-SUD vale solo per le regioni del Sud
    risultati = cerca_bandi.invoke({"regione": "Lombardia", "dimensione": "piccola", "settore": "servizi"})
    assert "GREEN-SUD" not in codici(risultati)


def test_filtro_per_settore_escluso():
    # START-INNOVA esclude il commercio
    risultati = cerca_bandi.invoke({"regione": "Sicilia", "dimensione": "micro", "settore": "commercio"})
    assert "START-INNOVA" not in codici(risultati)


def test_filtro_per_dimensione():
    risultati = cerca_bandi.invoke({"regione": "Sicilia", "dimensione": "grande", "settore": "servizi"})
    assert risultati == []


def test_bando_in_scadenza_segnalato_come_urgente():
    risultati = cerca_bandi.invoke({"regione": "Sicilia", "dimensione": "micro", "settore": "servizi"})
    per_codice = {b["bando_id"]: b for b in risultati}
    assert per_codice["DIGI-PMI"]["urgente"] is True      # scade tra 10 giorni
    assert per_codice["GREEN-SUD"]["urgente"] is False    # scade tra 150 giorni


# --- crea_promemoria ----------------------------------------------------------
def test_promemoria_registrato_in_agenda():
    risultato = crea_promemoria.invoke({"azienda": "Rossi Srl", "bando_id": "DIGI-PMI",
                                        "nota": "raccogliere i preventivi"})
    assert risultato["creato"] is True
    assert risultato["promemoria"]["id"] == "PR-1"
    assert len(strumenti.AGENDA) == 1


def test_promemoria_su_bando_inesistente_non_creato():
    risultato = crea_promemoria.invoke({"azienda": "Rossi Srl", "bando_id": "NON-ESISTE", "nota": "x"})
    assert "errore" in risultato
    assert strumenti.AGENDA == []
