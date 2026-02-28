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

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor("#1F3C88"),
        spaceAfter=20,
    )

    elements.append(Spacer(1, 6 * cm))
    elements.append(Paragraph(payload.title, title_style))

    if payload.subtitle:
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph(payload.subtitle, styles["Normal"]))

    if payload.author:
        elements.append(Spacer(1, 2 * cm))
        elements.append(Paragraph(f"Autor: {payload.author}", styles["Normal"]))

    elements.append(PageBreak())

    # ========================
    # SUMÁRIO REAL
    # ========================

    elements.append(Paragraph("Sumário", styles["Heading2"]))
    elements.append(Spacer(1, 0.5 * cm))

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name='TOCHeading1',
            fontSize=12,
            leftIndent=20,
            firstLineIndent=-20,
            spaceBefore=5
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

    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"{payload.title} — Página {page_num}"
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(doc.pagesize[0] - 2 * cm, 1.5 * cm, text)

    doc.build(elements, onLaterPages=add_page_number)

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
    }
