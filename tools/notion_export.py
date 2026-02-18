#!/usr/bin/env python3
"""
notion_export.py — Export Notion workspace to local Markdown files.

Connects to Notion API, discovers all pages and databases accessible
to the integration, and saves them as .md files preserving hierarchy.

Requirements:
    pip install requests python-dotenv

Usage:
    export NOTION_API_KEY="ntn_..."
    python3 tools/notion_export.py

    # Export a single root page only:
    python3 tools/notion_export.py --page-id <PAGE_ID>

    # Custom output directory:
    python3 tools/notion_export.py -o ./my_export
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is required. Install with: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"
REQUEST_DELAY = 0.35  # ~3 req/sec rate limit
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


# ---------------------------------------------------------------------------
# Notion API Client
# ---------------------------------------------------------------------------

class NotionClient:
    """Lightweight Notion API client with pagination and rate-limit handling."""

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        url = f"{NOTION_BASE_URL}{endpoint}"
        for attempt in range(MAX_RETRIES):
            time.sleep(REQUEST_DELAY)
            resp = getattr(self.session, method)(url, **kwargs)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", RETRY_BACKOFF * (attempt + 1)))
                print(f"  [rate-limit] waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                time.sleep(RETRY_BACKOFF * (attempt + 1))
                continue
            resp.raise_for_status()
        resp.raise_for_status()

    def get(self, endpoint: str, params: dict = None) -> dict:
        return self._request("get", endpoint, params=params)

    def post(self, endpoint: str, payload: dict = None) -> dict:
        return self._request("post", endpoint, json=payload or {})

    # -- High-level helpers --------------------------------------------------

    def get_page(self, page_id: str) -> dict:
        return self.get(f"/pages/{page_id}")

    def get_database(self, db_id: str) -> dict:
        return self.get(f"/databases/{db_id}")

    def get_block_children(self, block_id: str) -> list:
        """Fetch all children of a block, handling pagination."""
        results = []
        cursor = None
        while True:
            payload = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = self.get(f"/blocks/{block_id}/children", params=payload)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results

    def query_database(self, db_id: str) -> list:
        """Fetch all rows from a database, handling pagination."""
        results = []
        cursor = None
        while True:
            payload = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = self.post(f"/databases/{db_id}/query", payload=payload)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results

    def search(self, query: str = "", filter_type: str = None) -> list:
        """Search across the workspace."""
        results = []
        cursor = None
        while True:
            payload = {"page_size": 100}
            if query:
                payload["query"] = query
            if filter_type:
                payload["filter"] = {"value": filter_type, "property": "object"}
            if cursor:
                payload["start_cursor"] = cursor
            data = self.post("/search", payload=payload)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results


# ---------------------------------------------------------------------------
# Notion -> Markdown converter
# ---------------------------------------------------------------------------

def rich_text_to_md(rich_text_list: list) -> str:
    """Convert Notion rich_text array to Markdown string."""
    parts = []
    for rt in rich_text_list:
        text = rt.get("plain_text", "")
        annotations = rt.get("annotations", {})
        href = rt.get("href")

        if annotations.get("code"):
            text = f"`{text}`"
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("strikethrough"):
            text = f"~~{text}~~"
        if annotations.get("underline"):
            text = f"<u>{text}</u>"
        if href:
            text = f"[{text}]({href})"

        parts.append(text)
    return "".join(parts)


def get_page_title(page: dict) -> str:
    """Extract title from a page object."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return rich_text_to_md(prop.get("title", []))
    return "Untitled"


def get_database_title(db: dict) -> str:
    """Extract title from a database object."""
    title_parts = db.get("title", [])
    return rich_text_to_md(title_parts) if title_parts else "Untitled Database"


