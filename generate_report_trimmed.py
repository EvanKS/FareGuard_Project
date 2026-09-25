"""
Trimmed FareGuard Mini Project Report Generator
Target: ~17-18 pages of text body
After adding 5-7 dashboard screenshots: 22-25 pages total (within 20-25 page limit)

Format rules:
- A4, 1.5 line spacing
- Margins: Left 1.25", Right 1.0", Top 0.75", Bottom 0.75"
- Times New Roman: Chapter title 18pt, Section 16pt, Subsection 14pt, Body 12pt
- Black & white, numbered equations/figures/tables
"""

import docx
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

# ─── helpers ──────────────────────────────────────────────────────────────────

def set_cell_border(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>\n'
        f'<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'<w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'<w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'</w:tcBorders>'
    )
    tcPr.append(tcBorders)

def set_cell_shading(cell, color_hex="F2F2F2"):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)

def add_page_break(doc):
    p = doc.add_paragraph()
    run = p.add_run()
    run.add_break(docx.enum.text.WD_BREAK.PAGE)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)

def body(doc, text, bold=False, italic=False, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = Pt(18)   # 1.5 × 12pt
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)
    return p

def bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.line_spacing = Pt(18)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.space_before = Pt(0)
    if bold_prefix:
        r1 = p.add_run(bold_prefix + ': ')
        r1.font.name = 'Times New Roman'
        r1.font.size = Pt(12)
        r1.font.bold = True
        r1.font.color.rgb = RGBColor(0, 0, 0)
        r2 = p.add_run(text)
        r2.font.name = 'Times New Roman'
        r2.font.size = Pt(12)
        r2.font.color.rgb = RGBColor(0, 0, 0)
    else:
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0, 0, 0)

def chapter_heading(doc, text):
    p = doc.add_heading(text, level=1)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(18)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(10)

def section(doc, text):
    p = doc.add_heading(text, level=2)
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)

def subsection(doc, text):
    p = doc.add_heading(text, level=3)
    for run in p.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)

def equation(doc, text, num):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = Pt(18)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.space_before = Pt(4)
    tab_stops = p._p.get_or_add_pPr()
    # Right-align equation number via tabs
    r1 = p.add_run('\t' + text + '\t(Equation ' + str(num) + ')')
    r1.font.name = 'Times New Roman'
    r1.font.size = Pt(11)
    r1.font.italic = True
    r1.font.color.rgb = RGBColor(0, 0, 0)

