"""Academic Document Studio Engine: Templates, Assignment Analyzer, Real PDF/DOCX/MD Exports."""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from typing import Any

import markdown as md_lib
from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
)
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

CITATION_STYLES = ["APA 7", "IEEE", "Harvard", "MLA", "Chicago"]

DOCUMENT_TYPE_TEMPLATES: dict[str, dict[str, Any]] = {
    "assignment": {
        "name": "University Assignment",
        "sections": [
            "Introduction",
            "Main Analysis & Discussion",
            "Critical Evaluation",
            "Conclusion",
            "References",
        ],
    },
    "research_paper": {
        "name": "Academic Research Paper",
        "sections": [
            "Abstract",
            "1. Introduction",
            "2. Literature Review",
            "3. Methodology",
            "4. Results & Analysis",
            "5. Discussion",
            "6. Conclusion & Future Work",
            "References",
        ],
    },
    "project_proposal": {
        "name": "University Project Proposal",
        "sections": [
            "1. Executive Summary",
            "2. Problem Statement",
            "3. Objectives & Scope",
            "4. Proposed Methodology",
            "5. Project Timeline & Milestones",
            "6. Expected Deliverables",
            "References",
        ],
    },
    "fyp_report": {
        "name": "Final-Year Project Report",
        "sections": [
            "Abstract",
            "Chapter 1: Introduction",
            "Chapter 2: Background & Literature Review",
            "Chapter 3: Requirements & System Design",
            "Chapter 4: Implementation",
            "Chapter 5: Testing & Evaluation",
            "Chapter 6: Conclusion & Recommendations",
            "References",
            "Appendices",
        ],
    },
    "lab_report": {
        "name": "Laboratory Report",
        "sections": [
            "1. Objective",
            "2. Theoretical Background",
            "3. Apparatus & Materials",
            "4. Experimental Procedure",
            "5. Observations & Data Tables",
            "6. Error Analysis & Discussion",
            "7. Conclusion",
            "References",
        ],
    },
    "case_study": {
        "name": "Academic Case Study",
        "sections": [
            "Executive Summary",
            "Case Background",
            "Problem Identification",
            "Alternative Solutions Analysis",
            "Recommended Strategy",
            "Implementation Plan",
            "References",
        ],
    },
    "technical_documentation": {
        "name": "Technical Documentation / SRS",
        "sections": [
            "1. Purpose & System Overview",
            "2. Functional Requirements",
            "3. Non-Functional Requirements",
            "4. System Architecture",
            "5. Data Model & API Specification",
            "6. Security & Verification Plan",
            "References",
        ],
    },
    "internship_report": {
        "name": "Internship Report",
        "sections": [
            "Executive Summary",
            "Organization Overview",
            "Roles & Responsibilities",
            "Key Projects & Technical Contributions",
            "Skills Acquired & Reflection",
            "Conclusion",
        ],
    },
    "business_report": {
        "name": "Business Analysis Report",
        "sections": [
            "Executive Summary",
            "Market & Industry Context",
            "SWOT & Financial Analysis",
            "Strategic Recommendations",
            "Risk Assessment",
            "Conclusion",
            "References",
        ],
    },
    "reflective_journal": {
        "name": "Reflective Academic Journal",
        "sections": [
            "Context & Experience Summary",
            "Critical Reflection & Learning Outcomes",
            "Connection to Academic Theory",
            "Action Plan for Improvement",
            "References",
        ],
    },
}