def block_to_md(block: dict, indent: int = 0) -> str:
    """Convert a single Notion block to Markdown."""
    btype = block.get("type", "")
    bdata = block.get(btype, {})
    prefix = "    " * indent

    if btype == "paragraph":
        text = rich_text_to_md(bdata.get("rich_text", []))
        return f"{prefix}{text}\n"

    if btype in ("heading_1", "heading_2", "heading_3"):
        level = int(btype[-1])
        text = rich_text_to_md(bdata.get("rich_text", []))
        hashes = "#" * level
        return f"{hashes} {text}\n"

    if btype == "bulleted_list_item":
        text = rich_text_to_md(bdata.get("rich_text", []))
        return f"{prefix}- {text}\n"

    if btype == "numbered_list_item":
        text = rich_text_to_md(bdata.get("rich_text", []))
        return f"{prefix}1. {text}\n"

    if btype == "to_do":
        text = rich_text_to_md(bdata.get("rich_text", []))
        checked = "x" if bdata.get("checked") else " "
        return f"{prefix}- [{checked}] {text}\n"

    if btype == "toggle":
        text = rich_text_to_md(bdata.get("rich_text", []))
        return f"{prefix}<details><summary>{text}</summary>\n\n"

    if btype == "quote":
        text = rich_text_to_md(bdata.get("rich_text", []))
        lines = text.split("\n")
        quoted = "\n".join(f"{prefix}> {line}" for line in lines)
        return f"{quoted}\n"

    if btype == "callout":
        icon = ""
        icon_data = bdata.get("icon", {})
        if icon_data.get("type") == "emoji":
            icon = icon_data.get("emoji", "") + " "
        text = rich_text_to_md(bdata.get("rich_text", []))
        return f"{prefix}> {icon}{text}\n"

    if btype == "code":
        text = rich_text_to_md(bdata.get("rich_text", []))
        lang = bdata.get("language", "")
        return f"{prefix}```{lang}\n{text}\n{prefix}```\n"

    if btype == "divider":
        return f"{prefix}---\n"

    if btype == "image":
        img = bdata.get(bdata.get("type", ""), {})
        url = img.get("url", "")
        caption = rich_text_to_md(bdata.get("caption", []))
        alt = caption if caption else "image"
        return f"{prefix}![{alt}]({url})\n"

    if btype == "bookmark":
        url = bdata.get("url", "")
        caption = rich_text_to_md(bdata.get("caption", []))
        label = caption if caption else url
        return f"{prefix}[{label}]({url})\n"

    if btype == "embed":
        url = bdata.get("url", "")
        return f"{prefix}[Embed]({url})\n"

    if btype == "video":
        vid = bdata.get(bdata.get("type", ""), {})
        url = vid.get("url", "")
        return f"{prefix}[Video]({url})\n"

    if btype == "file":
        file_data = bdata.get(bdata.get("type", ""), {})
        url = file_data.get("url", "")
        name = bdata.get("name", "file")
        return f"{prefix}[{name}]({url})\n"

    if btype == "pdf":
        pdf_data = bdata.get(bdata.get("type", ""), {})
        url = pdf_data.get("url", "")
        return f"{prefix}[PDF]({url})\n"

    if btype == "equation":
        expr = bdata.get("expression", "")
        return f"{prefix}$$\n{expr}\n$$\n"

    if btype == "table_of_contents":
        return f"{prefix}<!-- Table of Contents -->\n"

    if btype == "breadcrumb":
        return ""

    if btype == "column_list":
        return ""

    if btype == "column":
        return ""

    if btype == "link_preview":
        url = bdata.get("url", "")
        return f"{prefix}[Link]({url})\n"

    if btype == "synced_block":
        return ""

    if btype == "template":
        text = rich_text_to_md(bdata.get("rich_text", []))
        return f"{prefix}**Template:** {text}\n"

    if btype == "link_to_page":
        target_type = bdata.get("type", "")
        target_id = bdata.get(target_type, "")
        return f"{prefix}-> [{target_type}: {target_id}]\n"

    if btype == "table":
        return ""

    if btype == "table_row":
        cells = bdata.get("cells", [])
        row = " | ".join(rich_text_to_md(cell) for cell in cells)
        return f"{prefix}| {row} |\n"

    if btype in ("child_page", "child_database"):
        return ""

    return f"{prefix}<!-- unsupported block: {btype} -->\n"


