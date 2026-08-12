from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path

from pypdf import PdfReader


PDF_NAME = "实战公考-酷酷刷-资料分析11302850(OCR).pdf"
OUT_DIR = Path("output/pdf")
MAX_CHARS = 1200
OVERLAP = 120


def normalize(text: str) -> str:
    """Light normalization only; retain the OCR text as a separate raw field."""
    text = unicodedata.normalize("NFKC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def page_type(page_no: int, text: str) -> str:
    if not text.strip():
        return "blank_or_image_only"
    if page_no == 1:
        return "cover"
    if "目录" in text:
        return "table_of_contents"
    if "参考答案" in text and page_no > 160:
        return "answer_key"
    if "练习" in text:
        return "exercise"
    return "content"


def section_hint(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if re.search(r"练习\s*[0-9一二三四五六七八九十]", line):
            return line[:120]
    return None


def split_chunks(text: str) -> list[tuple[int, int, str]]:
    if not text:
        return []
    chunks: list[tuple[int, int, str]] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + MAX_CHARS)
        if end < n:
            # Prefer a paragraph/line boundary so retrieval snippets stay readable.
            boundary = max(text.rfind("\n", start, end), text.rfind("。", start, end))
            if boundary > start + MAX_CHARS // 2:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            actual_start = text.find(chunk, start, end)
            actual_start = start if actual_start < 0 else actual_start
            chunks.append((actual_start, end, chunk))
        if end >= n:
            break
        start = max(end - OVERLAP, start + 1)
    return chunks


def main() -> None:
    pdf_path = Path(PDF_NAME)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    pages = []
    chunks = []
    for page_no, page in enumerate(reader.pages, 1):
        raw = page.extract_text() or ""
        text = normalize(raw)
        page_entry = {
            "page": page_no,
            "type": page_type(page_no, text),
            "section_hint": section_hint(text),
            "raw_text": raw,
            "char_count": len(text),
            "text": text,
        }
        pages.append(page_entry)
        for chunk_no, (start, end, chunk_text) in enumerate(split_chunks(text), 1):
            chunks.append(
                {
                    "id": f"p{page_no:03d}-c{chunk_no:02d}",
                    "page": page_no,
                    "chunk": chunk_no,
                    "start": start,
                    "end": end,
                    "text": chunk_text,
                }
            )

    manifest = {
        "source_file": pdf_path.name,
        "page_count": len(pages),
        "nonempty_pages": sum(1 for p in pages if p["char_count"] > 0),
        "empty_pages": [p["page"] for p in pages if p["char_count"] == 0],
        "total_char_count": sum(p["char_count"] for p in pages),
        "chunk_count": len(chunks),
        "ocr_note": "Text is embedded OCR from the supplied PDF. raw_text preserves the extractor output; text applies only conservative Unicode/whitespace normalization.",
        "embedding": {"included": False, "reason": "No embedding model was requested or available locally."},
    }
    bundle = {"manifest": manifest, "pages": pages}
    (OUT_DIR / "实战公考-酷酷刷-资料分析11302850_ocr.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (OUT_DIR / "实战公考-酷酷刷-资料分析11302850_chunks.jsonl").open("w", encoding="utf-8") as f:
        for item in chunks:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    (OUT_DIR / "实战公考-酷酷刷-资料分析11302850_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # A small, dependency-free local search database. FTS5 is available in the bundled SQLite.
    db_path = OUT_DIR / "实战公考-酷酷刷-资料分析11302850.sqlite"
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    con.execute("CREATE TABLE pages (page INTEGER PRIMARY KEY, type TEXT, section_hint TEXT, char_count INTEGER, text TEXT NOT NULL)")
    con.execute("CREATE TABLE chunks (id TEXT PRIMARY KEY, page INTEGER NOT NULL, chunk INTEGER NOT NULL, start INTEGER, end INTEGER, text TEXT NOT NULL)")
    con.execute("CREATE VIRTUAL TABLE pages_fts USING fts5(text, content='pages', content_rowid='page')")
    con.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(text, content='chunks', content_rowid='rowid')")
    con.executemany("INSERT INTO metadata VALUES (?, ?)", [(k, json.dumps(v, ensure_ascii=False)) for k, v in manifest.items()])
    con.executemany("INSERT INTO pages VALUES (?, ?, ?, ?, ?)", [(p["page"], p["type"], p["section_hint"], p["char_count"], p["text"]) for p in pages])
    con.executemany("INSERT INTO chunks(id,page,chunk,start,end,text) VALUES (?,?,?,?,?,?)", [(c["id"], c["page"], c["chunk"], c["start"], c["end"], c["text"]) for c in chunks])
    con.execute("INSERT INTO pages_fts(rowid,text) SELECT page,text FROM pages")
    con.execute("INSERT INTO chunks_fts(rowid,text) SELECT rowid,text FROM chunks")
    con.commit()
    con.close()
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
