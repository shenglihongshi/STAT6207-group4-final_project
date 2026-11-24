"""General mode: one JD/CV per file -> rankings.csv + rankings.md.

Put files in:
  data/input/jds/
  data/input/cvs/
Optional:
  data/input/ground_truth.csv   (jd_id,cv_id or jd_file,cv_file)

Run:
  python run_general.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def stage(title):
    print("\n" + "=" * 72)
    print("  " + title)
    print("=" * 72, flush=True)


def run(script, args):
    cmd = [PY, str(ROOT / "src" / script)] + args
    print("$ " + " ".join(cmd), flush=True)
    t0 = time.time()
    subprocess.run(cmd, cwd=ROOT, check=True)
    print(f"[ok] {script} ({time.time() - t0:.1f}s)", flush=True)


def doc_ids(path):
    return [json.loads(line)["doc_id"] for line in path.open(encoding="utf-8")]


def keyword_ids(path):
    if not path.exists():
        return []
    ids = []
    for line in path.open(encoding="utf-8"):
        try:
            ids.append(json.loads(line)["doc_id"])
        except Exception:
            pass
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--bottleneck", type=int, default=32)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skip-llm", action="store_true", help="reuse existing general keywords")
    ap.add_argument("--input", default=str(ROOT / "data" / "input"))
    args = ap.parse_args()

    input_root = Path(args.input).resolve()
    for d in ("jds", "cvs"):
        (input_root / d).mkdir(parents=True, exist_ok=True)

    stage("1/4 · parse general input")
    run("parse_general.py", ["--input", str(input_root)])

    docs_path = ROOT / "data" / "general" / "processed" / "documents.jsonl"
    docs = [json.loads(line) for line in docs_path.open(encoding="utf-8")]
    if not docs:
        print("No input documents found. Put JD files in data/input/jds and CV files in data/input/cvs.")
        sys.exit(1)
    if not any(d["doc_type"] == "jd" for d in docs) or not any(d["doc_type"] == "cv" for d in docs):
        print("General mode needs at least one JD and one CV.")
        sys.exit(1)

    stage("2/4 · local-LLM keyword extraction")
    kw = ROOT / "outputs" / "general" / "keywords" / "all_keywords.jsonl"
    docs_path = ROOT / "data" / "general" / "processed" / "documents.jsonl"
    if args.skip_llm and kw.exists():
        print(f"reuse {kw}")
    else:
        run(
            "extract_keywords.py",
            [
                "--input", str(docs_path),
                "--out-dir", str(ROOT / "outputs" / "general" / "keywords"),
                "--out", "all_keywords.jsonl",
                "--workers", str(args.workers),
            ],
        )

    # Validate completeness; retry missing documents once with the smaller prompt.
    expected = set(doc_ids(docs_path))
    for attempt in range(2):
        got = set(keyword_ids(kw))
        missing = sorted(expected - got)
        if not missing:
            break
        print(f"[retry {attempt + 1}] missing keyword profiles: {missing}", flush=True)
        run(
            "extract_keywords.py",
            [
                "--input", str(docs_path),
                "--out-dir", str(ROOT / "outputs" / "general" / "keywords"),
                "--out", "all_keywords.jsonl",
                "--resume",
                "--doc-ids", ",".join(missing),
                "--fast",
                "--workers", "1",
            ],
        )
    missing = sorted(expected - set(keyword_ids(kw)))
    if missing:
        print(f"Keyword extraction failed for: {missing}")
        sys.exit(1)

    stage("3/4 · keyword clustering + document-term matrix")
    run(
        "cluster_keywords.py",
        [
            "--input", str(kw),
            "--out-dir", str(ROOT / "outputs" / "general" / "clusters"),
        ],
    )

    stage("4/4 · autoencoder + top-10 ranking")
    run(
        "match_general.py",
        [
            "--epochs", str(args.epochs),
            "--bottleneck", str(args.bottleneck),
            "--gt", str(input_root / "ground_truth.csv"),
        ],
    )

    stage("done")
    print(f"rankings: {ROOT / 'outputs' / 'general' / 'rankings.csv'}")
    print(f"markdown: {ROOT / 'outputs' / 'general' / 'rankings.md'}")


if __name__ == "__main__":
    main()
