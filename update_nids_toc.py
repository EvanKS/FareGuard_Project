"""
Script to update the Table of Contents in NIDS_XAI_Project_Report.docx
Replaces the plain-text TOC entries (P28 onwards) with a properly formatted
TOC using tab leaders and correct hierarchy (Chapters bold 14pt, Sections 12pt).
"""

import docx
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy
import re

# ── TOC content definition ─────────────────────────────────────────────────
# Each entry: (level, text, page_number)
# level 1 = Chapter (bold, 14pt), level 2 = Section (normal, 12pt)
TOC_ENTRIES = [
    (1, "1. PROJECT TITLE & EXECUTIVE SUMMARY",      3),
    (2, "1.1 Project Title",                          3),
    (2, "1.2 Executive Summary",                      3),
    (2, "1.3 Relevance to Cryptography and Application Security", 4),

    (1, "2. PROBLEM STATEMENT",                       5),
    (2, "2.1 Network Attack Surface & Threat Vectors", 5),
    (2, "2.2 Shortcomings of Legacy Signature-Based NIDS", 5),
    (2, "2.3 The 'Black-Box' Dilemma in AI-Driven Detection", 6),
    (2, "2.4 Specific Problem Formulation",           6),

    (1, "3. OBJECTIVES",                              7),
    (2, "3.1 Primary Aim",                            7),
    (2, "3.2 Core Technical & Engineering Objectives", 7),
    (2, "3.3 Evaluation Standards & Success Criteria", 8),

    (1, "4. LITERATURE REVIEW",                       9),
    (2, "4.1 Review of Foundational Studies",          9),
    (2, "4.2 Comparative Summary Matrix of Prior Art", 10),
    (2, "4.3 Research Gap & Proposed XAI Advantage",  11),

    (1, "5. TECHNOLOGIES & TOOLS USED",               12),
    (2, "5.1 Core Programming Language & ML Stack",   12),
    (2, "5.2 Explainable Artificial Intelligence (XAI) Stack", 12),
    (2, "5.3 Web Architecture & Serving Stack",       13),
    (2, "5.4 Natural Language Generation Layer",      13),

    (1, "6. SYSTEM / MODULE DESIGN & ARCHITECTURE",  14),
    (2, "6.1 Architectural Overview & Decoupled Trust Boundary", 14),
    (2, "6.2 Data Flow Sequence",                     14),
    (2, "6.3 API Endpoint Catalogue",                 15),
    (2, "6.4 Frontend UI Module Architecture",        15),

    (1, "7. IMPLEMENTATION & TECHNICAL METHODOLOGY", 16),
    (2, "7.1 Dataset Description: NSL-KDD Feature Space", 16),
    (2, "7.2 Preprocessing Pipeline & Handling Unseen Test Categories", 16),
    (2, "7.3 Class Imbalance Mitigation Strategy",    17),
    (2, "7.4 Real-Time Asynchronous WebSocket Engine", 17),

    (1, "8. EXPERIMENTAL RESULTS & PERFORMANCE EVALUATION", 18),
    (2, "8.1 Benchmark Dataset Evaluation Standards", 18),
    (2, "8.2 Global Multi-Class Performance Metrics", 18),
    (2, "8.3 Per-Class Performance Breakdown",        19),
    (2, "8.4 5x5 Confusion Matrix Analysis",          19),
    (2, "8.5 Supervised vs. Unsupervised Control",    20),
    (2, "8.6 Global Feature Importance (Top SHAP Features)", 20),

    (1, "9. PROJECT SCREENSHOTS & VERIFICATION GUIDE", 21),

    (1, "10. CONCLUSION & FUTURE WORK",               22),
    (2, "10.1 Key Findings & Conclusion",             22),
    (2, "10.2 Operational Impact in Enterprise SOC Deployments", 22),
    (2, "10.3 Future Research & Engineering Directions", 23),

    (1, "11. INDIVIDUAL CONTRIBUTION MATRIX",         24),

    (1, "12. REFERENCES",                             25),
]

FONT_NAME = "Times New Roman"