def build_template_markdown(title: str, doc_type: str, citation_style: str = "APA 7") -> str:
    tpl = DOCUMENT_TYPE_TEMPLATES.get(doc_type, DOCUMENT_TYPE_TEMPLATES["assignment"])
    lines = [f"# {title}", ""]
    for sec in tpl["sections"]:
        lines.append(f"## {sec}")
        lines.append("")
        if sec.lower() == "references":
            lines.append(f"_Insert verified {citation_style} citations from Research Studio here._")
        else:
            lines.append(f"Draft the {sec.lower()} section here.")
        lines.append("")
    return "\n".join(lines).strip()


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def render_markdown_to_html(md_text: str) -> str:
    return md_lib.markdown(
        md_text or "",
        extensions=["tables", "fenced_code", "toc", "nl2br"],
    )


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _parse_markdown_blocks(md_text: str) -> list[dict[str, Any]]:
    """Parse Markdown into structured blocks (headings, paragraphs, lists, tables, equations, page breaks)."""
    blocks: list[dict[str, Any]] = []
    lines = (md_text or "").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped in {"---", "***", "<!-- pagebreak -->"}:
            blocks.append({"type": "pagebreak"})
            i += 1
            continue
        if stripped.startswith("### "):
            blocks.append({"type": "h3", "text": stripped[4:].strip()})
            i += 1
            continue
        if stripped.startswith("## "):
            blocks.append({"type": "h2", "text": stripped[3:].strip()})
            i += 1
            continue
        if stripped.startswith("# "):
            blocks.append({"type": "h1", "text": stripped[2:].strip()})
            i += 1
            continue
        img_match = re.match(r"^!\[([^\]]*)\]\(asset://([a-zA-Z0-9-]+)\)$", stripped)
        if img_match:
            blocks.append(
                {
                    "type": "image",
                    "caption": img_match.group(1).strip() or "Figure",
                    "asset_id": img_match.group(2).strip(),
                }
            )
            i += 1
            continue
        if stripped.startswith("$$"):
            eq_lines = [stripped.strip("$").strip()]
            i += 1
            while i < len(lines) and "$$" not in lines[i]:
                eq_lines.append(lines[i].strip())
                i += 1
            if i < len(lines):
                eq_lines.append(lines[i].replace("$$", "").strip())
                i += 1
            blocks.append({"type": "equation", "text": " ".join(e for e in eq_lines if e)})
            continue
        # Markdown pipe table
        if "|" in stripped and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:-]+\|[\s|:-]*$", lines[i + 1]):
            table_rows: list[list[str]] = []
            header = [c.strip() for c in stripped.strip("|").split("|")]
            table_rows.append(header)
            i += 2  # skip separator row
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                table_rows.append(row)
                i += 1
            blocks.append({"type": "table", "rows": table_rows})
            continue
        if re.match(r"^[-*+]\s+", stripped):
            items: list[str] = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*+]\s+", "", lines[i]).strip())
                i += 1
            blocks.append({"type": "bullet_list", "items": items})
            continue
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip())
                i += 1
            blocks.append({"type": "numbered_list", "items": items})
            continue
        # Paragraph
        para_lines = [stripped]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not lines[i].strip().startswith(("#", "- ", "* ", "$$", "---"))
            and not re.match(r"^\d+\.\s+", lines[i].strip())
            and "|" not in lines[i]
        ):
            para_lines.append(lines[i].strip())
            i += 1
        blocks.append({"type": "paragraph", "text": " ".join(para_lines)})
    return blocks


