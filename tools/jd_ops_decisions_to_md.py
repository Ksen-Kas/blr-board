#!/usr/bin/env python3
"""
Extract operational verbs + decision contexts from JD text (Excel) → Notion Markdown.

Focus (per JD):
- operational verbs (what the person DOES)
- decisions they must make
- daily data they work with
- risks they mitigate
- expected results / deliverables

Ignores HR language via sentence filtering heuristics.

No third-party deps: parses .xlsx via OOXML XML (zip + sharedStrings).

Usage:
  python3 tools/jd_ops_decisions_to_md.py \
    --input "/path/Strategy_Table_v2_fixed.xlsx" \
    --output "/path/jd_operational_decisions_for_notion.md"
"""

from __future__ import annotations

import argparse
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


NS_MAIN = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


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


CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def has_cyrillic(text: str) -> bool:
    return bool(CYRILLIC_RE.search(text or ""))


@dataclass(frozen=True)
class Sheet:
    name: str
    sheet_path: str


def iter_jd_rows(xlsx_path: Path, *, exclude_russian: bool = False) -> Iterable[Dict[str, Any]]:
    """Yield dicts with sheet,row,company,role,source,jd_text for each non-empty JD row."""
    with zipfile.ZipFile(xlsx_path, "r") as z:
        # shared strings
        shared: List[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS_MAIN):
                ts = si.findall(".//m:t", NS_MAIN)
                shared.append("".join(_t(t) for t in ts))

        # workbook sheets
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

            # find headers (source + jd or jd_text)
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
                yield {
                    "sheet": sname,
                    "row": rnum,
                    "company": norm_space(cells.get(company_col, "")) if company_col else "",
                    "role": norm_space(cells.get(role_col, "")) if role_col else "",
                    "source": norm_url(cells.get(source_col, "")),
                    "jd_text": jd,
                }


# ---------------------------
# Sentence segmentation + HR filtering
# ---------------------------

SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|[\n\r]+|;\s+")

HR_RE = re.compile(
    r"\b("
    r"apply|applicant|candidate|benefit|benefits|compensation|salary|equal opportunity|"
    r"we offer|join our|culture|diversity|inclusion|"
    r"отклик|кандидат|мы предлагаем|условия|соцпакет|заработн|"
    r"корпоративн|дмс|льгот|компенсац"
    r")\b",
    re.I,
)


def sentences(text: str) -> List[str]:
    parts = [p.strip() for p in SENT_SPLIT_RE.split(text) if p and p.strip()]
    # De-duplicate exact repeats (some JDs are concatenated)
    out: List[str] = []
    seen = set()
    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def is_hr_sentence(s: str) -> bool:
    # Also treat very short marketing fragments as HR-ish noise.
    if len(s) < 25 and re.search(r"\b(join|apply|отклик)\b", s, re.I):
        return True
    return bool(HR_RE.search(s))


# ---------------------------
# Extraction heuristics
# ---------------------------

# Canonical operational verbs → regex patterns (EN + RU)
OP_VERBS: List[Tuple[str, re.Pattern[str]]] = [
    ("analyze", re.compile(r"\b(analy[sz]e|analysis|анализ\w*)\b", re.I)),
    ("model", re.compile(r"\b(model|modeling|моделир\w*)\b", re.I)),
    ("simulate", re.compile(r"\b(simulat\w*|симулир\w*)\b", re.I)),
    ("forecast", re.compile(r"\b(forecast\w*|прогноз\w*)\b", re.I)),
    ("monitor", re.compile(r"\b(monitor\w*|surveillance|мониторинг\w*|контрол\w*)\b", re.I)),
    ("optimize", re.compile(r"\b(optimi[sz]e\w*|optimization|оптимизац\w*)\b", re.I)),
    ("plan", re.compile(r"\b(plan\w*|planning|планир\w*)\b", re.I)),
    ("evaluate", re.compile(r"\b(evaluat\w*|assess\w*|оцен\w*)\b", re.I)),
    ("review", re.compile(r"\b(review\w*|провер\w*|ревью)\b", re.I)),
    ("design", re.compile(r"\b(design\w*|проектир\w*)\b", re.I)),
    ("report", re.compile(r"\b(report\w*|отчет\w*|отчёт\w*)\b", re.I)),
    ("support", re.compile(r"\b(support\w*|сопровож\w*|поддерж\w*)\b", re.I)),
    ("coordinate", re.compile(r"\b(coordinat\w*|координ\w*)\b", re.I)),
    ("lead", re.compile(r"\b(lead\w*|manage\w*|mentor\w*|руковод\w*|управл\w*|настав\w*)\b", re.I)),
]

