import os
import base64
from io import BytesIO
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.doctemplate import BaseDocTemplate, Frame, PageTemplate
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4, letter

app = FastAPI(title="Ebook PDF Generator API", version="3.0.0")

API_KEY = os.getenv("API_KEY", "")

class Chapter(BaseModel):
    title: str
    content: str

class EbookRequest(BaseModel):
    title: str
    subtitle: Optional[str] = None
    author: Optional[str] = None
    page_size: Optional[str] = "A4"
    chapters: List[Chapter]

def get_page_size(size):
    return A4 if size == "A4" else letter


@app.post("/generate-ebook-pdf")
def generate_ebook_pdf(payload: EbookRequest, authorization: str = Header(default="")):

    # 🔐 Autenticação
    if API_KEY:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.replace("Bearer ", "").strip()
        if token != API_KEY:
            raise HTTPException(status_code=403, detail="Invalid token")

    buffer = BytesIO()
    pagesize = get_page_size(payload.page_size)

    doc = BaseDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id='normal')

    template = PageTemplate(id='template', frames=frame)
    doc.addPageTemplates([template])

    styles = getSampleStyleSheet()
    elements = []

    # ========================
    # CAPA
    # ========================

    from reportlab.pdfgen import canvas  # se ainda não tiver
# ...

PRIMARY = colors.HexColor("#0B1F3A")
ACCENT  = colors.HexColor("#1F3C88")
TEXT    = colors.HexColor("#2E2E2E")
MUTED   = colors.HexColor("#6B7280")
LINE    = colors.HexColor("#CBD5E1")

# CAPA (antes do PageBreak)
elements.append(Spacer(1, 4.5 * cm))

# faixa visual
band = Paragraph(
    f"""
    <para backColor="{PRIMARY.hexval()}" leftIndent="12" rightIndent="12"
          spaceBefore="0" spaceAfter="0">
      <font color="white" size="22"><b>{payload.title}</b></font><br/>
      <font color="{LINE.hexval()}" size="12">{payload.subtitle or ""}</font>
    </para>
    """,
    ParagraphStyle("CoverBand", parent=styles["Normal"], leading=18)
)
elements.append(band)

elements.append(Spacer(1, 1.2 * cm))

if payload.author:
    elements.append(Paragraph(f"<font color='{MUTED.hexval()}' size='11'>Autor: {payload.author}</font>", styles["Normal"]))

elements.append(Spacer(1, 0.6 * cm))
elements.append(Paragraph(f"<font color='{LINE.hexval()}' size='10'>Versão editorial • PDF profissional</font>", styles["Normal"]))

elements.append(band)

elements.append(Spacer(1, 1.2 * cm))

if payload.author:
    elements.append(Paragraph(f"<font color='{MUTED.hexval()}' size='11'>Autor: {payload.author}</font>", styles["Normal"]))

elements.append(Spacer(1, 0.6 * cm))
elements.append(Paragraph(f"<font color='{LINE.hexval()}' size='10'>Versão editorial • PDF profissional</font>", styles["Normal"]))

    elements.append(PageBreak())

    # ========================
    # SUMÁRIO
    # ========================
    elements.append(Paragraph("Sumário", styles["Heading2"]))
    elements.append(Spacer(1, 0.5 * cm))

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCHeading1",
            fontSize=11,
            textColor=colors.HexColor("#0B1F3A"),
            leftIndent=14,
            firstLineIndent=-14,
            spaceBefore=6,
        )
    ]

    elements.append(toc)
    elements.append(PageBreak())

    # ========================
    # ESTILO CAPÍTULOS
    # ========================

    chapter_style = ParagraphStyle(
        name="ChapterTitle",
        parent=styles["Heading2"],
        fontSize=20,
        textColor=colors.HexColor("#0A1F44"),
        spaceAfter=12
    )

    body_style = ParagraphStyle(
        name="BodyStyle",
        parent=styles["Normal"],
        fontSize=12,
        leading=20,
        spaceAfter=12
    )

    # ========================
    # CAPÍTULOS COM REGISTRO NO TOC
    # ========================

    for i, ch in enumerate(payload.chapters, start=1):

        chapter_title = f"Capítulo {i}: {ch.title}"

        heading = Paragraph(chapter_title, chapter_style)
        elements.append(heading)
        elements.append(Spacer(1, 0.5 * cm))

        elements.append(Paragraph(ch.content.replace("\n", "<br/>"), body_style))
        elements.append(PageBreak())

        # Registrar no TOC
        heading._bookmarkName = chapter_title

    # ========================
    # NUMERAÇÃO
    # ========================

  def add_header_footer(canvas, doc):
    w, h = doc.pagesize
    canvas.saveState()

    # Linha fina no topo
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(0.6)
    canvas.line(2.5*cm, h - 2.0*cm, w - 2.5*cm, h - 2.0*cm)

    # Cabeçalho: título curto
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(2.5*cm, h - 1.7*cm, (payload.title[:70] + "…") if len(payload.title) > 70 else payload.title)

    # Rodapé: página
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(w - 2.5*cm, 1.5*cm, f"Página {canvas.getPageNumber()}")

    canvas.restoreState()
              # CHAMA A GERAÇÃO DO PDF COM CABEÇALHO/RODAPÉ
    doc.build(elements, onLaterPages=add_header_footer)

    pdf_bytes = buffer.getvalue()
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    return {
        "openaiFileResponse": [
            {
                "name": "ebook_premium.pdf",
                "mime_type": "application/pdf",
                "content": b64
            }
        ]
