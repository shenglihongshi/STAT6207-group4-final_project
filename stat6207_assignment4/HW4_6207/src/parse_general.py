"""General input parser: one JD or one CV per file.

Input:
  data/input/jds/   -- any .pdf/.txt/.md/.docx, one JD per file
  data/input/cvs/   -- any .pdf/.txt/.md/.docx, one CV per file

Output:
  data/general/processed/documents.jsonl
  data/general/processed/jds.jsonl
  data/general/processed/cvs.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "input"
DEFAULT_OUT = ROOT / "data" / "general" / "processed"
SUPPORTED = {".pdf", ".txt", ".md", ".docx"}


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", name, flags=re.UNICODE).strip("_")
    return s or "document"


def read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        doc = pymupdf.open(path)
        return "\n".join(page.get_text() for page in doc)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        import docx

        d = docx.Document(path)
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    raise ValueError(f"unsupported file type: {path.suffix}")


def collect(folder: Path, doc_type: str, prefix: str) -> tuple[list[dict], set[str]]:
    rows: list[dict] = []
    used: set[str] = set()
    if not folder.exists():
        return rows, used
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        text = "\n".join(
            line.rstrip() for line in read_file(path).splitlines()
        )
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not text:
            continue
        base = slugify(path.stem)
        doc_id = f"{prefix}_{base}"
        n = 2
        while doc_id in used:
            doc_id = f"{prefix}_{base}_{n}"
            n += 1
        used.add(doc_id)
        rows.append(
            {
                "doc_id": doc_id,
                "doc_type": doc_type,
                "source_file": path.name,
                "role_title": path.stem if doc_type == "jd" else "",
                "title": path.stem,
                "text": text,
            }
        )
    return rows, used


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    input_root = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    jds, jd_ids = collect(input_root / "jds", "jd", "JD")
    cvs, cv_ids = collect(input_root / "cvs", "cv", "CV")
    # avoid collision between JD_/CV_ namespaces (prefix already separates them)
    documents = jds + cvs

    def write(name: str, rows: list[dict]) -> None:
        with (out_dir / name).open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    write("jds.jsonl", jds)
    write("cvs.jsonl", cvs)
    write("documents.jsonl", documents)

    print(f"JDs: {len(jds)}")
    print(f"CVs: {len(cvs)}")
    print(f"documents: {len(documents)}")
    print(f"output: {out_dir / 'documents.jsonl'}")
    if not documents:
        print("WARNING: no input documents found. Put files under data/input/jds and data/input/cvs.")


if __name__ == "__main__":
    main()