# Decision contexts (EN + RU)
DECISION_RE = re.compile(
    r"\b("
    r"decision|decide|recommend|recommendation|approve|select|prioritiz\w*|determin\w*|"
    r"trade-?off|screen(ing)?|"
    r"принят\w*\s+решен\w*|решен\w*\s+по|рекоменд\w*|утвержд\w*|выбор\w*|"
    r"приоритиз\w*|определ\w*|согласован\w*"
    r")\b",
    re.I,
)

# Data types (daily work)
DATA_TYPES: List[Tuple[str, re.Pattern[str]]] = [
    ("production rates / volumes", re.compile(r"\b(production|rates?|volumes?|добыч\w*|дебит\w*)\b", re.I)),
    ("pressure / PTA", re.compile(r"\b(pressure|pta\b|pressure transient|давлен\w*|гдис)\b", re.I)),
    ("well tests / surveillance", re.compile(r"\b(well test\w*|surveillance|monitoring|замер\w*|мониторинг)\b", re.I)),
    ("injection / waterflood", re.compile(r"\b(injection|waterflood|нагнетан\w*|закачк\w*)\b", re.I)),
    ("reservoir models (static/dynamic)", re.compile(r"\b(model\w*|simulation|геологическ\w*\s+модел\w*|гдм)\b", re.I)),
    ("PVT / lab data", re.compile(r"\b(pvt\w*|pvti|pvtsim|lab(oratory)?|лаборатор\w*|флюид\w*)\b", re.I)),
    ("well logs / GIS", re.compile(r"\b(logs?|well log|gis\b|гис)\b", re.I)),
    ("seismic", re.compile(r"\b(seismic|сейсмик\w*)\b", re.I)),
    ("economics / reserves", re.compile(r"\b(npv|emv|reserves?|prms|экономик\w*|запас\w*)\b", re.I)),
]

# Risk language
RISK_RE = re.compile(
    r"\b("
    r"risk|uncertainty|integrity|downtime|failure|hse|safety|assurance|"
    r"water breakthrough|coning|sand(ing)?|"
    r"риск\w*|неопределен\w*|авари\w*|простой|целостност\w*|охрана\s+труда|безопасност\w*|обводнен\w*|прорыв"
    r")\b",
    re.I,
)

# Expected results / deliverables
DELIV_RE = re.compile(
    r"\b("
    r"deliver|delivery|report\w*|recommendation\w*|plan\w*|strategy|"
    r"fdp|field development plan|reserves booking|"
    r"forecast\w*|model update\w*|optimization|study|screening|"
    r"результат\w*|отчет\w*|рекомендац\w*|план\w*|стратег\w*|"
    r"прогноз\w*|модел\w*|оптимизац\w*|исследован\w*"
    r")\b",
    re.I,
)


def extract_op_verbs(text: str) -> List[str]:
    found = []
    for canon, pat in OP_VERBS:
        if pat.search(text):
            found.append(canon)
    return found


def extract_decision_sentences(sents: List[str]) -> List[str]:
    out = []
    for s in sents:
        if DECISION_RE.search(s):
            out.append(s)
    return out


def extract_data_types(text: str) -> List[str]:
    out = []
    for canon, pat in DATA_TYPES:
        if pat.search(text):
            out.append(canon)
    return out


def extract_risk_sentences(sents: List[str]) -> List[str]:
    return [s for s in sents if RISK_RE.search(s)]


def extract_deliverable_sentences(sents: List[str]) -> List[str]:
    return [s for s in sents if DELIV_RE.search(s)]


