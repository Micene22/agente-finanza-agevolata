"""Agente LangGraph per la finanza agevolata (demo con dati inventati)."""
import os
import warnings

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt

from strumenti import calcola_contributo, cerca_bandi, crea_promemoria

load_dotenv()  # carica GOOGLE_API_KEY e GEMINI_MODEL dal file .env
# alcuni modelli (es. flash-lite) ignorano temperature: nascondo l'avviso ripetuto
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

# --- 1. Gli strumenti e il modello -------------------------------------------
STRUMENTI = [cerca_bandi, calcola_contributo, crea_promemoria]

llm = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL"), temperature=0)
llm_con_strumenti = llm.bind_tools(STRUMENTI)

ISTRUZIONI = SystemMessage(
    "Sei l'assistente di uno studio di consulenza in finanza agevolata. "
    "Aiuti le imprese a capire quali contributi possono ottenere. "
    "Per trovare i bandi adatti usa cerca_bandi: se ti mancano regione, dimensione "
    "o settore dell'impresa, chiedili prima di cercare. "
    "Non fare MAI calcoli a mente: usa sempre lo strumento calcola_contributo. "
    "Se un bando e' urgente, segnalalo chiaramente e proponi di creare un promemoria "
    "con crea_promemoria. "
    "Rispondi in italiano, in modo breve e chiaro."
)


# --- 2. I nodi del grafo -----------------------------------------------------
def consulente(state: MessagesState):
    """Nodo che chiama l'LLM: decide se rispondere o usare uno strumento."""
    risposta = llm_con_strumenti.invoke([ISTRUZIONI] + state["messages"])
    return {"messages": [risposta]}


nodo_strumenti = ToolNode(STRUMENTI)  # esegue gli strumenti chiesti dall'LLM


def approvazione_consulente(state: MessagesState):
    """Human-in-the-loop: il grafo si ferma finche' il consulente non decide."""
    bozza = state["messages"][-1]

    # interrupt() mette in PAUSA il grafo e restituisce la bozza a chi lo sta usando.
    # Quando si riprende con Command(resume=...), quel valore finisce in "decisione".
    decisione = interrupt({"bozza": bozza.text})

    if decisione["approvata"]:
        return {}  # nessuna modifica: la bozza diventa la risposta finale
    # stesso id della bozza -> MessagesState la SOSTITUISCE invece di aggiungerne una
    return {"messages": [AIMessage(content=decisione["testo"], id=bozza.id)]}


# --- 3. Il grafo: nodi + frecce ----------------------------------------------
grafo = StateGraph(MessagesState)
grafo.add_node("consulente", consulente)
grafo.add_node("strumenti", nodo_strumenti)
grafo.add_node("approvazione", approvazione_consulente)

grafo.add_edge(START, "consulente")
# se l'LLM ha chiesto uno strumento -> "strumenti", altrimenti la bozza va al consulente umano
grafo.add_conditional_edges("consulente", tools_condition, {"tools": "strumenti", END: "approvazione"})
grafo.add_edge("strumenti", "consulente")  # il risultato torna all'LLM
grafo.add_edge("approvazione", END)

# il checkpointer salva lo stato a ogni passo: serve per mettere in pausa e riprendere
# (e fa anche da memoria della conversazione, al posto della nostra lista)
agente = grafo.compile(checkpointer=InMemorySaver())


def stampa_passaggi(messaggi):
    """Mostra le chiamate agli strumenti fatte dall'agente in questo turno."""
    for messaggio in messaggi:
        if messaggio.type == "ai" and messaggio.tool_calls:
            for chiamata in messaggio.tool_calls:
                print("LLM CHIEDE:", chiamata["name"], chiamata["args"])
        elif messaggio.type == "tool":
            print("STRUMENTO :", messaggio.content)


def chiedi_decisione(bozza):
    """Mostra la bozza al consulente e raccoglie la sua decisione."""
    print("\n--- BOZZA DA APPROVARE ---------------------------------")
    print(bozza)
    print("--------------------------------------------------------")
    print("CONSULENTE: premi INVIO per approvare e inviare la bozza,")
    print("            oppure scrivi il testo da inviare AL POSTO della bozza.")
    scelta = input("CONSULENTE: ")
    if scelta.strip() == "":
        return {"approvata": True}
    return {"approvata": False, "testo": scelta}


if __name__ == "__main__":
    print("Chat con l'agente (scrivi 'esci' per uscire)\n")
    # ogni pratica ha il suo thread: il checkpointer ne ricorda la conversazione
    config = {"configurable": {"thread_id": "pratica-1"}}

    while True:
        domanda = input("AZIENDA   : ")
        if domanda.strip().lower() == "esci":
            break

        gia_visti = len(agente.get_state(config).values.get("messages", []))
        try:
            risultato = agente.invoke({"messages": [("user", domanda)]}, config)
            stampa_passaggi(risultato["messages"][gia_visti:])

            # il grafo si e' fermato in approvazione_consulente: aspetta l'umano
            while "__interrupt__" in risultato:
                bozza = risultato["__interrupt__"][0].value["bozza"]
                decisione = chiedi_decisione(bozza)
                risultato = agente.invoke(Command(resume=decisione), config)
        except Exception as errore:
            # es. quota gratuita finita (429) o server occupato (503)
            print("ERRORE    :", str(errore)[:200], "\n")
            continue

        print("\nINVIATA ALL'AZIENDA:", risultato["messages"][-1].text, "\n")
