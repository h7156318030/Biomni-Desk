"""Illustrated reports: charts and a report file (Markdown + one self-contained HTML page) the Results panel can open.

The official app ends deep tasks with "a report and its charts saved in a folder". These helpers give the agent the same
ending in two calls: `make_chart` for each figure, `build_report` to assemble the text, tables and figures.
"""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path
from typing import Any

_FONTS = ["Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC", "DejaVu Sans"]
_PALETTE = ["#2b6b5a", "#b4552b", "#3b6aa0", "#8a5a1f", "#7a5c99", "#5c8a3b", "#a03b5c", "#6a6555"]


def _slug(text: str, default: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:40]
    return s or default


def make_chart(kind: str, labels: list[str], values: list[float] | dict[str, list[float]], title: str = "",
               filename: str = "", ylabel: str = "") -> str:
    """Draw a bar / barh / line / pie chart and save it as a PNG; returns the file name.

    `values` is a list (one series) or {series name: list} (several series, same labels). Chinese text is supported.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = _FONTS
    plt.rcParams["axes.unicode_minus"] = False
    series = values if isinstance(values, dict) else {"": list(values)}
    for name, vals in series.items():
        if len(vals) != len(labels):
            raise ValueError(f"Series “{name}” has {len(vals)} values but {len(labels)} labels")
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=150)
    if kind == "pie":
        vals = next(iter(series.values()))
        ax.pie(vals, labels=labels, colors=_PALETTE, autopct="%1.0f%%", startangle=90, wedgeprops={"linewidth": 1, "edgecolor": "white"})
        ax.axis("equal")
    elif kind in ("bar", "barh"):
        n = len(series)
        width = 0.8 / n
        for i, (name, vals) in enumerate(series.items()):
            pos = [j + i * width - 0.4 + width / 2 for j in range(len(labels))]
            (ax.barh if kind == "barh" else ax.bar)(pos, vals, width * 0.92, label=name or None, color=_PALETTE[i % len(_PALETTE)])
        ticks = list(range(len(labels)))
        (ax.set_yticks if kind == "barh" else ax.set_xticks)(ticks)
        (ax.set_yticklabels if kind == "barh" else ax.set_xticklabels)(labels)
        if kind == "bar" and max(len(str(x)) for x in labels) > 6:
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    elif kind == "line":
        for i, (name, vals) in enumerate(series.items()):
            ax.plot(labels, vals, marker="o", label=name or None, color=_PALETTE[i % len(_PALETTE)], linewidth=2)
        if max(len(str(x)) for x in labels) > 6:
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    else:
        plt.close(fig)
        raise ValueError("kind must be bar, barh, line or pie")
    if kind != "pie":
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x" if kind == "barh" else "y", alpha=0.25)
        if ylabel:
            (ax.set_xlabel if kind == "barh" else ax.set_ylabel)(ylabel)
        if len(series) > 1 or next(iter(series)) != "":
            ax.legend(frameon=False)
    if title:
        ax.set_title(title, fontsize=12, pad=10)
    fig.tight_layout()
    name = filename or f"chart_{_slug(title, 'figure')}.png"
    if not name.lower().endswith(".png"):
        name += ".png"
    fig.savefig(name)
    plt.close(fig)
    return name


def _md_table(rows: list[list[Any]]) -> str:
    head, *body = rows
    cells = lambda r: "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |"
    return "\n".join([cells(head), "| " + " | ".join("---" for _ in head) + " |", *(cells(r) for r in body)])


def _html_table(rows: list[list[Any]]) -> str:
    head, *body = rows
    th = "".join(f"<th>{html.escape(str(c))}</th>" for c in head)
    tr = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in body)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def _html_text(text: str) -> str:
    """Paragraphs, '- ' bullets, pipe tables, ### headings, **bold** and bare links; nothing else (escaped first)."""
    out, bullets, rows = [], [], []

    def flush():
        if bullets:
            out.append("<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>")
            bullets.clear()
        if rows:
            body = [r for r in rows if not set("".join(r)) <= set("-: ")]
            if body:
                out.append(_html_table(body))
            rows.clear()

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
        return re.sub(r'(?<!href=")(https?://[^\s<)）]+)(?![^<]*</a>)', r'<a href="\1">\1</a>', s)

    for line in text.splitlines():
        t = line.strip()
        if t.startswith("|") and t.endswith("|"):
            if bullets:
                flush()
            rows.append([c.strip() for c in t.strip("|").split("|")])
        elif t.startswith(("- ", "• ")):
            if rows:
                flush()
            bullets.append(inline(t[2:]))
        elif t.startswith("###"):
            flush()
            out.append(f"<h3>{inline(t.lstrip('# '))}</h3>")
        elif t:
            flush()
            out.append(f"<p>{inline(t)}</p>")
    flush()
    return "\n".join(out)


