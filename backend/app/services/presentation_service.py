"""Presentation Studio Engine: Slide Outline Generation, Real PPTX (python-pptx) & PDF Export."""

from __future__ import annotations

import io
import re
from typing import Any

from pptx import Presentation as PptxPresentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

THEMES: dict[str, dict[str, tuple[int, int, int]]] = {
    "academic_navy": {
        "bg": (10, 16, 36),
        "title": (248, 250, 252),
        "accent": (124, 58, 237),
        "highlight": (6, 182, 212),
        "body": (203, 213, 225),
    },
    "violet_modern": {
        "bg": (17, 12, 34),
        "title": (255, 255, 255),
        "accent": (139, 92, 246),
        "highlight": (34, 211, 238),
        "body": (226, 232, 240),
    },
    "minimal_light": {
        "bg": (248, 250, 252),
        "title": (15, 23, 42),
        "accent": (79, 70, 229),
        "highlight": (8, 145, 178),
        "body": (51, 65, 85),
    },
    "ieee_slate": {
        "bg": (15, 23, 42),
        "title": (241, 245, 249),
        "accent": (37, 99, 235),
        "highlight": (56, 189, 248),
        "body": (203, 213, 225),
    },
}


def build_slides_from_source(
    title: str,
    source_text: str,
    slide_count: int = 6,
) -> list[dict[str, Any]]:
    """Deterministically build a structured slide deck from prompt/document/PDF/research text."""
    slides: list[dict[str, Any]] = [
        {
            "order_index": 0,
            "layout": "title",
            "title": title,
            "bullets": ["Academic Presentation", "Prepared with UNIFORGE AI Presentation Studio"],
            "body_text": "",
            "speaker_notes": f"Introduce the presentation topic: {title}.",
        }
    ]
    # Split source_text by Markdown headings or paragraphs
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Key Overview"
    current_lines: list[str] = []
    for raw in (source_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            cleaned = re.sub(r"^[-*+\d.)]+\s*", "", line)
            if cleaned:
                current_lines.append(cleaned)
    if current_lines:
        sections.append((current_heading, current_lines))

    if not sections:
        default_outline = [
            ("Problem Statement & Objectives", ["Define the core academic problem", "Outline key research questions", "Establish evaluation criteria"]),
            ("Background & Literature Context", ["Summarize foundational studies", "Identify gaps in prior approaches", "Connect to theoretical framework"]),
            ("Methodology & Architecture", ["Describe research design or system architecture", "Highlight data collection and tools", "Explain validation strategy"]),
            ("Key Findings & Analysis", ["Present empirical observations", "Compare quantitative and qualitative metrics", "Address limitations candidly"]),
            ("Conclusion & Future Directions", ["Recap primary contributions", "Discuss practical impact", "Outline next research milestones"]),
        ]
        for idx, (stitle, bullets) in enumerate(default_outline[: max(1, slide_count - 1)], start=1):
            slides.append(
                {
                    "order_index": idx,
                    "layout": "title_and_bullets",
                    "title": stitle,
                    "bullets": bullets,
                    "body_text": "",
                    "speaker_notes": f"Walk through {stitle.lower()} with supporting examples.",
                }
            )
        return slides

    for idx, (heading, lines) in enumerate(sections[: max(1, slide_count - 1)], start=1):
        bullets: list[str] = []
        for ln in lines:
            if len(ln) > 150:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", ln) if s.strip()]
                bullets.extend(sentences[:3])
            else:
                bullets.append(ln)
            if len(bullets) >= 5:
                break
        slides.append(
            {
                "order_index": idx,
                "layout": "title_and_bullets",
                "title": heading[:120],
                "bullets": bullets[:5] or ["Key point"],
                "body_text": "",
                "speaker_notes": f"Discuss {heading}: " + " ".join(bullets[:2]),
            }
        )
    return slides


def export_presentation_pptx(
    title: str,
    subtitle: str | None,
    theme_name: str,
    slides_data: list[dict[str, Any]],
    aspect_ratio: str = "16:9",
    image_lookup: dict[str, bytes] | None = None,
) -> bytes:
    """Generate a real native PowerPoint (.pptx) deck with editable shapes, charts, images & speaker notes."""
    prs = PptxPresentation()
    if aspect_ratio == "4:3":
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)
    else:
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

    palette = THEMES.get(theme_name, THEMES["academic_navy"])
    blank_layout = prs.slide_layouts[6]
    image_lookup = image_lookup or {}

    for idx, sdata in enumerate(slides_data):
        slide = prs.slides.add_slide(blank_layout)

        # Slide background
        bg = slide.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(*palette["bg"])

        # Top accent stripe
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), prs.slide_width, Inches(0.12))
        bar.fill.solid()
        bar.fill.fore_color.rgb = RGBColor(*palette["accent"])
        bar.line.fill.background()

        # Bottom highlight line
        foot = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), prs.slide_height - Inches(0.08), prs.slide_width, Inches(0.08)
        )
        foot.fill.solid()
        foot.fill.fore_color.rgb = RGBColor(*palette["highlight"])
        foot.line.fill.background()

        layout = sdata.get("layout", "title_and_bullets")
        stitle = str(sdata.get("title") or (title if idx == 0 else f"Slide {idx + 1}"))
        bullets = sdata.get("bullets") or []
        body_text = str(sdata.get("body_text") or "")

        if layout == "title" or idx == 0:
            tbox = slide.shapes.add_textbox(Inches(1.0), Inches(2.1), prs.slide_width - Inches(2.0), Inches(1.8))
            tf = tbox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = stitle
            p.font.size = Pt(40)
            p.font.bold = True
            p.font.color.rgb = RGBColor(*palette["title"])

            sub_text = subtitle or (" | ".join(bullets[:2]) if bullets else "UNIFORGE AI Presentation")
            sbox = slide.shapes.add_textbox(Inches(1.0), Inches(4.0), prs.slide_width - Inches(2.0), Inches(1.2))
            stf = sbox.text_frame
            stf.word_wrap = True
            sp = stf.paragraphs[0]
            sp.text = sub_text
            sp.font.size = Pt(20)
            sp.font.color.rgb = RGBColor(*palette["highlight"])
        else:
            # Slide title
            tbox = slide.shapes.add_textbox(Inches(0.8), Inches(0.45), prs.slide_width - Inches(1.6), Inches(1.0))
            tf = tbox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = stitle
            p.font.size = Pt(28)
            p.font.bold = True
            p.font.color.rgb = RGBColor(*palette["title"])

            has_chart = bool(sdata.get("chart_data") and sdata["chart_data"].get("categories"))
            has_img = bool(sdata.get("image_asset_id") and sdata["image_asset_id"] in image_lookup)
            content_width = Inches(6.0) if (has_chart or has_img) else (prs.slide_width - Inches(1.6))

            bbox = slide.shapes.add_textbox(Inches(0.8), Inches(1.65), content_width, Inches(5.0))
            btf = bbox.text_frame
            btf.word_wrap = True
            first = True
            for b in bullets:
                bp = btf.paragraphs[0] if first else btf.add_paragraph()
                first = False
                bp.text = f"•  {b}"
                bp.font.size = Pt(18)
                bp.space_after = Pt(12)
                bp.font.color.rgb = RGBColor(*palette["body"])
            if body_text:
                bp = btf.paragraphs[0] if first else btf.add_paragraph()
                bp.text = body_text
                bp.font.size = Pt(16)
                bp.font.color.rgb = RGBColor(*palette["body"])

            if has_chart:
                cdata = sdata["chart_data"]
                chart_data = CategoryChartData()
                chart_data.categories = cdata["categories"]
                for series in cdata.get("series", [{"name": "Values", "values": [10, 20, 30]}]):
                    chart_data.add_series(series.get("name", "Series"), series.get("values", []))
                slide.shapes.add_chart(
                    XL_CHART_TYPE.COLUMN_CLUSTERED,
                    Inches(7.1),
                    Inches(1.75),
                    Inches(5.4),
                    Inches(4.5),
                    chart_data,
                )
            elif has_img:
                img_bytes = image_lookup[sdata["image_asset_id"]]
                slide.shapes.add_picture(
                    io.BytesIO(img_bytes), Inches(7.2), Inches(1.75), width=Inches(5.2)
                )

        # Slide footer number
        nbox = slide.shapes.add_textbox(prs.slide_width - Inches(1.4), prs.slide_height - Inches(0.5), Inches(1.0), Inches(0.3))
        np = nbox.text_frame.paragraphs[0]
        np.text = f"{idx + 1} / {len(slides_data)}"
        np.font.size = Pt(11)
        np.font.color.rgb = RGBColor(*palette["body"])

        # Native speaker notes
        notes = str(sdata.get("speaker_notes") or "")
        if notes:
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = notes

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


