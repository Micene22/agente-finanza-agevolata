"""Test del grafo LangGraph con un LLM simulato: nessuna chiamata a Gemini, nessun costo.

Verifica il flusso completo: l'LLM chiede uno strumento, il codice calcola, la bozza si ferma
in attesa del consulente (interrupt) e riparte con la sua decisione (Command(resume=...)).
"""
import uuid

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command

import agente


class LLMSimulato:
    """Restituisce in ordine le risposte preparate, come farebbe Gemini."""

    def __init__(self, risposte):
        self.risposte = list(risposte)
        self.chiamate = []

    def invoke(self, messaggi):
        self.chiamate.append(messaggi)
        return self.risposte.pop(0)


@pytest.fixture
def config():
    return {"configurable": {"thread_id": f"test-{uuid.uuid4()}"}}


def prepara_llm(monkeypatch):
    llm = LLMSimulato([
        AIMessage(content="", tool_calls=[{"name": "calcola_contributo", "id": "call-1",
                                           "args": {"bando_id": "DIGI-PMI", "spesa": 8000}}]),
        AIMessage(content="Potete ottenere 4.000 euro dal Voucher Digitalizzazione PMI."),
    ])
    monkeypatch.setattr(agente, "llm_con_strumenti", llm)
    return llm


def test_la_bozza_si_ferma_in_attesa_del_consulente(monkeypatch, config):
    llm = prepara_llm(monkeypatch)
    risultato = agente.agente.invoke({"messages": [("user", "Quanto prendo su DIGI-PMI con 8000 euro?")]}, config)

    # il grafo e' in pausa: nessuna risposta parte senza approvazione
    assert "__interrupt__" in risultato
    assert "4.000 euro" in risultato["__interrupt__"][0].value["bozza"]

    # il risultato dello strumento e' tornato all'LLM: il calcolo l'ha fatto il codice
    risultato_strumento = [m for m in llm.chiamate[1] if m.type == "tool"][-1]
    assert '"contributo": 4000.0' in risultato_strumento.content


def test_bozza_approvata_diventa_la_risposta(monkeypatch, config):
    prepara_llm(monkeypatch)
    agente.agente.invoke({"messages": [("user", "Quanto prendo su DIGI-PMI con 8000 euro?")]}, config)

    finale = agente.agente.invoke(Command(resume={"approvata": True}), config)
    assert "__interrupt__" not in finale
    assert finale["messages"][-1].content == "Potete ottenere 4.000 euro dal Voucher Digitalizzazione PMI."


def test_bozza_corretta_dal_consulente_sostituisce_quella_dell_llm(monkeypatch, config):
    prepara_llm(monkeypatch)
    agente.agente.invoke({"messages": [("user", "Quanto prendo su DIGI-PMI con 8000 euro?")]}, config)

    testo = "Vi ricontattiamo noi con il dettaglio della pratica."
    finale = agente.agente.invoke(Command(resume={"approvata": False, "testo": testo}), config)
    assert finale["messages"][-1].content == testo
    # la bozza non approvata non resta nella conversazione
    assert all("4.000 euro" not in str(m.content) for m in finale["messages"] if m.type == "ai")