def database_to_md(client, db_id: str, db: dict) -> str:
    """Export a Notion database as a Markdown table."""
    title = get_database_title(db)
    lines = [f"# {title}\n"]

    props_schema = db.get("properties", {})
    prop_names = sorted(props_schema.keys())

    rows = client.query_database(db_id)
    if not rows:
        lines.append("*Empty database.*\n")
        return "\n".join(lines)

    lines.append("| " + " | ".join(prop_names) + " |")
    lines.append("| " + " | ".join("---" for _ in prop_names) + " |")

    for row in rows:
        row_props = row.get("properties", {})
        cells = []
        for name in prop_names:
            cells.append(property_value_to_str(row_props.get(name, {})))
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    return "\n".join(lines)


def property_value_to_str(prop: dict) -> str:
    """Convert a Notion property value to a plain string for table cells."""
    ptype = prop.get("type", "")

    if ptype == "title":
        return rich_text_to_md(prop.get("title", []))
    if ptype == "rich_text":
        return rich_text_to_md(prop.get("rich_text", []))
    if ptype == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "multi_select":
        items = prop.get("multi_select", [])
        return ", ".join(i.get("name", "") for i in items)
    if ptype == "status":
        st = prop.get("status")
        return st.get("name", "") if st else ""
    if ptype == "date":
        d = prop.get("date")
        if not d:
            return ""
        start = d.get("start", "")
        end = d.get("end", "")
        return f"{start} -> {end}" if end else start
    if ptype == "checkbox":
        return "yes" if prop.get("checkbox") else "no"
    if ptype == "url":
        return prop.get("url", "") or ""
    if ptype == "email":
        return prop.get("email", "") or ""
    if ptype == "phone_number":
        return prop.get("phone_number", "") or ""
    if ptype == "formula":
        f = prop.get("formula", {})
        ftype = f.get("type", "")
        return str(f.get(ftype, ""))
    if ptype == "relation":
        rels = prop.get("relation", [])
        return ", ".join(r.get("id", "") for r in rels)
    if ptype == "rollup":
        r = prop.get("rollup", {})
        rtype = r.get("type", "")
        if rtype == "array":
            items = r.get("array", [])
            return ", ".join(property_value_to_str(i) for i in items)
        return str(r.get(rtype, ""))
    if ptype == "people":
        people = prop.get("people", [])
        return ", ".join(p.get("name", p.get("id", "")) for p in people)
    if ptype == "files":
        files = prop.get("files", [])
        urls = []
        for f in files:
            ft = f.get("type", "")
            urls.append(f.get(ft, {}).get("url", f.get("name", "")))
        return ", ".join(urls)
    if ptype == "created_time":
        return prop.get("created_time", "")
    if ptype == "last_edited_time":
        return prop.get("last_edited_time", "")
    if ptype == "created_by":
        return prop.get("created_by", {}).get("name", "")
    if ptype == "last_edited_by":
        return prop.get("last_edited_by", {}).get("name", "")
    if ptype == "unique_id":
        uid = prop.get("unique_id", {})
        prefix = uid.get("prefix", "")
        number = uid.get("number", "")
        return f"{prefix}-{number}" if prefix else str(number)

    return ""


# ---------------------------------------------------------------------------
# Recursive traversal and export
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """Create a filesystem-safe filename from a Notion title."""
    name = name.strip()
    if not name:
        name = "Untitled"
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', ' ', name)
    return name[:120]


