"""
Script to generate the complete academic mini project report for FareGuard
Strictly adhering to:
- A4 size bond paper, 1.5 line spacing
- Margins: Left 1.25", Right 1.0", Top 0.75", Bottom 0.75"
- Font: Times New Roman
- Sizes: Chapter Title 18pt bold, Section 16pt bold, Subsection 14pt bold, Text 12pt regular
- Pure Black and White (RGBColor(0,0,0), grayscale tables, no colors)
- Numbered equations, figures, tables
- Comprehensive, detailed 21-24 pages coverage
"""

import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_border(cell, **kwargs):
    """
    kwargs: top, bottom, left, right
    values: dict(sz=12, val='single', color='000000', space='0')
    """
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

def create_report(output_filename):
    doc = docx.Document()
    
    # Page Setup
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.left_margin = Inches(1.25)
    section.right_margin = Inches(1.00)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    
    # Set default style
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(12)
    normal_style.font.color.rgb = RGBColor(0, 0, 0)
    
    # Configure heading styles for Auto-TOC support
    h1_style = doc.styles['Heading 1']
    h1_style.font.name = 'Times New Roman'
    h1_style.font.size = Pt(18)
    h1_style.font.bold = True
    h1_style.font.color.rgb = RGBColor(0, 0, 0)
    h1_style.paragraph_format.line_spacing = 1.5
    h1_style.paragraph_format.space_before = Pt(12)
    h1_style.paragraph_format.space_after = Pt(12)
    h1_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    h2_style = doc.styles['Heading 2']
    h2_style.font.name = 'Times New Roman'
    h2_style.font.size = Pt(16)
    h2_style.font.bold = True
    h2_style.font.color.rgb = RGBColor(0, 0, 0)
    h2_style.paragraph_format.line_spacing = 1.5
    h2_style.paragraph_format.space_before = Pt(14)
    h2_style.paragraph_format.space_after = Pt(6)
    h2_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    h3_style = doc.styles['Heading 3']
    h3_style.font.name = 'Times New Roman'
    h3_style.font.size = Pt(14)
    h3_style.font.bold = True
    h3_style.font.color.rgb = RGBColor(0, 0, 0)
    h3_style.paragraph_format.line_spacing = 1.5
    h3_style.paragraph_format.space_before = Pt(10)
    h3_style.paragraph_format.space_after = Pt(4)
    h3_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Helpers
    def add_p(text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=6, bold=False, italic=False, size=12):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after = Pt(space_after)
        if text:
            run = p.add_run(text)
            run.font.name = 'Times New Roman'
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_title(text, include_in_toc=True):
        p = doc.add_paragraph(style='Heading 1' if include_in_toc else None)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(12)
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(18)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_h1(text):
        p = doc.add_paragraph(style='Heading 2')
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_h2(text):
        p = doc.add_paragraph(style='Heading 3')
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_bullet(text, level=0):
        p = doc.add_paragraph(style='List Bullet')
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def add_figure_box(fig_num, caption, desc, dimensions="Height: 3.5 inches x Width: 6.0 inches"):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        cell.width = Inches(6.0)
        set_cell_border(cell)
        set_cell_shading(cell, "FAFAFA")
        
        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cp.paragraph_format.line_spacing = 1.15
        cp.paragraph_format.space_before = Pt(12)
        cp.paragraph_format.space_after = Pt(12)
        
        r1 = cp.add_run(f"[ SCREENSHOT / FIGURE PLACEHOLDER ]\n")
        r1.font.name = 'Times New Roman'
        r1.font.size = Pt(11)
        r1.font.bold = True
        r1.font.color.rgb = RGBColor(0, 0, 0)
        
        r2 = cp.add_run(f"Figure {fig_num}: {caption}\n")
        r2.font.name = 'Times New Roman'
        r2.font.size = Pt(11)
        r2.font.bold = True
        r2.font.color.rgb = RGBColor(0, 0, 0)
        
        r3 = cp.add_run(f"Recommended Dimensions: {dimensions}\n")
        r3.font.name = 'Times New Roman'
        r3.font.size = Pt(10)
        r3.font.italic = True
        r3.font.color.rgb = RGBColor(0, 0, 0)
        
        r4 = cp.add_run(f"Action: {desc}")
        r4.font.name = 'Times New Roman'
        r4.font.size = Pt(10)
        r4.font.color.rgb = RGBColor(0, 0, 0)
        
        # Caption below
        cap_p = doc.add_paragraph()
        cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_p.paragraph_format.line_spacing = 1.5
        cap_p.paragraph_format.space_before = Pt(4)
        cap_p.paragraph_format.space_after = Pt(12)
        r_cap = cap_p.add_run(f"Figure {fig_num}: {caption}")
        r_cap.font.name = 'Times New Roman'
        r_cap.font.size = Pt(11)
        r_cap.font.bold = True
        r_cap.font.color.rgb = RGBColor(0, 0, 0)

    # =========================================================================
    # 1. TITLE PAGE
    # =========================================================================
    add_p("DEPARTMENT OF", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=18, space_after=2, bold=True, size=16)
    add_p("AI AND DATA SCIENCE ENGINEERING", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=18, bold=True, size=16)
    
    add_p("CSE532P (CLOUD COMPUTING)", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=6, bold=True, size=14)
    add_p("MINI PROJECT REPORT", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=24, bold=True, size=16)
    
    add_title("FAREGUARD: A CLOUD-NATIVE ML-GRAPH INTELLIGENCE PLATFORM FOR REAL-TIME REVENUE LEAKAGE DETECTION AND TRANSIT AUDITING", include_in_toc=False)
    
    add_p("A Mini Project report submitted in partial fulfilment of the requirements for the award of the degree of", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=18, space_after=8, italic=True, size=12)
    add_p("Bachelor of Technology", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, bold=True, size=14)
    add_p("in", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, size=12)
    add_p("Computer Science and Engineering\n(Artificial Intelligence and Machine Learning)", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=24, bold=True, size=14)
    
    add_p("School of Engineering and Technology", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=18, space_after=2, bold=True, size=13)
    add_p("CHRIST (Deemed to be University)", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, bold=True, size=14)
    add_p("Kumbalagodu, Bengaluru - 560 074", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=8, size=12)
    add_p("September 2026", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=0, bold=True, size=12)
    
    doc.add_page_break()

    # =========================================================================
    # 2. CERTIFICATE PAGE
    # =========================================================================
    add_title("CERTIFICATE", include_in_toc=True)
    
    cert_p = add_p(
        "This is to certify that the mini project work entitled \"FAREGUARD: A CLOUD-NATIVE ML-GRAPH INTELLIGENCE "
        "PLATFORM FOR REAL-TIME REVENUE LEAKAGE DETECTION AND TRANSIT AUDITING\" has been successfully completed by "
        "[Student Name] (Register No.: [Register Number]) in partial fulfilment of the requirements for the course "
        "CSE532P (CLOUD COMPUTING) for the award of Bachelor of Technology in Computer Science and Engineering "
        "(Artificial Intelligence and Machine Learning) at the School of Engineering and Technology, CHRIST (Deemed to be University), "
        "Bengaluru during the academic year 2026–2027.",
        space_before=18, space_after=24
    )
    
    # Signature Table
    sig_table = doc.add_table(rows=2, cols=2)
    sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    sig_table.autofit = False
    
    c00 = sig_table.cell(0, 0)
    c01 = sig_table.cell(0, 1)
    c10 = sig_table.cell(1, 0)
    c11 = sig_table.cell(1, 1)
    
    c00.width = Inches(3.2)
    c01.width = Inches(3.2)
    c10.width = Inches(3.2)
    c11.width = Inches(3.2)
    
    p00 = c00.paragraphs[0]
    p00.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p00.paragraph_format.line_spacing = 1.5
    r00 = p00.add_run("_____________________________\nFACULTY-IN-CHARGE")
    r00.font.name = "Times New Roman"
    r00.font.bold = True
    r00.font.size = Pt(11)
    
    p01 = c01.paragraphs[0]
    p01.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p01.paragraph_format.line_spacing = 1.5
    r01 = p01.add_run("_____________________________\nHEAD OF THE DEPARTMENT")
    r01.font.name = "Times New Roman"
    r01.font.bold = True
    r01.font.size = Pt(11)
    
    p10 = c10.paragraphs[0]
    p10.paragraph_format.space_before = Pt(36)
    p10.paragraph_format.line_spacing = 1.5
    r10 = p10.add_run("EXAMINER 1: ____________________\nDate: ")
    r10.font.name = "Times New Roman"
    r10.font.bold = True
    r10.font.size = Pt(11)
    
    p11 = c11.paragraphs[0]
    p11.paragraph_format.space_before = Pt(36)
    p11.paragraph_format.line_spacing = 1.5
    p11.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r11 = p11.add_run("EXAMINER 2: ____________________\nDate: ")
    r11.font.name = "Times New Roman"
    r11.font.bold = True
    r11.font.size = Pt(11)
    
    add_p("", space_before=18, space_after=0)
    
    info_table = doc.add_table(rows=4, cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.LEFT
    info_data = [
        ("Student Name", ": [Your Full Name]"),
        ("Register Number", ": [Your Register Number]"),
        ("Examination Centre", ": School of Engineering and Technology, CHRIST (Deemed to be University)"),
        ("Date of Examination", ": September 2026")
    ]
    for row_idx, (k, v) in enumerate(info_data):
        c_k = info_table.cell(row_idx, 0)
        c_v = info_table.cell(row_idx, 1)
        c_k.width = Inches(2.2)
        c_v.width = Inches(4.2)
        pk = c_k.paragraphs[0]
        pk.paragraph_format.line_spacing = 1.5
        rk = pk.add_run(k)
        rk.font.name = "Times New Roman"
        rk.font.bold = True
        rk.font.size = Pt(11)
        
        pv = c_v.paragraphs[0]
        pv.paragraph_format.line_spacing = 1.5
        rv = pv.add_run(v)
        rv.font.name = "Times New Roman"
        rv.font.size = Pt(11)

    doc.add_page_break()

    # =========================================================================
    # 3. ABSTRACT
    # =========================================================================
    add_title("ABSTRACT")
    add_p(
        "Public bus transit corporations in metropolitan areas operate under immense logistical and economic stress. "
        "In developing economies such as India, transit agencies like the Bangalore Metropolitan Transport Corporation (BMTC) "
        "manage thousands of daily schedules carrying millions of commuters. Revenue collection in these environments relies on a "
        "heterogeneous mix of handheld Electronic Ticketing Machines (ETMs), printed cash receipts, physical daily or monthly passes, "
        "and digital QR-code transactions. Consequently, metropolitan transit authorities face substantial revenue leakage attributable "
        "to fare stage downgrading, conductor under-reporting, ticketless boarding, and electronic ticketing device synchronization delays. "
        "Traditional fare auditing methodologies depend on aggregate, end-of-month financial reconciliations. These retrospective "
        "audits fail to isolate the exact route segments, trips, and time intervals where financial deficits materialize, preventing "
        "timely intervention and accountability."
    )
    add_p(
        "This project introduces FareGuard, an end-to-end, cloud-native intelligence platform designed for real-time revenue leakage "
        "detection, topological discrepancy localization, and operational audit dispatch. FareGuard establishes an inductive, multi-stage "
        "computational architecture combining transit network graph topology, machine learning demand forecasting, unsupervised anomaly "
        "detection, and deterministic graph traversal algorithms. The system ingests General Transit Feed Specification (GTFS) data to "
        "construct a directed multigraph representing 9,887 geocoded bus stops and over 1,800 route corridors. Operating on streaming "
        "ticketing telemetry via a resilient dual-mode Redis and in-memory message broker capable of handling over 1,500 transactions "
        "per second, FareGuard predicts expected passenger loads using a high-fidelity Random Forest regressor (R² = 0.8942, MAE = 7.42 "
        "passengers). Multi-dimensional discrepancies between expected and reported collections are evaluated by a clean-reference "
        "Isolation Forest anomaly detector (F1 = 0.9355, precision = 90.62%, recall = 96.67%)."
    )
    add_p(
        "To bridge the gap between abstract anomaly flags and physical enforcement, FareGuard implements a topological discrepancy "
        "localizer that traverses the transit network graph to isolate contiguous corridor subpaths with high deficit concentration, "
        "achieving a 95.00% conditional overlap recall. A calibrated multi-factor risk engine synthesizes model scores, monetary losses, "
        "and route recurrence into actionable risk categories (NORMAL, MONITOR, SUSPICIOUS, HIGH_RISK) accompanied by explainable "
        "auditor dossiers with zero ground-truth label leakage. Deployed using containerized microservices comprising a FastAPI REST "
        "backend and a Streamlit operational control center, FareGuard empowers transit inspectors with interactive geographic maps, "
        "reconciliation ledgers, and immutable audit trails, demonstrating a cloud-native paradigm for sustainable urban transit revenue protection."
    )
    add_p(
        "Keywords: Cloud Computing, Machine Learning, Anomaly Detection, GTFS Transit Graph, Revenue Protection, BMTC, Microservices, FastAPI, Streamlit.",
        space_before=8, bold=True, size=11
    )
    doc.add_page_break()

    # =========================================================================
    # 4. TABLE OF CONTENTS
    # =========================================================================
    add_title("TABLE OF CONTENTS", include_in_toc=False)
    
    # Native dynamic Word TOC field paragraph
    p_dyn = doc.add_paragraph()
    p_dyn.paragraph_format.line_spacing = 1.15
    p_dyn.paragraph_format.space_before = Pt(4)
    p_dyn.paragraph_format.space_after = Pt(8)
    
    r_fld_begin = p_dyn.add_run()
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    r_fld_begin._r.append(fldChar1)
    
    r_instr = p_dyn.add_run()
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = 'TOC \\o "1-3" \\h \\z \\u'
    r_instr._r.append(instrText)
    
    r_fld_sep = p_dyn.add_run()
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    r_fld_sep._r.append(fldChar2)
    
    # Static structured TOC Table inside the field for immediate display and fallback
    toc_table = doc.add_table(rows=1, cols=3)
    toc_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    toc_table.autofit = False
    
    hdr_cells = toc_table.rows[0].cells
    hdr_cells[0].width = Inches(1.0)
    hdr_cells[1].width = Inches(4.5)
    hdr_cells[2].width = Inches(0.8)
    
    set_cell_border(hdr_cells[0])
    set_cell_border(hdr_cells[1])
    set_cell_border(hdr_cells[2])
    set_cell_shading(hdr_cells[0], "EAEAEA")
    set_cell_shading(hdr_cells[1], "EAEAEA")
    set_cell_shading(hdr_cells[2], "EAEAEA")
    
    for i, title in enumerate(["Chapter", "Title", "Page"]):
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i != 1 else WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(title)
        run.font.name = "Times New Roman"
        run.font.bold = True
        run.font.size = Pt(11)
        
    toc_entries = [
        ("", "Certificate", "ii"),
        ("", "Abstract", "iii"),
        ("", "List of Figures", "v"),
        ("", "List of Tables", "vi"),
        ("1", "INTRODUCTION", "1"),
        ("1.1", "Background and Motivation", "1"),
        ("1.2", "Context of Metropolitan Bus Transit (BMTC)", "2"),
        ("1.3", "Cloud Computing in Public Transit Analytics", "3"),
        ("1.4", "Scope of the Project", "4"),
        ("2", "LITERATURE REVIEW", "5"),
        ("2.1", "Evolution of Automated Fare Collection (AFC) Systems", "5"),
        ("2.2", "Passenger Demand Forecasting Models", "6"),
        ("2.3", "Anomaly Detection and Revenue Leakage Identification", "7"),
        ("2.4", "Graph-Based Spatial-Temporal Transit Network Modeling", "8"),
        ("2.5", "Summary of Research Gaps", "9"),
        ("3", "PROBLEM STATEMENT", "10"),
        ("3.1", "Formal Problem Definition", "10"),
        ("3.2", "Mathematical Formulation of Revenue Discrepancy", "10"),
        ("3.3", "Challenges in Traditional Transit Auditing", "11"),
        ("4", "OBJECTIVES", "12"),
        ("4.1", "Primary Aim", "12"),
        ("4.2", "Specific Technical Objectives", "12"),
        ("5", "DESIGN / METHODOLOGY", "13"),
        ("5.1", "Overall System Architecture", "13"),
        ("5.2", "Data Ingestion and GTFS Graph Modeling", "14"),
        ("5.3", "Machine Learning Demand Forecasting Subsystem", "15"),
        ("5.4", "Inductive Clean-Reference Anomaly Detection", "16"),
        ("5.5", "Topological Discrepancy Localization Algorithm", "17"),
        ("5.6", "Multi-Factor Operational Risk Scoring Engine", "18"),
        ("5.7", "Explainability and Evidence Synthesis", "19"),
        ("6", "IMPLEMENTATION", "20"),
        ("6.1", "Hardware and Software Requirements", "20"),
        ("6.2", "Cloud-Native Microservices Architecture", "21"),
        ("6.3", "Algorithmic Pipeline Implementation", "22"),
        ("6.4", "Data Persistence and REST API Engine", "24"),
        ("7", "OUTPUT SCREENSHOTS AND EXPERIMENTAL EVALUATION", "25"),
        ("7.1", "Operational Control Center Dashboard Modules", "25"),
        ("7.2", "Experimental Benchmark Results", "27"),
        ("7.3", "Ablation and Streaming Latency Analysis", "28"),
        ("8", "CONCLUSION AND FUTURE WORK", "29"),
        ("8.1", "Summary of Completed Work", "29"),
        ("8.2", "Future Enhancements", "30"),
        ("", "REFERENCES", "31"),
        ("", "APPENDIX: CORE SOURCE CODE", "33"),
    ]
    
    for ch, title, pg in toc_entries:
        row = toc_table.add_row()
        c0, c1, c2 = row.cells[0], row.cells[1], row.cells[2]
        c0.width = Inches(1.0)
        c1.width = Inches(4.5)
        c2.width = Inches(0.8)
        set_cell_border(c0)
        set_cell_border(c1)
        set_cell_border(c2)
        
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p0.paragraph_format.line_spacing = 1.15
        r0 = p0.add_run(ch)
        r0.font.name = "Times New Roman"
        r0.font.bold = (len(ch) == 1 and ch.isdigit()) or (ch == "")
        r0.font.size = Pt(10)
        
        p1 = c1.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p1.paragraph_format.line_spacing = 1.15
        r1 = p1.add_run(title)
        r1.font.name = "Times New Roman"
        r1.font.bold = (len(ch) == 1 and ch.isdigit()) or (ch == "" and title in ["REFERENCES", "APPENDIX: CORE SOURCE CODE", "CERTIFICATE", "ABSTRACT", "LIST OF FIGURES", "LIST OF TABLES"])
        r1.font.size = Pt(10)
        
        p2 = c2.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p2.paragraph_format.line_spacing = 1.15
        r2 = p2.add_run(pg)
        r2.font.name = "Times New Roman"
        r2.font.bold = (len(ch) == 1 and ch.isdigit()) or (ch == "")
        r2.font.size = Pt(10)

    # Closing run of the dynamic TOC field
    p_end = doc.add_paragraph()
    p_end.paragraph_format.space_before = Pt(4)
    p_end.paragraph_format.space_after = Pt(4)
    r_fld_end = p_end.add_run()
    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'end')
    r_fld_end._r.append(fldChar3)

    doc.add_page_break()

    # List of Figures & Tables
    add_title("LIST OF FIGURES")
    figures_list = [
        ("Figure 5.1", "End-to-End FareGuard Cloud-Native System Architecture", "13"),
        ("Figure 5.2", "GTFS Network Directed Graph Structure and Route Geometry", "14"),
        ("Figure 5.3", "Temporal Train/Validation/Test Split for Zero Future-Data Leakage", "15"),
        ("Figure 5.4", "Inductive Clean-Reference Isolation Forest Anomaly Detection Process", "16"),
        ("Figure 5.5", "Topological Discrepancy Localization along Bus Stop Corridors", "17"),
        ("Figure 6.1", "Microservices Container Interaction and Communication Flowchart", "21"),
        ("Figure 7.1", "Streamlit Control Center - Executive Fleet Health and Risk Mix Overview", "25"),
        ("Figure 7.2", "Real-Time Telemetry Streaming Monitor and DLQ Health", "26"),
        ("Figure 7.3", "Interactive Geographic Transit Map with Localized Anomaly Subpaths", "26"),
        ("Figure 7.4", "Auditor Alert Queue and Multi-Factor Severity Progress Display", "27"),
        ("Figure 7.5", "Human-in-the-Loop Investigation Workstation with Evidence Reconciliation", "27"),
        ("Figure 7.6", "Longitudinal Revenue Leakage and Corridor Repeat Discrepancy Analytics", "28"),
        ("Figure 7.7", "System Status, Microservice Heartbeats, and SHA-256 Checksum Ledger", "28"),
    ]
    for num_f, cap_f, pg_f in figures_list:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.2
        p.paragraph_format.space_after = Pt(4)
        r1 = p.add_run(f"{num_f}: {cap_f}")
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(11)
        r2 = p.add_run(f"  ...........................................................................  {pg_f}")
        r2.font.name = "Times New Roman"
        r2.font.size = Pt(11)

    add_p("", space_before=12, space_after=6)
    add_title("LIST OF TABLES")
    tables_list = [
        ("Table 6.1", "Hardware and Infrastructure Specifications", "20"),
        ("Table 6.2", "Software, Framework, and Cloud Dependency Stack", "21"),
        ("Table 7.1", "Demand Prediction Model Benchmark Comparison", "27"),
        ("Table 7.2", "Revenue Anomaly Detection Performance Metrics", "27"),
        ("Table 7.3", "Topological Graph Discrepancy Localization Evaluation", "28"),
        ("Table 7.4", "Streaming Telemetry Ingestion Latency and Throughput Benchmarks", "28"),
    ]
    for num_t, cap_t, pg_t in tables_list:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.2
        p.paragraph_format.space_after = Pt(4)
        r1 = p.add_run(f"{num_t}: {cap_t}")
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(11)
        r2 = p.add_run(f"  ...........................................................................  {pg_t}")
        r2.font.name = "Times New Roman"
        r2.font.size = Pt(11)

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 1: INTRODUCTION
    # =========================================================================
    add_title("CHAPTER 1\nINTRODUCTION")
    
    add_h1("1.1 Background and Motivation")
    add_p(
        "Metropolitan surface public transportation systems constitute the vital circulatory infrastructure of contemporary "
        "urban economies. Municipal transit undertakings operate extensive bus fleets that accommodate millions of commuter trips "
        "every day, connecting residential colonies, commercial hubs, industrial zones, and educational institutions. "
        "In developing economies, bus transit networks represent the most cost-effective, energy-efficient, and accessible mode of "
        "mechanized mobility. However, public transport operators consistently face acute structural deficits, escalating operating "
        "expenditures, volatile fuel prices, and severe revenue loss attributable to fare evasion and collection irregularities."
    )
    add_p(
        "Unlike enclosed rapid rail or metro systems where physical fare barriers, turnstiles, and automated platform gates enforce "
        "strict pay-to-enter protocols, metropolitan bus transit remains inherently permeable. Bus stops are distributed across "
        "uncontrolled roadside environments, passenger boarding is highly decentralized, and fare collection is mediated either by "
        "on-board conductors utilizing handheld Electronic Ticketing Machines (ETMs) or via mixed cash and mobile payment modes. "
        "This operational reality introduces profound vulnerabilities to revenue leakage. Conductor under-reporting, fare stage "
        "downgrading, cash pocketing without ticket issuance, off-line synchronization tampering, and non-compliance by passengers "
        "during peak crowding collectively drain public transport revenues."
    )

    add_h1("1.2 Context of Metropolitan Bus Transit (BMTC)")
    add_p(
        "The Bangalore Metropolitan Transport Corporation (BMTC) serves as the empirical foundation and operational benchmark for this "
        "research. BMTC manages one of the largest and most complex municipal bus fleets in South Asia, deploying over 6,500 buses "
        "across approximately 2,000 routes and facilitating more than 4 million passenger journeys per day across the Bangalore urban "
        "agglomeration. The scale and operational diversity of BMTC epitomize the challenges of modern transit revenue administration:"
    )
    add_bullet("Diverse Route Topologies: Operations span high-frequency arterial corridors, ring road loops, intra-neighborhood feeders, and long-distance IT corridor express schedules (e.g., Vajra and Vayu Vajra Volvo fleets).")
    add_bullet("Heterogeneous Ticketing Modalities: The corporation utilizes handheld ETM devices, daily printed commuter passes, monthly smart passes, student concession cards, and mobile UPI QR-code payments.")
    add_bullet("Dynamic Commuter Volumes: Severe diurnal demand fluctuations occur during morning (07:30 - 10:30) and evening (16:30 - 20:30) peak hours, resulting in passenger surges where on-board ticket issuance becomes constrained by physical dwell times.")
    add_bullet("Dispersed Operational Nodes: BMTC encompasses over 9,800 physical bus stops and 50 depots, making centralized, real-time manual surveillance physically impossible.")

    add_h1("1.3 Cloud Computing in Public Transit Analytics")
    add_p(
        "Modern cloud computing architectures provide the horizontal scalability, elasticity, distributed storage, and decoupled "
        "microservices necessary to process streaming transit telemetry at city-scale. A typical metropolitan bus fleet generates "
        "hundreds of thousands of discrete ticketing events, GPS coordinate pings, and telemetry state changes per hour. "
        "Legacy monolithic enterprise database systems fail when subjected to such high-velocity streams, resulting in delayed "
        "batch reconciliations that occur days or weeks after trip completion."
    )
    add_p(
        "By leveraging cloud-native architectural patterns—including asynchronous message brokers (e.g., Redis Streams), containerized "
        "stateless REST application programming interfaces (FastAPI), scalable object stores, and relational audit ledgers—transit authorities "
        "can execute real-time machine learning inference at the edge and in the cloud. Cloud-hosted analytics frameworks bridge the critical "
        "gap between telemetry generation and physical enforcement, transforming delayed accounting into instant operational dispatch."
    )

    add_h1("1.4 Scope of the Project")
    add_p(
        "The scope of the FareGuard platform encompasses the design, implementation, and empirical verification of an end-to-end "
        "cloud-native intelligence framework tailored for metropolitan bus operations. The system incorporates:"
    )
    add_bullet("Spatial-topological modeling of 9,887 geocoded stops and 1,800+ routes using official BMTC General Transit Feed Specification (GTFS) data.")
    add_bullet("Development of a synthetic simulation engine capable of generating realistic passenger boarding distributions and reproducing authentic revenue fraud patterns (fare downgrading, under-reporting, and ETM offline tampering).")
    add_bullet("Implementation of an asynchronous, dual-mode message streaming broker handling >1,500 transactions/sec with sub-5 millisecond latency.")
    add_bullet("Training of an inductive Random Forest demand regressor achieving R² = 0.8942 and a clean-reference Isolation Forest anomaly detector achieving F1 = 0.9355.")
    add_bullet("Development of a graph discrepancy localizer achieving 95% corridor overlap recall to pinpoint exact subpaths of leakage.")
    add_bullet("Deployment of a multi-container microservices architecture featuring a REST API and an interactive Streamlit operational control center.")

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 2: LITERATURE REVIEW
    # =========================================================================
    add_title("CHAPTER 2\nLITERATURE REVIEW")
    
    add_h1("2.1 Evolution of Automated Fare Collection (AFC) Systems")
    add_p(
        "Automated Fare Collection (AFC) systems have evolved dramatically over the past four decades, transitioning from mechanical "
        "coin-operated turnstiles and paper magnetic stripe cards to contactless smart cards (e.g., London Oyster, Hong Kong Octopus) "
        "and contemporary Account-Based Ticketing (ABT) utilizing open-loop EMV bank cards and mobile QR standards. Peluso et al. [1] "
        "examined the operational resilience of AFC infrastructure in dense urban centers, observing that while automated ticketing "
        "drastically reduces cash-handling overheads, it generates vast, complex transaction logs characterized by missing taps, "
        "offline transaction caching, and unsynchronized time stamps. In developing regions, hybrid ticketing paradigms predominate, "
        "where conductor-operated handheld ETM devices process cash alongside digital wallets, preserving manual intermediary touchpoints "
        "that remain vulnerable to human discretion and collection anomalies [2]."
    )

    add_h1("2.2 Passenger Demand Forecasting Models")
    add_p(
        "Accurate transit passenger demand prediction is fundamental for both fleet scheduling and anomaly baselining. Early transportation "
        "literature relied heavily on classical statistical formulations, including Autoregressive Integrated Moving Average (ARIMA) and "
        "seasonal Holt-Winters exponential smoothing. Smith and Demetsky [3] demonstrated that linear time-series techniques exhibit limited "
        "accuracy when subjected to rapid weather fluctuations, school holidays, and traffic congestion. To address non-linear transit "
        "dynamics, researchers introduced machine learning architectures. Moretti et al. [4] benchmarked Support Vector Regressors (SVR) "
        "and Multi-Layer Perceptrons (MLP) against ensemble tree models, demonstrating that Random Forest and Gradient Boosted Decision Trees "
        "(GBDT) deliver superior predictive power on tabular tabular transit features. Ensemble architectures effectively capture diurnal "
        "peak transitions and calendar effects without requiring extensive hyperparameter recalibration across distinct spatial corridors [5]."
    )

    add_h1("2.3 Anomaly Detection and Revenue Leakage Identification")
    add_p(
        "Anomaly detection within municipal transit operations has historically focused on vehicle GPS tracking, engine telematics fault "
        "diagnosis, and schedule delay estimation. Chandola et al. [6] provided a comprehensive taxonomy of anomaly detection, highlighting "
        "the profound difficulties of identifying point, contextual, and collective anomalies in unlabelled operational datasets. In fare "
        "protection research, traditional rule-based thresholding systems flag trips where ticket sales fall below fixed historical bounds. "
        "However, rule heuristics generate unacceptable false positive rates during inclement weather or unexpected traffic diversions. "
        "Recent literature has adopted unsupervised learning. Liu et al. [7] introduced Isolation Forests for identifying spatial-temporal "
        "outliers in transportation networks. A critical vulnerability identified in recent machine learning literature is data leakage: "
        "models trained on contaminated data or supplied with oracle ground-truth features during validation exhibit artificial perfection "
        "in laboratory settings but fail completely when deployed in real-world environments [8]."
    )

    add_h1("2.4 Graph-Based Spatial-Temporal Transit Network Modeling")
    add_p(
        "Public transportation networks are inherently topological, defined by nodes (stops/stations) and directed edges (scheduled routes "
        "and physical roadway segments). Derrible and Kennedy [9] established the utility of graph theory and network centrality metrics in "
        "analyzing transit network robustness. In contemporary spatial data science, GTFS data feeds are routinely converted into directed "
        "multigraphs to simulate transit flows, optimize headways, and compute shortest-path routing. Kipf and Welling [10] popularized "
        "Graph Convolutional Networks (GCN), which have been adapted to model spatial-temporal passenger flow across transit stations. "
        "However, for high-speed edge inference and localized discrepancy isolation along linear bus corridors, deterministic graph traversal "
        "and cumulative deficit search algorithms over directed multigraphs offer significant computational advantages, eliminating heavy GPU "
        "dependencies while ensuring exact, interpretable subpath attribution [11]."
    )

    add_h1("2.5 Summary of Research Gaps")
    add_p(
        "A rigorous synthesis of the reviewed literature reveals three fundamental research gaps that directly motivate this investigation:"
    )
    add_bullet("Temporal Coarseness: Existing revenue audit solutions operate on aggregate monthly or weekly financial statements, failing to localize deficits to specific trips, hours, or bus stop intervals.")
    add_bullet("Topological Disconnect: Conventional machine learning anomaly detectors generate scalar risk flags without mapping the discrepancy back to the physical transit graph geometry, leaving inspectors without actionable spatial guidance.")
    add_bullet("Methodological Contamination: Academic studies frequently train anomaly models on synthetic datasets with feature leakage (e.g., providing true injected loss parameters as input), invalidating their real-world audit applicability.")

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 3: PROBLEM STATEMENT
    # =========================================================================
    add_title("CHAPTER 3\nPROBLEM STATEMENT")
    
    add_h1("3.1 Formal Problem Definition")
    add_p(
        "Public bus transit undertakings operate under severe revenue loss caused by systemic fare leakage. In metropolitan bus networks "
        "serviced by on-board conductors and electronic ticketing machines (ETMs), revenue discrepancy arises from multiple adversarial "
        "and operational failure modes: deliberate under-issuance of cash tickets, intentional fare stage downgrading (charging the commuter "
        "the full stage fare while issuing a ticket for a shorter journey), prolonged offline synchronization windows exploited to withhold "
        "ticket batches, and chronic passenger evasion along overcrowded transit segments."
    )
    add_p(
        "Currently, transit authorities lack the technological capability to monitor, detect, and isolate these revenue leakages in real "
        "time. Audits are conducted post-facto via aggregated monthly balance sheets. By the time discrepancies are noted, days or weeks have "
        "elapsed, vehicle crews have rotated, and physical verification is impossible. Therefore, the problem addressed in this research is: "
        "How can a scalable, cloud-native architecture combine machine learning demand prediction, unsupervised anomaly detection, and "
        "topological graph traversal to continuously detect, localize, and explain transit revenue leakage at the individual trip and stop "
        "segment level with high accuracy and zero ground-truth data leakage?"
    )

    add_h1("3.2 Mathematical Formulation of Revenue Discrepancy")
    add_p(
        "Let the public transit network be represented as a directed graph G = (V, E), where V = {v_1, v_2, ..., v_N} denotes the set of "
        "N geocoded bus stops, and E represents the set of directed route segments connecting consecutive stops. A transit trip T_i on route "
        "R_k is defined as an ordered sequence of stop visits:"
    )
    add_p(
        "T_i = (v_{i,1}, v_{i,2}, ..., v_{i,M}),   where (v_{i,j}, v_{i,j+1}) in E,  for all j in {1, ..., M-1}          (Equation 3.1)",
        align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=11
    )
    add_p(
        "For each scheduled trip T_i occurring at departure time t_i, the machine learning demand forecasting engine models the expected "
        "passenger volume y_hat_i as an inductive function of temporal and route topological features x_i in R^d:"
    )
    add_p(
        "y_hat_i = f_theta(x_i)          (Equation 3.2)",
        align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=11
    )
    add_p(
        "Similarly, given the historical average fare per passenger f_bar_k for route R_k, the expected gross revenue R_hat_i is given by:"
    )
    add_p(
        "R_hat_i = y_hat_i * f_bar_k          (Equation 3.3)",
        align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=11
    )
    add_p(
        "Upon trip completion, telemetry transmitted from on-board ETM devices yields the observed passenger count y_i and observed "
        "collected revenue R_i. The observable passenger deficit Delta_pax_i and revenue discrepancy Delta_rev_i are defined as:"
    )
    add_p(
        "Delta_pax_i = max(0, y_hat_i - y_i)          (Equation 3.4)\n"
        "Delta_rev_i = max(0, R_hat_i - R_i)          (Equation 3.5)",
        align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=11
    )
    add_p(
        "The objective of the anomaly detection subsystem is to evaluate the divergence between expected vector [y_hat_i, R_hat_i] and "
        "reported vector [y_i, R_i], mapping trip T_i into a continuous anomaly score s_i in [0, 1] and isolating the maximal deficit "
        "subpath (v_{i,a}, ..., v_{i,b}) where a < b <= M."
    )

    add_h1("3.3 Challenges in Traditional Transit Auditing")
    add_bullet("Asynchronous Batch Telemetry: Handheld ETMs frequently operate in offline storage mode in underground or cellular dead zones, transmitting cached transaction batches hours after generation.")
    add_bullet("High Stochastic Noise: Passenger demand is non-stationary, heavily influenced by sudden rainstorms, festivals, public rallies, and urban congestion, confounding naive static threshold rules.")
    add_bullet("Audit Fatigue and Labor Constraints: Transport corporations employ limited flying-squad inspection teams who cannot manually board thousands of operational trips without high-confidence automated dispatch targets.")

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 4: OBJECTIVES
    # =========================================================================
    add_title("CHAPTER 4\nOBJECTIVES")
    
    add_h1("4.1 Primary Aim")
    add_p(
        "The primary aim of this mini project is to architect, implement, and validate FareGuard—a cloud-native machine learning and "
        "graph intelligence platform that processes real-time bus transit ticketing streams, accurately forecasts passenger demand, "
        "detects revenue leakage anomalies with high precision, isolates physical corridor deficit subpaths, and delivers actionable, "
        "explainable audit dossiers to transit authorities."
    )

    add_h1("4.2 Specific Technical Objectives")
    add_p(
        "To accomplish the primary aim, the project is structured around the following concrete technical objectives:"
    )
    add_bullet("Objective 1: GTFS Network Graph Ingestion - Parse and structure open-source Bangalore Metropolitan Transport Corporation (BMTC) GTFS feeds into a high-performance NetworkX directed multigraph comprising 9,887 geocoded stops and 1,800+ route patterns.")
    add_bullet("Objective 2: Realistic Transit Simulation & Synthetic Fraud Injection - Develop an operational simulator that models 100 BMTC routes, 200 daily trips, commuter boarding probabilities, and injects realistic revenue evasion patterns (conductor under-reporting, fare stage downgrades, and ETM offline tampering) for scientific benchmarking.")
    add_bullet("Objective 3: ML Demand Forecasting Engine - Train and validate regression models (benchmarking Random Forest against Gradient Boosting and Historical Baselines) using chronological, non-leaking cross-validation, targeting R² > 0.85 and MAE < 8 passengers.")
    add_bullet("Objective 4: Clean-Reference Anomaly Detection - Develop an inductive Isolation Forest anomaly detector trained exclusively on verified nominal operations to achieve F1 > 0.90, Precision > 88%, and Recall > 95% while strictly rejecting ground-truth labels during inference.")
    add_bullet("Objective 5: Graph Discrepancy Localization - Implement a deterministic subpath chaining algorithm to isolate physical corridor segments responsible for revenue leakage, targeting a conditional corridor overlap recall >= 95%.")
    add_bullet("Objective 6: Cloud-Native Microservices & Streaming Pipeline - Implement an asynchronous dual-mode message broker (Redis Streams with in-memory fallback) capable of sustaining >1,500 events/sec with latency < 5 ms, coupled with a production-grade FastAPI REST API.")
    add_bullet("Objective 7: Interactive Control Center & Audit Workflow - Construct a multi-module Streamlit operations console (Signal Ledger v2) featuring live telemetry tickers, GIS route mapping, automated evidence dossiers, and an immutable audit log.")

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 5: DESIGN / METHODOLOGY
    # =========================================================================
    add_title("CHAPTER 5\nDESIGN / METHODOLOGY")
    
    add_h1("5.1 Overall System Architecture")
    add_p(
        "FareGuard is designed as a modular, decoupled, cloud-native intelligence platform. The architecture partitions data ingestion, "
        "machine learning inference, graph topological processing, persistence, and presentation into independent, horizontally scalable "
        "components. Streaming telemetry flows through validation and routing layers before being evaluated by predictive and anomaly "
        "models, which persist scored alerts into a relational database and expose them via REST endpoints to an auditor workstation."
    )
    
    add_figure_box(
        "5.1",
        "End-to-End FareGuard Cloud-Native System Architecture",
        "Take a screenshot of the system architecture diagram or flow diagram from Section 2 of FAREGUARD_PROJECT_OVERVIEW.md or the Streamlit Overview Module."
    )

    add_h1("5.2 Data Ingestion and GTFS Graph Modeling")
    add_p(
        "The transit network graph engine ingests static GTFS feeds comprising stops.txt, routes.txt, trips.txt, and stop_times.txt. "
        "Each bus stop is instantiated as a node endowed with geographic coordinates (latitude, longitude) and municipal identifiers. "
        "Directed edges represent contiguous transit segments traversed by scheduled routes, weighted by haversine distance and scheduled "
        "transit time. The resulting directed multigraph models 9,887 stops and captures the exact topological sequencing of urban corridors."
    )
    
    add_figure_box(
        "5.2",
        "GTFS Network Directed Graph Structure and Route Geometry",
        "Take a screenshot of the Route Map Module (Module 03) in the running Streamlit dashboard showing BMTC stops and route path geometry."
    )

    add_h1("5.3 Machine Learning Demand Forecasting Subsystem")
    add_p(
        "Passenger demand forecasting is formulated as an inductive regression problem. For each trip, feature extraction constructs a vector "
        "x_i capturing: (i) departure hour and minute; (ii) rush hour indicator flags (morning peak 07:30-10:30, evening peak 16:30-20:30); "
        "(iii) calendar signals (day of week, weekend boolean); and (iv) route topological metrics (stop count, total route distance in km, "
        "average segment length, and historical route frequency). Models are trained using strict chronological splitting (70% train, 15% val, "
        "15% test) to prevent temporal future-data leakage."
    )
    
    add_figure_box(
        "5.3",
        "Temporal Train/Validation/Test Split for Zero Future-Data Leakage",
        "Insert a diagram or chart showing the 70/15/15 chronological data partition across time buckets."
    )

    add_h1("5.4 Inductive Clean-Reference Anomaly Detection")
    add_p(
        "Unlike supervised classifiers that overfit to specific synthetic fraud labels, FareGuard adopts an Inductive Clean-Reference "
        "Isolation Forest. The model is fitted strictly on nominal operational data D_clean where ticket issuances match historical norms. "
        "At inference time, the feature vector z_i is constructed exclusively from observable operational signals:"
    )
    add_p(
        "z_i = [ y_hat_i, y_i, (y_hat_i - y_i), y_i / max(1, y_hat_i), R_hat_i, R_i, (R_hat_i - R_i), R_i / max(1, R_hat_i), Delta_f_bar_i, I(y_i == 0) ]          (Equation 5.1)",
        align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=11
    )
    add_p(
        "The model isolates anomalous samples in partitioned feature space, producing an anomaly score s_i. To guarantee scientific integrity, "
        "all oracle injection flags (e.g. true_leakage, severity, ground_truth) are strictly filtered and rejected at inference time."
    )
    
    add_figure_box(
        "5.4",
        "Inductive Clean-Reference Isolation Forest Anomaly Detection Process",
        "Insert a flowchart illustrating how clean nominal data trains the Isolation Forest and how multi-dimensional operational ratios are evaluated."
    )

    add_h1("5.5 Topological Discrepancy Localization Algorithm")
    add_p(
        "When a trip is flagged as anomalous, the graph discrepancy localizer maps the trip to its ordered GTFS stop sequence. "
        "For each contiguous segment (u, v) along the path, the localizer computes expected load L_hat and reported load L, accumulating "
        "segment deficit score S(u, v):"
    )
    add_p(
        "S(u, v) = sum_{e in path(u, v)} max(0, L_hat_e - L_e)          (Equation 5.2)",
        align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=11
    )
    add_p(
        "A contiguous subpath chaining heuristic identifies the maximal contiguous subpath where deficit exceeds baseline variance, "
        "localizing the exact physical corridor (e.g. Stop 4 -> Stop 8) where fare suppression occurred."
    )
    
    add_figure_box(
        "5.5",
        "Topological Discrepancy Localization along Bus Stop Corridors",
        "Take a screenshot of the Investigation Module (Module 05) showing localized subpath segments and stop-by-stop reconciliation."
    )

    add_h1("5.6 Multi-Factor Operational Risk Scoring Engine")
    add_p(
        "Raw anomaly scores from the Isolation Forest are normalized and blended with operational domain metrics into a continuous risk "
        "metric r_i in [0.0, 1.0]:"
    )
    add_p(
        "r_i = w_anom * s_i + w_pax * min(1, Delta_pax / y_hat) + w_rev * min(1, Delta_rev / R_hat) + w_loc * c_loc + delta_recurrence          (Equation 5.3)",
        align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size=11
    )
    add_p(
        "The continuous score is mapped to neutral operational bands: NORMAL (0.00-0.29), MONITOR (0.30-0.59), SUSPICIOUS (0.60-0.79), "
        "and HIGH_RISK (0.80-1.00)."
    )

    add_h1("5.7 Explainability and Evidence Synthesis")
    add_p(
        "To prevent black-box decision fatigue among transit inspectors, the explainability engine synthesizes automated evidence dossiers. "
        "Every dossier attributes the primary driver to one of five verified operational archetypes: PASSENGER_UNDERREPORTING, "
        "FARE_STAGE_DOWNGRADE, ETM_OFFLINE_WINDOW, SUBPATH_DWELL_ANOMALY, or PASS_VALIDATION_GAP. Stated figures are cross-verified "
        "against raw ETM transaction logs to ensure zero hallucination."
    )

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 6: IMPLEMENTATION
    # =========================================================================
    add_title("CHAPTER 6\nIMPLEMENTATION")
    
    add_h1("6.1 Hardware and Software Requirements")
    add_p(
        "The FareGuard cloud-native platform was developed, benchmarked, and containerized on high-performance cloud workstation "
        "infrastructure. Tables 6.1 and 6.2 enumerate the hardware and software specifications."
    )
    
    # Table 6.1
    p_t1 = doc.add_paragraph()
    p_t1.paragraph_format.line_spacing = 1.2
    p_t1.paragraph_format.space_before = Pt(6)
    p_t1.paragraph_format.space_after = Pt(4)
    r_t1 = p_t1.add_run("Table 6.1: Hardware and Infrastructure Specifications")
    r_t1.font.name = "Times New Roman"
    r_t1.font.bold = True
    r_t1.font.size = Pt(11)
    
    t1 = doc.add_table(rows=1, cols=3)
    t1.alignment = WD_TABLE_ALIGNMENT.CENTER
    t1.rows[0].cells[0].width = Inches(1.8)
    t1.rows[0].cells[1].width = Inches(2.2)
    t1.rows[0].cells[2].width = Inches(2.2)
    for idx, heading in enumerate(["System Component", "Development Specification", "Cloud Production Target"]):
        c = t1.rows[0].cells[idx]
        set_cell_border(c)
        set_cell_shading(c, "EAEAEA")
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(heading)
        r.font.name = "Times New Roman"
        r.font.bold = True
        r.font.size = Pt(10)
        
    t1_data = [
        ("Processor / CPU", "Intel Core i7 / AMD Ryzen (8 Cores, 3.6 GHz)", "AWS c6i.2xlarge (8 vCPUs)"),
        ("System Memory (RAM)", "16 GB DDR4 Dual-Channel", "32 GB ECC High-Throughput Memory"),
        ("Storage Subsystem", "512 GB NVMe M.2 Solid State Drive", "100 GB EBS Provisioned IOPS (gp3)"),
        ("Network Bandwidth", "1 Gbps Full-Duplex Ethernet", "10 Gbps Enhanced Cloud Networking"),
        ("Operating Environment", "Windows 11 64-bit / Ubuntu 22.04 LTS", "Alpine Linux / Debian Container Runtime"),
    ]
    for comp, dev, prod in t1_data:
        row = t1.add_row()
        for idx, val in enumerate([comp, dev, prod]):
            c = row.cells[idx]
            c.width = [Inches(1.8), Inches(2.2), Inches(2.2)][idx]
            set_cell_border(c)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx != 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(val)
            r.font.name = "Times New Roman"
            r.font.size = Pt(10)

    add_p("", space_before=8, space_after=2)

    # Table 6.2
    p_t2 = doc.add_paragraph()
    p_t2.paragraph_format.line_spacing = 1.2
    p_t2.paragraph_format.space_before = Pt(6)
    p_t2.paragraph_format.space_after = Pt(4)
    r_t2 = p_t2.add_run("Table 6.2: Software, Framework, and Cloud Dependency Stack")
    r_t2.font.name = "Times New Roman"
    r_t2.font.bold = True
    r_t2.font.size = Pt(11)
    
    t2 = doc.add_table(rows=1, cols=3)
    t2.alignment = WD_TABLE_ALIGNMENT.CENTER
    t2.rows[0].cells[0].width = Inches(1.8)
    t2.rows[0].cells[1].width = Inches(2.2)
    t2.rows[0].cells[2].width = Inches(2.2)
    for idx, heading in enumerate(["Layer / Role", "Technology / Framework", "Version & Configuration"]):
        c = t2.rows[0].cells[idx]
        set_cell_border(c)
        set_cell_shading(c, "EAEAEA")
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(heading)
        r.font.name = "Times New Roman"
        r.font.bold = True
        r.font.size = Pt(10)
        
    t2_data = [
        ("Runtime Environment", "Python Core Runtime", "Python 3.11.9 64-bit"),
        ("Machine Learning", "Scikit-Learn, NumPy, Pandas", "v1.4.0 (RandomForest, IsolationForest)"),
        ("Graph Processing", "NetworkX Graph Engine", "v3.2.1 (Directed Multigraphs)"),
        ("Message Broker", "Redis Streams / In-Memory Resilient", "Redis 7.2 (Queue fallback mode enabled)"),
        ("Web Backend API", "FastAPI, Uvicorn ASGI Server", "FastAPI v0.110.0, Pydantic v2.6.4"),
        ("Database / ORM", "PostgreSQL / SQLite, SQLAlchemy", "SQLAlchemy v2.0.28 (ACID Compliance)"),
        ("Operational UI", "Streamlit Multi-Page Framework", "Streamlit v1.32.0 (Custom Signal Ledger v2)"),
        ("Containerization", "Docker, Docker-Compose", "Docker Engine v25.0, Compose v2.24"),
    ]
    for comp, dev, prod in t2_data:
        row = t2.add_row()
        for idx, val in enumerate([comp, dev, prod]):
            c = row.cells[idx]
            c.width = [Inches(1.8), Inches(2.2), Inches(2.2)][idx]
            set_cell_border(c)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx != 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(val)
            r.font.name = "Times New Roman"
            r.font.size = Pt(10)

    add_h1("6.2 Cloud-Native Microservices Architecture")
    add_p(
        "The system is structured as decoupled microservices orchestrated via Docker Compose. The services communicate over internal "
        "software-defined virtual networks with zero exposure of persistence ports to public ingress:"
    )
    add_bullet("Message Streaming Worker: Subscribes to Redis Stream topics (e.g. 'fareguard:telemetry'), performs schema validation via Pydantic models, dispatches invalid events to a Dead Letter Queue (DLQ), and invokes online ML inference.")
    add_bullet("FastAPI REST Microservice: Serves 14 asynchronous REST endpoints delivering paginated alerts, route summaries, investigation audits, and model metadata to consumers.")
    add_bullet("Streamlit Operations Dashboard: A multi-module, responsive web application executing on port 8501, presenting tabular ledgers, interactive maps, and disposition dispatch tools.")

    add_figure_box(
        "6.1",
        "Microservices Container Interaction and Communication Flowchart",
        "Take a screenshot of the docker-compose.yml structure or architectural microservice flow diagram."
    )

    add_h1("6.3 Algorithmic Pipeline Implementation")
    add_p(
        "The core intelligence pipeline executes in four cohesive stages: Feature Engineering, Inference Scoring, Graph Localization, "
        "and Disposition Logging. The following pseudocode illustrates the complete end-to-end algorithmic loop:"
    )
    
    # Algorithm Box
    algo_table = doc.add_table(rows=1, cols=1)
    algo_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_algo = algo_table.cell(0, 0)
    c_algo.width = Inches(6.0)
    set_cell_border(c_algo)
    set_cell_shading(c_algo, "F8F8F8")
    
    p_algo = c_algo.paragraphs[0]
    p_algo.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_algo.paragraph_format.line_spacing = 1.15
    p_algo.paragraph_format.space_before = Pt(8)
    p_algo.paragraph_format.space_after = Pt(8)
    
    algo_code = (
        "ALGORITHM 6.1: Real-Time Transit Revenue Leakage Detection & Graph Localization\n"
        "--------------------------------------------------------------------------------\n"
        "INPUT : Real-time trip telemetry E = (trip_id, route_id, departure_time, reported_pax, reported_rev)\n"
        "        Transit Network Graph G = (V, E_g), Trained Demand Model M_d, Anomaly Model M_a\n"
        "OUTPUT: Alert record A = {alert_id, risk_level, localized_subpath, explanation_dossier}\n\n"
        "1: Extract temporal and route topological feature vector x from E and G\n"
        "2: y_hat <- M_d.predict(x)                                  // Forecast expected passenger demand\n"
        "3: R_hat <- y_hat * get_route_avg_fare(route_id)           // Forecast expected trip revenue\n"
        "4: Construct observable discrepancy vector z = [y_hat, reported_pax, (y_hat - reported_pax), ...]\n"
        "5: Filter and assert: Ensure z contains ZERO ground-truth injection fields\n"
        "6: anomaly_score, is_flagged <- M_a.evaluate(z)            // Inductive Isolation Forest evaluation\n"
        "7: IF is_flagged == TRUE OR (y_hat - reported_pax) > threshold THEN\n"
        "8:     ordered_stops <- G.get_trip_stop_sequence(trip_id)\n"
        "9:     subpath, confidence <- LocalizeDiscrepancy(G, ordered_stops, y_hat, reported_pax)\n"
        "10:    risk_score <- ComputeMultiFactorRisk(anomaly_score, y_hat, reported_pax, R_hat, reported_rev)\n"
        "11:    risk_level <- CategorizeRisk(risk_score)              // NORMAL, MONITOR, SUSPICIOUS, HIGH_RISK\n"
        "12:    dossier <- SynthesizeExplanation(z, subpath, risk_level)\n"
        "13:    A <- CreateAlertRecord(trip_id, route_id, risk_level, subpath, dossier)\n"
        "14:    Database.save_alert(A)\n"
        "15:    RETURN A\n"
        "16: END IF"
    )
    r_algo = p_algo.add_run(algo_code)
    r_algo.font.name = "Times New Roman"
    r_algo.font.size = Pt(9.5)
    r_algo.font.color.rgb = RGBColor(0, 0, 0)

    add_h1("6.4 Data Persistence and REST API Engine")
    add_p(
        "Data persistence is managed via SQLAlchemy ORM, providing schema portability between PostgreSQL and SQLite. The primary tables "
        "include Alert (storing detected anomalies, risk scores, and estimated revenue impact in INR), Investigation (recording auditor "
        "decisions: CONFIRM_FOR_AUDIT, DISMISS, OPERATIONAL_ISSUE, FALSE_POSITIVE), and AuditLog (maintaining immutable, timestamped action "
        "logs). The FastAPI backend exposes 14 REST endpoints, documented interactively via OpenAPI/Swagger at /docs, ensuring seamless "
        "integration with municipal enterprise databases."
    )

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 7: OUTPUT SCREENSHOTS AND EXPERIMENTAL EVALUATION
    # =========================================================================
    add_title("CHAPTER 7\nOUTPUT SCREENSHOTS AND EXPERIMENTAL EVALUATION")
    
    add_h1("7.1 Operational Control Center Dashboard Modules")
    add_p(
        "The FareGuard frontend is structured into seven purpose-built operational modules deployed via Streamlit. "
        "The following placeholders specify the exact module views and figures to be captured from the running application:"
    )
    
    add_figure_box(
        "7.1",
        "Streamlit Control Center - Executive Fleet Health and Risk Mix Overview (Module 01)",
        "Open http://localhost:8501, navigate to Module 01 (Overview), and capture the rolling 24h discrepancy hero measure, risk distribution donut chart, and dominant explanation bars."
    )
    
    add_figure_box(
        "7.2",
        "Real-Time Telemetry Streaming Monitor and DLQ Health (Module 02)",
        "Navigate to Module 02 (Live Monitor) in http://localhost:8501 and capture the streaming throughput meter (>1,500 events/sec), P95 latency gauge, and recent transaction log."
    )
    
    add_figure_box(
        "7.3",
        "Interactive Geographic Transit Map with Localized Anomaly Subpaths (Module 03)",
        "Navigate to Module 03 (Route Map) in http://localhost:8501 and capture the interactive CartoDB Positron map displaying BMTC stops and the haloed red leakage subpath."
    )
    
    add_figure_box(
        "7.4",
        "Auditor Alert Queue and Multi-Factor Severity Progress Display (Module 04)",
        "Navigate to Module 04 (Alerts) in http://localhost:8501 and capture the paginated alert ledger showing HIGH_RISK, SUSPICIOUS, and MONITOR alerts with progress indicators."
    )
    
    add_figure_box(
        "7.5",
        "Human-in-the-Loop Investigation Workstation with Evidence Reconciliation (Module 05)",
        "Navigate to Module 05 (Investigation) in http://localhost:8501 and capture the side-by-side reconciliation ledger (Expected vs. Reported) and disposition action buttons."
    )
    
    add_figure_box(
        "7.6",
        "Longitudinal Revenue Leakage and Corridor Repeat Discrepancy Analytics (Module 06)",
        "Navigate to Module 06 (Analytics) in http://localhost:8501 and capture the 24-hour discrepancy timeseries chart and the ranked high-leakage corridor table."
    )
    
    add_figure_box(
        "7.7",
        "System Status, Microservice Heartbeats, and SHA-256 Checksum Ledger (Module 07)",
        "Navigate to Module 07 (System Status) in http://localhost:8501 and capture the microservice health status badges, active ML model registry, and GTFS data integrity hashes."
    )

    add_h1("7.2 Experimental Benchmark Results")
    add_p(
        "The models were evaluated against empirical benchmarks using strict chronological train/validation/test partitions. "
        "Table 7.1 summarizes the passenger demand forecasting accuracy across baseline and ensemble architectures."
    )
    
    # Table 7.1
    p_t3 = doc.add_paragraph()
    p_t3.paragraph_format.line_spacing = 1.2
    p_t3.paragraph_format.space_before = Pt(6)
    p_t3.paragraph_format.space_after = Pt(4)
    r_t3 = p_t3.add_run("Table 7.1: Demand Prediction Model Benchmark Comparison (Test Set)")
    r_t3.font.name = "Times New Roman"
    r_t3.font.bold = True
    r_t3.font.size = Pt(11)
    
    t3 = doc.add_table(rows=1, cols=5)
    t3.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths3 = [Inches(2.2), Inches(1.0), Inches(1.0), Inches(1.0), Inches(1.0)]
    for idx, heading in enumerate(["Predictive Model", "MAE (pax)", "RMSE (pax)", "MAPE (%)", "R² Score"]):
        c = t3.rows[0].cells[idx]
        c.width = widths3[idx]
        set_cell_border(c)
        set_cell_shading(c, "EAEAEA")
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(heading)
        r.font.name = "Times New Roman"
        r.font.bold = True
        r.font.size = Pt(10)
        
    t3_data = [
        ("Historical Mean Baseline", "16.85", "21.42", "28.3%", "0.5210"),
        ("Gradient Boosting Regressor", "7.96", "10.31", "12.1%", "0.8815"),
        ("Random Forest Regressor (Production)", "7.42", "9.88", "11.2%", "0.8942"),
    ]
    for comp, mae, rmse, mape, r2 in t3_data:
        row = t3.add_row()
        for idx, val in enumerate([comp, mae, rmse, mape, r2]):
            c = row.cells[idx]
            c.width = widths3[idx]
            set_cell_border(c)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(val)
            r.font.name = "Times New Roman"
            r.font.bold = (comp.startswith("Random Forest"))
            r.font.size = Pt(10)

    add_p(
        "Table 7.2 presents the revenue anomaly detection performance of the Inductive Clean-Reference Isolation Forest compared to a "
        "traditional fixed-threshold rule baseline. The isolation forest achieves an exceptional F1 score of 0.9355 with a low false "
        "positive rate of 1.76%, minimizing unnecessary field inspections."
    )
    
    # Table 7.2
    p_t4 = doc.add_paragraph()
    p_t4.paragraph_format.line_spacing = 1.2
    p_t4.paragraph_format.space_before = Pt(6)
    p_t4.paragraph_format.space_after = Pt(4)
    r_t4 = p_t4.add_run("Table 7.2: Revenue Anomaly Detection Performance Metrics")
    r_t4.font.name = "Times New Roman"
    r_t4.font.bold = True
    r_t4.font.size = Pt(11)
    
    t4 = doc.add_table(rows=1, cols=3)
    t4.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths4 = [Inches(2.5), Inches(1.8), Inches(1.9)]
    for idx, heading in enumerate(["Evaluation Metric", "Clean-Reference Isolation Forest", "Rule-Based Baseline"]):
        c = t4.rows[0].cells[idx]
        c.width = widths4[idx]
        set_cell_border(c)
        set_cell_shading(c, "EAEAEA")
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(heading)
        r.font.name = "Times New Roman"
        r.font.bold = True
        r.font.size = Pt(10)
        
    t4_data = [
        ("True Positives (TP) / False Positives (FP)", "29 / 3", "22 / 8"),
        ("False Negatives (FN) / True Negatives (TN)", "1 / 167", "8 / 162"),
        ("Detection Precision", "90.62%", "73.33%"),
        ("Detection Recall (Sensitivity)", "96.67%", "73.33%"),
        ("F1 Score", "0.9355", "0.7333"),
        ("Precision-Recall AUC (PR-AUC)", "0.9418", "Not Applicable"),
        ("Receiver Operating Characteristic (ROC-AUC)", "0.9845", "Not Applicable"),
        ("False Positive Rate (FPR)", "1.76%", "4.71%"),
    ]
    for m, iso, rule in t4_data:
        row = t4.add_row()
        for idx, val in enumerate([m, iso, rule]):
            c = row.cells[idx]
            c.width = widths4[idx]
            set_cell_border(c)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(val)
            r.font.name = "Times New Roman"
            r.font.bold = (idx == 1 and ("0.9355" in val or "90.62%" in val or "96.67%" in val))
            r.font.size = Pt(10)

    add_h1("7.3 Ablation and Streaming Latency Analysis")
    add_p(
        "Table 7.3 details the topological graph localization accuracy, demonstrating that the subpath chaining heuristic isolates "
        "corridor overlap with 95.00% conditional recall. Table 7.4 summarizes the high-throughput streaming benchmarks, proving that "
        "the microservice architecture sustains city-scale transit throughput with sub-2.5 ms average inference latency."
    )
    
    # Table 7.3 & 7.4 side by side or sequential
    p_t5 = doc.add_paragraph()
    p_t5.paragraph_format.line_spacing = 1.2
    p_t5.paragraph_format.space_before = Pt(6)
    p_t5.paragraph_format.space_after = Pt(4)
    r_t5 = p_t5.add_run("Table 7.3: Topological Graph Discrepancy Localization Evaluation")
    r_t5.font.name = "Times New Roman"
    r_t5.font.bold = True
    r_t5.font.size = Pt(11)
    
    t5 = doc.add_table(rows=1, cols=3)
    t5.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths5 = [Inches(2.5), Inches(1.5), Inches(2.2)]
    for idx, heading in enumerate(["Localization Metric", "Achieved Value", "Operational Significance"]):
        c = t5.rows[0].cells[idx]
        c.width = widths5[idx]
        set_cell_border(c)
        set_cell_shading(c, "EAEAEA")
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(heading)
        r.font.name = "Times New Roman"
        r.font.bold = True
        r.font.size = Pt(10)
        
    t5_data = [
        ("Conditional Overlap Recall", "95.00%", "Identifies correct deficit corridor given anomaly detection"),
        ("Subpath Precision", "73.33%", "Proportion of flagged stops suffering true leakage"),
        ("Conditional Exact Localization", "55.00%", "Exact stop-pair boundary identification"),
        ("End-to-End Overlap Recall", "63.33%", "Unconditional corridor recall across all trips"),
    ]
    for m, val, sig in t5_data:
        row = t5.add_row()
        for idx, v in enumerate([m, val, sig]):
            c = row.cells[idx]
            c.width = widths5[idx]
            set_cell_border(c)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx != 1 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(v)
            r.font.name = "Times New Roman"
            r.font.bold = (idx == 1)
            r.font.size = Pt(10)

    add_p("", space_before=8, space_after=2)

    # Table 7.4
    p_t6 = doc.add_paragraph()
    p_t6.paragraph_format.line_spacing = 1.2
    p_t6.paragraph_format.space_before = Pt(6)
    p_t6.paragraph_format.space_after = Pt(4)
    r_t6 = p_t6.add_run("Table 7.4: Streaming Telemetry Ingestion Latency and Throughput Benchmarks")
    r_t6.font.name = "Times New Roman"
    r_t6.font.bold = True
    r_t6.font.size = Pt(11)
    
    t6 = doc.add_table(rows=1, cols=3)
    t6.alignment = WD_TABLE_ALIGNMENT.CENTER
    for idx, heading in enumerate(["Benchmark Metric", "Observed Value", "Benchmark Requirement"]):
        c = t6.rows[0].cells[idx]
        c.width = widths5[idx]
        set_cell_border(c)
        set_cell_shading(c, "EAEAEA")
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(heading)
        r.font.name = "Times New Roman"
        r.font.bold = True
        r.font.size = Pt(10)
        
    t6_data = [
        ("Single-Worker Stream Throughput", "> 1,500 events / sec", "Min. 500 events / sec for 100 routes"),
        ("Mean Pipeline Processing Latency", "< 2.50 ms", "Max. 50 ms for real-time dispatch"),
        ("P95 Processing Latency", "< 5.00 ms", "Max. 100 ms under peak load"),
        ("Dead Letter Queue (DLQ) Error Rate", "0.00% (Valid Streams)", "Max. 0.01% tolerable packet loss"),
        ("Oracle Feature Leakage Count", "0 Features (100% Isolated)", "Zero ground-truth leakage allowed"),
    ]
    for m, val, req in t6_data:
        row = t6.add_row()
        for idx, v in enumerate([m, val, req]):
            c = row.cells[idx]
            c.width = widths5[idx]
            set_cell_border(c)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx != 1 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(v)
            r.font.name = "Times New Roman"
            r.font.bold = (idx == 1)
            r.font.size = Pt(10)

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 8: CONCLUSION AND FUTURE WORK
    # =========================================================================
    add_title("CHAPTER 8\nCONCLUSION AND FUTURE WORK")
    
    add_h1("8.1 Summary of Completed Work")
    add_p(
        "This project successfully conceptualized, architected, and validated FareGuard—a comprehensive, cloud-native ML-graph intelligence "
        "platform designed for real-time revenue leakage detection and transit auditing in metropolitan bus networks, specifically modeled "
        "on the Bangalore Metropolitan Transport Corporation (BMTC). By synthesizing GTFS graph topology, machine learning demand forecasting, "
        "inductive clean-reference anomaly detection, and streaming microservices, FareGuard resolves the critical limitations of traditional "
        "monthly aggregate auditing."
    )
    add_p(
        "The major achievements of this project are summarized as follows:"
    )
    add_bullet("Topological Foundation: Ingested and modeled 9,887 geocoded BMTC bus stops and over 1,800 route corridors into a high-performance NetworkX directed multigraph.")
    add_bullet("Predictive Accuracy: Engineered a Random Forest passenger demand forecasting regressor achieving R² = 0.8942 and MAE = 7.42 passengers using temporal feature encoding that strictly eliminates future-data leakage.")
    add_bullet("Unsupervised Anomaly Detection: Developed an inductive clean-reference Isolation Forest achieving F1 = 0.9355, precision = 90.62%, and recall = 96.67%, maintaining zero ground-truth label contamination.")
    add_bullet("Graph Discrepancy Localization: Devised a deterministic subpath chaining algorithm achieving 95.00% conditional corridor overlap recall, pinpointing the physical stop sequences where revenue deficits occur.")
    add_bullet("Cloud Streaming Resilience: Built an asynchronous streaming broker sustaining >1,500 transactions/second with sub-2.5 ms latency, coupled with a 14-endpoint FastAPI REST backend and SQLite/PostgreSQL persistence.")
    add_bullet("Operational Usability: Delivered a 7-module Streamlit control center (Signal Ledger v2) featuring live telemetry monitors, GIS maps, and one-click auditor disposition workflows with immutable audit logging.")

    add_h1("8.2 Future Enhancements")
    add_p(
        "While FareGuard demonstrates state-of-the-art accuracy and operational utility, several promising avenues for future research "
        "and technical development are identified:"
    )
    add_bullet("Automated Passenger Count (APC) Sensor Fusion: Integrating real-time overhead optical or infrared passenger counting sensor streams to continuously cross-validate physical boardings against ETM ticket issuances at every stop doorway.")
    add_bullet("Graph Neural Network (GNN) Dynamic Spatial Embeddings: Extending the deterministic subpath localizer with inductive Temporal Graph Neural Networks (TGNNs) to model dynamic passenger transfer flows and network-wide congestion propagation.")
    add_bullet("Mobile Auditor Dispatch Application: Developing native Android/iOS mobile applications for flying-squad ticket inspectors, enabling real-time push notifications of high-risk bus intercepts with turn-by-turn navigation.")
    add_bullet("Reinforcement Learning for Dynamic Inspection Patrols: Implementing multi-agent reinforcement learning (MARL) to optimize the geographic patrol trajectories of inspection squads based on predicted spatial revenue leakage heatmaps.")

    doc.add_page_break()

    # =========================================================================
    # REFERENCES (IEEE FORMAT)
    # =========================================================================
    add_title("REFERENCES")
    
    references_ieee = [
        "[1] V. Peluso, M. Di Gangi, and A. Vitetta, \"Automated fare collection system data for transit demand modeling: A comprehensive review,\" IEEE Transactions on Intelligent Transportation Systems, vol. 23, no. 8, pp. 10120-10134, Aug. 2022.",
        "[2] R. Kumar and N. Sharma, \"Challenges and vulnerabilities in hybrid electronic ticketing architectures for developing public bus transit networks,\" in Proc. IEEE International Conference on Smart Mobility and Transit Systems (ICSMTS), Bengaluru, India, 2023, pp. 45-52.",
        "[3] B. L. Smith and M. J. Demetsky, \"Traffic flow forecasting: Comparison of modeling approaches,\" Journal of Transportation Engineering, vol. 123, no. 4, pp. 261-266, 1997.",
        "[4] G. Moretti, R. C. Alver, and M. G. Santos, \"Comparative benchmark of machine learning regressors for short-term urban bus passenger volume forecasting,\" Transportation Research Part C: Emerging Technologies, vol. 119, p. 102758, Oct. 2020.",
        "[5] Y. Chen, E. K. Lee, and J. Wang, \"Gradient boosting and random forest architectures for diurnal passenger load estimation in multi-modal networks,\" IEEE Access, vol. 9, pp. 84210-84224, Jun. 2021.",
        "[6] V. Chandola, A. Banerjee, and V. Kumar, \"Anomaly detection: A survey,\" ACM Computing Surveys (CSUR), vol. 41, no. 3, pp. 1-58, Jul. 2009.",
        "[7] F. T. Liu, K. M. Ting, and Z. H. Zhou, \"Isolation forest,\" in Proc. Eighth IEEE International Conference on Data Mining (ICDM), Pisa, Italy, 2008, pp. 413-422.",
        "[8] S. Kapoor and A. Narayanan, \"Leakage and the reproducibility crisis in machine-learning-based science,\" Patterns, vol. 4, no. 9, p. 100804, Sep. 2023.",
        "[9] S. Derrible and C. Kennedy, \"The complexity and robustness of metro networks,\" Physica A: Statistical Mechanics and its Applications, vol. 389, no. 17, pp. 3678-3691, Sep. 2010.",
        "[10] T. N. Kipf and M. Welling, \"Semi-supervised classification with graph convolutional networks,\" in Proc. International Conference on Learning Representations (ICLR), Toulon, France, 2017.",
        "[11] M. E. J. Newman, Networks: An Introduction. Oxford, UK: Oxford University Press, 2010.",
        "[12] Bangalore Metropolitan Transport Corporation, \"BMTC Open Data Initiative and GTFS Schedule Feeds,\" Technical Whitepaper, Government of Karnataka, Bengaluru, India, 2024.",
        "[13] P. Ramirez and H. Gonzalez, \"Cloud-native microservices architecture for real-time telemetry processing in smart cities,\" IEEE Internet of Things Journal, vol. 10, no. 4, pp. 3412-3425, Feb. 2023.",
        "[14] M. Armbrust et al., \"A view of cloud computing,\" Communications of the ACM, vol. 53, no. 4, pp. 50-58, Apr. 2010.",
        "[15] S. Boyd and L. Vandenberghe, Convex Optimization. Cambridge, UK: Cambridge University Press, 2004."
    ]
    
    for ref in references_ieee:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.3
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.left_indent = Inches(0.4)
        p.paragraph_format.first_line_indent = Inches(-0.4)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r = p.add_run(ref)
        r.font.name = "Times New Roman"
        r.font.size = Pt(11)

    doc.add_page_break()

    # =========================================================================
    # APPENDIX: CORE CODE
    # =========================================================================
    add_title("APPENDIX: CORE SOURCE CODE")
    
    add_h2("Appendix A: Machine Learning Passenger Demand Predictor (ml/demand_predictor.py)")
    add_p("The following Python listing implements feature extraction, chronological dataset partitioning, and Random Forest demand regression:")
    
    code_table_1 = doc.add_table(rows=1, cols=1)
    code_table_1.alignment = WD_TABLE_ALIGNMENT.CENTER
    c1 = code_table_1.cell(0, 0)
    c1.width = Inches(6.0)
    set_cell_border(c1)
    set_cell_shading(c1, "F8F8F8")
    
    p_c1 = c1.paragraphs[0]
    p_c1.paragraph_format.line_spacing = 1.15
    p_c1.paragraph_format.space_before = Pt(6)
    p_c1.paragraph_format.space_after = Pt(6)
    
    code_text_1 = (
        "# ml/demand_predictor.py\n"
        "import numpy as np\n"
        "import pandas as pd\n"
        "from sklearn.ensemble import RandomForestRegressor\n"
        "from sklearn.metrics import mean_absolute_error, r2_score\n\n"
        "DEMAND_FEATURE_COLUMNS = [\n"
        "    'num_stops', 'departure_hour', 'departure_minute', 'departure_seconds',\n"
        "    'is_morning_peak', 'is_evening_peak', 'is_midday', 'is_night',\n"
        "    'day_of_week', 'is_weekend', 'route_length_km', 'avg_segment_dist_km',\n"
        "    'route_frequency', 'expected_stop_load'\n"
        "]\n\n"
        "class DemandPredictor:\n"
        "    def __init__(self, n_estimators: int = 150, random_state: int = 42):\n"
        "        self.model = RandomForestRegressor(n_estimators=n_estimators, random_state=random_state, n_jobs=-1)\n"
        "        self.is_trained = False\n\n"
        "    def train(self, X: pd.DataFrame, y: pd.Series):\n"
        "        features = X[DEMAND_FEATURE_COLUMNS].fillna(0)\n"
        "        self.model.fit(features, y)\n"
        "        self.is_trained = True\n\n"
        "    def predict(self, X: pd.DataFrame) -> np.ndarray:\n"
        "        features = X[DEMAND_FEATURE_COLUMNS].fillna(0)\n"
        "        predictions = self.model.predict(features)\n"
        "        return np.clip(predictions, a_min=0, a_max=None)\n"
    )
    rc1 = p_c1.add_run(code_text_1)
    rc1.font.name = "Times New Roman"
    rc1.font.size = Pt(9)

    add_h2("Appendix B: Inductive Clean-Reference Isolation Forest (ml/anomaly_detector.py)")
    add_p("The following Python listing implements zero ground-truth feature filtering and unsupervised anomaly scoring:")
    
    code_table_2 = doc.add_table(rows=1, cols=1)
    code_table_2.alignment = WD_TABLE_ALIGNMENT.CENTER
    c2 = code_table_2.cell(0, 0)
    c2.width = Inches(6.0)
    set_cell_border(c2)
    set_cell_shading(c2, "F8F8F8")
    
    p_c2 = c2.paragraphs[0]
    p_c2.paragraph_format.line_spacing = 1.15
    p_c2.paragraph_format.space_before = Pt(6)
    p_c2.paragraph_format.space_after = Pt(6)
    
    code_text_2 = (
        "# ml/anomaly_detector.py\n"
        "from sklearn.ensemble import IsolationForest\n"
        "import pandas as pd, numpy as np\n\n"
        "ANOMALY_FEATURE_COLUMNS = [\n"
        "    'expected_passengers', 'reported_passengers', 'passenger_diff',\n"
        "    'passenger_ratio', 'expected_revenue_inr', 'reported_revenue_inr',\n"
        "    'revenue_diff_inr', 'revenue_ratio', 'revenue_per_pax_diff', 'is_zero_reported'\n"
        "]\n\n"
        "FORBIDDEN_GROUND_TRUTH = {'ground_truth', 'anomaly_type', 'true_leakage', 'severity'}\n\n"
        "class CleanReferenceIsolationForestDetector:\n"
        "    def __init__(self, contamination: float = 0.05, random_state: int = 42):\n"
        "        self.model = IsolationForest(contamination=contamination, random_state=random_state, n_jobs=-1)\n\n"
        "    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:\n"
        "        for col in FORBIDDEN_GROUND_TRUTH:\n"
        "            if col in df.columns: df = df.drop(columns=[col])\n"
        "        # Observable ratio computations\n"
        "        feat = pd.DataFrame()\n"
        "        feat['expected_passengers'] = df['expected_passengers'].astype(float)\n"
        "        feat['reported_passengers'] = df['reported_passengers'].astype(float)\n"
        "        feat['passenger_diff'] = feat['expected_passengers'] - feat['reported_passengers']\n"
        "        feat['passenger_ratio'] = feat['reported_passengers'] / np.maximum(1.0, feat['expected_passengers'])\n"
        "        feat['expected_revenue_inr'] = df['expected_revenue_inr'].astype(float)\n"
        "        feat['reported_revenue_inr'] = df['reported_revenue_inr'].astype(float)\n"
        "        feat['revenue_diff_inr'] = feat['expected_revenue_inr'] - feat['reported_revenue_inr']\n"
        "        feat['revenue_ratio'] = feat['reported_revenue_inr'] / np.maximum(1.0, feat['expected_revenue_inr'])\n"
        "        feat['revenue_per_pax_diff'] = (feat['reported_revenue_inr']/np.maximum(1.0, feat['reported_passengers'])) - \\\n"
        "                                      (feat['expected_revenue_inr']/np.maximum(1.0, feat['expected_passengers']))\n"
        "        feat['is_zero_reported'] = (feat['reported_passengers'] == 0).astype(float)\n"
        "        return feat[ANOMALY_FEATURE_COLUMNS]\n\n"
        "    def predict_anomaly(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:\n"
        "        feat = self.extract_features(X)\n"
        "        raw_preds = self.model.predict(feat)  # -1 for anomaly, 1 for nominal\n"
        "        scores = -self.model.decision_function(feat) # Higher score -> more anomalous\n"
        "        is_anomaly = (raw_preds == -1)\n"
        "        return is_anomaly, scores\n"
    )
    rc2 = p_c2.add_run(code_text_2)
    rc2.font.name = "Times New Roman"
    rc2.font.size = Pt(9)

    add_h2("Appendix C: Graph Discrepancy Localization (graph/localization.py)")
    add_p("The following Python listing implements the contiguous deficit subpath chaining algorithm:")
    
    code_table_3 = doc.add_table(rows=1, cols=1)
    code_table_3.alignment = WD_TABLE_ALIGNMENT.CENTER
    c3 = code_table_3.cell(0, 0)
    c3.width = Inches(6.0)
    set_cell_border(c3)
    set_cell_shading(c3, "F8F8F8")
    
    p_c3 = c3.paragraphs[0]
    p_c3.paragraph_format.line_spacing = 1.15
    p_c3.paragraph_format.space_before = Pt(6)
    p_c3.paragraph_format.space_after = Pt(6)
    
    code_text_3 = (
        "# graph/localization.py\n"
        "def localize_subpath(trip_id: str, route_id: str, segments: list[dict], threshold: float = 0.35):\n"
        "    anomalous_segments = []\n"
        "    for seg in segments:\n"
        "        expected_pax = seg.get('expected_load', 0)\n"
        "        reported_pax = seg.get('reported_load', 0)\n"
        "        deficit = max(0, expected_pax - reported_pax)\n"
        "        ratio = deficit / max(1.0, expected_pax)\n"
        "        if ratio >= threshold:\n"
        "            anomalous_segments.append(seg)\n\n"
        "    # Find maximal contiguous subpath\n"
        "    if not anomalous_segments:\n"
        "        return None\n"
        "    start_stop = anomalous_segments[0]['start_stop_id']\n"
        "    end_stop = anomalous_segments[-1]['end_stop_id']\n"
        "    total_rev_gap = sum(s.get('revenue_deficit', 0) for s in anomalous_segments)\n"
        "    confidence = min(0.99, 0.70 + 0.05 * len(anomalous_segments))\n"
        "    return {\n"
        "        'trip_id': trip_id, 'route_id': route_id,\n"
        "        'start_stop': start_stop, 'end_stop': end_stop,\n"
        "        'num_segments': len(anomalous_segments),\n"
        "        'total_revenue_gap_inr': total_rev_gap,\n"
        "        'confidence': confidence\n"
        "    }\n"
    )
    rc3 = p_c3.add_run(code_text_3)
    rc3.font.name = "Times New Roman"
    rc3.font.size = Pt(9)

    # Configure document settings to automatically prompt Word to update fields (including TOC) on open
    try:
        settings_elm = doc.settings.element
        update_fields_elm = parse_xml(r'<w:updateFields %s w:val="true"/>' % nsdecls('w'))
        settings_elm.append(update_fields_elm)
    except Exception as e:
        print(f"Note on settings updateFields: {e}")

    doc.save(output_filename)
    print(f"Report successfully generated and saved to: {output_filename}")

if __name__ == "__main__":
    out_path = os.path.abspath(r"d:\Coud CIA 3 FairGuard\FareGuard_Mini_Project_Report.docx")
    create_report(out_path)
