"""Server-side fpdf2 rendering, embedded OFL fonts and bounded complete pagination."""
from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from ..errors import ApiError
from ..schemas import ErrorCode
from .model import text

FONTS = Path(__file__).resolve().parents[2] / "fonts"
MAX_BYTES = 4_000_000  # Below the deployment response ceiling, with room for headers.
MAX_PAGES = 200
MAX_TEXT_CHARS = 500_000


def bounded(data: bytes) -> bytes:
    if len(data) > MAX_BYTES:
        raise ApiError(ErrorCode.EXPORT_TOO_LARGE)
    return data


class HandoffPDF(FPDF):
    historical = False

    def header(self):
        if self.page_no() > MAX_PAGES:
            raise ApiError(ErrorCode.EXPORT_TOO_LARGE)
        self.set_font("Body", size=9)
        self.set_text_color(55, 75, 90)
        self.cell(0, 6, "MEDITRACE / REFERRAL HANDOFF", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if self.historical:
            self.set_text_color(155, 65, 30)
            self.cell(0, 6, "Historical revision - not current", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Body", size=8)
        self.set_text_color(75, 85, 95)
        self.cell(0, 5, f"Confirmed referral material | Page {self.page_no()} / {{nb}}", align="C")


def render(view) -> bytes:
    content = text(view)
    if len(content) > MAX_TEXT_CHARS:
        raise ApiError(ErrorCode.EXPORT_TOO_LARGE)
    pdf = HandoffPDF(format="A4")
    pdf.set_margins(18, 12, 18)
    pdf.set_auto_page_break(True, margin=21)
    pdf.add_font("Body", fname=str(FONTS / "SourceSans3-Regular.ttf"))
    pdf.add_font("CJK", fname=str(FONTS / "SourceHanSansCN-Regular.ttf"))
    pdf.set_font("Body", size=11)
    pdf.set_fallback_fonts(["CJK"])
    coverage = set().union(*(set(font.cmap) for font in pdf.fonts.values()))
    # Never silently drop a name or replace unsupported characters with boxes.
    if any(ord(char) not in coverage for char in content if char not in "\n\r\t"):
        raise ApiError(ErrorCode.EXPORT_UNSUPPORTED_TEXT)
    # Complex-script shaping is deliberately not claimed without a shaping engine.
    if any(0x0590 <= ord(char) <= 0x0DFF for char in content):
        raise ApiError(ErrorCode.EXPORT_UNSUPPORTED_TEXT)
    pdf.set_title(view.title)
    pdf.set_author("MediTrace")
    pdf.historical = view.historical
    pdf.alias_nb_pages()
    pdf.add_page()
    def paragraph(value, size=11, color=(25, 38, 48), gap=3):
        pdf.set_font("Body", size=size)
        pdf.set_text_color(*color)
        pdf.multi_cell(0, 5.8 if size < 14 else 8, value.replace("\t", "    ").replace("\r\n", "\n").replace("\r", "\n"),
            new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        pdf.ln(gap)
    paragraph(view.title, 22, (20, 65, 80))
    paragraph(view.status, 13)
    for warning in view.warnings:
        paragraph(warning, 11, (150, 55, 20))
    for section in view.sections:
        # Keep each section heading with at least two lines of its first paragraph.
        if pdf.will_page_break(24):
            pdf.add_page()
        paragraph(section.heading, 14, (20, 65, 80), 2)
        for value in section.paragraphs:
            paragraph(value)
    return bounded(bytes(pdf.output()))
