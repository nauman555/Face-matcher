"""
engines/report_engine.py
PDF report generation using ReportLab.
Install: pip install reportlab
"""

import datetime
from typing import List, Dict, Optional

from PIL import Image

from config import APP_NAME, APP_AUTHOR, APP_EMAIL, get_logger

logger = get_logger("ReportEngine")

# Optional ReportLab import
reportlab_ok = False
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, Image as RLImage,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    reportlab_ok = True
except ImportError:
    pass


class ReportEngine:
    """Generates a professional landscape PDF report of all matched files."""

    # Color palette
    COL_HEADER_BG = None   # set after import check below
    COL_ROW_ODD   = None
    COL_ROW_EVEN  = None
    COL_GRID      = None
    COL_ACCENT    = None
    COL_TITLE     = None

    def __init__(self):
        self.available = reportlab_ok
        if reportlab_ok:
            ReportEngine.COL_HEADER_BG = colors.HexColor("#1a1a2e")
            ReportEngine.COL_ROW_ODD   = colors.HexColor("#f4f6ff")
            ReportEngine.COL_ROW_EVEN  = colors.HexColor("#e8ecf8")
            ReportEngine.COL_GRID      = colors.HexColor("#b0b8d8")
            ReportEngine.COL_ACCENT    = colors.HexColor("#5a4ed1")
            ReportEngine.COL_TITLE     = colors.HexColor("#1a1a2e")

    # ── Thumbnail helper ──────────────────────────────────────────
    @staticmethod
    def _thumb_image(filepath: str) -> Optional["RLImage"]:
        """Create a high-quality RLImage for PDF embedding (images only)."""
        import io as _io
        try:
            pil = Image.open(filepath).convert("RGB")
            pil.thumbnail((200, 150), Image.LANCZOS)
            buf = _io.BytesIO()
            pil.save(buf, format="JPEG", quality=95, subsampling=0)
            buf.seek(0)
            aspect = pil.height / pil.width if pil.width else 0.75
            w_mm   = 38 * mm
            return RLImage(buf, width=w_mm, height=w_mm * aspect)
        except Exception:
            return None

    # ── Main generate method ──────────────────────────────────────
    def generate(self,
                 results: List[Dict],
                 output_path: str,
                 total_scanned: int,
                 scan_mode: str) -> bool:
        """
        Build and save the PDF report.

        Args:
            results       : combined list of matched results (images + docs)
            output_path   : full path for the output .pdf file
            total_scanned : total files scanned (for summary table)
            scan_mode     : human-readable scan mode string

        Returns:
            True on success, False on failure.
        """
        if not self.available:
            logger.error("reportlab not installed.")
            return False

        try:
            PAGE   = landscape(A4)
            page_w = PAGE[0] - 20 * mm   # 277mm usable at 10mm margins each side
            ts     = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            doc = SimpleDocTemplate(
                output_path,
                pagesize=PAGE,
                rightMargin=10 * mm, leftMargin=10 * mm,
                topMargin=18 * mm,   bottomMargin=22 * mm,
            )

            # ── Canvas footer — runs on every page ────────────────
            footer_txt = (
                f"A software by {APP_AUTHOR}  ·  {APP_EMAIL}  ·  {APP_NAME}"
            )

            def _draw_footer(cv, doc_obj):
                cv.saveState()
                cv.setFont("Helvetica", 7)
                cv.setFillColor(colors.HexColor("#555577"))
                cv.drawString(10 * mm, 10 * mm, footer_txt)
                cv.drawRightString(
                    PAGE[0] - 10 * mm, 10 * mm, f"Page {doc_obj.page}")
                # Top cyan rule
                cv.setStrokeColor(colors.HexColor("#00b4d8"))
                cv.setLineWidth(1.5)
                cv.line(10 * mm, PAGE[1] - 14 * mm,
                        PAGE[0] - 10 * mm, PAGE[1] - 14 * mm)
                # Bottom rule
                cv.setStrokeColor(colors.HexColor("#aaaacc"))
                cv.setLineWidth(0.5)
                cv.line(10 * mm, 14 * mm, PAGE[0] - 10 * mm, 14 * mm)
                cv.restoreState()

            story = []

            # ── Banner header ─────────────────────────────────────
            banner_tbl = Table(
                [[Paragraph("DOCUMENTS / IMAGES FINDER TOOL — SEARCH REPORT",
                            ParagraphStyle("bn", fontName="Helvetica-Bold",
                                           fontSize=17, textColor=colors.white,
                                           alignment=TA_CENTER, leading=22))],
                 [Paragraph(f"{APP_NAME}  ·  Advanced Search & Analysis",
                            ParagraphStyle("sb", fontName="Helvetica",
                                           fontSize=10,
                                           textColor=colors.HexColor("#ccccee"),
                                           alignment=TA_CENTER, leading=14))]],
                colWidths=[page_w],
            )
            banner_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), self.COL_HEADER_BG),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING",   (0, 0), (-1, -1), 14),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
            ]))
            story.append(banner_tbl)
            story.append(Spacer(1, 4 * mm))

            # ── Summary table ─────────────────────────────────────
            sp  = ParagraphStyle("sp", fontName="Helvetica",     fontSize=9,
                                 textColor=colors.HexColor("#333355"), leading=13)
            sbp = ParagraphStyle("sbp", fontName="Helvetica-Bold", fontSize=9,
                                 textColor=self.COL_TITLE, leading=13)
            info_rows = [
                [Paragraph("Scan Timestamp", sbp), Paragraph(ts, sp)],
                [Paragraph("Scan Mode",      sbp), Paragraph(scan_mode, sp)],
                [Paragraph("Total Scanned",  sbp),
                 Paragraph(f"{total_scanned:,}", sp)],
                [Paragraph("Total Matched",  sbp),
                 Paragraph(str(len(results)), sp)],
            ]
            sum_tbl = Table(info_rows, colWidths=[42 * mm, 80 * mm])
            sum_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#eef0ff")),
                ("GRID",          (0, 0), (-1, -1), 0.3, self.COL_GRID),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ]))
            story.append(sum_tbl)
            story.append(Spacer(1, 6 * mm))

            if not results:
                story.append(Paragraph("No matches found.", sp))
                doc.build(story, onFirstPage=_draw_footer,
                          onLaterPages=_draw_footer)
                return True

            # ── Evidence table ────────────────────────────────────
            headers = [
                "#", "Preview", "File Name", "Folder / Path",
                "MD5 Hash", "Device", "Capture Date",
                "Last Modified", "Last Accessed", "File Size",
            ]
            col_widths = [
                7  * mm,   # #
                38 * mm,   # preview
                40 * mm,   # file name
                54 * mm,   # folder/path
                44 * mm,   # MD5
                26 * mm,   # device
                22 * mm,   # capture date
                22 * mm,   # last modified
                22 * mm,   # last accessed
            ]
            used = sum(col_widths)
            col_widths.append(max(18 * mm, page_w - used))
            total_w = sum(col_widths)
            if total_w > page_w:
                scale      = page_w / total_w
                col_widths = [w * scale for w in col_widths]

            hdr_s  = ParagraphStyle("hdr",  fontName="Helvetica-Bold",
                                    fontSize=8, textColor=colors.white,
                                    alignment=TA_CENTER, leading=11)
            cell_s = ParagraphStyle("cell", fontName="Helvetica",
                                    fontSize=8,
                                    textColor=colors.HexColor("#111133"),
                                    leading=11)
            mono_s = ParagraphStyle("mono", fontName="Courier",
                                    fontSize=7,
                                    textColor=colors.HexColor("#222244"),
                                    leading=10)

            table_data = [[Paragraph(h, hdr_s) for h in headers]]

            for idx, r in enumerate(results, 1):
                meta   = r.get("metadata", {})
                hashes = r.get("hashes",   {})
                nd     = "—"

                # Preview — image thumbnail or doc type label
                preview = Paragraph("No preview", cell_s)
                rl_img  = self._thumb_image(r["filepath"])
                if rl_img:
                    preview = rl_img
                else:
                    ext = r.get("extension", "").upper().strip(".")
                    if ext:
                        preview = Paragraph(f"[{ext}]", cell_s)

                folder_txt = meta.get("folder", nd)
                if len(folder_txt) > 55:
                    folder_txt = "…" + folder_txt[-54:]

                # For keyword results, include matched keywords in file name cell
                fname = meta.get("filename", nd)
                if r.get("keywords_found"):
                    kws   = ", ".join(list(r["keywords_found"].keys())[:3])
                    fname = f"{fname}\n[{kws}]"

                table_data.append([
                    Paragraph(str(idx),                      cell_s),
                    preview,
                    Paragraph(fname,                          cell_s),
                    Paragraph(folder_txt,                     cell_s),
                    Paragraph(hashes.get("md5",          nd), mono_s),
                    Paragraph(meta.get("device",         nd), cell_s),
                    Paragraph(meta.get("capture_date",   nd), cell_s),
                    Paragraph(meta.get("last_modified",  nd), cell_s),
                    Paragraph(meta.get("last_accessed",  nd), cell_s),
                    Paragraph(meta.get("filesize",       nd), cell_s),
                ])

            tbl = Table(table_data, colWidths=col_widths,
                        repeatRows=1, hAlign="LEFT")
            tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0),  self.COL_HEADER_BG),
                ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
                ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, 0),  8),
                ("TOPPADDING",    (0, 0), (-1, 0),  7),
                ("BOTTOMPADDING", (0, 0), (-1, 0),  7),
                ("ALIGN",         (0, 0), (-1, 0),  "CENTER"),
                ("VALIGN",        (0, 0), (-1, 0),  "MIDDLE"),
                ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE",      (0, 1), (-1, -1), 8),
                ("ROWBACKGROUNDS",(0, 1), (-1, -1),
                 [self.COL_ROW_ODD, self.COL_ROW_EVEN]),
                ("VALIGN",        (0, 1), (-1, -1), "MIDDLE"),
                ("ALIGN",         (0, 1), (0,  -1), "CENTER"),
                ("ALIGN",         (1, 1), (1,  -1), "CENTER"),
                ("TOPPADDING",    (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 4),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
                ("GRID",          (0, 0), (-1, -1), 0.4, self.COL_GRID),
                ("LINEBELOW",     (0, 0), (-1, 0),  1.2, self.COL_ACCENT),
            ]))

            story.append(tbl)
            story.append(Spacer(1, 6 * mm))

            doc.build(story, onFirstPage=_draw_footer,
                      onLaterPages=_draw_footer)
            logger.info(f"PDF written: {output_path}")
            return True

        except Exception as e:
            logger.error(f"PDF generation error: {e}")
            import traceback
            traceback.print_exc()
            return False
