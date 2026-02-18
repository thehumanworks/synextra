from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass

from synextra.repositories.rag_document_repository import ChunkRecord
from synextra.retrieval.types import EvidenceChunk

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


@dataclass(frozen=True)
class _Bm25Corpus:
    tokenized_docs: list[list[str]]
    chunk_records: list[ChunkRecord]


class _Bm25Scorer:
    """Small BM25 scorer with optional rank_bm25 acceleration."""

    def __init__(self, corpus: _Bm25Corpus) -> None:
        self._corpus = corpus

        self._rank_bm25 = None
        self._idf: dict[str, float] | None = None
        self._doc_tf: list[dict[str, int]] | None = None
        self._doc_len: list[int] | None = None
        self._avg_dl: float | None = None

        try:
            from rank_bm25 import BM25Okapi  # type: ignore

            self._rank_bm25 = BM25Okapi(corpus.tokenized_docs)
        except Exception:
            self._rank_bm25 = None

        if self._rank_bm25 is None:
            self._build_fallback_index()

    def _build_fallback_index(self) -> None:
        docs = self._corpus.tokenized_docs
        doc_tf: list[dict[str, int]] = []
        df: dict[str, int] = {}
        doc_len: list[int] = []

        for tokens in docs:
            tf: dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            doc_tf.append(tf)
            doc_len.append(len(tokens))
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1

        n_docs = len(docs) or 1
        idf: dict[str, float] = {}
        for token, freq in df.items():
            # BM25+ style idf.
            idf[token] = math.log(1 + (n_docs - freq + 0.5) / (freq + 0.5))

        self._idf = idf
        self._doc_tf = doc_tf
        self._doc_len = doc_len
        self._avg_dl = sum(doc_len) / n_docs

    def score(self, query: str) -> list[float]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return [0.0 for _ in self._corpus.tokenized_docs]

        if self._rank_bm25 is not None:
            rank_scores = self._rank_bm25.get_scores(query_tokens)
            return [float(score) for score in rank_scores]

        assert self._idf is not None
        assert self._doc_tf is not None
        assert self._doc_len is not None
        assert self._avg_dl is not None

        k1 = 1.5
        b = 0.75

        scores: list[float] = []
        for idx, tf in enumerate(self._doc_tf):
            dl = self._doc_len[idx]
            denom_norm = k1 * (1 - b + b * (dl / self._avg_dl))

            score = 0.0
            for token in query_tokens:
                if token not in tf:
                    continue
                idf = self._idf.get(token, 0.0)
                freq = tf[token]
                score += idf * (freq * (k1 + 1)) / (freq + denom_norm)
            scores.append(score)
        return scores


class Bm25Index:
    def __init__(self, *, document_id: str, chunks: list[ChunkRecord], signature: str) -> None:
        self.document_id = document_id
        self.signature = signature
        self._chunk_records = list(chunks)
        tokenized_docs = [_tokenize(chunk.text) for chunk in chunks]
        self._corpus = _Bm25Corpus(tokenized_docs=tokenized_docs, chunk_records=self._chunk_records)
        self._scorer = _Bm25Scorer(self._corpus)

    def search(self, *, query: str, top_k: int = 6) -> list[EvidenceChunk]:
        scores = self._scorer.score(query)
        indexed = list(enumerate(scores))
        indexed.sort(key=lambda pair: (-pair[1], pair[0]))
        evidence: list[EvidenceChunk] = []
        for idx, score in indexed[: max(1, top_k)]:
            chunk = self._chunk_records[idx]
            if score <= 0:
                continue
            evidence.append(
                EvidenceChunk(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    score=float(score),
                    source_tool="bm25_search",
                )
            )
        return evidence


class Bm25IndexStore:
    """Thread-safe in-memory registry of BM25 indexes."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._indexes: dict[str, Bm25Index] = {}

    def upsert(self, *, document_id: str, chunks: list[ChunkRecord], signature: str) -> None:
        with self._lock:
            existing = self._indexes.get(document_id)
            if existing and existing.signature == signature:
                return
            self._indexes[document_id] = Bm25Index(
                document_id=document_id,
                chunks=chunks,
                signature=signature,
            )

    def search(
        self,
        *,
        query: str,
        top_k: int = 6,
        document_ids: list[str] | None = None,
    ) -> list[EvidenceChunk]:
        with self._lock:
            candidate_ids = document_ids or sorted(self._indexes.keys())
            evidence: list[EvidenceChunk] = []
            for document_id in candidate_ids:
                index = self._indexes.get(document_id)
                if not index:
                    continue
                evidence.extend(index.search(query=query, top_k=top_k))

        evidence.sort(key=lambda chunk: (-chunk.score, chunk.chunk_id))
        return evidence[: max(1, top_k)]

    def has_document(self, document_id: str) -> bool:
        with self._lock:
            return document_id in self._indexes
