#!/usr/bin/env python3
"""
Analyze JD dataset (Excel) and output:
- Top 10 recurring decision tasks
- Top 10 recurring technical contexts
- Vocabulary used by operators vs service companies

Excludes Russian JDs by default (any Cyrillic in jd_text).

No third-party dependencies: parses .xlsx via OOXML XML (zip + sharedStrings).

Usage:
  python3 tools/jd_operator_service_analysis_to_md.py \
    --input "/path/Strategy_Table_v2_fixed.xlsx" \
    --output "/path/jd_operator_vs_service_analysis.md"
"""

from __future__ import annotations

import argparse
import math
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


NS_MAIN = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def has_cyrillic(text: str) -> bool:
    return bool(CYRILLIC_RE.search(text or ""))


def _t(el: Optional[ET.Element]) -> str:
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


def norm_space(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())


def norm_url(u: Any) -> str:
    s = str(u or "").strip().strip('"')
    if not s:
        return ""
    s = re.sub(r"://linkedin\.com/", "://www.linkedin.com/", s)
    return s.split("?", 1)[0].split("#", 1)[0]


@dataclass(frozen=True)
class JdRow:
    sheet: str
    row: int
    company: str
    role: str
    source: str
    jd_text: str


def iter_jd_rows(xlsx_path: Path, *, exclude_russian: bool = True) -> Iterable[JdRow]:
    with zipfile.ZipFile(xlsx_path, "r") as z:
        shared: List[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS_MAIN):
                ts = si.findall(".//m:t", NS_MAIN)
                shared.append("".join(_t(t) for t in ts))

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
                return _t(cel.find("m:is/m:t", NS_MAIN))
            v = cel.find("m:v", NS_MAIN)
            if t == "s":
                try:
                    return shared[int(_t(v))]
                except Exception:
                    return ""
            return _t(v)

        def row_cells(row_el: ET.Element) -> Dict[int, str]:
            out: Dict[int, str] = {}
            for c in row_el.findall("m:c", NS_MAIN):
                rc = _cell_to_rc(c.attrib.get("r", ""))
                if not rc:
                    continue
                _, cidx = rc
                out[cidx] = cell_value(c)
            return out

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

            # header row: must contain Source + (jd_text or jd)
            header_row: Optional[int] = None
            header_map: Dict[str, int] = {}
            jd_key: Optional[str] = None

            for row in sheet_data.findall("m:row", NS_MAIN):
                rnum = int(row.attrib.get("r", "0"))
                if rnum > 120:
                    break
                cells = row_cells(row)
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

            source_col = header_map.get("source")
            jd_col = header_map.get(jd_key)
            company_col = header_map.get("company")
            role_col = header_map.get("role")
            if not source_col or not jd_col:
                continue

            for row in sheet_data.findall("m:row", NS_MAIN):
                rnum = int(row.attrib.get("r", "0"))
                if rnum <= header_row:
                    continue
                cells = row_cells(row)
                jd = norm_space(cells.get(jd_col, ""))
                if not jd:
                    continue
                if exclude_russian and has_cyrillic(jd):
                    continue

                yield JdRow(
                    sheet=sname,
                    row=rnum,
                    company=norm_space(cells.get(company_col, "")) if company_col else "",
                    role=norm_space(cells.get(role_col, "")) if role_col else "",
                    source=norm_url(cells.get(source_col, "")),
                    jd_text=jd,
                )


# ---------------------------
# Categorization: decisions + technical contexts
# ---------------------------

DECISION_TASKS: List[Tuple[str, re.Pattern[str]]] = [
    ("Field development planning / FDP", re.compile(r"\b(fdp|field development plan|development planning|development plan)\b", re.I)),
    ("Reserves booking / PRMS", re.compile(r"\b(reserves? booking|prms|reserves? certification|reserves? evaluation)\b", re.I)),
    ("Economic evaluation (NPV/EMV/CAPEX/OPEX)", re.compile(r"\b(npv|emv|economic evaluation|economics|capex|opex|budget)\b", re.I)),
    ("Well planning / placement decisions", re.compile(r"\b(well planning|well placement|well proposal|inflow review|well review)\b", re.I)),
    ("Drilling / workover / intervention decisions", re.compile(r"\b(drilling|workover|intervention|completion|recompletion)\b", re.I)),
    ("Depletion / development strategy", re.compile(r"\b(depletion|development strategy|depletion strategy)\b", re.I)),
    ("IOR/EOR screening / pilots", re.compile(r"\b(ior|eor|screening|pilot)\b", re.I)),
    ("Production optimization actions", re.compile(r"\b(optimization|optimize|integrated production|production optimization)\b", re.I)),
    ("Model update / history match decisions", re.compile(r"\b(history match|history matching|model update|calibration)\b", re.I)),
    ("Surveillance thresholds / operating guidance", re.compile(r"\b(surveillance|monitoring|waterflood|injection balance|production forecasting)\b", re.I)),
    ("Software support triage (L2/L3)", re.compile(r"\b(l2|l3|technical support|issue resolution|customer issue)\b", re.I)),
]