_CSS = """body{font:15px/1.75 'Microsoft YaHei','Segoe UI',system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1.2rem;color:#1e1c17;background:#faf9f6}
h1{font-size:1.7rem;margin-bottom:.2rem}h2{font-size:1.2rem;margin-top:2rem;padding-bottom:.25rem;border-bottom:1px solid #e6e2d8}
.summary{background:#e0eee8;border-radius:10px;padding:.8rem 1.1rem;margin:1rem 0}.meta{color:#6a6555;font-size:.85rem}
table{border-collapse:collapse;width:100%;margin:.8rem 0;font-size:.92rem}th,td{border:1px solid #e6e2d8;padding:.4rem .6rem;text-align:left;vertical-align:top}
th{background:#efece4}figure{margin:1rem 0;text-align:center}figure img{max-width:100%;border:1px solid #e6e2d8;border-radius:8px;background:#fff}
figcaption{color:#6a6555;font-size:.85rem}a{color:#2b6b5a}"""


def build_report(title: str, summary: str, sections: list[dict[str, Any]], filename: str = "", sources: list[str] | None = None) -> str:
    """Write `<name>.md` and `<name>.html` (images embedded, opens anywhere) and return a line naming both.

    Each section is a dict with `heading` and any of: `text` (paragraphs; lines starting with "- " become bullets),
    `table` (list of rows, first row = header), `figure` (PNG file name from make_chart), `caption`.
    `sources` are lines like "PMID: 123 | title" or a URL; they are listed at the end so every claim can be traced.
    """
    from datetime import date

    stem = filename.removesuffix(".html").removesuffix(".md") if filename else f"report_{_slug(title, '') or __import__('time').strftime('%Y%m%d_%H%M')}"
    today = date.today().isoformat()
    md = [f"# {title}", f"*Generated: {today}*", "", f"> {summary}", ""]
    page = [f"<h1>{html.escape(title)}</h1><p class='meta'>Generated: {today}</p>", f"<div class='summary'>{_html_text(summary)}</div>"]
    for s in sections:
        head = s.get("heading", "")
        md += [f"## {head}", ""]
        page.append(f"<h2>{html.escape(head)}</h2>")
        if s.get("text"):
            md += [s["text"], ""]
            page.append(_html_text(s["text"]))
        if s.get("table"):
            md += [_md_table(s["table"]), ""]
            page.append(_html_table(s["table"]))
        if s.get("figure"):
            fig = Path(s["figure"])
            cap = s.get("caption", "")
            md += [f"![{cap}]({fig.name})", ""]
            if fig.exists():
                b64 = base64.b64encode(fig.read_bytes()).decode()
                page.append(f"<figure><img src='data:image/png;base64,{b64}' alt='{html.escape(cap)}'><figcaption>{html.escape(cap)}</figcaption></figure>")
            else:
                page.append(f"<p class='meta'>(image {html.escape(fig.name)} not found)</p>")
    if sources:
        md += ["## Sources", "", *[f"{i}. {x}" for i, x in enumerate(sources, 1)], ""]
        page += ["<h2>Sources</h2><ol>" + "".join(f"<li>{_html_text(x)[3:-4]}</li>" for x in sources) + "</ol>"]
    Path(f"{stem}.md").write_text("\n".join(md), encoding="utf-8")
    Path(f"{stem}.html").write_text(f"<!doctype html><html lang='zh'><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>{_CSS}</style></head><body>{''.join(page)}</body></html>", encoding="utf-8")
    return f"Report saved: {stem}.html (text and figures, opens directly) and {stem}.md"