def export_blocks_to_md(client, block_id: str, indent: int = 0) -> str:
    """Recursively export all blocks under a given block as Markdown."""
    blocks = client.get_block_children(block_id)
    md_parts = []

    for block in blocks:
        btype = block.get("type", "")
        bid = block.get("id", "")

        if btype == "table":
            table_data = block.get("table", {})
            table_width = table_data.get("table_width", 0)
            has_header = table_data.get("has_column_header", False)
            table_rows = client.get_block_children(bid)
            for i, row_block in enumerate(table_rows):
                md_parts.append(block_to_md(row_block, indent))
                if i == 0 and has_header:
                    md_parts.append("| " + " | ".join("---" for _ in range(table_width)) + " |\n")
            md_parts.append("\n")
            continue

        md_parts.append(block_to_md(block, indent))

        if block.get("has_children") and btype not in ("child_page", "child_database", "table"):
            child_indent = indent + (1 if btype in ("bulleted_list_item", "numbered_list_item", "to_do", "toggle") else 0)
            child_md = export_blocks_to_md(client, bid, child_indent)
            md_parts.append(child_md)

            if btype == "toggle":
                md_parts.append("</details>\n\n")

    return "".join(md_parts)


def export_page(client, page_id: str, output_dir, depth: int = 0):
    """Export a single Notion page and its children recursively."""
    indent_str = "  " * depth
    page = client.get_page(page_id)
    title = get_page_title(page)
    safe_title = sanitize_filename(title)

    print(f"{indent_str}[page] {title}")

    lines = [f"# {title}\n"]

    created = page.get("created_time", "")
    edited = page.get("last_edited_time", "")
    if created or edited:
        lines.append(f"<!-- created: {created} | edited: {edited} -->\n")

    lines.append("")

    body = export_blocks_to_md(client, page_id)
    lines.append(body)

    page_dir = Path(output_dir) / safe_title
    page_dir.mkdir(parents=True, exist_ok=True)
    md_path = page_dir / f"{safe_title}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"{indent_str}   -> {md_path}")

    blocks = client.get_block_children(page_id)
    for block in blocks:
        btype = block.get("type", "")
        bid = block.get("id", "")

        if btype == "child_page":
            export_page(client, bid, page_dir, depth + 1)
        elif btype == "child_database":
            export_database(client, bid, page_dir, depth + 1)


def export_database(client, db_id: str, output_dir, depth: int = 0):
    """Export a Notion database and all its page entries."""
    indent_str = "  " * depth
    db = client.get_database(db_id)
    title = get_database_title(db)
    safe_title = sanitize_filename(title)

    print(f"{indent_str}[database] {title}")

    db_dir = Path(output_dir) / safe_title
    db_dir.mkdir(parents=True, exist_ok=True)

    overview_md = database_to_md(client, db_id, db)
    overview_path = db_dir / f"_index_{safe_title}.md"
    overview_path.write_text(overview_md, encoding="utf-8")
    print(f"{indent_str}   -> {overview_path}")

    rows = client.query_database(db_id)
    for row in rows:
        row_id = row.get("id", "")
        row_title = get_page_title(row) or row_id[:8]
        safe_row = sanitize_filename(row_title)

        print(f"{indent_str}  [row] {row_title}")

        row_lines = [f"# {row_title}\n"]

        row_props = row.get("properties", {})
        row_lines.append("| Property | Value |")
        row_lines.append("| --- | --- |")
        for pname, pval in sorted(row_props.items()):
            val_str = property_value_to_str(pval)
            if val_str:
                val_str = val_str.replace("|", "\\|")
                row_lines.append(f"| {pname} | {val_str} |")
        row_lines.append("")

        body = export_blocks_to_md(client, row_id)
        if body.strip():
            row_lines.append("---\n")
            row_lines.append(body)

        row_path = db_dir / f"{safe_row}.md"
        counter = 1
        while row_path.exists():
            counter += 1
            row_path = db_dir / f"{safe_row}_{counter}.md"

        row_path.write_text("\n".join(row_lines), encoding="utf-8")
        print(f"{indent_str}     -> {row_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def discover_root_objects(client) -> tuple:
    """
    Discover all pages and databases accessible to the integration.
    Returns (root_pages, root_databases, child_pages_with_parent).
    Root = parent is workspace. Others are children of root pages.
    """
    all_items = client.search()
    root_pages = []
    root_databases = []

    seen_ids = set()
    for item in all_items:
        item_id = item.get("id", "")
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)

        parent = item.get("parent", {})
        parent_type = parent.get("type", "")
        obj_type = item.get("object", "")

        if parent_type == "workspace":
            if obj_type == "page":
                root_pages.append(item)
            elif obj_type == "database":
                root_databases.append(item)

    return root_pages, root_databases