def export_document_pdf(
    title: str,
    content_markdown: str,
    citation_style: str = "APA 7",
    cover_page: dict[str, Any] | None = None,
    formatting_profile: dict[str, Any] | None = None,
    bibliography: list[str] | None = None,
    image_lookup: dict[str, bytes] | None = None,
) -> bytes:
    """Export a genuine formatted academic PDF using ReportLab with headers, footers, page numbers, tables, images, TOC."""
    image_lookup = image_lookup or {}
    profile = formatting_profile or {}
    cover = cover_page or {}
    page_size = A4 if str(profile.get("page_size", "A4")).upper() == "A4" else LETTER
    margin_in = float(profile.get("margin_inches", 1.0))
    font_size = int(profile.get("font_size", 11))
    line_spacing = float(profile.get("line_spacing", 1.5))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=margin_in * inch,
        rightMargin=margin_in * inch,
        topMargin=margin_in * inch,
        bottomMargin=margin_in * inch,
        title=title,
        author=str(cover.get("author", "UNIFORGE AI Student")),
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "AcademicBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=font_size,
        leading=font_size * line_spacing,
        spaceAfter=8,
        textColor=colors.HexColor("#1E293B"),
    )
    h1_style = ParagraphStyle(
        "AcademicH1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=font_size + 7,
        leading=(font_size + 7) * 1.25,
        spaceBefore=14,
        spaceAfter=8,
        textColor=colors.HexColor("#0F172A"),
    )
    h2_style = ParagraphStyle(
        "AcademicH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=font_size + 4,
        leading=(font_size + 4) * 1.25,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#1E3A8A"),
    )
    h3_style = ParagraphStyle(
        "AcademicH3",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=font_size + 2,
        leading=(font_size + 2) * 1.25,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#334155"),
    )
    eq_style = ParagraphStyle(
        "AcademicEq",
        parent=body_style,
        fontName="Courier",
        alignment=1,
        backColor=colors.HexColor("#F1F5F9"),
        borderPadding=8,
        spaceBefore=6,
        spaceAfter=10,
    )
    cover_title_style = ParagraphStyle(
        "CoverTitle",
        parent=h1_style,
        fontSize=24,
        leading=30,
        alignment=1,
        textColor=colors.HexColor("#0F172A"),
    )
    cover_meta_style = ParagraphStyle(
        "CoverMeta",
        parent=body_style,
        fontSize=12,
        leading=18,
        alignment=1,
        textColor=colors.HexColor("#475569"),
    )

    story: list[Any] = []

    # Optional cover page
    if cover.get("enabled", True):
        story.append(Spacer(1, 1.4 * inch))
        if cover.get("institution"):
            story.append(Paragraph(_escape_xml(str(cover["institution"])), cover_meta_style))
            story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(_escape_xml(title), cover_title_style))
        story.append(Spacer(1, 0.25 * inch))
        if cover.get("subtitle"):
            story.append(Paragraph(_escape_xml(str(cover["subtitle"])), cover_meta_style))
        story.append(Spacer(1, 0.6 * inch))
        meta_lines = [
            f"Author: {cover.get('author', 'Student Author')}",
            f"Course: {cover.get('course', 'Academic Coursework')}",
            f"Citation Format: {citation_style}",
            f"Date: {cover.get('date', datetime.now(timezone.utc).strftime('%B %d, %Y'))}",
        ]
        for ml in meta_lines:
            story.append(Paragraph(_escape_xml(ml), cover_meta_style))
        story.append(PageBreak())

    blocks = _parse_markdown_blocks(content_markdown)

    # Table of Contents when >= 3 headings
    headings = [b["text"] for b in blocks if b["type"] in {"h1", "h2"}]
    if profile.get("include_toc", True) and len(headings) >= 3:
        story.append(Paragraph("Table of Contents", h2_style))
        for idx, h in enumerate(headings, start=1):
            story.append(Paragraph(f"{idx}. {_escape_xml(h)}", body_style))
        story.append(Spacer(1, 0.2 * inch))

    for blk in blocks:
        btype = blk["type"]
        if btype == "pagebreak":
            story.append(PageBreak())
        elif btype == "h1":
            story.append(Paragraph(_escape_xml(blk["text"]), h1_style))
        elif btype == "h2":
            story.append(Paragraph(_escape_xml(blk["text"]), h2_style))
        elif btype == "h3":
            story.append(Paragraph(_escape_xml(blk["text"]), h3_style))
        elif btype == "equation":
            story.append(Paragraph(_escape_xml(blk["text"]), eq_style))
        elif btype == "image":
            raw_img = image_lookup.get(blk["asset_id"])
            if raw_img:
                try:
                    from PIL import Image as PILImage

                    pil_im = PILImage.open(io.BytesIO(raw_img))
                    w_px, h_px = pil_im.size
                    max_w = 5.6 * inch
                    scale = min(1.0, max_w / max(1, w_px))
                    draw_w = max(1.5 * inch, min(max_w, w_px * scale))
                    draw_h = draw_w * (h_px / max(1, w_px))
                    if draw_h > 4.2 * inch:
                        draw_h = 4.2 * inch
                        draw_w = draw_h * (w_px / max(1, h_px))
                    story.append(Spacer(1, 6))
                    story.append(RLImage(io.BytesIO(raw_img), width=draw_w, height=draw_h))
                    cap_style = ParagraphStyle(
                        "FigCaption",
                        parent=body_style,
                        fontName="Helvetica-Oblique",
                        fontSize=max(9, font_size - 1),
                        alignment=1,
                        textColor=colors.HexColor("#475569"),
                    )
                    story.append(Paragraph(_escape_xml(blk["caption"]), cap_style))
                    story.append(Spacer(1, 8))
                except Exception:
                    story.append(Paragraph(_escape_xml(f"[Figure: {blk['caption']}]"), body_style))
            else:
                story.append(Paragraph(_escape_xml(f"[Figure: {blk['caption']}]"), body_style))
        elif btype == "bullet_list":
            for item in blk["items"]:
                story.append(Paragraph(f"&bull;&nbsp;&nbsp;{_escape_xml(item)}", body_style))
        elif btype == "numbered_list":
            for idx, item in enumerate(blk["items"], start=1):
                story.append(Paragraph(f"{idx}.&nbsp;&nbsp;{_escape_xml(item)}", body_style))
        elif btype == "table":
            rows = blk["rows"]
            col_count = max(len(r) for r in rows)
            norm_rows = [
                [Paragraph(_escape_xml(c), body_style) for c in (r + [""] * (col_count - len(r)))]
                for r in rows
            ]
            tbl = Table(norm_rows, repeatRows=1)
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("PADDING", (0, 0), (-1, -1), 6),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(Spacer(1, 4))
            story.append(tbl)
            story.append(Spacer(1, 10))
        else:
            story.append(Paragraph(_escape_xml(blk["text"]), body_style))

    if bibliography:
        story.append(PageBreak())
        story.append(Paragraph(f"Bibliography ({citation_style})", h2_style))
        for entry in bibliography:
            story.append(Paragraph(_escape_xml(entry), body_style))

    header_text = str(profile.get("header_text") or title[:65])

    def _draw_header_footer(canvas, doc_obj):
        canvas.saveState()
        width, height = page_size
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#64748B"))
        if doc_obj.page > 1 or not cover.get("enabled", True):
            canvas.drawString(margin_in * inch, height - 0.55 * inch, header_text)
            canvas.drawRightString(width - margin_in * inch, height - 0.55 * inch, citation_style)
            canvas.line(margin_in * inch, height - 0.62 * inch, width - margin_in * inch, height - 0.62 * inch)
        canvas.drawString(margin_in * inch, 0.5 * inch, "Prepared with UNIFORGE AI Academic Studio")
        canvas.drawRightString(width - margin_in * inch, 0.5 * inch, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_header_footer, onLaterPages=_draw_header_footer)
    return buf.getvalue()


