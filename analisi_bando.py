"""Analisi di un bando reale: dal PDF a una scheda strutturata e alla verifica dei requisiti.

Flusso:  PDF -> testo (con numeri di pagina) -> LLM compila SchedaBando
         SchedaBando + profilo azienda -> LLM compila Verifica
         Il contributo lo calcola il codice (stima_contributo), non l'LLM.
"""
import io
import os
import warnings
from typing import Literal, Optional

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from pypdf import PdfReader

load_dotenv()
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

# Limite di sicurezza per la quota gratuita (circa 150.000 token)
MAX_CARATTERI = 600_000

llm = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL"), temperature=0)


# --- 1. Lettura del documento ------------------------------------------------
def estrai_testo(nome_file: str, contenuto: bytes) -> tuple[str, int]:
    """Restituisce il testo del bando e il numero di pagine.

    Ogni pagina e' preceduta da [Pagina N]: cosi' l'LLM puo' citare la fonte.
    """
    if nome_file.lower().endswith(".pdf"):
        lettore = PdfReader(io.BytesIO(contenuto))
        pagine = [f"[Pagina {i}]\n{p.extract_text() or ''}" for i, p in enumerate(lettore.pages, start=1)]
        return "\n\n".join(pagine), len(pagine)
    if nome_file.lower().endswith(".docx"):
        from docx import Document
        doc = Document(io.BytesIO(contenuto))
        return "\n".join(par.text for par in doc.paragraphs), 1
    return contenuto.decode("utf-8", errors="ignore"), 1


# --- 2. La scheda del bando (output strutturato) -----------------------------
# Le descrizioni dei campi sono istruzioni per l'LLM: Pydantic le trasforma in
# uno schema JSON e Gemini e' obbligato a rispondere con quella forma.
class Requisito(BaseModel):
    testo: str = Field(description="Il requisito, riassunto in una frase chiara")
    fonte: str = Field(description="Dove si trova nel bando, es. 'Art. 4, pag. 6'")


class SchedaBando(BaseModel):
    nome: str = Field(description="Nome ufficiale del bando o avviso")
    ente: str = Field(description="Ente che gestisce il bando (es. Invitalia, Regione...)")
    obiettivo: str = Field(description="A cosa serve il bando, in 2-3 frasi")
    beneficiari: list[str] = Field(description="Chi puo' partecipare (tipo di impresa, eta', forma giuridica...)")
    territori: list[str] = Field(description="Regioni o aree ammesse; ['Tutta Italia'] se non ci sono limiti")
    requisiti: list[Requisito] = Field(description="Tutti i requisiti di ammissibilita' del beneficiario")
    spese_ammissibili: list[str] = Field(description="Le categorie di spesa finanziabili")
    spese_escluse: list[str] = Field(description="Spese esplicitamente non finanziabili")
    agevolazione: str = Field(description="Forma e intensita' dell'aiuto (fondo perduto, finanziamento, voucher...)")
    percentuale_fondo_perduto: Optional[float] = Field(
        default=None, description="Percentuale principale di contributo a fondo perduto sulla spesa, es. 50. Null se non indicata")
    massimale_euro: Optional[float] = Field(default=None, description="Contributo massimo in euro. Null se non indicato")
    spesa_minima_euro: Optional[float] = Field(default=None, description="Investimento minimo in euro. Null se non indicato")
    scadenza: str = Field(description="Scadenza o finestra di presentazione delle domande; 'non indicata' se manca")
    documenti_richiesti: list[str] = Field(description="Documenti e allegati da presentare con la domanda")
    criteri_valutazione: list[str] = Field(description="Criteri di valutazione o punteggio, se presenti")
    punti_di_attenzione: list[str] = Field(description="Clausole insidiose, divieti di cumulo, obblighi successivi")


ISTRUZIONI_SCHEDA = (
    "Sei un consulente esperto di finanza agevolata. Leggi il bando qui sotto e compila la scheda. "
    "Usa SOLO informazioni presenti nel testo: se un dato manca scrivi 'non indicato' o lascia null. "
    "Per ogni requisito indica la fonte (articolo e pagina, usando i segnaposto [Pagina N]). "
    "Scrivi in italiano.\n\nTESTO DEL BANDO:\n"
)


def analizza_bando(testo: str) -> SchedaBando:
    """Una sola chiamata all'LLM: il bando intero entra nel contesto (niente RAG per l'MVP)."""
    estrattore = llm.with_structured_output(SchedaBando)
    return estrattore.invoke(ISTRUZIONI_SCHEDA + testo[:MAX_CARATTERI])


# --- 3. Verifica dei requisiti per un'azienda --------------------------------
class EsitoRequisito(BaseModel):
    requisito: str
    esito: Literal["soddisfatto", "non soddisfatto", "da verificare"]
    motivazione: str = Field(description="Perche', in una frase, citando i dati dell'azienda")


class Verifica(BaseModel):
    esiti: list[EsitoRequisito] = Field(description="Un esito per OGNI requisito della scheda")
    giudizio: Literal["ammissibile", "non ammissibile", "da approfondire"]
    sintesi: str = Field(description="Giudizio complessivo in 3-4 frasi, per il cliente")
    spese_finanziabili_del_progetto: list[str] = Field(
        description="Quali spese del progetto dell'azienda rientrano tra quelle ammissibili")
    prossimi_passi: list[str] = Field(description="Cosa deve fare l'azienda, in ordine")


ISTRUZIONI_VERIFICA = (
    "Sei un consulente di finanza agevolata. Confronta il profilo dell'azienda con la scheda del bando. "
    "Per ogni requisito scegli: 'soddisfatto' solo se i dati dell'azienda lo dimostrano, "
    "'non soddisfatto' se lo contraddicono, 'da verificare' se mancano informazioni. "
    "Non inventare dati sull'azienda. Non calcolare importi: li calcola il sistema. Scrivi in italiano."
)


def verifica_azienda(scheda: SchedaBando, profilo: dict) -> Verifica:
    valutatore = llm.with_structured_output(Verifica)
    richiesta = (
        f"{ISTRUZIONI_VERIFICA}\n\nSCHEDA DEL BANDO:\n{scheda.model_dump_json(indent=2)}"
        f"\n\nPROFILO DELL'AZIENDA:\n{profilo}"
    )
    return valutatore.invoke(richiesta)


# --- 4. Il calcolo lo fa il codice, non l'LLM -----------------------------
def stima_contributo(scheda: SchedaBando, spesa: float) -> dict:
    """Stessa regola di calcola_contributo: percentuale sulla spesa, tetto al massimale."""
    if scheda.percentuale_fondo_perduto is None:
        return {"calcolabile": False, "motivo": "Il bando non indica una percentuale semplice: serve il consulente."}
    if scheda.spesa_minima_euro and spesa < scheda.spesa_minima_euro:
        return {"calcolabile": True, "ammissibile": False,
                "motivo": f"Spesa sotto il minimo di {scheda.spesa_minima_euro:,.0f} €"}
    contributo = spesa * scheda.percentuale_fondo_perduto / 100
    tetto = scheda.massimale_euro is not None and contributo > scheda.massimale_euro
    if tetto:
        contributo = scheda.massimale_euro
    return {"calcolabile": True, "ammissibile": True, "contributo": round(contributo, 2),
            "percentuale": scheda.percentuale_fondo_perduto, "massimale_applicato": tetto}
