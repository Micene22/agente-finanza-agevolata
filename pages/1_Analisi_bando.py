"""Pagina 2: analisi di un bando reale e relazione di pre-fattibilita' in Word.

Tre passi, e il consulente ha l'ultima parola (human-in-the-loop):
  1. carica il bando  -> l'AI compila la scheda
  2. profilo azienda  -> l'AI verifica i requisiti, il codice calcola il contributo
  3. il consulente corregge e approva -> si genera la relazione .docx
"""
import hashlib
from datetime import date

import pandas as pd
import streamlit as st

from analisi_bando import EsitoRequisito, Verifica, analizza_bando, estrai_testo, stima_contributo, verifica_azienda
from documento import crea_relazione, euro

st.set_page_config(page_title="Analisi bando", page_icon="📄", layout="wide")

REGIONI = ["Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia-Romagna", "Friuli-Venezia Giulia", "Lazio",
           "Liguria", "Lombardia", "Marche", "Molise", "Piemonte", "Puglia", "Sardegna", "Sicilia", "Toscana",
           "Trentino-Alto Adige", "Umbria", "Valle d'Aosta", "Veneto"]
ESITI = ["soddisfatto", "non soddisfatto", "da verificare"]

ss = st.session_state  # abbreviazione: qui vive tutto cio' che deve sopravvivere ai clic


def chiama_ai(funzione, *argomenti, messaggio="L'AI sta lavorando..."):
    """Esegue una chiamata all'LLM e mostra un errore leggibile (es. quota 429)."""
    try:
        with st.spinner(messaggio):
            return funzione(*argomenti)
    except Exception as errore:
        st.error(f"Errore: {str(errore)[:300]}")
        st.stop()


with st.sidebar:
    studio = st.text_input("Nome dello studio", value="Studio di consulenza")
    if st.button("🗂️ Nuova analisi"):
        ss.clear()
        st.rerun()

st.title("📄 Analisi bando e relazione di pre-fattibilità")
st.caption("MVP: l'AI legge il bando e prepara la bozza, il consulente verifica e firma.")

# --- PASSO 1: il bando -------------------------------------------------------
st.header("1. Carica il bando")
file = st.file_uploader("Avviso pubblico (PDF, DOCX o TXT)", type=["pdf", "docx", "txt"])

if file:
    contenuto = file.getvalue()
    impronta = hashlib.md5(contenuto).hexdigest()  # stesso file = non rianalizzo (risparmio quota)
    if ss.get("impronta") != impronta:
        testo, pagine = estrai_testo(file.name, contenuto)
        ss.update(impronta=impronta, testo=testo, pagine=pagine, scheda=None, verifica=None)
    st.caption(f"{ss.pagine} pagine · {len(ss.testo):,} caratteri letti".replace(",", "."))
    if len(ss.testo.strip()) < 200:
        st.warning("Ho letto pochissimo testo: forse il PDF è una scansione (immagine). Serve un PDF con testo.")
    if ss.scheda is None and st.button("🔍 Analizza il bando", type="primary"):
        ss.scheda = chiama_ai(analizza_bando, ss.testo, messaggio="Sto leggendo il bando...")
        st.rerun()

