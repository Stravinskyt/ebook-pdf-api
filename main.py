import os
import base64
from io import BytesIO
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, PageBreak, Frame, PageTemplate
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.doctemplate import BaseDocTemplate


app = FastAPI(title="Ebook PDF Generator API", version="4.0.0")

API_KEY = os.getenv("API_KEY", "").strip()


# =========================
# MODELS
# =========================
class Chapter(BaseModel):
    title: str
    content: str


class EbookRequest(BaseModel):
    title: str
    subtitle: Optional[str] = None
    author: Optional[str] = None
    page_size: Optional[str] = "A4"
    chapters: List[Chapter]


def get_page_size(size: str):
    return A4 if (size or "A4").upper() == "A4" else letter


def safe_text_to_paragraph_html(text: str) -> str:
    """
    Minimal conversion: newlines -> <br/> for ReportLab Paragraph.
    Avoid heavy HTML/Markdown. Keep it simple.
    """
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def strip_capitulo_prefix(title: str) -> str:
    """
    Avoid duplicated 'Capítulo X' if the GPT already sends it.
    """
    if not title:
        return ""
    t = title.strip()
    lower = t.lower()
    if lower.startswith("capítulo ") or lower.startswith("capitulo "):
        # Remove leading "Capítulo 1:" or "Capitulo 1 -"
        for sep in [":", "-", "–", "—"]:
            if sep in t:
                left, right = t.split(sep, 1)
                if left.lower().startswith(("capítulo", "capitulo")):
                    return right.strip()
        # If no separator, just return original title without the first word
        parts = t.split(" ", 1)
        return parts[1].strip() if len(parts) > 1 else t
    return t


# =========================
# PDF DOC TEMPLATE (TOC)
# =========================
class EbookDocTemplate(BaseDocTemplate):
    def __init__(self, *args, **kwargs):
        self.payload_title = kwargs.pop("payload_title", "")
        self.brand_color = kwargs.pop("brand_color", colors.HexColor("#0B1F3A"))
        self.muted_color = kwargs.pop("muted_color", colors.HexColor("#6B7280"))
        super().__init__(*args, **kwargs)
        self._last_bookmark = None

    def afterFlowable(self, flowable):
        """
        This is what makes TableOfContents work:
        whenever we add a heading paragraph with bookmark+level,
        we notify the TOC and create an outline entry.
        """
        if getattr(flowable, "_is_toc_heading", False):
            text = getattr(flowable, "_toc_text", None)
            level = getattr(flowable, "_toc_level", 0)
            key = getattr(flowable, "_bookmark_name", None)

            if text and key:
                # Notify TOC
                self.notify("TOCEntry", (level, text, self.page))
                # PDF outline/bookmark
                try:
                    self.canv.bookmarkPage(key)
                    self.canv.addOutlineEntry(text, key, level=level, closed=False)
                except Exception:
                    pass


