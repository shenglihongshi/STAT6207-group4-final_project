"""One-command entry point for the HW4 CV–JD matching pipeline.

Quick mode (default):
    python run_pipeline.py
    -> reuses cached keywords/clusters/metrics, regenerates the report.

Full mode (from raw PDFs):
    python run_pipeline.py --full
    -> parse PDFs -> local-LLM keyword extraction -> clustering -> AE -> evaluation -> report.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def stage(title: str):
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72, flush=True)


def run(script: str, args: list[str] | None = None):
    args = args or []
    cmd = [PY, str(ROOT / "src" / script)] + args
    print("$ " + " ".join(cmd), flush=True)
    t0 = time.time()
    subprocess.run(cmd, cwd=ROOT, check=True)
    print(f"[ok] {script} ({time.time() - t0:.1f}s)", flush=True)


def lmstudio_ok() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="re-parse PDFs and re-run the local LLM extraction")
    ap.add_argument("--skip-report", action="store_true")
    args = ap.parse_args()

    stage("HW4 6207 · CV–JD matching pipeline")
    print(f"project: {ROOT}")
    print(f"python:  {PY}")

    if args.full:
        if not lmstudio_ok():
            print(
                "\n[ERROR] LM Studio API is not reachable at http://127.0.0.1:1234/v1.\n"
                "Start LM Studio and load the models first:\n"
                "  lms server start\n"
                "  lms load qwen2.5-coder-14b-instruct --gpu max --context-length 8192 "
                "--identifier qwen2.5-coder-14b-instruct\n"
                "  lms load text-embedding-nomic-embed-text-v1.5 --gpu max --identifier nomic-embed\n"
            )
            sys.exit(1)

        stage("1/6 · parse PDFs")
        run("parse_data.py")

        stage("2/6 · local-LLM keyword extraction (120 documents)")
        run("extract_keywords.py", ["--out", "all_keywords.jsonl", "--workers", "4"])

        stage("3/6 · keyword clustering + document-term matrix")
        run("cluster_keywords.py")

        stage("4/6 · baselines + autoencoder + LOPO evaluation")
        run("train_eval.py", ["--mode", "all", "--epochs", "100", "--bottleneck", "32"])

        stage("5/6 · error analysis")
        run("error_analysis.py")
    else:
        required = [
            ROOT / "data" / "processed" / "documents.jsonl",
            ROOT / "outputs" / "keywords" / "all_keywords.jsonl",
            ROOT / "outputs" / "clusters" / "doc_term_tfidf.npy",
            ROOT / "outputs" / "metrics" / "metrics.json",
            ROOT / "outputs" / "retrieval" / "per_query.csv",
        ]
        missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
        if missing:
            print("\n[ERROR] Quick mode needs cached artefacts; missing:")
            for p in missing:
                print("  -", p)
            print("\nRun `python run_pipeline.py --full` once to build them.")
            sys.exit(1)
        stage("quick mode · reuse cached keywords/clusters/metrics")
        stage("5/6 · error analysis")
        run("error_analysis.py")

    if not args.skip_report:
        stage("6/6 · bilingual PDF report")
        run("make_report.py")

    stage("done")
    print(f"report (zh): {ROOT / 'report' / 'HW4_6207_Report_CN.pdf'}")
    print(f"report (en): {ROOT / 'report' / 'HW4_6207_Report_EN.pdf'}")
    print(f"metrics:     {ROOT / 'outputs' / 'metrics' / 'metrics.json'}")


if __name__ == "__main__":
    main()
