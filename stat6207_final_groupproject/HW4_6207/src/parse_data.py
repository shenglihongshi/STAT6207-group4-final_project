"""Parse the 10 JD+hired-CV PDFs and the 100 anonymised CV PDFs.

Outputs (all under HW4_6207/data/processed):
  jd_10.jsonl       -- 10 natural-language JDs
  hired_cv_10.jsonl -- 10 hired CVs (positives)
  cv_100.jsonl      -- 100 anonymised CVs
  documents.jsonl   -- all 120 documents in one file
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)


def read_pdf(path: Path) -> str:
    doc = fitz.open(path)
    pages = [p.get_text() for p in doc]
    return "\n".join(pages)


def clean_lines(text: str) -> str:
    """Remove dataset headers/footers and page markers, keep content."""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not s:
            out.append("")
            continue
        if s.startswith("Anonymised example"):
            continue
        if s.startswith("Anonymised candidate profile"):
            continue
        if re.fullmatch(r"P\d{2} · page \d+", s):
            continue
        if re.fullmatch(r"CV-\d{3} · page \d+", s):
            continue
        if re.fullmatch(r"CV-\d{3}", s):
            continue
        if re.fullmatch(r"P\d{2} · JOB DESCRIPTION · .+", s):
            continue
        if re.fullmatch(r"P\d{2} · CV OF THE HIRED CANDIDATE", s):
            continue
        if s.startswith("Hired for:"):
            continue
        out.append(line)

    # collapse 3+ blank lines to 1, trim
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_pairs() -> tuple[list[dict], list[dict]]:
    jds: list[dict] = []
    cvs: list[dict] = []
    for pdf in sorted((RAW / "jd_cv_pairs").glob("*.pdf")):
        pair_id = pdf.name.split(" - ")[0].strip()
        role = pdf.name.split(" - ", 1)[1].rsplit(".pdf", 1)[0].strip()
        text = read_pdf(pdf)
        marker = "CV OF THE HIRED CANDIDATE"
        if marker not in text:
            raise ValueError(f"Marker not found in {pdf.name}")
        jd_raw, cv_raw = text.split(marker, 1)
        jd_text = clean_lines(jd_raw)
        cv_text = clean_lines(cv_raw)

        jds.append(
            {
                "doc_id": f"JD_{pair_id}",
                "doc_type": "jd",
                "pair_id": pair_id,
                "role_title": role,
                "source_file": pdf.name,
                "text": jd_text,
            }
        )
        cvs.append(
            {
                "doc_id": f"HIRED_{pair_id}",
                "doc_type": "cv",
                "pair_id": pair_id,
                "role_title": role,
                "source_file": pdf.name,
                "text": cv_text,
                "is_hired": True,
            }
        )
    return jds, cvs


def parse_cvs() -> list[dict]:
    rows: list[dict] = []
    for pdf in sorted((RAW / "cvs_100").glob("*.pdf")):
        cv_id = pdf.stem
        text = clean_lines(read_pdf(pdf))
        rows.append(
            {
                "doc_id": cv_id,
                "doc_type": "cv",
                "pair_id": None,
                "source_file": pdf.name,
                "text": text,
                "is_hired": False,
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    jds, hired = parse_pairs()
    cvs = parse_cvs()
    write_jsonl(OUT / "jd_10.jsonl", jds)
    write_jsonl(OUT / "hired_cv_10.jsonl", hired)
    write_jsonl(OUT / "cv_100.jsonl", cvs)
    write_jsonl(OUT / "documents.jsonl", jds + hired + cvs)

    print(f"JDs: {len(jds)}")
    print(f"hired CVs: {len(hired)}")
    print(f"anonymised CVs: {len(cvs)}")
    print(f"documents: {len(jds) + len(hired) + len(cvs)}")
    print("\nJD lengths:")
    for r in jds:
        print(f"  {r['doc_id']}: {len(r['text'])} chars | {r['role_title']}")
    print("\nSample JD head:")
    print(jds[0]["text"][:500])
    print("\nSample hired CV head:")
    print(hired[0]["text"][:500])


if __name__ == "__main__":
    main()