def _cjk(run: Any, font: str = "Microsoft YaHei") -> None:
    """python-pptx only sets the Latin typeface; Chinese text needs the east-Asian one as well."""
    from pptx.oxml.ns import qn

    rpr = run._r.get_or_add_rPr()
    run.font.name = font
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = rpr.makeelement(qn(tag), {})
            rpr.append(el)
        el.set("typeface", font)


def make_deck(title: str, slides: list[dict[str, Any]], filename: str = "", subtitle: str = "") -> str:
    """Build an editable PowerPoint (16:9) and save it; returns the file name.

    `slides`: each {'heading': str, 'bullets': [str], 'table': [[header...], [row...]], 'figure': 'chart.png', 'source': str, 'notes': str};
    everything but 'heading' is optional. Put the source of each slide in 'source' (links, PMIDs, DOIs).
    """
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    ink, accent, soft = RGBColor(0x26, 0x24, 0x20), RGBColor(0x2B, 0x6B, 0x5A), RGBColor(0x6A, 0x65, 0x55)

    def text(slide: Any, x: float, y: float, w: float, h: float, lines: list[str], size: int, color: Any = ink, bold: bool = False, bullet: bool = False) -> None:
        box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = box.text_frame
        tf.word_wrap = True
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = ("• " if bullet else "") + str(line)
            run.font.size, run.font.bold = Pt(size), bold
            run.font.color.rgb = color
            _cjk(run)
            p.space_after = Pt(8 if bullet else 2)

    cover = prs.slides.add_slide(blank)
    text(cover, 0.9, 2.6, 11.5, 1.6, [title], 40, accent, True)
    if subtitle:
        text(cover, 0.9, 4.3, 11.5, 1.0, [subtitle], 20, soft)

    for s in slides:
        sl = prs.slides.add_slide(blank)
        text(sl, 0.6, 0.35, 12.1, 0.9, [s.get("heading", "")], 28, accent, True)
        figure = s.get("figure")
        has_fig = bool(figure) and Path(str(figure)).is_file()
        table = s.get("table") or []
        body_w = 6.2 if has_fig else 12.1
        y = 1.4
        if s.get("bullets"):
            text(sl, 0.6, y, body_w, 3.3 if table else 5.0, list(s["bullets"]), 18, ink, bullet=True)
            y += 3.4 if table else 5.0
        if has_fig:
            sl.shapes.add_picture(str(figure), Inches(7.1), Inches(1.4), width=Inches(5.7))
        if table:
            rows, cols = len(table), max(len(r) for r in table)
            shape = sl.shapes.add_table(rows, cols, Inches(0.6), Inches(min(y, 4.4) if s.get("bullets") else 1.4), Inches(body_w), Inches(0.4 * rows))
            for i, row in enumerate(table):
                for j in range(cols):
                    cell = shape.table.cell(i, j)
                    cell.text = ""
                    run = cell.text_frame.paragraphs[0].add_run()
                    run.text = str(row[j]) if j < len(row) else ""
                    run.font.size, run.font.bold = Pt(12), (i == 0)
                    _cjk(run)
        if s.get("source"):
            text(sl, 0.6, 6.85, 12.1, 0.5, ["Source: " + str(s["source"])], 10, soft)
        if s.get("notes"):
            sl.notes_slide.notes_text_frame.text = str(s["notes"])
    name = filename or f"deck_{_slug(title, 'deck')}.pptx"
    if not name.lower().endswith(".pptx"):
        name += ".pptx"
    prs.save(name)
    return f"{name}({len(slides) + 1} slides)"