def export_document_docx(
    title: str,
    content_markdown: str,
    citation_style: str = "APA 7",
    cover_page: dict[str, Any] | None = None,
    formatting_profile: dict[str, Any] | None = None,
    bibliography: list[str] | None = None,
    image_lookup: dict[str, bytes] | None = None,
) -> bytes:
    """Export a genuine Microsoft Word (.docx) file using python-docx with embedded images & captions."""
    image_lookup = image_lookup or {}
    profile = formatting_profile or {}
    cover = cover_page or {}
    docx_doc = DocxDocument()

    margin_in = float(profile.get("margin_inches", 1.0))
    for section in docx_doc.sections:
        section.top_margin = Inches(margin_in)
        section.bottom_margin = Inches(margin_in)
        section.left_margin = Inches(margin_in)
        section.right_margin = Inches(margin_in)
        header = section.header
        header_para = header.paragraphs[0]
        header_para.text = f"{title[:70]}  |  {citation_style}"
        footer = section.footer
        footer_para = footer.paragraphs[0]
        footer_para.text = "UNIFORGE AI — Academic Document Studio"

    normal_style = docx_doc.styles["Normal"]
    normal_style.font.name = str(profile.get("font_family", "Calibri"))
    normal_style.font.size = Pt(int(profile.get("font_size", 11)))

    # Cover Page
    if cover.get("enabled", True):
        if cover.get("institution"):
            p_inst = docx_doc.add_paragraph(str(cover["institution"]))
            p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_title = docx_doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_title.add_run(title)
        run.bold = True
        run.font.size = Pt(22)
        run.font.color.rgb = RGBColor(15, 23, 42)
        for line in [
            cover.get("subtitle", ""),
            f"Author: {cover.get('author', 'Student Author')}",
            f"Course: {cover.get('course', 'Academic Coursework')}",
            f"Citation Style: {citation_style}",
            f"Date: {cover.get('date', datetime.now(timezone.utc).strftime('%B %d, %Y'))}",
        ]:
            if line:
                p_meta = docx_doc.add_paragraph(str(line))
                p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
        docx_doc.add_page_break()

    blocks = _parse_markdown_blocks(content_markdown)
    for blk in blocks:
        btype = blk["type"]
        if btype == "pagebreak":
            docx_doc.add_page_break()
        elif btype == "h1":
            docx_doc.add_heading(blk["text"], level=1)
        elif btype == "h2":
            docx_doc.add_heading(blk["text"], level=2)
        elif btype == "h3":
            docx_doc.add_heading(blk["text"], level=3)
        elif btype == "equation":
            p = docx_doc.add_paragraph(blk["text"])
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].italic = True
        elif btype == "image":
            raw_img = image_lookup.get(blk["asset_id"])
            if raw_img:
                try:
                    docx_doc.add_picture(io.BytesIO(raw_img), width=Inches(5.4))
                    cap_p = docx_doc.add_paragraph(blk["caption"])
                    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    if cap_p.runs:
                        cap_p.runs[0].italic = True
                except Exception:
                    docx_doc.add_paragraph(f"[Figure: {blk['caption']}]")
            else:
                docx_doc.add_paragraph(f"[Figure: {blk['caption']}]")
        elif btype == "bullet_list":
            for item in blk["items"]:
                docx_doc.add_paragraph(item, style="List Bullet")
        elif btype == "numbered_list":
            for item in blk["items"]:
                docx_doc.add_paragraph(item, style="List Number")
        elif btype == "table":
            rows = blk["rows"]
            col_count = max(len(r) for r in rows)
            table = docx_doc.add_table(rows=len(rows), cols=col_count)
            table.style = "Table Grid"
            for r_idx, row in enumerate(rows):
                for c_idx in range(col_count):
                    cell_text = row[c_idx] if c_idx < len(row) else ""
                    cell = table.cell(r_idx, c_idx)
                    cell.text = cell_text
                    if r_idx == 0 and cell.paragraphs and cell.paragraphs[0].runs:
                        cell.paragraphs[0].runs[0].bold = True
        else:
            docx_doc.add_paragraph(blk["text"])

    if bibliography:
        docx_doc.add_page_break()
        docx_doc.add_heading(f"Bibliography ({citation_style})", level=2)
        for entry in bibliography:
            docx_doc.add_paragraph(entry)

    out = io.BytesIO()
    docx_doc.save(out)
    return out.getvalue()