TECH_CONTEXTS: List[Tuple[str, re.Pattern[str]]] = [
    ("Dynamic simulation (ECLIPSE/tNavigator/CMG)", re.compile(r"\b(simulation|simulator|eclipse|tnavigator|cmg|nexus)\b", re.I)),
    ("Static/dynamic integration (Petrel / geomodel)", re.compile(r"\b(petrel|geomodel|geological model|static[- ]dynamic)\b", re.I)),
    ("History matching / calibration", re.compile(r"\b(history match|history matching|calibration)\b", re.I)),
    ("Production forecasting", re.compile(r"\b(forecast|forecasting|production forecast)\b", re.I)),
    ("Waterflood / injection management", re.compile(r"\b(waterflood|injection|injector|voidage|injection balance)\b", re.I)),
    ("Well performance / inflow / PTA-RCA", re.compile(r"\b(well performance|inflow|pta\b|pressure transient|rca\b)\b", re.I)),
    ("Reservoir management / surveillance", re.compile(r"\b(reservoir management|surveillance|monitoring)\b", re.I)),
    ("Reserves & PRMS", re.compile(r"\b(reserves?|prms)\b", re.I)),
    ("Economics / valuation", re.compile(r"\b(npv|emv|economics|economic)\b", re.I)),
    ("Software/customer support context", re.compile(r"\b(technical support|customer|issue|training)\b", re.I)),
]


def match_categories(text: str, cats: List[Tuple[str, re.Pattern[str]]]) -> List[str]:
    return [name for name, pat in cats if pat.search(text)]


# ---------------------------
# Operator vs service classification + vocabulary
# ---------------------------

SERVICE_COMPANY_HINTS = [
    "schlumberger",
    "slb",
    "halliburton",
    "baker hughes",
    "weatherford",
    "wood",
    "airswift",
    "leap29",
    "kintec",
    "sofomation",
    "visuna",
    "aspen",
    "capgemini",
    "reach subsea",
    "get global",
    "petroplan",
]

OPERATOR_HINTS = [
    "bp",
    "aramco",
    "jadestone",
    "reliance",
    "totalenergies",
    "exxonmobil",
    "energean",
    "qatarenergy",
    "adnoc",
    "kufpec",
    "anton",
]


def company_type(company: str, role: str) -> str:
    c = (company or "").lower()
    r = (role or "").lower()

    if any(h in c for h in SERVICE_COMPANY_HINTS):
        return "service"
    if any(h in c for h in OPERATOR_HINTS):
        return "operator"

    # Role-based hints
    if "technical support" in r or "pmc" in r or "consult" in r or "contract" in r:
        return "service"

    # Default: operator (better than \"unknown\" for this dataset)
    return "operator"


EN_STOP = set(
    """
a an the and or to of in for on with by from as is are be this that will can may plus
we you your our us
role roles responsibilities requirements preferred strong
""".split()
)


def tokens(text: str) -> List[str]:
    text = text.lower()
    parts = re.findall(r"[a-z0-9][a-z0-9+\-_/]*", text)
    out = []
    for p in parts:
        if len(p) <= 2:
            continue
        if p in EN_STOP:
            continue
        # de-noise obvious location/company-ish bits seen in this dataset
        if p in {"dhahran", "doha", "baku", "kuwait", "qatar", "saudi", "norway", "malaysia", "india"}:
            continue
        out.append(p)
    return out


def log_odds_ratio(term: str, a: Counter, b: Counter, alpha: float = 0.5) -> float:
    """
    Log-odds with additive smoothing.
    Higher => more associated with group A.
    """
    a_total = sum(a.values())
    b_total = sum(b.values())
    a_t = a.get(term, 0)
    b_t = b.get(term, 0)
    return math.log((a_t + alpha) / (a_total + alpha)) - math.log((b_t + alpha) / (b_total + alpha))


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").strip()


