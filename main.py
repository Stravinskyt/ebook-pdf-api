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


app = FastAPI(title="Ebook PDF Generator API", version="5.0.0")

API_KEY = os.getenv("API_KEY", "").strip()


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

    # Autenticação
    # if API_KEY:
#     if not authorization.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Missing Bearer token")
#     token = authorization.replace("Bearer ", "").strip()
#     if token != API_KEY:
#         raise HTTPException(status_code=403, detail="Invalid token")

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=get_page_size(payload.page_size),
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ================= CAPA =================
    title_style = ParagraphStyle(
        name="TitleStyle",
        parent=styles["Heading1"],
        fontSize=26,
        textColor=colors.HexColor("#0B1F3A"),
        spaceAfter=16,
    )

    elements.append(Spacer(1, 6 * cm))
    elements.append(Paragraph(payload.title, title_style))

    if payload.subtitle:
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph(payload.subtitle, styles["Normal"]))

    if payload.author:
        elements.append(Spacer(1, 1 * cm))
        elements.append(Paragraph(f"Autor: {payload.author}", styles["Normal"]))

    elements.append(PageBreak())

    # ================= SUMÁRIO =================
    elements.append(Paragraph("Sumário", styles["Heading2"]))
    elements.append(Spacer(1, 0.5 * cm))

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCLevel1",
            fontSize=11,
            leftIndent=20,
            firstLineIndent=-20,
            spaceBefore=5,
        )
    ]

    elements.append(toc)
    elements.append(PageBreak())

    # ================= CAPÍTULOS =================
    chapter_style = ParagraphStyle(
        name="ChapterTitle",
        parent=styles["Heading2"],
        fontSize=18,
        textColor=colors.HexColor("#0B1F3A"),
        spaceAfter=10,
    )

    body_style = ParagraphStyle(
        name="BodyTextPremium",
        parent=styles["Normal"],
        fontSize=11.5,
        leading=18,
        spaceAfter=10,
    )

    for i, ch in enumerate(payload.chapters, start=1):

        clean_title = ch.title.replace("Capítulo", "").strip()

        chapter_title = f"Capítulo {i}: {clean_title}"

        heading = Paragraph(chapter_title, chapter_style)
        heading._bookmarkName = f"ch_{i}"

        elements.append(heading)
        elements.append(Spacer(1, 0.3 * cm))

        content_html = ch.content.replace("\n", "<br/>")
        elements.append(Paragraph(content_html, body_style))

        elements.append(PageBreak())

    # ================= BUILD =================
    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    return {
        "openaiFileResponse": [
            {
                "name": "ebook_premium.pdf",
                "mime_type": "application/pdf",
                "content": b64,
            }
        ]
    }