def export_document_markdown(
    title: str,
    content_markdown: str,
    citation_style: str = "APA 7",
    bibliography: list[str] | None = None,
) -> bytes:
    header = f"---\ntitle: \"{title}\"\ncitation_style: \"{citation_style}\"\nexported_at: \"{datetime.now(timezone.utc).isoformat()}\"\n---\n\n"
    body = content_markdown or ""
    if bibliography:
        body += f"\n\n## Bibliography ({citation_style})\n\n" + "\n".join(f"- {b}" for b in bibliography)
    return (header + body + "\n").encode("utf-8")


def analyze_assignment_brief(
    brief_text: str,
    draft_markdown: str = "",
) -> dict[str, Any]:
    """Extract requirements from an assignment brief/rubric and compare against student draft."""
    text = (brief_text or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Extract word limits (supports ranges like "1500-2500 words" and separate min/max clauses)
    word_limit_min: int | None = None
    word_limit_max: int | None = None
    range_match = re.search(
        r"(\d[\d,]+)\s*(?:-|to|–)\s*(\d[\d,]+)\s*words?", text, re.IGNORECASE
    )
    if range_match:
        word_limit_min = int(range_match.group(1).replace(",", ""))
        word_limit_max = int(range_match.group(2).replace(",", ""))
    else:
        min_match = re.search(
            r"(?:minimum|min|at least)\s+(?:of\s+)?(\d[\d,]+)\s*words?", text, re.IGNORECASE
        )
        max_match = re.search(
            r"(?:maximum|max|up to|limit(?: of)?|not exceed)\s+(?:of\s+)?(\d[\d,]+)\s*words?",
            text,
            re.IGNORECASE,
        )
        if min_match:
            word_limit_min = int(min_match.group(1).replace(",", ""))
        if max_match:
            word_limit_max = int(max_match.group(1).replace(",", ""))
        if word_limit_min is None and word_limit_max is None:
            single_match = re.search(r"(\d[\d,]{2,})\s*words?", text, re.IGNORECASE)
            if single_match:
                word_limit_max = int(single_match.group(1).replace(",", ""))

    # Extract citation / formatting rules
    detected_styles = [
        style for style in ["APA 7", "APA", "IEEE", "Harvard", "MLA", "Chicago"]
        if re.search(rf"\b{re.escape(style)}\b", text, re.IGNORECASE)
    ]
    formatting_rules: list[str] = []
    if detected_styles:
        formatting_rules.append(f"Citation format mentioned: {', '.join(detected_styles)}")
    for pat, label in [
        (r"double[\s-]?spac", "Double line spacing specified"),
        (r"12\s*pt|12[\s-]?point", "12pt font size specified"),
        (r"times new roman|arial|calibri", "Specific font family requested"),
        (r"pdf|docx|word document", "Submission file format specified"),
        (r"cover page|title page", "Cover / title page required"),
        (r"table of contents", "Table of contents required"),
        (r"references|bibliography", "References / bibliography required"),
    ]:
        if re.search(pat, text, re.IGNORECASE):
            formatting_rules.append(label)

    # Extract questions
    questions = [ln for ln in lines if ln.endswith("?") or re.match(r"^(?:Q\d+|Question\s+\d+)[:.)]", ln, re.I)][:15]

    # Extract required sections
    common_sections = [
        "Abstract",
        "Executive Summary",
        "Introduction",
        "Literature Review",
        "Methodology",
        "System Design",
        "Architecture",
        "Implementation",
        "Results",
        "Discussion",
        "Evaluation",
        "Testing",
        "Conclusion",
        "Recommendations",
        "References",
        "Bibliography",
        "Appendix",
    ]
    required_sections = [
        sec for sec in common_sections if re.search(rf"\b{re.escape(sec)}\b", text, re.IGNORECASE)
    ]

    # Extract rubric / assessment criteria lines
    assessment_criteria = [
        ln for ln in lines
        if re.search(r"(\d+\s*%|marks|points|criteria|rubric|weight)", ln, re.IGNORECASE)
    ][:15]

    # Extract submission requirements / deadlines
    submission_requirements = [
        ln for ln in lines
        if re.search(r"(submit|deadline|due|upload|portal|turnitin|pdf|docx)", ln, re.IGNORECASE)
    ][:10]

    # Compare student's draft against requirements
    draft_words = count_words(draft_markdown)
    draft_lower = (draft_markdown or "").lower()
    checklist: list[dict[str, Any]] = []
    missing_items: list[str] = []

    for sec in required_sections:
        present = sec.lower() in draft_lower
        checklist.append(
            {
                "item": f"Include '{sec}' section",
                "category": "section",
                "status": "satisfied" if present else "missing",
            }
        )
        if not present:
            missing_items.append(f"Missing section: {sec}")

    if word_limit_min is not None:
        ok = draft_words >= word_limit_min
        checklist.append(
            {
                "item": f"Minimum word count ({word_limit_min} words; current: {draft_words})",
                "category": "word_limit",
                "status": "satisfied" if ok else "missing",
            }
        )
        if not ok:
            missing_items.append(f"Add at least {word_limit_min - draft_words} more words to reach minimum length.")

    if word_limit_max is not None:
        ok = draft_words <= word_limit_max and draft_words > 0
        checklist.append(
            {
                "item": f"Maximum word count ({word_limit_max} words; current: {draft_words})",
                "category": "word_limit",
                "status": "satisfied" if ok else ("missing" if draft_words == 0 else "exceeded"),
            }
        )
        if draft_words > word_limit_max:
            missing_items.append(f"Reduce length by {draft_words - word_limit_max} words to stay within limit.")

    suggestions: list[str] = []
    if missing_items:
        suggestions.extend(missing_items)
    if questions and draft_words < 100:
        suggestions.append("Address each extracted assignment question explicitly with structured subheadings.")
    if detected_styles:
        suggestions.append(f"Verify all in-text citations and bibliography match {detected_styles[0]} formatting.")
    if not suggestions:
        suggestions.append("All detected structural checkpoints are covered; review clarity, evidence, and citations.")

    satisfied = sum(1 for c in checklist if c["status"] == "satisfied")
    coverage_percent = round((satisfied / len(checklist)) * 100, 1) if checklist else 100.0

    return {
        "questions": questions,
        "required_sections": required_sections,
        "formatting_rules": formatting_rules,
        "word_limits": {
            "min": word_limit_min,
            "max": word_limit_max,
            "current_draft_words": draft_words,
        },
        "submission_requirements": submission_requirements,
        "assessment_criteria": assessment_criteria,
        "checklist": checklist,
        "missing_requirements": missing_items,
        "improvement_suggestions": suggestions,
        "coverage_percent": coverage_percent,
        "disclaimer": (
            "This automated compliance check helps verify structural coverage against your uploaded brief. "
            "It does not predict or guarantee any academic grade."
        ),
    }