def set_toc_para_style(para, level, text, page_num):
    """
    Format a TOC paragraph with:
    - Left-aligned text
    - Right-aligned page number with dot leaders (tab stop)
    - Font: Times New Roman
    - Chapter (level 1): Bold, 14pt
    - Section  (level 2): Normal, 12pt, indented 0.25"
    """
    para.clear()
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # ── Set the paragraph XML tab stop for right-aligned page num ─────────
    pPr = para._p.get_or_add_pPr()
    # Remove existing tabs
    for tabs_el in pPr.findall(qn('w:tabs')):
        pPr.remove(tabs_el)
    tabs = OxmlElement('w:tabs')
    tab = OxmlElement('w:tab')
    tab.set(qn('w:val'), 'right')
    tab.set(qn('w:leader'), 'dot')
    # 6.25 inches = right margin position for A4 with 1.25"+1.0" margins
    tab.set(qn('w:pos'), '8910')  # twips (1 inch = 1440 twips) => ~6.18 inches
    tabs.append(tab)
    pPr.append(tabs)

    # ── Set indentation ────────────────────────────────────────────────────
    ind = OxmlElement('w:ind')
    if level == 1:
        ind.set(qn('w:left'), '0')
    else:
        ind.set(qn('w:left'), '360')  # 0.25 inch indent for subsections
    pPr.append(ind)

    # ── Add text run ───────────────────────────────────────────────────────
    run_text = para.add_run(text)
    run_text.font.name = FONT_NAME
    run_text.font.bold = (level == 1)
    run_text.font.size = Pt(14 if level == 1 else 12)
    run_text.font.color.rgb = RGBColor(0, 0, 0)

    # ── Add tab + page number run ──────────────────────────────────────────
    run_tab = para.add_run('\t' + str(page_num))
    run_tab.font.name = FONT_NAME
    run_tab.font.bold = (level == 1)
    run_tab.font.size = Pt(14 if level == 1 else 12)
    run_tab.font.color.rgb = RGBColor(0, 0, 0)

    # Small spacing after paragraph
    para.paragraph_format.space_after = Pt(2 if level == 2 else 4)
    para.paragraph_format.space_before = Pt(4 if level == 1 else 0)