# =========================
# ENDPOINT
# =========================
@app.post("/generate-ebook-pdf")
def generate_ebook_pdf(payload: EbookRequest, authorization: str = Header(default="")):
    # --- Auth (optional) ---
    if API_KEY:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.replace("Bearer ", "").strip()
        if token != API_KEY:
            raise HTTPException(status_code=403, detail="Invalid token")

    # --- Colors (corporate blue) ---
    PRIMARY = colors.HexColor("#0B1F3A")
    ACCENT = colors.HexColor("#1F3C88")
    TEXT = colors.HexColor("#2E2E2E")
    MUTED = colors.HexColor("#6B7280")
    LINE = colors.HexColor("#CBD5E1")

    buffer = BytesIO()
    pagesize = get_page_size(payload.page_size)

    doc = EbookDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        payload_title=payload.title or "",
        brand_color=PRIMARY,
        muted_color=MUTED,
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    template = PageTemplate(id="main", frames=[frame])
    doc.addPageTemplates([template])

    styles = getSampleStyleSheet()

    # --- Styles ---
    cover_band_style = ParagraphStyle(
        "CoverBand",
        parent=styles["Normal"],
        leading=18,
        spaceBefore=0,
        spaceAfter=0,
    )

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=28,
        textColor=ACCENT,
        spaceAfter=14,
    )

    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["Normal"],
        fontSize=13,
        leading=18,
        textColor=MUTED,
        spaceAfter=10,
    )

    small_muted = ParagraphStyle(
        "SmallMuted",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=MUTED,
    )

    chapter_style = ParagraphStyle(
        "ChapterTitle",
        parent=styles["Heading2"],
        fontSize=18,
        leading=22,
        textColor=PRIMARY,
        spaceBefore=8,
        spaceAfter=10,
    )

    body_style = ParagraphStyle(
        "BodyTextPremium",
        parent=styles["Normal"],
        fontSize=11.5,
        leading=18,
        textColor=TEXT,
        spaceAfter=10,
    )

    toc_header_style = ParagraphStyle(
        "TOCHeader",
        parent=styles["Heading2"],
        fontSize=16,
        leading=20,
        textColor=PRIMARY,
        spaceAfter=10,
    )

    # --- Build elements ---
    elements = []

    # =========================
    # COVER
    # =========================
    elements.append(Spacer(1, 4.0 * cm))

    # Band with background color (using Paragraph with backColor)
    subtitle_line = payload.subtitle or ""
    band_html = f"""
    <para backColor="{PRIMARY.hexval()}" leftIndent="12" rightIndent="12" spaceBefore="10" spaceAfter="10">
      <font color="white" size="22"><b>{(payload.title or '').strip()}</b></font><br/>
      <font color="{LINE.hexval()}" size="12">{subtitle_line}</font>
    </para>
    """
    elements.append(Paragraph(band_html, cover_band_style))

    elements.append(Spacer(1, 1.0 * cm))

    if payload.author:
        elements.append(Paragraph(f"<font color='{MUTED.hexval()}' size='11'>Autor: {payload.author}</font>", styles["Normal"]))

    elements.append(Spacer(1, 0.6 * cm))
    elements.append(Paragraph(f"<font color='{LINE.hexval()}' size='10'>Versão editorial • PDF profissional</font>", styles["Normal"]))

    elements.append(PageBreak())

    # =========================
    # TOC
    # =========================
    elements.append(Paragraph("Sumário", toc_header_style))
    elements.append(Spacer(1, 0.4 * cm))

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCLevel0",
            fontSize=11,
            leading=14,
            textColor=PRIMARY,
            leftIndent=14,
            firstLineIndent=-14,
            spaceBefore=6,
        )
    ]
    elements.append(toc)
    elements.append(PageBreak())

    # =========================
    # CHAPTERS
    # =========================
    for i, ch in enumerate(payload.chapters, start=1):
        clean_title = strip_capitulo_prefix(ch.title)
        chapter_title = f"Capítulo {i}: {clean_title}"

        # Create heading paragraph and mark it for TOC
        heading = Paragraph(chapter_title, chapter_style)
        heading._is_toc_heading = True
        heading._toc_text = chapter_title
        heading._toc_level = 0
        heading._bookmark_name = f"ch_{i}"

        elements.append(heading)
        elements.append(Spacer(1, 0.3 * cm))

        elements.append(Paragraph(safe_text_to_paragraph_html(ch.content), body_style))
        elements.append(PageBreak())

    # =========================
    # HEADER/FOOTER
    # =========================
    def add_header_footer(canvas, doc_):
        w, h = doc_.pagesize
        canvas.saveState()

        # top line
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(2.5 * cm, h - 2.0 * cm, w - 2.5 * cm, h - 2.0 * cm)

        # header title (trim)
        header_title = (payload.title or "").strip()
        if len(header_title) > 70:
            header_title = header_title[:70] + "…"

        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(MUTED)
        canvas.drawString(2.5 * cm, h - 1.7 * cm, header_title)

        # footer page
        canvas.setFillColor(MUTED)
        canvas.drawRightString(w - 2.5 * cm, 1.5 * cm, f"Página {canvas.getPageNumber()}")

        canvas.restoreState()

    doc.build(elements, onLaterPages=add_header_footer)

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