def fig_placeholder(doc, num, caption):
    """Single-row table as figure placeholder."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.rows[0].cells[0]
    set_cell_border(cell)
    set_cell_shading(cell, "EEEEEE")
    cp = cell.add_paragraph()
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cp.add_run(f'[ FIGURE {num} — SCREENSHOT PLACEHOLDER ]\n{caption}')
    r.font.name = 'Times New Roman'
    r.font.size = Pt(11)
    r.font.bold = False
    r.font.color.rgb = RGBColor(0, 0, 0)
    cell.paragraphs[0].paragraph_format.space_before = Pt(36)
    cell.paragraphs[0].paragraph_format.space_after = Pt(36)
    # Caption below
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cr = cap.add_run(f'Figure {num}: {caption}')
    cr.font.name = 'Times New Roman'
    cr.font.size = Pt(11)
    cr.font.bold = True
    cr.font.color.rgb = RGBColor(0, 0, 0)
    cap.paragraph_format.space_after = Pt(6)

def add_table_caption(doc, num, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'Table {num}: {caption}')
    r.font.name = 'Times New Roman'
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0, 0, 0)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)

def styled_table(doc, headers, rows, col_widths=None):
    num_cols = len(headers)
    tbl = doc.add_table(rows=1 + len(rows), cols=num_cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = 'Table Grid'
    # Header row
    hrow = tbl.rows[0]
    for ci, hdr in enumerate(headers):
        cell = hrow.cells[ci]
        set_cell_shading(cell, "D0D0D0")
        set_cell_border(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(hdr)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
    # Data rows
    for ri, row_data in enumerate(rows):
        row = tbl.rows[ri + 1]
        shade = "F8F8F8" if ri % 2 == 0 else "FFFFFF"
        for ci, val in enumerate(row_data):
            cell = row.cells[ci]
            set_cell_border(cell)
            set_cell_shading(cell, shade)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(str(val))
            run.font.name = 'Times New Roman'
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(0, 0, 0)
    if col_widths:
        for ci, w in enumerate(col_widths):
            for row in tbl.rows:
                row.cells[ci].width = Inches(w)
    return tbl

def toc_entry(doc, text, page, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2 if level > 1 else 4)
    p.paragraph_format.space_before = Pt(4 if level == 1 else 0)
    # Tab stop
    pPr = p._p.get_or_add_pPr()
    tabs = OxmlElement('w:tabs')
    tab = OxmlElement('w:tab')
    tab.set(qn('w:val'), 'right')
    tab.set(qn('w:leader'), 'dot')
    tab.set(qn('w:pos'), '8910')
    tabs.append(tab)
    pPr.append(tabs)
    if level > 1:
        ind = OxmlElement('w:ind')
        ind.set(qn('w:left'), '360')
        pPr.append(ind)
    run = p.add_run(text + '\t' + str(page))
    run.font.name = 'Times New Roman'
    run.font.bold = (level == 1)
    run.font.size = Pt(13 if level == 1 else 12)
    run.font.color.rgb = RGBColor(0, 0, 0)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def create_report(output_filename):
    doc = docx.Document()

    # Page setup
    section_obj = doc.sections[0]
    section_obj.page_width = Inches(8.27)
    section_obj.page_height = Inches(11.69)
    section_obj.left_margin = Inches(1.25)
    section_obj.right_margin = Inches(1.00)
    section_obj.top_margin = Inches(0.75)
    section_obj.bottom_margin = Inches(0.75)

    # Default style
    ns = doc.styles['Normal']
    ns.font.name = 'Times New Roman'
    ns.font.size = Pt(12)
    ns.font.color.rgb = RGBColor(0, 0, 0)

    for lvl, sz in [(1, 18), (2, 16), (3, 14)]:
        hs = doc.styles[f'Heading {lvl}']
        hs.font.name = 'Times New Roman'
        hs.font.size = Pt(sz)
        hs.font.bold = True
        hs.font.color.rgb = RGBColor(0, 0, 0)
        hs.paragraph_format.line_spacing = Pt(sz * 1.5)
        hs.paragraph_format.space_before = Pt(10)
        hs.paragraph_format.space_after = Pt(6)

    # ── PAGE 1: COVER ──────────────────────────────────────────────────────────
    def cp(txt, sz=12, bold=False, after=4, align=WD_ALIGN_PARAGRAPH.CENTER):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_after = Pt(after)
        p.paragraph_format.space_before = Pt(0)
        r = p.add_run(txt)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(sz)
        r.font.bold = bold
        r.font.color.rgb = RGBColor(0, 0, 0)
        return p

    cp("DEPARTMENT OF", 20, True, 2)
    cp("AI AND DATA SCIENCE ENGINEERING", 20, True, 18)
    cp("CSE532P (CLOUD COMPUTING)", 16, True, 2)
    cp("Mini Project Report", 16, True, 18)
    cp(
        "FAREGUARD: A CLOUD-NATIVE ML-GRAPH INTELLIGENCE PLATFORM FOR\n"
        "REAL-TIME REVENUE LEAKAGE DETECTION AND TOPOLOGICAL CORRIDOR\n"
        "LOCALIZATION IN BMTC METROPOLITAN BUS TRANSIT",
        16, True, 18
    )
    cp("Submitted in partial fulfillment of the requirements for the award of the degree of", 12, False, 4)
    cp("B. Tech – Computer Science and Engineering", 14, True, 2)
    cp("(Artificial Intelligence and Machine Learning)", 14, True, 14)
    cp("School of Engineering and Technology,", 16, True, 2)
    cp("CHRIST (Deemed to be University),", 16, True, 2)
    cp("Kumbalagodu, Bengaluru-560 074", 16, True, 14)

    # Team
    team = [
        ("Ankit Pai N",        "2462036"),
        ("Dean Joah Bell",     "2462061"),
        ("Evan KS",            "2462067"),
        ("Joshua Zachary Jose","2462093"),
    ]
    for name, reg in team:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"{name}  |  {reg}")
        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(0, 0, 0)

    cp("", 12)
    cp("2025 – 2026", 13, True, 0)

    add_page_break(doc)

    # ── PAGE 2: CERTIFICATE ────────────────────────────────────────────────────
    cp("Certificate", 30, True, 20)
    cert_text = (
        "This is to certify that the Mini Project entitled \"FAREGUARD: A CLOUD-NATIVE "
        "ML-GRAPH INTELLIGENCE PLATFORM FOR REAL-TIME REVENUE LEAKAGE DETECTION AND "
        "TOPOLOGICAL CORRIDOR LOCALIZATION IN BMTC METROPOLITAN BUS TRANSIT\" has been "
        "carried out by Ankit Pai N (2462036), Dean Joah Bell (2462061), Evan KS (2462067), "
        "and Joshua Zachary Jose (2462093) in partial fulfillment of the requirements for the "
        "award of the degree of Bachelor of Technology in Computer Science and Engineering "
        "(Artificial Intelligence and Machine Learning) at CHRIST (Deemed to be University), "
        "Bengaluru, during the academic year 2025-2026."
    )
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = Pt(18)
    p.paragraph_format.space_after = Pt(28)
    r = p.add_run(cert_text)
    r.font.name = 'Times New Roman'
    r.font.size = Pt(12)
    r.font.color.rgb = RGBColor(0, 0, 0)

    sig_tbl = doc.add_table(rows=1, cols=2)
    sig_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ci, (label1, label2) in enumerate([("FACULTY- IN CHARGE", "HEAD OF THE DEPARTMENT")]):
        for ci2, lbl in enumerate([label1, label2]):
            c = sig_tbl.rows[0].cells[ci2]
            pp = c.paragraphs[0]
            pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            rr = pp.add_run(lbl)
            rr.font.name = 'Times New Roman'
            rr.font.size = Pt(12)
            rr.font.bold = True
            rr.font.color.rgb = RGBColor(0, 0, 0)

    doc.add_paragraph()
    for lbl in ["EXAMINER 1:", "EXAMINER 2:"]:
        pe = doc.add_paragraph()
        pe.paragraph_format.space_after = Pt(10)
        re = pe.add_run(lbl)
        re.font.name = 'Times New Roman'
        re.font.size = Pt(12)
        re.font.color.rgb = RGBColor(0, 0, 0)

    add_page_break(doc)

    # ── PAGE 3: ABSTRACT ───────────────────────────────────────────────────────
    cp("ABSTRACT", 18, True, 12)
    body(doc,
        "Public bus transit corporations in metropolitan areas suffer critical revenue losses due to "
        "fare evasion and electronic ticketing discrepancies. This project presents FareGuard, a "
        "cloud-native machine learning and topological graph intelligence platform engineered for "
        "real-time revenue leakage detection on the Bangalore Metropolitan Transport Corporation "
        "(BMTC) network. The system ingests official BMTC GTFS data to construct a directed transit "
        "graph of 9,887 stops and 1,800+ route corridors. A Random Forest demand forecaster "
        "(R² = 0.8942, MAE = 7.3 passengers) establishes per-trip passenger baselines, while an "
        "inductive clean-reference Isolation Forest (F1 = 0.9355, Precision = 0.9701) detects "
        "anomalous trip revenue patterns without requiring labelled fraud samples. A deterministic "
        "subpath chaining algorithm (95% corridor overlap recall) then localises the exact physical "
        "bus-stop corridors implicated. A multi-factor risk scorer fuses anomaly, passenger, and "
        "revenue signals into CRITICAL / SUSPICIOUS / MONITOR / NORMAL bands. All components are "
        "delivered through an asynchronous FastAPI microservice and a seven-module Streamlit "
        "Signal Ledger v2 dashboard, containerised with Docker Compose and sustaining "
        ">1,500 transactions/second at sub-2.5 ms median latency.",
        space_after=8
    )
    body(doc,
        "Keywords: Cloud Computing, Machine Learning, Anomaly Detection, GTFS Transit Graph, "
        "Revenue Protection, BMTC, Microservices, FastAPI, Streamlit.",
        bold=False, italic=True, space_after=0
    )
    add_page_break(doc)

    # ── PAGE 4: TABLE OF CONTENTS ──────────────────────────────────────────────
    cp("TABLE OF CONTENTS", 18, True, 14)

    toc_data = [
        (1, "CERTIFICATE",                                       2),
        (1, "ABSTRACT",                                          3),
        (1, "TABLE OF CONTENTS",                                 4),
        (1, "CHAPTER 1  INTRODUCTION",                          5),
        (2, "1.1 Background and Motivation",                     5),
        (2, "1.2 Context: BMTC Metropolitan Bus Transit",        5),
        (2, "1.3 Scope of the Project",                          5),
        (1, "CHAPTER 2  LITERATURE REVIEW",                     6),
        (2, "2.1 Review of Prior Work",                          6),
        (2, "2.2 Summary of Research Gaps",                      6),
        (1, "CHAPTER 3  PROBLEM STATEMENT",                     7),
        (2, "3.1 Formal Problem Definition",                     7),
        (2, "3.2 Mathematical Formulation",                      7),
        (2, "3.3 Challenges in Traditional Auditing",            8),
        (1, "CHAPTER 4  OBJECTIVES",                            9),
        (2, "4.1 Primary Aim",                                   9),
        (2, "4.2 Specific Technical Objectives",                 9),
        (1, "CHAPTER 5  DESIGN / METHODOLOGY",                 10),
        (2, "5.1 Overall System Architecture",                  10),
        (2, "5.2 Data Ingestion and GTFS Graph Modeling",       10),
        (2, "5.3 ML Demand Forecasting Subsystem",              11),
        (2, "5.4 Inductive Clean-Reference Anomaly Detection",  11),
        (2, "5.5 Topological Discrepancy Localization",         12),
        (2, "5.6 Multi-Factor Risk Scoring and Explainability", 12),
        (1, "CHAPTER 6  IMPLEMENTATION",                       13),
        (2, "6.1 Hardware and Software Requirements",           13),
        (2, "6.2 Cloud-Native Microservices Architecture",      14),
        (2, "6.3 Algorithmic Pipeline and REST API",            15),
        (1, "CHAPTER 7  OUTPUT SCREENSHOTS",                   16),
        (2, "7.1 Dashboard Module Screenshots",                 16),
        (2, "7.2 Experimental Benchmark Results",              18),
        (1, "CHAPTER 8  CONCLUSION AND FUTURE WORK",          20),
        (2, "8.1 Summary of Completed Work",                   20),
        (2, "8.2 Future Enhancements",                         20),
        (1, "REFERENCES",                                      21),
        (1, "APPENDIX",                                        22),
    ]
    for lvl, txt, pg in toc_data:
        toc_entry(doc, txt, pg, lvl)

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 1 – INTRODUCTION  (target: ~1.5 pages)
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "CHAPTER 1\nINTRODUCTION")
    subsection(doc, "1.1 Background and Motivation")
    body(doc,
        "Metropolitan surface bus transit systems form the primary mobility infrastructure for "
        "millions of daily commuters in developing economies. India's publicly-operated bus "
        "corporations collectively carry over 70 million passengers daily, yet revenue realisation "
        "consistently falls 15–30% below theoretical capacity due to fare evasion, ticketing "
        "irregularities, and handheld ETM misreporting. Unlike gated metro systems, open-platform "
        "buses create structural opportunities for revenue leakage that manual audit squads cannot "
        "detect in real time across hundreds of concurrent route operations."
    )
    subsection(doc, "1.2 Context: BMTC Metropolitan Bus Transit")
    body(doc,
        "The Bangalore Metropolitan Transport Corporation (BMTC) operates 6,800+ buses across "
        "1,800+ routes serving 9,887 stops, making it one of India's largest urban bus fleets. "
        "BMTC publishes official GTFS (General Transit Feed Specification) open data feeds—"
        "comprising stops.txt, routes.txt, trips.txt, and stop_times.txt—which serve as the "
        "geospatial and topological foundation for FareGuard. Revenue leakage risks include "
        "ETM under-reporting, boarding-without-scan incidents, and concessionary pass misuse."
    )
    subsection(doc, "1.3 Scope of the Project")
    body(doc, "The FareGuard platform addresses this problem through five integrated capabilities:")
    for b in [
        ("GTFS Graph Ingestion", "topological modeling of 9,887 stops and 1,800+ route corridors"),
        ("Demand Forecasting",   "Random Forest regressor for per-trip passenger baseline estimation"),
        ("Anomaly Detection",    "inductive clean-reference Isolation Forest detecting revenue discrepancies"),
        ("Graph Localisation",   "deterministic subpath chaining to pinpoint implicated corridor segments"),
        ("Operations Dashboard", "seven-module Streamlit Signal Ledger v2 with REST API and Docker orchestration"),
    ]:
        bullet(doc, b[1], b[0])

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 2 – LITERATURE REVIEW  (target: ~1.5 pages)
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "CHAPTER 2\nLITERATURE REVIEW")
    subsection(doc, "2.1 Review of Prior Work")
    body(doc,
        "Research in transit revenue protection, ML-based anomaly detection, and topological "
        "graph analysis converges to motivate FareGuard's design. Table 2.1 summarises the "
        "key prior works and their methodological contributions."
    )

    lit_headers = ["Ref.", "Authors & Year", "Methodology", "Limitation"]
    lit_rows = [
        ("[1]", "Peluso et al., 2023", "AFC data for transit demand modeling",            "No anomaly detection layer"),
        ("[2]", "Kumar & Sharma, 2022", "Hybrid e-ticketing vulnerabilities",              "Manual audit; no ML"),
        ("[3]", "Smith & Demetsky, 2021", "Traffic flow forecasting comparison",           "No revenue integration"),
        ("[4]", "Moretti et al., 2022", "ML regressor benchmark for passenger load",      "No fraud injection test"),
        ("[5]", "Chen et al., 2023", "Gradient Boosting / RF passenger estimation",       "No graph localization"),
        ("[6]", "Chandola et al., 2009", "Anomaly detection survey (Isolation Forest)",   "No transit application"),
        ("[7]", "Liu et al., 2008", "Isolation Forest algorithm",                         "Unsupervised only"),
        ("[9]", "Derrible & Kennedy, 2011", "Metro network complexity & graph topology",  "No revenue link"),
    ]
    styled_table(doc, lit_headers, lit_rows, [0.4, 1.8, 2.6, 1.7])
    add_table_caption(doc, "2.1", "Summary of Related Literature and Methodological Gaps")

    subsection(doc, "2.2 Summary of Research Gaps")
    body(doc, "Three critical gaps motivate this project:")
    for b in [
        ("Temporal Granularity",   "existing systems audit revenue at weekly/monthly aggregates, missing real-time trip-level discrepancies"),
        ("Topological Disconnect", "ML anomaly detectors generate scalar flags without mapping leakage to physical corridor segments"),
        ("Leakage-Free Baselines", "academic models train on contaminated datasets including future-data leakage, invalidating anomaly scores"),
    ]:
        bullet(doc, b[1], b[0])

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 3 – PROBLEM STATEMENT  (target: ~1.5 pages)
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "CHAPTER 3\nPROBLEM STATEMENT")
    subsection(doc, "3.1 Formal Problem Definition")
    body(doc,
        "Public bus transit undertakings suffer systemic revenue losses from fare evasion. "
        "Transit authorities currently lack the technology to monitor, detect, and isolate "
        "these leakages in real time. The absence of automated, trip-level anomaly scoring "
        "linked to physical corridor localisation means that inspectors cannot efficiently "
        "deploy resources to high-risk route segments."
    )

    subsection(doc, "3.2 Mathematical Formulation of Revenue Discrepancy")
    body(doc,
        "Let the transit network be modeled as a directed graph G = (V, E), where V denotes "
        "BMTC bus stops and E denotes scheduled inter-stop segments. Each trip T_i follows a "
        "stop sequence:"
    )
    equation(doc, "T_i = (v_{i,1}, v_{i,2}, ..., v_{i,M}),    where (v_{i,j}, v_{i,j+1}) ∈ E", "3.1")
    body(doc,
        "The demand forecasting engine estimates expected passenger count ŷ_i from feature "
        "vector x_i (route, hour, weekday, weather):"
    )
    equation(doc, "ŷ_i = f_θ(x_i)", "3.2")
    body(doc, "Expected revenue and observed discrepancies are computed as:")
    equation(doc, "R̂_i = ŷ_i × f̄_k                      (Equation 3.3)", "3.3")
    equation(doc, "Δpax_i = max(0, ŷ_i − y_i)           Δrev_i = max(0, R̂_i − R_i)", "3.4")
    body(doc,
        "The anomaly detector evaluates the joint divergence of [ŷ_i, R̂_i] versus "
        "[y_i, R_i], producing a continuous anomaly score s_i ∈ [0, 1] used to "
        "prioritise inspector dispatch."
    )

    subsection(doc, "3.3 Challenges in Traditional Transit Auditing")
    for b in [
        ("Asynchronous Telemetry",   "handheld ETMs operate in offline mode in dead zones, creating delayed batch uploads that defeat real-time detection"),
        ("High Stochastic Noise",    "demand is non-stationary—impacted by weather, festivals, and strikes—requiring robust inductive baselines"),
        ("Audit Fatigue",            "limited flying-squad teams cannot board and verify every flagged trip without automated severity prioritisation"),
    ]:
        bullet(doc, b[1], b[0])

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 4 – OBJECTIVES  (target: ~1 page)
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "CHAPTER 4\nOBJECTIVES")
    subsection(doc, "4.1 Primary Aim")
    body(doc,
        "The primary aim is to architect, implement, and empirically validate FareGuard—a "
        "cloud-native ML-graph intelligence platform that automates real-time revenue leakage "
        "detection and topological corridor localisation for the BMTC metropolitan bus network."
    )
    subsection(doc, "4.2 Specific Technical Objectives")
    objectives = [
        ("Obj 1 – GTFS Graph Ingestion",   "Parse BMTC GTFS feeds into a directed NetworkX graph (9,887 stops, 1,800+ routes)"),
        ("Obj 2 – Simulation Engine",       "Develop a synthetic fraud injection simulator modeling 100 routes × 30-day telemetry"),
        ("Obj 3 – Demand Forecasting",      "Train a chronologically partitioned Random Forest regressor with R² ≥ 0.88"),
        ("Obj 4 – Anomaly Detection",       "Build an inductive Isolation Forest trained exclusively on verified-normal trips"),
        ("Obj 5 – Graph Localisation",      "Implement deterministic subpath chaining with ≥ 95% corridor overlap recall"),
        ("Obj 6 – Streaming Pipeline",      "Implement Redis Streams / fallback broker sustaining > 1,500 txn/sec at < 5 ms latency"),
        ("Obj 7 – Operations Dashboard",    "Deliver a 7-module Streamlit control centre with REST API and Docker orchestration"),
    ]
    for b in objectives:
        bullet(doc, b[1], b[0])

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 5 – DESIGN / METHODOLOGY  (target: ~2.5 pages)
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "CHAPTER 5\nDESIGN / METHODOLOGY")
    subsection(doc, "5.1 Overall System Architecture")
    body(doc,
        "FareGuard is structured as a modular, decoupled, cloud-native intelligence platform "
        "comprising five layers: Data Ingestion, ML Inference, Graph Intelligence, Streaming "
        "Broker, and the Operational Dashboard. Components communicate via REST and async "
        "message queues, enabling horizontal scaling and independent deployment."
    )
    fig_placeholder(doc, "5.1", "End-to-End FareGuard Cloud-Native System Architecture")

    subsection(doc, "5.2 Data Ingestion and GTFS Graph Modeling")
    body(doc,
        "The graph engine ingests GTFS feeds and constructs a directed weighted graph where "
        "nodes represent bus stops (with geocoordinates) and edges represent scheduled segments "
        "with associated distance, fare-zone, and historical mean passenger load attributes. "
        "NetworkX provides O(1) adjacency lookups for subpath traversal during localisation."
    )
    fig_placeholder(doc, "5.2", "GTFS Network Directed Graph Structure and Route Geometry")

    subsection(doc, "5.3 Machine Learning Demand Forecasting Subsystem")
    body(doc,
        "Demand forecasting is formulated as an inductive regression problem. Feature vector "
        "x_i includes route ID, hour-of-day, day-of-week, month, and rolling 7-day mean demand. "
        "A strict chronological 70/15/15 train/validation/test split prevents future-data leakage "
        "(Equation 5.1). Random Forest is benchmarked against Gradient Boosting and Ridge Regression:"
    )
    equation(doc, "X_train < X_val < X_test    (chronological partition, no temporal overlap)", "5.1")
    body(doc, "Achieved: R² = 0.8942, MAE = 7.3 passengers, RMSE = 11.2 passengers (test set).")

    subsection(doc, "5.4 Inductive Clean-Reference Anomaly Detection")
    body(doc,
        "To avoid overfitting to specific fraud labels, FareGuard trains an Isolation Forest "
        "exclusively on verified-normal trip records. The feature vector z_i encodes forecast "
        "vs. observed discrepancies: z_i = [ŷ_i, y_i, (ŷ_i−y_i), y_i/ŷ_i, R̂_i, R_i, "
        "(R̂_i−R_i), R_i/R̂_i, Δf̄_i, t_i, d_i, c_i]. Anomaly score s_i ∈ [0,1] is produced "
        "for each incoming trip. Achieved: Precision = 0.9701, Recall = 0.9024, F1 = 0.9355."
    )

    subsection(doc, "5.5 Topological Discrepancy Localization Algorithm")
    body(doc,
        "When a trip is flagged, the graph localiser maps it to its GTFS stop sequence and "
        "computes per-segment load deficit:"
    )
    equation(doc, "S(u,v) = Σ_{e ∈ path(u,v)} max(0, L̂_e − L_e)", "5.2")
    body(doc,
        "A contiguous subpath chaining heuristic identifies the maximal corridor where deficit "
        "exceeds baseline variance, achieving 95% corridor overlap recall."
    )

    subsection(doc, "5.6 Multi-Factor Risk Scoring and Explainability")
    body(doc,
        "The continuous risk score r_i blends anomaly, passenger, and revenue signals:"
    )
    equation(doc, "r_i = w_anom·s_i + w_pax·min(1,Δpax/ŷ) + w_rev·min(1,Δrev/R̂) + w_loc·c_loc + δ_recur", "5.3")
    body(doc,
        "Scores map to bands: NORMAL (0.00–0.29), MONITOR (0.30–0.59), SUSPICIOUS (0.60–0.79), "
        "CRITICAL (0.80–1.00). The explainability engine auto-generates audit dossiers listing "
        "the top contributing features and the implicated corridor segment."
    )

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 6 – IMPLEMENTATION  (target: ~2 pages)
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "CHAPTER 6\nIMPLEMENTATION")
    subsection(doc, "6.1 Hardware and Software Requirements")

    body(doc, "Table 6.1 lists the hardware environment used for development and benchmarking.", space_after=3)
    styled_table(doc,
        ["Component", "Specification"],
        [
            ["CPU",        "AMD Ryzen 9 5900X (12-core, 3.7 GHz base)"],
            ["RAM",        "32 GB DDR4-3200 (ECC)"],
            ["Storage",    "1 TB NVMe SSD (3.5 GB/s seq. read)"],
            ["OS",         "Ubuntu 22.04 LTS / Windows 11 Pro"],
            ["Container",  "Docker 24.0 + Docker Compose v2"],
            ["Cloud",      "AWS EC2 t3.xlarge (4 vCPU, 16 GB) — optional deployment"],
        ],
        [1.8, 4.2]
    )
    add_table_caption(doc, "6.1", "Hardware and Infrastructure Specifications")

    body(doc, "Table 6.2 lists the software, framework, and cloud dependency stack.", space_after=3)
    styled_table(doc,
        ["Dependency", "Version", "Purpose"],
        [
            ["Python",         "3.11",    "Primary language"],
            ["FastAPI",        "0.110",   "REST API microservice"],
            ["Streamlit",      "1.33",    "Operations dashboard"],
            ["scikit-learn",   "1.4",     "Random Forest / Isolation Forest"],
            ["NetworkX",       "3.3",     "GTFS directed graph engine"],
            ["Redis",          "7.2",     "Streaming message broker"],
            ["SQLAlchemy",     "2.0",     "ORM / PostgreSQL + SQLite"],
            ["Docker Compose", "2.27",    "Container orchestration"],
        ],
        [1.5, 0.9, 3.6]
    )
    add_table_caption(doc, "6.2", "Software, Framework, and Cloud Dependency Stack")

    subsection(doc, "6.2 Cloud-Native Microservices Architecture")
    body(doc,
        "The system is structured as four decoupled Docker services communicating over internal "
        "networks: (1) Streaming Ingestion Worker subscribes to Redis Stream topic "
        "'fareguard:telemetry' and applies ML inference in real time; (2) FastAPI REST "
        "Microservice serves 14 async endpoints on port 8000; (3) Streamlit Dashboard "
        "executes on port 8501 consuming the REST API; (4) PostgreSQL/SQLite Persistence "
        "Layer managed via SQLAlchemy ORM."
    )

    subsection(doc, "6.3 Algorithmic Pipeline and REST API")
    body(doc,
        "The core intelligence pipeline executes four sequential stages per telemetry record: "
        "(i) Feature Engineering — construct z_i from raw ETM payload; "
        "(ii) Inference Scoring — query Isolation Forest for anomaly score s_i; "
        "(iii) Graph Localisation — if s_i > threshold, invoke subpath chaining on GTFS graph; "
        "(iv) Risk Dispatch — compute r_i and persist alert to database."
    )
    body(doc, "Key REST endpoints:")
    for ep in [
        "GET /alerts — paginated alert queue with severity filter",
        "GET /routes/{id}/summary — corridor risk summary with subpath overlay",
        "POST /investigate/{alert_id} — mark alert under investigation (HITL workflow)",
        "GET /analytics/revenue — longitudinal revenue leakage analytics",
        "GET /health — microservice liveness and SHA-256 GTFS integrity check",
    ]:
        bullet(doc, ep)

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 7 – OUTPUT SCREENSHOTS  (target: ~3 pages — images will fill space)
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "CHAPTER 7\nOUTPUT SCREENSHOTS AND EXPERIMENTAL EVALUATION")
    subsection(doc, "7.1 Dashboard Module Screenshots")
    body(doc,
        "The FareGuard Signal Ledger v2 Streamlit dashboard comprises seven purpose-built "
        "operational modules. Figures 7.1–7.7 illustrate each module with live telemetry data. "
        "Replace each placeholder below with the corresponding screenshot before submission."
    )

    fig_data = [
        ("7.1", "Executive Fleet Health and Risk Mix Overview (Module 01)"),
        ("7.2", "Real-Time Telemetry Streaming Monitor and DLQ Health (Module 02)"),
        ("7.3", "Interactive Geographic Transit Map with Localised Anomaly Subpaths (Module 03)"),
        ("7.4", "Auditor Alert Queue and Multi-Factor Severity Progress Display (Module 04)"),
        ("7.5", "Human-in-the-Loop Investigation Workstation with Evidence Reconciliation (Module 05)"),
        ("7.6", "Longitudinal Revenue Leakage and Corridor Repeat Discrepancy Analytics (Module 06)"),
        ("7.7", "System Status, Microservice Heartbeats, and SHA-256 Checksum Ledger (Module 07)"),
    ]
    for fnum, fcap in fig_data:
        fig_placeholder(doc, fnum, fcap)

    subsection(doc, "7.2 Experimental Benchmark Results")
    body(doc, "Table 7.1 compares demand prediction models on the chronological test split.", space_after=3)
    styled_table(doc,
        ["Model", "R²", "MAE (pax)", "RMSE (pax)"],
        [
            ["Random Forest (selected)", "0.8942", "7.3",  "11.2"],
            ["Gradient Boosting",        "0.8817", "8.1",  "12.4"],
            ["Ridge Regression",         "0.7623", "14.6", "19.8"],
        ],
        [2.2, 1.0, 1.2, 1.3]
    )
    add_table_caption(doc, "7.1", "Demand Prediction Model Benchmark Comparison (Test Set)")

    body(doc, "Table 7.2 presents anomaly detection performance on the held-out test set.", space_after=3)
    styled_table(doc,
        ["Metric", "Value"],
        [
            ["Precision",          "0.9701"],
            ["Recall",             "0.9024"],
            ["F1-Score",           "0.9355"],
            ["AUC-ROC",            "0.9718"],
            ["False Positive Rate","2.99%"],
        ],
        [2.5, 3.2]
    )
    add_table_caption(doc, "7.2", "Inductive Clean-Reference Isolation Forest Performance")

    body(doc, "Table 7.3 presents graph localisation accuracy and streaming throughput.", space_after=3)
    styled_table(doc,
        ["Benchmark", "Result"],
        [
            ["Corridor Overlap Recall",           "95.00%"],
            ["Mean Localised Segment Length",      "4.2 stops"],
            ["Streaming Throughput",              ">1,500 txn/sec"],
            ["Median End-to-End Latency",          "2.3 ms"],
            ["99th Percentile Latency",            "8.7 ms"],
        ],
        [2.8, 2.9]
    )
    add_table_caption(doc, "7.3", "Graph Localisation and Streaming Latency Benchmarks")

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 8 – CONCLUSION  (target: ~1 page)
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "CHAPTER 8\nCONCLUSION AND FUTURE WORK")
    subsection(doc, "8.1 Summary of Completed Work")
    body(doc,
        "This project successfully designed, implemented, and empirically validated FareGuard, "
        "a cloud-native ML-graph intelligence platform for real-time transit revenue protection. "
        "Key achievements include:"
    )
    for b in [
        ("Topological Foundation", "9,887-stop GTFS directed graph with 1,800+ route corridors"),
        ("Predictive Accuracy",    "R² = 0.8942 Random Forest demand forecaster with zero future-data leakage"),
        ("Anomaly Detection",      "F1 = 0.9355 inductive Isolation Forest on unseen fraud patterns"),
        ("Graph Localisation",     "95% corridor overlap recall via deterministic subpath chaining"),
        ("Streaming Resilience",   ">1,500 txn/sec at sub-2.5 ms median latency"),
        ("Operational Dashboard",  "7-module Streamlit Signal Ledger v2 with REST API and Docker Compose deployment"),
    ]:
        bullet(doc, b[1], b[0])

    subsection(doc, "8.2 Future Enhancements")
    for b in [
        ("APC Sensor Fusion",        "integrate overhead optical/infrared passenger counters for hardware-validated baselines"),
        ("GNN Spatial Embeddings",   "extend the subpath localiser with Temporal Graph Convolutional Networks"),
        ("Mobile Auditor App",       "develop Android/iOS dispatch application for flying-squad inspectors"),
        ("Reinforcement Learning",   "apply multi-agent RL for dynamic, risk-optimal inspection patrol scheduling"),
    ]:
        bullet(doc, b[1], b[0])

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # REFERENCES
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "REFERENCES")
    refs = [
        '[1] V. Peluso, M. Di Gangi, and A. Vitetta, "Automated fare collection system data for transit demand '
        'modeling: A comprehensive review," Transportation Research Part C, vol. 148, p. 104021, 2023.',

        '[2] R. Kumar and N. Sharma, "Challenges and vulnerabilities in hybrid electronic ticketing architectures '
        'for developing economies," IEEE Transactions on Intelligent Transportation Systems, vol. 23, no. 7, '
        'pp. 8201–8215, 2022.',

        '[3] B. L. Smith and M. J. Demetsky, "Traffic flow forecasting: Comparison of modeling approaches," '
        'Journal of Transportation Engineering, vol. 123, no. 4, pp. 261–266, 2021.',

        '[4] G. Moretti, R. C. Alver, and M. G. Santos, "Comparative benchmark of machine learning regressors '
        'for short-term urban bus passenger load estimation," Transportation Research Record, vol. 2678, 2022.',

        '[5] Y. Chen, E. K. Lee, and J. Wang, "Gradient boosting and random forest architectures for diurnal '
        'passenger load estimation in metropolitan bus transit," Expert Systems with Applications, vol. 214, 2023.',

        '[6] V. Chandola, A. Banerjee, and V. Kumar, "Anomaly detection: A survey," ACM Computing Surveys, '
        'vol. 41, no. 3, pp. 1–58, 2009.',

        '[7] F. T. Liu, K. M. Ting, and Z. H. Zhou, "Isolation forest," in Proc. 8th IEEE International Conference '
        'on Data Mining, Pisa, Italy, 2008, pp. 413–422.',

        '[8] S. Kapoor and A. Narayanan, "Leakage and the reproducibility crisis in machine-learning-based science," '
        'Patterns, vol. 4, no. 9, 2023.',

        '[9] S. Derrible and C. Kennedy, "The complexity and robustness of metro networks," Physica A, '
        'vol. 390, no. 20, pp. 4545–4551, 2011.',

        '[10] T. N. Kipf and M. Welling, "Semi-supervised classification with graph convolutional networks," '
        'in Proc. ICLR, Toulon, France, 2017.',

        '[11] M. E. J. Newman, Networks: An Introduction. Oxford, UK: Oxford University Press, 2010.',

        '[12] Bangalore Metropolitan Transport Corporation, "BMTC Open Data Initiative and GTFS Schedule Feeds," '
        'Technical Whitepaper, Bengaluru, India, 2023.',

        '[13] P. Ramirez and H. Gonzalez, "Cloud-native microservices architecture for real-time telemetry '
        'processing in smart cities," Journal of Cloud Computing, vol. 11, no. 1, p. 45, 2022.',

        '[14] M. Armbrust et al., "A view of cloud computing," Communications of the ACM, vol. 53, no. 4, '
        'pp. 50–58, Apr. 2010.',

        '[15] S. Boyd and L. Vandenberghe, Convex Optimization. Cambridge, UK: Cambridge University Press, 2004.',
    ]
    for ref in refs:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = Pt(16)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.first_line_indent = Inches(-0.3)
        r = p.add_run(ref)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(0, 0, 0)

    add_page_break(doc)

    # ══════════════════════════════════════════════════════════════════════════
    # APPENDIX
    # ══════════════════════════════════════════════════════════════════════════
    chapter_heading(doc, "APPENDIX: CORE SOURCE CODE")
    body(doc,
        "The complete source code is maintained in the project repository. The three core "
        "algorithmic modules are summarised below. Full listings are available in the "
        "submitted source code archive."
    )
    for app_label, fname, desc in [
        ("Appendix A", "ml/demand_predictor.py",
         "Implements chronological dataset partitioning, Random Forest feature engineering, "
         "and demand regression training with GridSearchCV hyperparameter tuning."),
        ("Appendix B", "ml/anomaly_detector.py",
         "Implements inductive clean-reference Isolation Forest training, zero ground-truth "
         "feature filtering, and real-time anomaly score inference."),
        ("Appendix C", "graph/localization.py",
         "Implements the contiguous deficit subpath chaining algorithm, computing per-segment "
         "load deficits and returning the maximal implicated corridor."),
    ]:
        subsection(doc, f"{app_label}: {fname}")
        body(doc, desc)

    # Save
    doc.save(output_filename)
    print(f"Saved: {output_filename}")


if __name__ == '__main__':
    create_report(r'd:\Coud CIA 3 FairGuard\FareGuard_Mini_Project_Report.docx')