def main():
    parser = argparse.ArgumentParser(
        description="Export all Notion pages and databases accessible to the integration."
    )
    default_output = os.path.expanduser(
        "~/Documents/Cursor AI/ARCHIVE_KS/NOTION"
    )
    parser.add_argument(
        "--output", "-o",
        default=default_output,
        help=f"Output directory (default: {default_output})"
    )
    parser.add_argument(
        "--page-id",
        default=None,
        help="Export only a single root page by ID"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="Remove existing files in output dir before export"
    )
    args = parser.parse_args()

    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        print("ERROR: NOTION_API_KEY not set.")
        print("  Export it or add to .env file:")
        print('  export NOTION_API_KEY="ntn_..."')
        sys.exit(1)

    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  Notion -> Markdown Export")
    print(f"  Output: {output_dir}")
    print(f"  Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    client = NotionClient(api_key)

    # Single page mode
    single_id = args.page_id or os.environ.get("NOTION_ROOT_PAGE_ID")
    if single_id:
        page = client.get_page(single_id)
        title = get_page_title(page)
        print(f"Single page mode: {title} ({single_id})")
        print("-" * 60)
        export_page(client, single_id, output_dir)
        print("-" * 60)
        print(f"\nExport complete -> {output_dir}")
        _write_meta(output_dir, [single_id], [title])
        return

    # Full workspace mode — discover all root objects
    print("Discovering accessible pages and databases...")
    root_pages, root_databases = discover_root_objects(client)

    print(f"  Found {len(root_pages)} root pages, {len(root_databases)} root databases")
    print()

    if not root_pages and not root_databases:
        print("Nothing to export. Make sure the integration is connected to pages in Notion.")
        sys.exit(0)

    exported_ids = []
    exported_titles = []

    print("Starting export...")
    print("-" * 60)

    for db in root_databases:
        db_id = db.get("id", "")
        try:
            export_database(client, db_id, output_dir, depth=0)
            exported_ids.append(db_id)
            exported_titles.append(get_database_title(db))
        except Exception as e:
            print(f"  [ERROR] database {db_id}: {e}")

    for page in root_pages:
        page_id = page.get("id", "")
        try:
            export_page(client, page_id, output_dir, depth=0)
            exported_ids.append(page_id)
            exported_titles.append(get_page_title(page))
        except Exception as e:
            print(f"  [ERROR] page {page_id}: {e}")

    print("-" * 60)
    print(f"\nExport complete -> {output_dir}")
    print(f"  Exported {len(exported_ids)} root objects")

    _write_meta(output_dir, exported_ids, exported_titles)


def _write_meta(output_dir, ids: list, titles: list):
    """Write export metadata JSON."""
    meta_path = Path(output_dir) / "_export_meta.json"
    meta = {
        "exported_at": datetime.now().isoformat(),
        "notion_api_version": NOTION_API_VERSION,
        "exported_roots": [
            {"id": eid, "title": etitle}
            for eid, etitle in zip(ids, titles)
        ],
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Metadata -> {meta_path}")


if __name__ == "__main__":
    main()
