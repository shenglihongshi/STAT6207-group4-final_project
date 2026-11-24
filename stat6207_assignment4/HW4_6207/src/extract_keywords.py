"""Extract keyword profiles from JDs and CVs with a local LLM via LM Studio.

Usage:
  python src/extract_keywords.py --limit 3
  python src/extract_keywords.py --all
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data" / "processed" / "documents.jsonl"
OUT_DIR = ROOT / "outputs" / "keywords"
OUT_DIR.mkdir(parents=True, exist_ok=True)

API = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "qwen2.5-coder-14b-instruct"

SYSTEM = """You are an expert technical recruiter and information-extraction engine.
Return ONE valid JSON object only. No markdown, no code fences, no commentary."""

PROMPT = """Extract a canonical keyword profile from the DOCUMENT below.

Rules:
- Return 15-40 deduplicated keywords.
- Prefer hard skills, tools, technologies, methodologies, domain knowledge, certifications, and spoken languages.
- Exclude company names, person names, university/institution names, generic verbs, and vague soft claims such as "hard-working".
- Use canonical English terms. Expand common abbreviations, e.g. "ML" -> "Machine Learning", but keep the acronym in parentheses if useful.
- importance: 3 = must-have / core, 2 = important / working, 1 = mentioned / context.
- For a JD: importance 3 = must-have requirement, 2 = nice-to-have, 1 = context.
- For a CV: importance 3 = core or advanced skill, 2 = working skill, 1 = mentioned.
- "languages" must contain ONLY human spoken languages (e.g. English, Mandarin, Bahasa Indonesia). NEVER put Python, Java, SQL, or other programming languages there.
- Programming languages belong in "keywords" with category "programming_language".
- evidence: a short phrase (<= 12 words) from the document.
- If work history is present, infer total relevant years for "years_experience"; otherwise use null.
- If a field is unknown, use null or [].
- Do not invent facts.

JSON schema:
{{
  "doc_id": "...",
  "doc_type": "jd" or "cv",
  "role_title": "...",
  "seniority": "junior" | "mid" | "senior" | "lead" | "unknown",
  "years_experience": number or null,
  "location": "...",
  "languages": ["human spoken languages only"],
  "keywords": [
    {{"term": "...", "category": "programming_language|skill|tool|framework|database|cloud|domain|methodology|certification|language|education|responsibility|other", "importance": 1|2|3, "evidence": "..."}}
  ]
}}

DOCUMENT TYPE: {doc_type}
DOCUMENT ID: {doc_id}
DOCUMENT:
{text}
"""

FAST_PROMPT = """Extract 12-25 canonical keywords from the DOCUMENT below.

Rules:
- Prefer hard skills, tools, technologies, frameworks, databases, cloud platforms, methodologies, domain knowledge, certifications, and human spoken languages.
- Exclude company names, person names, university names, generic verbs, and vague soft claims.
- Use canonical English terms; expand common abbreviations.
- importance: 3 = must-have/core, 2 = important/working, 1 = mentioned/context.
- "languages" must contain ONLY human spoken languages, never programming languages.
- Programming languages use category "programming_language".
- Do not invent facts.

Return ONE JSON object with this schema:
{{
  "doc_id": "...",
  "doc_type": "jd" or "cv",
  "role_title": "...",
  "seniority": "junior" | "mid" | "senior" | "lead" | "unknown",
  "years_experience": number or null,
  "location": "...",
  "languages": ["human spoken languages only"],
  "keywords": [
    {{"term": "...", "category": "programming_language|skill|tool|framework|database|cloud|domain|methodology|certification|language|education|responsibility|other", "importance": 1|2|3}}
  ]
}}

DOCUMENT TYPE: {doc_type}
DOCUMENT ID: {doc_id}
DOCUMENT:
{text}
"""


def post_chat(messages: list[dict], max_tokens: int = 1400) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def extract(doc: dict, retries: int = 2, fast: bool = False) -> dict:
    template = FAST_PROMPT if fast else PROMPT
    prompt = template.format(
        doc_type=doc["doc_type"],
        doc_id=doc["doc_id"],
        text=doc["text"],
    )
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": prompt},
    ]
    last_err = None
    for attempt in range(retries + 1):
        try:
            raw = post_chat(messages, max_tokens=1300 if fast else 1600)
            obj = parse_json(raw)
            obj["doc_id"] = doc["doc_id"]
            obj["doc_type"] = doc["doc_type"]
            obj["role_title"] = doc.get("role_title") or obj.get("role_title")
            obj["_raw_response"] = raw
            return obj
        except Exception as e:
            last_err = e
            time.sleep(2 + attempt * 2)
            messages.append(
                {
                    "role": "user",
                    "content": "Your previous answer was not valid JSON. Return only the JSON object, no markdown.",
                }
            )
    raise RuntimeError(f"{doc['doc_id']}: {last_err}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--doc-ids", default="")
    ap.add_argument("--out", default="test_keywords.jsonl")
    ap.add_argument("--input", default=str(IN))
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    in_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    docs = [json.loads(line) for line in in_path.open(encoding="utf-8")]
    if args.doc_ids:
        wanted = {x.strip() for x in args.doc_ids.split(",") if x.strip()}
        docs = [d for d in docs if d["doc_id"] in wanted]
    elif args.limit:
        docs = docs[: args.limit]

    out_path = out_dir / args.out
    existing = set()
    if args.resume and out_path.exists():
        for line in out_path.open(encoding="utf-8"):
            try:
                existing.add(json.loads(line)["doc_id"])
            except Exception:
                pass
        docs = [d for d in docs if d["doc_id"] not in existing]
        print(f"resume: {len(existing)} existing, {len(docs)} remaining", flush=True)

    done = 0
    mode = "a" if args.resume and out_path.exists() else "w"
    if args.workers > 1:
        with out_path.open(mode, encoding="utf-8") as f, concurrent.futures.ThreadPoolExecutor(
            max_workers=args.workers
        ) as ex:
            futures = {ex.submit(extract, doc, fast=args.fast): doc for doc in docs}
            for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
                doc = futures[fut]
                t0 = time.time()
                try:
                    obj = fut.result()
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    f.flush()
                    done += 1
                    n = len(obj.get("keywords", []))
                    print(
                        f"[{i}/{len(docs)}] {doc['doc_id']} ok: {n} keywords",
                        flush=True,
                    )
                except Exception as e:
                    print(f"[{i}/{len(docs)}] {doc['doc_id']} FAILED: {e}", flush=True)
    else:
        with out_path.open(mode, encoding="utf-8") as f:
            for i, doc in enumerate(docs, 1):
                t0 = time.time()
                try:
                    obj = extract(doc, fast=args.fast)
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    f.flush()
                    done += 1
                    n = len(obj.get("keywords", []))
                    print(
                        f"[{i}/{len(docs)}] {doc['doc_id']} ok: {n} keywords, "
                        f"{time.time()-t0:.1f}s",
                        flush=True,
                    )
                except Exception as e:
                    print(f"[{i}/{len(docs)}] {doc['doc_id']} FAILED: {e}", flush=True)
    print(f"done {done}/{len(docs)} -> {out_path}")


if __name__ == "__main__":
    main()