def export_presentation_pdf(
    title: str,
    theme_name: str,
    slides_data: list[dict[str, Any]],
) -> bytes:
    """Export presentation slides as a landscape 16:9 PDF deck via ReportLab."""
    page_w, page_h = 960, 540  # 16:9 landscape points
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(page_w, page_h),
        leftMargin=48,
        rightMargin=48,
        topMargin=42,
        bottomMargin=36,
        title=title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SlideTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=16,
    )
    bullet_style = ParagraphStyle(
        "SlideBullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=15,
        leading=22,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=10,
    )
    notes_style = ParagraphStyle(
        "SlideNotes",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B"),
    )

    story: list[Any] = []
    for idx, s in enumerate(slides_data):
        stitle = str(s.get("title") or f"Slide {idx + 1}").replace("&", "&amp;").replace("<", "&lt;")
        story.append(Paragraph(f"{idx + 1}. {stitle}", title_style))
        for b in s.get("bullets") or []:
            safe_b = str(b).replace("&", "&amp;").replace("<", "&lt;")
            story.append(Paragraph(f"&bull;&nbsp;&nbsp;{safe_b}", bullet_style))
        if s.get("body_text"):
            safe_body = str(s["body_text"]).replace("&", "&amp;").replace("<", "&lt;")
            story.append(Paragraph(safe_body, bullet_style))
        if s.get("speaker_notes"):
            story.append(Spacer(1, 24))
            safe_notes = str(s["speaker_notes"]).replace("&", "&amp;").replace("<", "&lt;")
            story.append(Paragraph(f"Speaker Notes: {safe_notes}", notes_style))
        if idx < len(slides_data) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()