scheda = ss.get("scheda")
if scheda:
    st.success(f"**{scheda.nome}** · {scheda.ente}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fondo perduto", f"{scheda.percentuale_fondo_perduto:g}%" if scheda.percentuale_fondo_perduto else "n.d.")
    c2.metric("Massimale", euro(scheda.massimale_euro, 0) if scheda.massimale_euro else "n.d.")
    c3.metric("Spesa minima", euro(scheda.spesa_minima_euro, 0) if scheda.spesa_minima_euro else "n.d.")
    c4.metric("Scadenza", scheda.scadenza[:25])
    st.write(scheda.obiettivo)
    with st.expander("📋 Scheda completa del bando"):
        st.markdown("**Agevolazione:** " + scheda.agevolazione)
        st.markdown("**Territori:** " + ", ".join(scheda.territori))
        for titolo, voci in [("Beneficiari", scheda.beneficiari), ("Spese ammissibili", scheda.spese_ammissibili),
                             ("Spese escluse", scheda.spese_escluse), ("Documenti richiesti", scheda.documenti_richiesti),
                             ("Criteri di valutazione", scheda.criteri_valutazione),
                             ("Punti di attenzione", scheda.punti_di_attenzione)]:
            st.markdown(f"**{titolo}**\n" + "\n".join(f"- {v}" for v in voci or ["non indicato"]))
        st.markdown("**Requisiti**")
        st.dataframe(pd.DataFrame([r.model_dump() for r in scheda.requisiti]), hide_index=True, width="stretch")

    # --- PASSO 2: l'azienda --------------------------------------------------
    st.header("2. Profilo dell'azienda")
    with st.form("form_profilo"):  # nome diverso da ss.profilo: Streamlit non accetta due chiavi uguali
        a, b = st.columns(2)
        profilo = {
            "ragione_sociale": a.text_input("Ragione sociale", "Rossi Ingegneria S.r.l."),
            "regione": b.selectbox("Regione della sede operativa", REGIONI, index=REGIONI.index("Sicilia")),
            "forma_giuridica": a.selectbox("Forma giuridica", ["S.r.l.", "S.r.l.s.", "S.p.A.", "S.n.c.", "S.a.s.",
                                                                "Ditta individuale", "Libero professionista",
                                                                "Cooperativa", "Da costituire"]),
            "dimensione": b.selectbox("Dimensione", ["micro", "piccola", "media", "grande"]),
            "settore": a.text_input("Settore / codice ATECO", "71.12 - Attività degli studi d'ingegneria"),
            "anno_costituzione": b.number_input("Anno di costituzione", 1950, date.today().year + 1, 2020),
            "dipendenti": a.number_input("Dipendenti", 0, 10_000, 8),
            "eta_titolari": b.text_input("Età dei soci/titolari (se rilevante)", "34, 41"),
            "progetto": st.text_area("Progetto da finanziare",
                                     "Acquisto di software BIM e droni per rilievi, formazione del personale "
                                     "e ammodernamento della sede."),
            "spesa": st.number_input("Investimento previsto (€)", 0.0, 100_000_000.0, 120_000.0, step=5_000.0),
            "altre_info": st.text_area("Altre informazioni utili (DURC, aiuti già ricevuti, fatturato...)", ""),
        }
        if st.form_submit_button("✅ Verifica i requisiti", type="primary"):
            ss.profilo, ss.docx = profilo, None
            ss.verifica = chiama_ai(verifica_azienda, scheda, profilo, messaggio="Verifico i requisiti...")
            ss.stima = stima_contributo(scheda, profilo["spesa"])  # calcolo deterministico, niente AI
            st.rerun()

# --- PASSO 3: il consulente rivede e approva ---------------------------------
verifica = ss.get("verifica")
if scheda and verifica:
    st.header("3. Revisione del consulente")
    stima = ss.stima
    if stima.get("contributo") is not None:
        st.metric("Contributo stimato (calcolato dal codice)", euro(stima["contributo"]),
                  help="Percentuale del bando × investimento, limitato al massimale")
    elif stima.get("motivo"):
        st.info(stima["motivo"])

    st.write("Correggi gli esiti se l'AI ha sbagliato: nella relazione finisce **la tua** versione.")
    tabella = st.data_editor(
        pd.DataFrame([e.model_dump() for e in verifica.esiti]),
        column_config={
            "requisito": st.column_config.TextColumn("Requisito", disabled=True, width="large"),
            "esito": st.column_config.SelectboxColumn("Esito", options=ESITI, required=True),
            "motivazione": st.column_config.TextColumn("Motivazione", width="large"),
        },
        hide_index=True, width="stretch", key="esiti",
    )
    giudizio = st.selectbox("Giudizio complessivo", ["ammissibile", "non ammissibile", "da approfondire"],
                            index=["ammissibile", "non ammissibile", "da approfondire"].index(verifica.giudizio))
    sintesi = st.text_area("Sintesi per il cliente", verifica.sintesi, height=120)
    note = st.text_area("Note del consulente (finiscono nella relazione)", "")

    if st.button("📝 Approva e genera la relazione", type="primary"):
        verifica_approvata = Verifica(
            esiti=[EsitoRequisito(**riga) for riga in tabella.to_dict("records")],
            giudizio=giudizio, sintesi=sintesi,
            spese_finanziabili_del_progetto=verifica.spese_finanziabili_del_progetto,
            prossimi_passi=verifica.prossimi_passi,
        )
        ss.docx = crea_relazione(scheda, ss.profilo, verifica_approvata, stima, note, studio)

    if ss.get("docx"):
        nome = f"Prefattibilita_{ss.profilo['ragione_sociale'].replace(' ', '_')}.docx"
        st.download_button("⬇️ Scarica la relazione (Word)", ss.docx, file_name=nome,
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
