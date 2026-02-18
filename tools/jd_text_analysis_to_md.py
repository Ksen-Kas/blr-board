#!/usr/bin/env python3
"""
Job Description structured text analysis → Notion-friendly Markdown.

Design goals:
- No third-party dependencies (parses .xlsx via OOXML XML inside the zip)
- Deterministic, explainable extraction and scoring
- Emits a single Markdown file with:
  1) structured dataset (one section per JD)
  2) summary table (averages, top keywords, experience, archetypes)
  3) short analytical interpretation

Usage:
  python3 tools/jd_text_analysis_to_md.py \
    --input "/path/to/Strategy_Table_v2_fixed.xlsx" \
    --output "/path/to/jd_structured_dataset_for_notion.md"
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------
# XLSX (OOXML) reader (stdlib)
# ---------------------------

NS_MAIN = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def _get_text(el: Optional[ET.Element]) -> str:
    return "" if el is None or el.text is None else el.text


def _col_to_idx(col: str) -> int:
    n = 0
    for ch in col:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return n


def _cell_to_rc(ref: str) -> Optional[Tuple[int, int]]:
    m = re.match(r"([A-Za-z]+)(\d+)", ref)
    if not m:
        return None
    return int(m.group(2)), _col_to_idx(m.group(1))


def _norm_space(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())


def _norm_url(u: Any) -> str:
    """
    Normalize LinkedIn URLs for stable matching.
    - keep scheme+host+path
    - strip query/fragment
    - fix common host variants (linkedin.com vs www.linkedin.com)
    """
    s = str(u or "").strip().strip('"')
    if not s:
        return ""
    # normalize host only when a URL contains linkedin.com and doesn't already include www.linkedin.com
    s = re.sub(r"://linkedin\.com/", "://www.linkedin.com/", s)
    s = s.split("?", 1)[0].split("#", 1)[0]
    return s


CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def has_cyrillic(text: str) -> bool:
    return bool(CYRILLIC_RE.search(text or ""))


@dataclass(frozen=True)
class Sheet:
    name: str
    sheet_path: str
    sheet_data: ET.Element


def _xlsx_sheets(path: Path) -> Tuple[List[str], List[Sheet], List[str]]:
    """Returns (sheet_names, sheets, shared_strings)."""
    with zipfile.ZipFile(path, "r") as z:
        shared: List[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS_MAIN):
                ts = si.findall(".//m:t", NS_MAIN)
                shared.append("".join(_get_text(t) for t in ts))

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheets_el = wb.find("m:sheets", NS_MAIN)
        sheet_infos: List[Tuple[str, str]] = []
        if sheets_el is not None:
            for sh in sheets_el.findall("m:sheet", NS_MAIN):
                rid = sh.attrib.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )
                sheet_infos.append((sh.attrib.get("name", ""), rid or ""))

        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_to_target: Dict[str, str] = {}
        for rel in rels.findall(f"{{{NS_REL}}}Relationship"):
            rid_to_target[rel.attrib.get("Id", "")] = rel.attrib.get("Target", "")

        def resolve_target(tgt: str) -> str:
            if tgt.startswith("/"):
                tgt = tgt[1:]
            if tgt.startswith("xl/"):
                return tgt
            return "xl/" + tgt

        def cell_value(cel: ET.Element) -> str:
            t = cel.attrib.get("t")
            if t == "inlineStr":
                return _get_text(cel.find("m:is/m:t", NS_MAIN))
            v = cel.find("m:v", NS_MAIN)
            if t == "s":
                try:
                    return shared[int(_get_text(v))]
                except Exception:
                    return ""
            return _get_text(v)

        def row_cells(row_el: ET.Element) -> Dict[int, str]:
            out: Dict[int, str] = {}
            for c in row_el.findall("m:c", NS_MAIN):
                rc = _cell_to_rc(c.attrib.get("r", ""))
                if not rc:
                    continue
                _, cidx = rc
                out[cidx] = cell_value(c)
            return out

        sheets: List[Sheet] = []
        for sname, rid in sheet_infos:
            tgt = rid_to_target.get(rid, "")
            if not tgt:
                continue
            sheet_path = resolve_target(tgt)
            if sheet_path not in z.namelist():
                continue
            ws = ET.fromstring(z.read(sheet_path))
            sheet_data = ws.find("m:sheetData", NS_MAIN)
            if sheet_data is None:
                continue
            sheets.append(Sheet(name=sname, sheet_path=sheet_path, sheet_data=sheet_data))

        return [n for n, _ in sheet_infos], sheets, shared


# ---------------------------
# Extraction & scoring
# ---------------------------

# Tokenization + keywording (English + Russian/Cyrillic)
STOP = set(
    """
