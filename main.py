import os
import base64
from io import BytesIO
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas

app = FastAPI(title="Ebook PDF Generator API", version="1.0.0")

API_KEY = os.getenv("API_KEY", "")

class Chapter(BaseModel):
    title: str
    content: str

class EbookRequest(BaseModel):
    title: str
    subtitle: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = "pt-BR"
    page_size: Optional[str] = "A4"  # A4 or LETTER
    chapters: List[Chapter]

def _pagesize(name: str):
    return A4 if (name or "").upper() == "A4" else letter

@app.post("/generate-ebook-pdf")
def generate_ebook_pdf(payload: EbookRequest, authorization: str = Header(default="")):
    # Simple API key auth (Bearer <key>)
    if API_KEY:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.replace("Bearer ", "").strip()
        if token != API_KEY:
            raise HTTPException(status_code=403, detail="Invalid token")

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=_pagesize(payload.page_size))
    width, height = _pagesize(payload.page_size)

    # Basic typography layout
    left = 48
    top = height - 64
    line_height = 14
    y = top

    def draw_line(text, font="Helvetica", size=11, extra_space=0):
        nonlocal y
        c.setFont(font, size)
        # wrap manually (simple)
        max_chars = 95 if width > 600 else 80
        words = text.split()
        line = ""
        for w in words:
            if len(line) + len(w) + 1 <= max_chars:
                line = (line + " " + w).strip()
            else:
                if y < 72:
                    c.showPage()
                    y = top
                c.drawString(left, y, line)
                y -= line_height
                line = w
        if line:
            if y < 72:
                c.showPage()
                y = top
            c.drawString(left, y, line)
            y -= (line_height + extra_space)

    # Cover-ish first page
    c.setFont("Helvetica-Bold", 20)
    c.drawString(left, y, payload.title)
    y -= 28

    if payload.subtitle:
        c.setFont("Helvetica", 13)
        c.drawString(left, y, payload.subtitle)
        y -= 22

    if payload.author:
        c.setFont("Helvetica-Oblique", 11)
        c.drawString(left, y, f"Autor: {payload.author}")
        y -= 18

    y -= 10
    draw_line("—" * 60, size=10, extra_space=8)

    # Chapters
    for i, ch in enumerate(payload.chapters, start=1):
        if y < 120:
            c.showPage()
            y = top

        c.setFont("Helvetica-Bold", 16)
        c.drawString(left, y, f"Capítulo {i}: {ch.title}")
        y -= 22

        draw_line(ch.content, font="Helvetica", size=11, extra_space=10)
        y -= 6

    c.save()
    pdf_bytes = buffer.getvalue()
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    return {
        "openaiFileResponse": [
            {
                "name": "ebook.pdf",
                "mime_type": "application/pdf",
                "content": b64
            }
        ]
    }
