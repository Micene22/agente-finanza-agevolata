"""Test dell'analisi bandi senza chiamare Gemini: scheda e verifica sono costruite a mano."""
import io

from docx import Document

from analisi_bando import EsitoRequisito, Requisito, SchedaBando, Verifica, estrai_testo, stima_contributo
from documento import crea_relazione, euro


def scheda_di_prova(**modifiche):
    dati = dict(
        nome="Bando di prova", ente="Regione", obiettivo="Digitalizzazione", beneficiari=["PMI"],
        territori=["Sicilia"], requisiti=[Requisito(testo="Sede in Sicilia", fonte="Art. 3, pag. 2")],
        spese_ammissibili=["Software"], spese_escluse=["Opere murarie"], agevolazione="Fondo perduto",
        percentuale_fondo_perduto=60, massimale_euro=50_000, spesa_minima_euro=20_000,
        scadenza="31/03/2027", documenti_richiesti=["DURC"], criteri_valutazione=[], punti_di_attenzione=[],
    )
    dati.update(modifiche)
    return SchedaBando(**dati)


def test_stima_sotto_il_massimale():
    assert stima_contributo(scheda_di_prova(), 30_000)["contributo"] == 18_000


def test_stima_limitata_al_massimale():
    stima = stima_contributo(scheda_di_prova(), 120_000)
    assert stima["contributo"] == 50_000 and stima["massimale_applicato"]


def test_stima_sotto_la_spesa_minima():
    assert stima_contributo(scheda_di_prova(), 10_000)["ammissibile"] is False


def test_stima_senza_percentuale_lascia_decidere_il_consulente():
    assert stima_contributo(scheda_di_prova(percentuale_fondo_perduto=None), 30_000)["calcolabile"] is False


def test_estrai_testo_txt():
    testo, pagine = estrai_testo("bando.txt", "Art. 1 - Finalità".encode("utf-8"))
    assert "Finalità" in testo and pagine == 1


def test_euro_formato_italiano():
    assert euro(12345.5) == "12.345,50 €"


def test_relazione_word_contiene_i_dati():
    scheda = scheda_di_prova()
    verifica = Verifica(
        esiti=[EsitoRequisito(requisito="Sede in Sicilia", esito="soddisfatto", motivazione="Sede a Palermo")],
        giudizio="ammissibile", sintesi="Tutto in regola.", spese_finanziabili_del_progetto=["Software"],
        prossimi_passi=["Raccogliere i preventivi"],
    )
    profilo = dict(ragione_sociale="Rossi S.r.l.", regione="Sicilia", forma_giuridica="S.r.l.", dimensione="micro",
                   settore="71.12", anno_costituzione=2020, progetto="Software BIM", spesa=30_000.0)
    contenuto = crea_relazione(scheda, profilo, verifica, stima_contributo(scheda, 30_000), "Nota", "Studio X")
    doc = Document(io.BytesIO(contenuto))
    testo = "\n".join(p.text for p in doc.paragraphs)
    celle = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "Relazione di pre-fattibilità" in testo
    assert "18.000,00 €" in testo
    assert "Rossi S.r.l." in celle and "Art. 3, pag. 2" in celle
