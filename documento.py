"""Genera la relazione di pre-fattibilita' in formato Word (.docx)."""
import io
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from analisi_bando import SchedaBando, Verifica

def euro(valore: float, decimali: int = 2) -> str:
    """12345.5 -> '12.345,50 €' (formato italiano)."""
    testo = f"{valore:,.{decimali}f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


SIMBOLI = {"soddisfatto": "✔ Soddisfatto", "non soddisfatto": "✘ Non soddisfatto", "da verificare": "? Da verificare"}


def _elenco(doc, voci):
    for voce in voci or ["Non indicato"]:
        doc.add_paragraph(voce, style="List Bullet")


def _tabella(doc, righe, intestazione=None):
    tabella = doc.add_table(rows=0, cols=len(righe[0]))
    tabella.style = "Light Grid Accent 1"
    if intestazione:
        celle = tabella.add_row().cells
        for cella, testo in zip(celle, intestazione):
            cella.text = testo
            cella.paragraphs[0].runs[0].bold = True
    for riga in righe:
        for cella, testo in zip(tabella.add_row().cells, riga):
            cella.text = str(testo)
    return tabella


def crea_relazione(scheda: SchedaBando, profilo: dict, verifica: Verifica,
                   stima: dict, note_consulente: str, studio: str) -> bytes:
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)

    # Intestazione
    titolo = doc.add_heading("Relazione di pre-fattibilità", level=0)
    titolo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"{scheda.nome}").alignment = WD_ALIGN_PARAGRAPH.CENTER
    _tabella(doc, [
        ("Cliente", profilo["ragione_sociale"]),
        ("Preparata da", studio),
        ("Data", date.today().strftime("%d/%m/%Y")),
        ("Esito della pre-analisi", verifica.giudizio.upper()),
    ])

    # 1. Sintesi
    doc.add_heading("1. Sintesi", level=1)
    doc.add_paragraph(verifica.sintesi)
    if stima.get("contributo") is not None:
        p = doc.add_paragraph()
        p.add_run(f"Contributo a fondo perduto stimato: {euro(stima['contributo'])}").bold = True

    # 2. Il bando
    doc.add_heading("2. Il bando in sintesi", level=1)
    _tabella(doc, [
        ("Ente", scheda.ente),
        ("Obiettivo", scheda.obiettivo),
        ("Agevolazione", scheda.agevolazione),
        ("Territori", ", ".join(scheda.territori)),
        ("Scadenza", scheda.scadenza),
    ])
    doc.add_heading("Beneficiari", level=2)
    _elenco(doc, scheda.beneficiari)
    doc.add_heading("Spese ammissibili", level=2)
    _elenco(doc, scheda.spese_ammissibili)
    doc.add_heading("Spese escluse", level=2)
    _elenco(doc, scheda.spese_escluse)

    # 3. L'azienda
    doc.add_heading("3. Profilo dell'azienda", level=1)
    _tabella(doc, [
        ("Ragione sociale", profilo["ragione_sociale"]),
        ("Sede", profilo["regione"]),
        ("Forma giuridica", profilo["forma_giuridica"]),
        ("Dimensione", profilo["dimensione"]),
        ("Settore / ATECO", profilo["settore"]),
        ("Anno di costituzione", profilo["anno_costituzione"]),
        ("Progetto", profilo["progetto"]),
        ("Investimento previsto", euro(profilo["spesa"], 0)),
    ])

    # 4. Requisiti
    doc.add_heading("4. Verifica dei requisiti", level=1)
    fonti = {r.testo: r.fonte for r in scheda.requisiti}
    _tabella(doc, [(e.requisito, SIMBOLI[e.esito], e.motivazione, fonti.get(e.requisito, "")) for e in verifica.esiti],
             intestazione=("Requisito", "Esito", "Motivazione", "Fonte nel bando"))
    doc.add_heading("Spese del progetto potenzialmente finanziabili", level=2)
    _elenco(doc, verifica.spese_finanziabili_del_progetto)

    # 5. Contributo
    doc.add_heading("5. Stima del contributo", level=1)
    if not stima.get("calcolabile"):
        doc.add_paragraph(stima["motivo"])
    elif not stima["ammissibile"]:
        doc.add_paragraph(f"Progetto non ammissibile: {stima['motivo']}.")
    else:
        testo = (f"Applicando il {stima['percentuale']:g}% all'investimento previsto di "
                 f"{euro(profilo['spesa'], 0)} si ottiene un contributo stimato di {euro(stima['contributo'])}")
        if stima["massimale_applicato"]:
            testo += " (limitato al massimale del bando)"
        doc.add_paragraph(testo + ". La stima va confermata in base alle singole voci di spesa ammesse.")

    # 6. Documenti e prossimi passi
    doc.add_heading("6. Documenti da preparare", level=1)
    _elenco(doc, scheda.documenti_richiesti)
    doc.add_heading("7. Prossimi passi", level=1)
    for passo in verifica.prossimi_passi:
        doc.add_paragraph(passo, style="List Number")
    if scheda.punti_di_attenzione:
        doc.add_heading("Punti di attenzione", level=2)
        _elenco(doc, scheda.punti_di_attenzione)

    # 8. Note del consulente (la parte umana)
    doc.add_heading("8. Note del consulente", level=1)
    doc.add_paragraph(note_consulente or "Nessuna nota aggiuntiva.")

    avviso = doc.add_paragraph(
        "Documento di pre-analisi preparato con il supporto di un assistente AI e verificato dal consulente. "
        "Non sostituisce la lettura integrale del bando né costituisce garanzia di ammissione al contributo.")
    avviso.runs[0].italic = True
    avviso.runs[0].font.size = Pt(9)
    avviso.runs[0].font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