def render_md(
    rows: List[Dict[str, Any]],
    decision_top10: List[Tuple[str, int]],
    context_top10: List[Tuple[str, int]],
    vocab_operator: List[Tuple[str, float, int]],
    vocab_service: List[Tuple[str, float, int]],
    counts: Dict[str, int],
) -> str:
    lines: List[str] = []
    lines.append("## JD dataset analysis (exclude Russian)\n")
    lines.append(f"- **Rows analyzed**: {len(rows)}")
    lines.append(f"- **Operators**: {counts.get('operator', 0)}")
    lines.append(f"- **Service companies**: {counts.get('service', 0)}\n")

    lines.append("## Top 10 recurring decision tasks\n")
    lines.append("| Decision task | #JDs |")
    lines.append("|---|---:|")
    for name, c in decision_top10:
        lines.append(f"| {md_escape(name)} | {c} |")
    lines.append("")

    lines.append("## Top 10 recurring technical contexts\n")
    lines.append("| Technical context | #JDs |")
    lines.append("|---|---:|")
    for name, c in context_top10:
        lines.append(f"| {md_escape(name)} | {c} |")
    lines.append("")

    lines.append("## Vocabulary by company type (overrepresented terms)\n")
    lines.append("### Operator-leaning vocabulary\n")
    lines.append("| Term | Association (log-odds) | Operator count |")
    lines.append("|---|---:|---:|")
    for term, score, cnt in vocab_operator:
        lines.append(f"| {md_escape(term)} | {score:.2f} | {cnt} |")
    lines.append("")

    lines.append("### Service-leaning vocabulary\n")
    lines.append("| Term | Association (log-odds) | Service count |")
    lines.append("|---|---:|---:|")
    for term, score, cnt in vocab_service:
        lines.append(f"| {md_escape(term)} | {score:.2f} | {cnt} |")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to Excel .xlsx with JD text")
    ap.add_argument("--output", required=True, help="Path to output markdown file")
    args = ap.parse_args()

    xlsx_path = Path(args.input).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()

    jd_rows = list(iter_jd_rows(xlsx_path, exclude_russian=True))

    # Count categories per JD (presence/absence)
    decision_counts = Counter()
    context_counts = Counter()

    # Vocabulary by group
    op_tf = Counter()
    sv_tf = Counter()
    counts = Counter()

    rows_out: List[Dict[str, Any]] = []

    for r in jd_rows:
        ctype = company_type(r.company, r.role)
        counts[ctype] += 1

        decisions = set(match_categories(r.jd_text, DECISION_TASKS))
        contexts = set(match_categories(r.jd_text, TECH_CONTEXTS))
        decision_counts.update(decisions)
        context_counts.update(contexts)

        toks = tokens(r.jd_text)
        if ctype == "operator":
            op_tf.update(toks)
        else:
            sv_tf.update(toks)

        rows_out.append(
            {
                "company": r.company,
                "role": r.role,
                "type": ctype,
                "sheet": r.sheet,
                "row": r.row,
                "source": r.source,
            }
        )

    decision_top10 = decision_counts.most_common(10)
    context_top10 = context_counts.most_common(10)

    # Compute log-odds for terms across groups and take top 20 each side.
    vocab = set(op_tf.keys()) | set(sv_tf.keys())
    op_terms = []
    sv_terms = []
    for t in vocab:
        # Require minimal evidence to avoid noise
        if op_tf.get(t, 0) + sv_tf.get(t, 0) < 4:
            continue
        lo = log_odds_ratio(t, op_tf, sv_tf, alpha=0.5)
        if lo > 0:
            op_terms.append((t, lo, op_tf.get(t, 0)))
        elif lo < 0:
            sv_terms.append((t, lo, sv_tf.get(t, 0)))

    op_terms.sort(key=lambda x: x[1], reverse=True)
    sv_terms.sort(key=lambda x: x[1])  # most negative first

    vocab_operator = op_terms[:20]
    vocab_service = [(t, abs(lo), cnt) for t, lo, cnt in sv_terms[:20]]

    md = render_md(
        rows=rows_out,
        decision_top10=decision_top10,
        context_top10=context_top10,
        vocab_operator=vocab_operator,
        vocab_service=vocab_service,
        counts=dict(counts),
    )

    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote: {out_path}")
    print(f"Rows analyzed: {len(rows_out)} (operators={counts['operator']}, service={counts['service']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

