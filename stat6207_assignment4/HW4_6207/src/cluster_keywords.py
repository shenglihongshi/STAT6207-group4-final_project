"""Merge/normalise keywords and build the document-term matrix.

Pipeline:
  alias normalisation -> Nomic keyword embeddings (local LM Studio)
  -> agglomerative clustering -> canonical term -> TF-IDF matrix.

If the embedding endpoint is unavailable, falls back to character n-gram TF-IDF.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfTransformer, TfidfVectorizer

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = ROOT / "outputs" / "keywords" / "all_keywords.jsonl"
OUT = ROOT / "outputs" / "clusters"
OUT.mkdir(parents=True, exist_ok=True)

EMBED_API = "http://127.0.0.1:1234/v1/embeddings"
EMBED_MODEL = "nomic-embed"

ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "golang": "go",
    "go lang": "go",
    "postgres": "postgresql",
    "postgre sql": "postgresql",
    "gcp": "google cloud platform",
    "google cloud": "google cloud platform",
    "aws": "amazon web services",
    "amazon web services": "amazon web services",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "ci cd": "ci/cd",
    "ci/cd": "ci/cd",
    "rest": "rest api",
    "restful": "rest api",
    "restful api": "rest api",
    "api": "rest api",
    "apis": "rest api",
    "rest apis": "rest api",
    "restful apis": "rest api",
    "rest api design": "rest api",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "nodejs": "node.js",
    "node": "node.js",
    "k8s": "kubernetes",
    "ms sql": "microsoft sql server",
    "sql server": "microsoft sql server",
    "powerbi": "power bi",
    "nlp": "natural language processing",
    "llm": "large language model",
    "llms": "large language model",
    "oop": "object-oriented programming",
    "tdd": "test-driven development",
    "c sharp": "c#",
    "c plus plus": "c++",
}

PROTECTED = {
    "java", "javascript", "c", "c++", "c#", "sql", "mysql", "postgresql",
    "react", "react native", "amazon web services", "azure",
    "google cloud platform", "docker", "kubernetes",
    "system design", "design system",
    "github", "github actions", "portfolio management", "stock management",
    "statistical modeling", "quality consistency", "cloud functions",
    "presentation skills", "retail sales", "scrum master",
}


def norm_term(term: str) -> str:
    t = term.strip().lower()
    t = t.replace("&", " and ")
    t = re.sub(r"[\(\)\[\]\{\}]", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" .,;:-")
    return ALIASES.get(t, t)


def embed_terms(terms: list[str]) -> np.ndarray:
    vectors = []
    for i in range(0, len(terms), 64):
        batch = terms[i : i + 64]
        payload = {"model": EMBED_MODEL, "input": batch}
        req = urllib.request.Request(
            EMBED_API,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        vectors.extend([x["embedding"] for x in data["data"]])
    X = np.asarray(vectors, dtype=np.float32)
    X = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    return X


def cluster_terms(terms: list[str], use_embeddings: bool = True):
    if use_embeddings:
        try:
            X = embed_terms(terms)
            print(f"embedded {len(terms)} terms with {EMBED_MODEL}")
        except Exception as e:
            print(f"embedding failed ({e}); falling back to char TF-IDF")
            use_embeddings = False
    if not use_embeddings:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
        X = vec.fit_transform(terms).toarray()
    cl = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.20 if use_embeddings else 0.30,
        metric="cosine",
        linkage="average",
    )
    cl.fit(X)
    return cl.labels_


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-embed", action="store_true")
    ap.add_argument("--input", default=str(KEYWORDS))
    ap.add_argument("--out-dir", default=str(OUT))
    args = ap.parse_args()

    keywords_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    docs = [json.loads(line) for line in keywords_path.open(encoding="utf-8")]
    print(f"loaded {len(docs)} keyword profiles")

    variants: dict[str, Counter] = defaultdict(Counter)
    doc_terms: list[dict] = []
    for doc in docs:
        terms = []
        seen = set()
        for kw in doc.get("keywords", []):
            raw = str(kw.get("term", "")).strip()
            if not raw:
                continue
            t = norm_term(raw)
            if not t:
                continue
            imp = int(kw.get("importance", 1) or 1)
            variants[t][raw] += 1
            if t not in seen:
                terms.append((t, imp))
                seen.add(t)
        doc_terms.append({"doc_id": doc["doc_id"], "terms": terms})

    unique_terms = sorted(variants)
    print(f"unique normalised keywords: {len(unique_terms)}")

    protected = [t for t in unique_terms if t in PROTECTED]
    candidate = [t for t in unique_terms if t not in PROTECTED]

    labels = {t: i for i, t in enumerate(protected)}
    next_id = len(protected)
    if candidate:
        labs = cluster_terms(candidate, use_embeddings=not args.no_embed)
        for term, lab in zip(candidate, labs):
            labels[term] = next_id + int(lab)
        next_id += len(set(labs))

    groups: dict[int, list[str]] = defaultdict(list)
    for term, lab in labels.items():
        groups[lab].append(term)

    def total_imp(term: str) -> int:
        return sum(imp for d in doc_terms for t, imp in d["terms"] if t == term)

    def doc_freq(term: str) -> int:
        return sum(1 for d in doc_terms if any(t == term for t, _ in d["terms"]))

    clusters = []
    term_to_cluster: dict[str, int] = {}
    for cid, terms in groups.items():
        terms_sorted = sorted(terms, key=lambda t: (-total_imp(t), -doc_freq(t), t))
        canonical = terms_sorted[0]
        for t in terms:
            term_to_cluster[t] = cid
        clusters.append(
            {
                "cluster_id": cid,
                "canonical": canonical,
                "variants": sorted(terms),
                "doc_freq": doc_freq(canonical),
                "total_importance": total_imp(canonical),
            }
        )
    clusters.sort(key=lambda x: (-x["doc_freq"], -x["total_importance"], x["canonical"]))
    cluster_ids = [c["cluster_id"] for c in clusters]
    canonical_by_cluster = {c["cluster_id"]: c["canonical"] for c in clusters}

    doc_ids = [d["doc_id"] for d in docs]
    vocab = [canonical_by_cluster[cid] for cid in cluster_ids]
    idx = {cid: i for i, cid in enumerate(cluster_ids)}
    counts = np.zeros((len(docs), len(vocab)), dtype=np.float32)
    for i, d in enumerate(doc_terms):
        for term, imp in d["terms"]:
            counts[i, idx[term_to_cluster[term]]] += float(imp)

    tfidf = TfidfTransformer(norm="l2", use_idf=True, smooth_idf=True)
    X = tfidf.fit_transform(counts).astype(np.float32).toarray()

    np.save(out_dir / "doc_term_counts.npy", counts)
    np.save(out_dir / "doc_term_tfidf.npy", X)
    (out_dir / "doc_ids.json").write_text(json.dumps(doc_ids, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "vocab.json").write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "keyword_clusters.json").write_text(
        json.dumps(clusters, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (out_dir / "doc_terms.jsonl").open("w", encoding="utf-8") as f:
        for d in doc_terms:
            f.write(json.dumps(
                {
                    "doc_id": d["doc_id"],
                    "terms": [
                        {"term": canonical_by_cluster[term_to_cluster[t]], "importance": imp}
                        for t, imp in d["terms"]
                    ],
                },
                ensure_ascii=False,
            ) + "\n")

    print(f"clusters: {len(clusters)}; vocab: {len(vocab)}; matrix: {counts.shape}")
    print("top clusters:")
    for c in clusters[:20]:
        print(f"  {c['canonical']!r}: {c['variants']} (df={c['doc_freq']})")


if __name__ == "__main__":
    main()