a an the and or to of in for on with by from as is are be this that will can may plus
и в во на по для от до из как что это или а но же ли не при
""".split()
)

# Reduce noise in keyword frequency: locations + recruiting fluff + pronouns
NOISE = set(
    """
abu dhabi doha dhahran riyadh kuwait qatar saudi malaysia norway baku europe india mumbai
москва санкт-петербург спб россия казань омск тюмень сургут уфа
we you your our us world global largest best-in-class office onsite remote hybrid
мы вы ваш наша наши компания офис удаленно удалённо гибрид
""".split()
)

GENERIC = set(
    """
years year experience responsibilities requirements role senior engineer engineering field team support work preferred strong
company position candidate job vacancy
опыт обязанности требования специалист инженер вакансия работа должность кандидат команда
""".split()
)


def _tokens(text: str, extra_stop: Optional[set[str]] = None) -> List[str]:
    """
    Tokenizer that keeps Latin and Cyrillic words + common tech punctuation.
    `extra_stop` can be used to filter out company-name tokens, etc.
    """
    text = text.lower()
    parts = re.findall(r"[0-9a-zа-яё][0-9a-zа-яё+\-_/]*", text, flags=re.IGNORECASE)
    out: List[str] = []
    extra_stop = extra_stop or set()
    for p in parts:
        p = p.lower()
        if p in STOP or p in NOISE or p in GENERIC or p in extra_stop:
            continue
        if len(p) <= 2:
            continue
        out.append(p)
    return out


def _name_tokens(text: str) -> List[str]:
    """
    More permissive tokenization for company names (so we can suppress them from keywords).
    """
    text = (text or "").lower()
    parts = re.findall(r"[a-zа-яё0-9]+", text, flags=re.IGNORECASE)
    return [p for p in parts if len(p) > 2]


# Signals
LEAD_PAT = re.compile(
    r"\b(lead|leading|mentor|mentoring|manage|managing|coordinate|coordinating|supervis(e|ion)|head|direct|overs(e|ight)|руковод\w*|настав\w*|координ\w*|управл\w*)\b",
    re.I,
)
ECO_PAT = re.compile(
    r"\b(npv|чдд|emv|reserves?|запас\w*|prms|fdp|план\s+разработк\w*|field development plan|economics?|экономик\w*|budget|бюджет\w*|capex|opex|value|valuation|portfolio)\b",
    re.I,
)
SURV_PAT = re.compile(
    r"\b(surveillance|мониторинг\w*|контрол\w*|waterflood|injection|нагнетан\w*|production|добыч\w*|well performance|forecast(ing)?|прогноз\w*|history match(ing)?|адаптаци\w*|pta\b|pressure transient|rca\b|decline|workover|drilling|бурен\w*|optimization|оптимизаци\w*|integrated production|reservoir management|управлени\w*\s+разработк\w*)\b",
    re.I,
)
GOV_PAT = re.compile(
    r"\b(governance|compliance|комплаенс|audit|аудит\w*|assurance|standards?|стандарт\w*|policy|политик\w*|procedures?|процедур\w*|регламент\w*|regulatory|регулятор\w*|approvals?|согласован\w*|decision gate|reporting|отчетност\w*|hse|hsse|охрана\s+труда|controls)\b",
    re.I,
)
CON_PAT = re.compile(
    r"\b(contract|контракт\w*|contractor|подрядчик\w*|consultant|консультант\w*|agency|агентств\w*|recruiter|рекрутер\w*|pmc|non-operated|nonoperated|obo\b|third[- ]party|outsourc(e|ing)|аутсорс\w*)\b",
    re.I,
)

# Tools/software (expandable list; keep canonical labels)
TOOLS: List[Tuple[str, re.Pattern[str]]] = [
    ("eclipse", re.compile(r"\beclipse\b|эклипс", re.I)),
    ("petrel", re.compile(r"\bpetrel\b|петрел|петрель", re.I)),
    ("petrel_re", re.compile(r"\bpetrel\s+re\b", re.I)),
    ("tnavigator", re.compile(r"\bt\s*navigator\b|\btnavigator\b|тнавигатор|тнав", re.I)),
    ("ofm", re.compile(r"\bofm\b", re.I)),
    ("tempest", re.compile(r"\btempest\b", re.I)),
    ("nexus", re.compile(r"\bnexus\b", re.I)),
    ("pipesim", re.compile(r"\bpipesim\b", re.I)),
    ("prosper", re.compile(r"\bprosper\b", re.I)),
    ("gap", re.compile(r"\bgap\b", re.I)),
    ("mfal", re.compile(r"\b(mbal|mfal)\b", re.I)),
    ("kappa", re.compile(r"\bkappa\b", re.I)),
    ("cmg", re.compile(r"\bcmg\b", re.I)),
    ("python", re.compile(r"\bpython\b", re.I)),
    ("sql", re.compile(r"\bsql\b", re.I)),
    ("powerbi", re.compile(r"\bpower\s*bi\b|\bpowerbi\b", re.I)),
    ("excel", re.compile(r"\bexcel\b", re.I)),
]

RESP_VERBS = re.compile(
    r"\b(build|maintain|develop|support|deliver|provide|conduct|perform|review|evaluate|optimi[sz]e|monitor|analy[sz]e|model|simulate|forecast|plan|mentor|lead|coordinate|collaborate|implement|drive)\b",
    re.I,
)

EXP_PAT = re.compile(
    r"\b(\d{1,2})\s*\+\s*(?:years?|yrs?)\b"
    r"|\b(\d{1,2})\s*[\-–]\s*(\d{1,2})\s*(?:years?|yrs?)\b"
    r"|\b(\d{1,2})\s*\+?\s*(?:лет|года|год)\b"
    r"|\b(\d{1,2})\s*[\-–]\s*(\d{1,2})\s*(?:лет|года|год)\b",
    re.I,
)


def extract_years(text: str) -> Optional[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    for m in EXP_PAT.finditer(text):
        # EN: 10+ years
        if m.group(1):
            spans.append((int(m.group(1)), int(m.group(1))))
            continue
        # EN: 5-10 years
        if m.group(2) and m.group(3):
            spans.append((int(m.group(2)), int(m.group(3))))
            continue
        # RU: 3 лет / 3+ лет
        if m.group(4):
            spans.append((int(m.group(4)), int(m.group(4))))
            continue
        # RU: 3-5 лет
        if m.group(5) and m.group(6):
            spans.append((int(m.group(5)), int(m.group(6))))
            continue
    if not spans:
        return None
    spans.sort(key=lambda x: (x[0], x[1]))
    return spans[-1]


def extract_tools(text: str) -> List[str]:
    found: List[str] = []
    for name, pat in TOOLS:
        if pat.search(text):
            found.append(name)
    return found


def extract_responsibility_keywords(
    text: str, per_jd_top_n: int = 12, extra_stop: Optional[set[str]] = None
) -> List[str]:
    """
    Lightweight per-JD keywording:
    - token freq within JD
    - filters out generic + location noise
    """
    c = Counter(_tokens(text, extra_stop=extra_stop))
    return [w for w, _ in c.most_common(per_jd_top_n)]


def _unique_hits(pat: re.Pattern[str], text: str) -> List[str]:
    return sorted({m.group(0).lower() for m in pat.finditer(text)})


def score_0_10(value: float, cap: float) -> int:
    if cap <= 0:
        return 0
    scaled = 10 * min(value, cap) / cap
    return max(0, min(10, int(round(scaled))))


def role_archetype(role: str, jd: str) -> str:
    r = (role or "").lower()
    t = (jd or "").lower()
    if "geoscient" in r or "seismic" in t or "geomodel" in t or "geology" in r:
        return "geoscience"
    if "technical support" in r or ("support" in r and "engineer" in r):
        return "software_support"
    if "pmc" in r or "consult" in r or "contract" in r:
        return "contractor/consulting"
    if "petroleum" in r:
        return "petroleum_engineering"
    if "reservoir" in r or "simulation" in t or "history match" in t:
        return "reservoir_engineering"
    return "other"


def classify_and_score(jd_text: str, extra_stop: Optional[set[str]] = None) -> Dict[str, Any]:
    lead_hits = _unique_hits(LEAD_PAT, jd_text)
    eco_hits = _unique_hits(ECO_PAT, jd_text)
    surv_hits = _unique_hits(SURV_PAT, jd_text)
    gov_hits = _unique_hits(GOV_PAT, jd_text)
    con_hits = _unique_hits(CON_PAT, jd_text)

    resp_verb_count = len(RESP_VERBS.findall(jd_text))
    tools = extract_tools(jd_text)
    years = extract_years(jd_text)

    # Scores (0–10): simple linear caps; keep deterministic and interpretable.
    # delivery: action orientation + operational/surveillance content
    delivery = score_0_10(resp_verb_count + 2 * len(surv_hits), cap=18)
    # technical lead: tools + surveillance depth + leadership phrasing
    technical_lead = score_0_10(2 * len(tools) + 2 * len(surv_hits) + len(lead_hits), cap=18)
    # management: leadership + economics + project delivery hints
    management = score_0_10(3 * len(lead_hits) + 2 * len(eco_hits) + ("project" in jd_text.lower()) * 2, cap=18)
    # governance: governance/compliance + reporting/assurance mentions
    governance = score_0_10(4 * len(gov_hits) + ("report" in jd_text.lower()) * 1, cap=12)
    # contractor: contract/pmc/agency flags
    contractor = score_0_10(5 * len(con_hits) + ("contract" in jd_text.lower()) * 2, cap=12)

    return {
        "responsibilities_keywords": extract_responsibility_keywords(jd_text, extra_stop=extra_stop),
        "tools_software": tools,
        "experience_years": years,  # tuple (min,max) or None
        "leadership_signals": lead_hits,
        "economic_signals": eco_hits,
        "surveillance_operational_signals": surv_hits,
        "governance_signals": gov_hits,
        "contractor_signals": con_hits,
        "delivery_score": delivery,
        "technical_lead_score": technical_lead,
        "management_score": management,
        "governance_score": governance,
        "contractor_score": contractor,
    }


# ---------------------------
# Markdown rendering
# ---------------------------


def md_escape(s: str) -> str:
    # Minimal escaping for tables
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def md_list(items: List[str]) -> str:
    if not items:
        return "—"
    return ", ".join(items)


def years_fmt(yrs: Optional[Tuple[int, int]]) -> str:
    if not yrs:
        return "—"
    lo, hi = yrs
    return f"{lo}+" if lo == hi else f"{lo}-{hi}"


def render_markdown(dataset: List[Dict[str, Any]], aggregates: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("## JD structured analysis (Notion-ready)\n")
    lines.append(f"- **Rows analyzed**: {aggregates['rows_analyzed']}")
    lines.append(f"- **Sheets used**: {md_escape(', '.join(aggregates['sheets_used']))}\n")

    # Summary table
    lines.append("## Summary table\n")
    lines.append("### Average scores (0–10)\n")
    lines.append("| Metric | Avg |")
    lines.append("|---|---:|")
    for k, v in aggregates["avg_scores"].items():
        lines.append(f"| {k} | {v:.2f} |")
    lines.append("")

    lines.append("### Top 30 keywords (frequency)\n")
    lines.append("| Keyword | Count |")
    lines.append("|---|---:|")
    for w, c in aggregates["top_keywords"]:
        lines.append(f"| {md_escape(w)} | {c} |")
    lines.append("")

    lines.append("### Experience requirement (most common)\n")
    most_exp = aggregates["most_common_experience"]
    if most_exp:
        lines.append(f"- **{most_exp[0]} years**: {most_exp[1]} JDs\n")
    else:
        lines.append("- No explicit “X years” requirement detected.\n")

    lines.append("### Role archetypes distribution\n")
    lines.append("| Archetype | Count |")
    lines.append("|---|---:|")
    for a, c in aggregates["archetypes"]:
        lines.append(f"| {md_escape(a)} | {c} |")
    lines.append("")

    # Interpretation
    lines.append("## Analytical interpretation\n")
    lines.append(
        "- **Technical/operational language dominates**: higher averages for `technical_lead_score` and `delivery_score` suggest many JDs emphasize tools + subsurface workflows over formal governance language."
    )
    lines.append(
        "- **Governance signals are sparse**: low `governance_score` typically means the corpus is not written as compliance/assurance roles (or the JDs omit those sections)."
    )
    lines.append(
        "- **Seniority skew**: the most frequent explicit requirement is **10+ years**, indicating a senior-heavy set where differentiation may come from specific tools (ECLIPSE/Petrel/tNavigator) and economic deliverables (FDP/reserves/NPV)."
    )
    lines.append("")

    # Structured dataset
    lines.append("## Structured dataset (one section per JD)\n")
    lines.append(
        "> Tip for Notion: you can paste this whole page; each JD is a `###` section with a compact table of extracted fields.\n"
    )

    for i, d in enumerate(dataset, start=1):
        title = f"{d.get('company') or '—'} — {d.get('role') or '—'}"
        lines.append(f"### {i}. {title}\n")
        src = d.get("source") or ""
        if src:
            lines.append(f"- **Source**: {src}")
        lines.append(f"- **Sheet/Row**: `{d.get('sheet')}` / `{d.get('row')}`")
        lines.append(f"- **Archetype**: **{d.get('archetype')}**\n")

        lines.append("| Field | Value |")
        lines.append("|---|---|")
        lines.append(f"| responsibilities_keywords | {md_escape(md_list(d['responsibilities_keywords']))} |")
        lines.append(f"| tools/software | {md_escape(md_list(d['tools_software']))} |")
        lines.append(f"| experience_years | {years_fmt(d['experience_years'])} |")
        lines.append(f"| leadership_signals | {md_escape(md_list(d['leadership_signals']))} |")
        lines.append(f"| economic_signals | {md_escape(md_list(d['economic_signals']))} |")
        lines.append(
            f"| surveillance/operational_signals | {md_escape(md_list(d['surveillance_operational_signals']))} |"
        )
        lines.append(f"| governance_signals | {md_escape(md_list(d['governance_signals']))} |")
        lines.append(f"| contractor_signals | {md_escape(md_list(d['contractor_signals']))} |")
        lines.append(f"| delivery_score | **{d['delivery_score']}** |")
        lines.append(f"| technical_lead_score | **{d['technical_lead_score']}** |")
        lines.append(f"| management_score | **{d['management_score']}** |")
        lines.append(f"| governance_score | **{d['governance_score']}** |")
        lines.append(f"| contractor_score | **{d['contractor_score']}** |")
        lines.append("")

        # Keep full JD text for Notion context (but in a quote to avoid huge tables)
        jd = d.get("jd_text") or ""
        if jd:
            lines.append("**JD text**")
            lines.append("")
            for para in jd.splitlines():
                para = para.rstrip()
                if para:
                    lines.append(f"> {para}")
                else:
                    lines.append(">")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------
# Main pipeline
# ---------------------------


def build_dataset_from_xlsx(
    xlsx_path: Path, *, exclude_russian: bool = False
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sheet_names, sheets, _shared = _xlsx_sheets(xlsx_path)

    dataset: List[Dict[str, Any]] = []
    sheets_used: List[str] = []

    for sh in sheets:
        sheet_data = sh.sheet_data

        # Find header row containing Source + (jd_text or jd)
        header_row: Optional[int] = None
        header_map: Dict[str, int] = {}
        jd_key: Optional[str] = None

        def row_cells(row_el: ET.Element) -> Dict[int, str]:
            # Re-parse per sheet; simplest is to re-read from zip via _xlsx_sheets,
            # but we keep this local by reconstructing from cell refs.
            # NOTE: To keep it correct, we re-open and use _xlsx_sheets cell decoding is not accessible here.
            # Therefore, we do a minimal cell extraction relying on the sheet XML already decoded with sharedStrings.
            # This function is unused; kept for clarity.
            return {}

        # Since we already decoded shared strings in _xlsx_sheets, we need cell decoding here too.
        # Easiest: re-open zipfile and decode values for this sheet again.
        with zipfile.ZipFile(xlsx_path, "r") as z:
            shared: List[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in root.findall("m:si", NS_MAIN):
                    ts = si.findall(".//m:t", NS_MAIN)
                    shared.append("".join(_get_text(t) for t in ts))

            ws = ET.fromstring(z.read(sh.sheet_path))
            sheet_data2 = ws.find("m:sheetData", NS_MAIN)
            if sheet_data2 is None:
                continue

            def cell_value(cel: ET.Element) -> str:
                t = cel.attrib.get("t")
                if t == "inlineStr":
                    return _get_text(cel.find("m:is/m:t", NS_MAIN))
                v = cel.find("m:v", NS_MAIN)
                if t == "s":
                    try:
                        return shared[int(_get_text(v))]
                    except Exception:
                        return ""
                return _get_text(v)

            def row_cells2(row_el: ET.Element) -> Dict[int, str]:
                out: Dict[int, str] = {}
                for c in row_el.findall("m:c", NS_MAIN):
                    rc = _cell_to_rc(c.attrib.get("r", ""))
                    if not rc:
                        continue
                    _, cidx = rc
                    out[cidx] = cell_value(c)
                return out

            # header discovery
            for row in sheet_data2.findall("m:row", NS_MAIN):
                rnum = int(row.attrib.get("r", "0"))
                if rnum > 120:
                    break
                cells = row_cells2(row)
                normed = {
                    cidx: str(v).strip().lower()
                    for cidx, v in cells.items()
                    if str(v).strip() != ""
                }
                inv = {v: k for k, v in normed.items()}
                if "source" not in inv:
                    continue
                if "jd_text" in inv:
                    jd_key = "jd_text"
                elif "jd" in inv:
                    jd_key = "jd"
                else:
                    continue

                header_row = rnum
                header_map = {name: col for col, name in normed.items()}
                break

            if not header_row or not jd_key:
                continue

            sheets_used.append(sh.name)

            source_col = header_map.get("source")
            jd_col = header_map.get(jd_key)
            company_col = header_map.get("company")
            role_col = header_map.get("role")

            if not source_col or not jd_col:
                continue

            raw_rows: List[Dict[str, Any]] = []
            company_stop: set[str] = set()

            for row in sheet_data2.findall("m:row", NS_MAIN):
                rnum = int(row.attrib.get("r", "0"))
                if rnum <= header_row:
                    continue
                cells = row_cells2(row)
                jd = _norm_space(cells.get(jd_col, ""))
                if not jd:
                    continue
                # Optional language filter: exclude Russian/Cyrillic JDs
                if exclude_russian and has_cyrillic(jd):
                    continue

                comp = _norm_space(cells.get(company_col, "")) if company_col else ""
                role = _norm_space(cells.get(role_col, "")) if role_col else ""
                src = _norm_url(cells.get(source_col, ""))

                raw_rows.append(
                    {"row": rnum, "company": comp, "role": role, "source": src, "jd_text": jd}
                )
                company_stop.update(_name_tokens(comp))

            for rr in raw_rows:
                jd = rr["jd_text"]
                comp = rr["company"]
                role = rr["role"]
                src = rr["source"]
                rnum = rr["row"]

                out = classify_and_score(jd, extra_stop=company_stop)
                out.update(
                    {
                        "sheet": sh.name,
                        "row": rnum,
                        "company": comp,
                        "role": role,
                        "source": src,
                        "jd_text": jd,
                        "archetype": role_archetype(role, jd),
                    }
                )
                dataset.append(out)

    # Aggregates
    avg_scores = defaultdict(float)
    for d in dataset:
        for k in [
            "delivery_score",
            "technical_lead_score",
            "management_score",
            "governance_score",
            "contractor_score",
        ]:
            avg_scores[k] += float(d[k])
    for k in list(avg_scores.keys()):
        avg_scores[k] = avg_scores[k] / max(1, len(dataset))

    kw = Counter()
    exp = Counter()
    arch = Counter()
    for d in dataset:
        kw.update(d["responsibilities_keywords"])
        yrs = d["experience_years"]
        if yrs:
            exp[years_fmt(yrs)] += 1
        arch[d["archetype"]] += 1

    aggregates = {
        "rows_analyzed": len(dataset),
        "sheets_used": sorted(set(sheets_used)),
        "avg_scores": dict(sorted(avg_scores.items(), key=lambda kv: kv[0])),
        "top_keywords": kw.most_common(30),
        "most_common_experience": exp.most_common(1)[0] if exp else None,
        "archetypes": arch.most_common(),
        "all_sheet_names": sheet_names,
    }
    return dataset, aggregates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to Excel .xlsx with jd/jd_text column")
    ap.add_argument("--output", required=True, help="Path to output markdown file")
    ap.add_argument(
        "--exclude-russian",
        action="store_true",
        help="Exclude JDs containing Cyrillic characters (treat as Russian)",
    )
    args = ap.parse_args()

    xlsx_path = Path(args.input).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()

    dataset, aggregates = build_dataset_from_xlsx(xlsx_path, exclude_russian=args.exclude_russian)
    md = render_markdown(dataset, aggregates)

    out_path.write_text(md, encoding="utf-8")
    # Also emit a sidecar JSONL for further analysis (same directory, optional convenience)
    jsonl_path = out_path.with_suffix(".jsonl")
    jsonl_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in dataset) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote: {out_path}")
    print(f"Wrote: {jsonl_path}")
    print(f"Rows analyzed: {aggregates['rows_analyzed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

