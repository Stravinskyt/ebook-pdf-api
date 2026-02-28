import os
import base64
from io import BytesIO
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import ListFlowable, ListItem
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

app = FastAPI(title="Ebook PDF Generator API", version="2.0.0")

API_KEY = os.getenv("API_KEY", "")

class Chapter(BaseModel):
    title: str
    content: str

class EbookRequest(BaseModel):
    title: str
    subtitle: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = "pt-BR"
    page_size: Optional[str] = "A4"
    chapters: List[Chapter]

def get_page_size(size):
    return A4 if size == "A4" else letter

@app.post("/generate-ebook-pdf")
def generate_ebook_pdf(payload: EbookRequest, authorization: str = Header(default="")):

    if API_KEY:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.replace("Bearer ", "").strip()
        if token != API_KEY:
            raise HTTPException(status_code=403, detail="Invalid token")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=get_page_size(payload.page_size),
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    elements = []

    # ===== CAPA =====
    title_style = ParagraphStyle(
        name="TitleStyle",
        parent=styles["Heading1"],
        fontSize=26,
        spaceAfter=20,
        textColor=colors.HexColor("#1F3C88")
    )

    subtitle_style = ParagraphStyle(
        name="SubtitleStyle",
        parent=styles["Normal"],
        fontSize=14,
        textColor=colors.grey
    )

    author_style = ParagraphStyle(
        name="AuthorStyle",
        parent=styles["Normal"],
        fontSize=12,
        spaceBefore=40,
        textColor=colors.black
    )

    elements.append(Spacer(1, 6*cm))
    elements.append(Paragraph(payload.title, title_style))

    if payload.subtitle:
        elements.append(Paragraph(payload.subtitle, subtitle_style))

    if payload.author:
        elements.append(Paragraph(f"Autor: {payload.author}", author_style))

    elements.append(PageBreak())

    # ===== SUMÁRIO =====
    elements.append(Paragraph("Sumário", styles["Heading2"]))
    elements.append(Spacer(1, 0.5*cm))

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            fontSize=12,
            name='TOCHeading1',
            leftIndent=20,
            firstLineIndent=-20,
            spaceBefore=5
        )
    ]
    elements.append(toc)
    elements.append(PageBreak())

    # ===== CAPÍTULOS =====
    chapter_style = ParagraphStyle(
        name="ChapterTitle",
        parent=styles["Heading2"],
        fontSize=18,
        spaceAfter=10,
        textColor=colors.HexColor("#0A1F44")
    )

    body_style = ParagraphStyle(
        name="BodyTextPremium",
        parent=styles["Normal"],
        fontSize=12,
        leading=18,
        spaceAfter=12
    )

    for i, ch in enumerate(payload.chapters, start=1):
        chapter_title = f"Capítulo {i}: {ch.title}"
        elements.append(Paragraph(chapter_title, chapter_style))
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph(ch.content.replace("\n", "<br/>"), body_style))
        elements.append(PageBreak())

    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"{payload.title} — Página {page_num}"
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(19*cm, 1*cm, text)

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
