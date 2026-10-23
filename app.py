"""Interfaccia web (Streamlit) dell'agente per la finanza agevolata.

Avvio:  .venv\\Scripts\\streamlit run app.py
"""
import uuid

import streamlit as st
from langgraph.types import Command

from agente import agente
from dati_finti import BANDI
from strumenti import AGENDA

st.set_page_config(page_title="Agente Finanza Agevolata", page_icon="💶", layout="wide")

# Streamlit riesegue TUTTO lo script a ogni clic: quello che deve sopravvivere
# tra un clic e l'altro va in st.session_state (qui: il numero della pratica)
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": st.session_state.thread_id}}

# Lo stato vero (messaggi, pausa in corso) lo leggiamo dal checkpointer di LangGraph
stato = agente.get_state(config)
messaggi = stato.values.get("messages", [])
in_attesa = bool(stato.interrupts)  # True se il grafo e' fermo in approvazione_consulente


def esegui(input_grafo):
    """Fa girare l'agente e mostra un errore leggibile se qualcosa va storto."""
    try:
        with st.spinner("L'agente sta lavorando..."):
            agente.invoke(input_grafo, config)
    except Exception as errore:  # es. quota gratuita finita (429)
        st.error(f"Errore: {str(errore)[:200]}")
        st.stop()
    st.rerun()  # ridisegna la pagina con lo stato aggiornato


# --- Barra laterale: bandi e agenda ------------------------------------------
with st.sidebar:
    st.header("📅 Agenda dello studio")
    if AGENDA:
        for p in AGENDA:
            st.markdown(f"**{p['id']}** · {p['azienda']} · {p['bando_id']}  \n{p['nota']} (scade {p['scadenza']})")
    else:
        st.caption("Nessun promemoria")

    st.header("📋 Bandi (inventati)")
    for codice, bando in BANDI.items():
        st.markdown(f"**{codice}** · {bando['percentuale']}% fino a {bando['massimale']:,} €")

    if st.button("🗂️ Nuova pratica"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

st.title("💶 Agente Finanza Agevolata")
st.caption("Demo con dati inventati: non è una consulenza reale. Ogni risposta è approvata da un consulente.")

col_chat, col_consulente = st.columns([3, 2])

# --- Colonna sinistra: la chat vista dall'azienda ----------------------------
with col_chat:
    st.subheader("🏢 Chat con l'azienda")
    for i, m in enumerate(messaggi):
        bozza_non_approvata = in_attesa and i == len(messaggi) - 1
        if m.type == "human":
            st.chat_message("user").write(m.content)
        elif m.type == "ai" and m.tool_calls:
            for chiamata in m.tool_calls:
                st.caption(f"🔧 l'agente usa **{chiamata['name']}** {chiamata['args']}")
        elif m.type == "tool":
            with st.expander(f"risultato di {m.name}"):
                st.code(m.content)
        elif m.type == "ai" and not bozza_non_approvata:
            st.chat_message("assistant").write(m.text)

    domanda = st.chat_input("Scrivi come azienda...", disabled=in_attesa)
    if domanda:
        esegui({"messages": [("user", domanda)]})

# --- Colonna destra: il pannello del consulente (human-in-the-loop) ----------
with col_consulente:
    st.subheader("🧑‍💼 Consulente")
    if in_attesa:
        bozza = stato.interrupts[0].value["bozza"]
        st.warning("Bozza in attesa di approvazione")
        testo = st.text_area("Puoi modificarla prima di inviarla:", value=bozza, height=300)
        if st.button("✅ Approva e invia", type="primary"):
            if testo == bozza:
                esegui(Command(resume={"approvata": True}))
            else:
                esegui(Command(resume={"approvata": False, "testo": testo}))
    else:
        st.info("Nessuna bozza da approvare. Le risposte dell'agente arriveranno qui prima di essere inviate.")