def uniq_preserve(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        k = x.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").strip()


def render_md(rows: List[Dict[str, Any]], aggregates: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("## JD operational verbs & decision contexts (Notion-ready)\n")
    lines.append(f"- **Rows analyzed**: {aggregates['rows_analyzed']}")
    lines.append(f"- **Sheets used**: {', '.join(aggregates['sheets_used'])}\n")

    lines.append("## Aggregates\n")
    lines.append("### Top operational verbs\n")
    lines.append("| Verb | Count |")
    lines.append("|---|---:|")
    for v, c in aggregates["top_verbs"]:
        lines.append(f"| {md_escape(v)} | {c} |")
    lines.append("")

    lines.append("### Most common data types\n")
    lines.append("| Data type | Count |")
    lines.append("|---|---:|")
    for v, c in aggregates["top_data_types"]:
        lines.append(f"| {md_escape(v)} | {c} |")
    lines.append("")

    lines.append("### Risk themes (keyword hits)\n")
    lines.append("| Theme | Count |")
    lines.append("|---|---:|")
    for v, c in aggregates["top_risk_keywords"]:
        lines.append(f"| {md_escape(v)} | {c} |")
    lines.append("")

    lines.append("## Per JD (extracted)\n")
    lines.append(
        "> HR / recruiting sentences are filtered out heuristically. Everything below is best-effort extraction from the JD text.\n"
    )

    for i, r in enumerate(rows, start=1):
        title = f"{r.get('company') or '—'} — {r.get('role') or '—'}"
        lines.append(f"### {i}. {title}\n")
        if r.get("source"):
            lines.append(f"- **Source**: {r['source']}")
        lines.append(f"- **Sheet/Row**: `{r['sheet']}` / `{r['row']}`\n")

        lines.append("#### Operational verbs")
        ov = r.get("operational_verbs", [])
        lines.append(f"- {', '.join(ov) if ov else '—'}\n")

        lines.append("#### Decisions (what they decide / recommend)")
        dec = r.get("decisions", [])
        if dec:
            for s in dec[:8]:
                lines.append(f"- {s}")
        else:
            lines.append("- —")
        lines.append("")

        lines.append("#### Daily data (what they work with)")
        dt = r.get("daily_data_types", [])
        lines.append(f"- **Data types**: {', '.join(dt) if dt else '—'}")
        dctx = r.get("data_context_sentences", [])
        if dctx:
            lines.append("- **Evidence**:")
            for s in dctx[:6]:
                lines.append(f"  - {s}")
        lines.append("")

        lines.append("#### Risks mitigated")
        risks = r.get("risks", [])
        if risks:
            for s in risks[:6]:
                lines.append(f"- {s}")
        else:
            lines.append("- —")
        lines.append("")

        lines.append("#### Expected results / deliverables")
        outs = r.get("expected_results", [])
        if outs:
            for s in outs[:8]:
                lines.append(f"- {s}")
        else:
            lines.append("- —")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to Excel .xlsx containing JD rows")
    ap.add_argument("--output", required=True, help="Path to output markdown")
    ap.add_argument(
        "--exclude-russian",
        action="store_true",
        help="Exclude JDs containing Cyrillic characters (treat as Russian)",
    )
    args = ap.parse_args()

    xlsx_path = Path(args.input).expanduser().resolve()
    out_path = Path(args.output).expanduser().resolve()

    raw = list(iter_jd_rows(xlsx_path, exclude_russian=args.exclude_russian))

    rows_out: List[Dict[str, Any]] = []
    verbs_counter = Counter()
    data_counter = Counter()
    risk_kw_counter = Counter()
    sheets_used = set()

    for rr in raw:
        sheets_used.add(rr["sheet"])
        jd = rr["jd_text"]
        sents_all = sentences(jd)
        sents = [s for s in sents_all if not is_hr_sentence(s)]

        op_verbs = uniq_preserve([v for v in extract_op_verbs(jd)])
        verbs_counter.update(op_verbs)

        # Decision contexts: sentences matching DECISION_RE, but also include operational sentences that contain key decision objects
        decisions = uniq_preserve(extract_decision_sentences(sents))

        # Daily data types + supporting sentences
        data_types = uniq_preserve(extract_data_types(jd))
        data_counter.update(data_types)

        data_ctx = []
        if data_types:
            # pick sentences that include any of the data signals
            for s in sents:
                if any(p.search(s) for _canon, p in DATA_TYPES):
                    data_ctx.append(s)
        data_ctx = uniq_preserve(data_ctx)

        # Risks: sentences with risk language
        risks = uniq_preserve(extract_risk_sentences(sents))
        # Also count risk keywords (rough)
        for m in RISK_RE.finditer(jd):
            risk_kw_counter[m.group(0).lower()] += 1

        # Expected results: deliverable-like sentences
        expected = uniq_preserve(extract_deliverable_sentences(sents))

        rows_out.append(
            {
                **rr,
                "operational_verbs": op_verbs,
                "decisions": decisions,
                "daily_data_types": data_types,
                "data_context_sentences": data_ctx,
                "risks": risks,
                "expected_results": expected,
            }
        )

    aggregates = {
        "rows_analyzed": len(rows_out),
        "sheets_used": sorted(sheets_used),
        "top_verbs": verbs_counter.most_common(20),
        "top_data_types": data_counter.most_common(20),
        "top_risk_keywords": risk_kw_counter.most_common(20),
    }

    md = render_md(rows_out, aggregates)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote: {out_path}")
    print(f"Rows analyzed: {aggregates['rows_analyzed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