def update_nids_toc():
    path = r'd:\Coud CIA 3 FairGuard\NIDS_XAI_Project_Report.docx'
    doc = Document(path)

    # ── Locate "TABLE OF CONTENTS" paragraph ──────────────────────────────
    toc_title_idx = None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip() == 'TABLE OF CONTENTS':
            toc_title_idx = i
            break

    if toc_title_idx is None:
        print("ERROR: Could not find 'TABLE OF CONTENTS' paragraph.")
        return

    print(f"Found 'TABLE OF CONTENTS' at paragraph index {toc_title_idx}")

    # ── Style the TOC title itself ─────────────────────────────────────────
    title_para = doc.paragraphs[toc_title_idx]
    title_para.clear()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run("TABLE OF CONTENTS")
    title_run.font.name = FONT_NAME
    title_run.font.bold = True
    title_run.font.size = Pt(16)
    title_run.font.color.rgb = RGBColor(0, 0, 0)
    title_para.paragraph_format.space_after = Pt(12)

    # ── Identify the range of old TOC entries to replace ──────────────────
    # The old TOC runs from toc_title_idx+1 until we hit the first content
    # paragraph that is NOT a TOC line (i.e., paragraph 30+ with real body text).
    # From our analysis, P28 and P29 are empty, P30 starts old TOC entries
    # which run until before the actual chapter content (P30 "1. PROJECT TITLE...")
    # But wait - P30 IS actually in the TOC area (it's the old TOC entry).
    # The real body starts at the first paragraph AFTER the TOC that has matching
    # content (the heading itself). We need to find where the TOC ends.
    # 
    # Strategy: delete paragraphs from toc_title_idx+1 up to (but not including)
    # the first paragraph whose text starts with "1. PROJECT TITLE" AND is NOT
    # immediately after the TOC title (i.e., comes after some content).
    # 
    # From the analysis: P27=TOC title, P28/29 empty, P30..~P38 = old TOC entries,
    # then the real content begins. But since ALL body paragraphs use "Normal" style,
    # we'll look for a pattern break: the old TOC ends when we see a paragraph
    # that matches a chapter title exactly (size 14, bold) which is NOT part of TOC.
    # 
    # Easiest: just delete P28 through the paragraph just before "1. PROJECT TITLE"
    # appears as BODY content (not TOC). We'll find this by looking for P that
    # has style="Normal", bold=True, size=14 OR a blank page break paragraph.
    #
    # From our scan: real content starts at P30 in the OLD doc structure.
    # But P30 text is "1. PROJECT TITLE & EXECUTIVE SUMMARY" - which is BOTH
    # in the old TOC and in the body. We need to find where the TOC section ENDS
    # and body begins. The TOC in this doc appears to have NO page breaks separating
    # them visually from body - so we need to check for the actual chapter heading
    # that comes AFTER a page break or after significant blank paragraphs.
    #
    # Let's find the second occurrence of "1. PROJECT TITLE" text:
    occurrences = []
    for i, p in enumerate(doc.paragraphs):
        if '1. PROJECT TITLE' in p.text:
            occurrences.append(i)
    print(f"'1. PROJECT TITLE' found at indices: {occurrences}")

    # The TOC entry is the FIRST occurrence; body chapter heading is the SECOND.
    # Delete paragraphs from toc_title_idx+1 to body_start-1 (exclusive).
    # Then insert our new TOC entries after the title.

    if len(occurrences) >= 2:
        toc_content_start = occurrences[0]
        body_start = occurrences[1]
    elif len(occurrences) == 1:
        # Only one occurrence - the TOC and body share the same paragraph
        # We'll insert after the TOC title and delete the single occurrence
        toc_content_start = occurrences[0]
        body_start = occurrences[0]
    else:
        toc_content_start = toc_title_idx + 1
        body_start = toc_title_idx + 1

    print(f"TOC content start: {toc_content_start}, Body start: {body_start}")

    # ── Delete old TOC entries (from after title to before body) ──────────
    # We'll delete paragraphs from toc_content_start to body_start-1 (inclusive).
    # Since we delete from the XML parent, we need the body element.
    body = doc.element.body
    all_paras = list(body.iterchildren())

    # Get the actual XML elements for the range we want to delete
    # doc.paragraphs maps to <w:p> elements inside body
    # We need to find the <w:p> elements at positions toc_content_start .. body_start-1
    p_elements = [p._p for p in doc.paragraphs]

    delete_start = toc_content_start
    delete_end = body_start  # exclusive (don't delete body_start)

    print(f"Deleting paragraph XML elements at indices {delete_start} to {delete_end - 1}")

    # Remove them (must collect first, then remove to avoid index shifting)
    to_remove = p_elements[delete_start:delete_end]
    for p_el in to_remove:
        p_el.getparent().remove(p_el)

    print(f"Deleted {len(to_remove)} old TOC paragraphs.")

    # ── Now insert new TOC paragraphs after the TOC title paragraph ────────
    # Re-get the title paragraph's _p element (index may have shifted)
    # Find the TOC title paragraph again
    toc_title_p = None
    for p in doc.paragraphs:
        if p.text.strip() == 'TABLE OF CONTENTS':
            toc_title_p = p._p
            break

    if toc_title_p is None:
        print("ERROR: Cannot re-find TOC title after deletion.")
        return

    # Insert new TOC paragraphs after the title, in reverse order
    # (each inserted right after title, so last entry inserted first will end up last)
    # Actually insert in forward order, each after the previously inserted paragraph
    insert_after_p = toc_title_p

    # Add a blank line after title
    blank_p = OxmlElement('w:p')
    blank_pPr = OxmlElement('w:pPr')
    blank_pStyle = OxmlElement('w:pStyle')
    blank_pStyle.set(qn('w:val'), 'Normal')
    blank_pPr.append(blank_pStyle)
    blank_p.append(blank_pPr)
    insert_after_p.addnext(blank_p)
    insert_after_p = blank_p

    for level, text, page_num in TOC_ENTRIES:
        # Create a new paragraph element
        new_p_el = OxmlElement('w:p')
        insert_after_p.addnext(new_p_el)
        insert_after_p = new_p_el

        # Wrap in a docx Paragraph object for easier manipulation
        from docx.text.paragraph import Paragraph
        new_para = Paragraph(new_p_el, doc)
        set_toc_para_style(new_para, level, text, page_num)

    # ── Save the document ──────────────────────────────────────────────────
    out_path = r'd:\Coud CIA 3 FairGuard\NIDS_XAI_Project_Report.docx'
    doc.save(out_path)
    print(f"\nSaved successfully: {out_path}")
    print("TOC has been updated with proper formatting.")


if __name__ == '__main__':
    update_nids_toc()
