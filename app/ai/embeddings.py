import os
from typing import List, Tuple
from pathlib import Path
import json

try:  # Optional heavy dependency
    from sentence_transformers import SentenceTransformer  # type: ignore
    has_transformer = True
except Exception:
    SentenceTransformer = None  # type: ignore
    has_transformer = False

# Provide lightweight internal fallbacks if scikit-learn is not installed.
try:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
    from sklearn.neighbors import NearestNeighbors  # type: ignore
    has_sklearn = True
except Exception:
    has_sklearn = False

    class TfidfVectorizer:  # type: ignore
        def __init__(self, stop_words=None):
            self.vocab = {}
        def fit_transform(self, texts):
            # Extremely naive bag-of-words frequency matrix
            docs = []
            vocab_index = {}
            for t in texts:
                counts = {}
                for w in t.lower().split():
                    counts[w] = counts.get(w,0)+1
                docs.append(counts)
                for w in counts:
                    if w not in vocab_index:
                        vocab_index[w] = len(vocab_index)
            import math
            matrix = []
            for d in docs:
                row = [0]*len(vocab_index)
                for w,c in d.items():
                    row[vocab_index[w]] = c
                matrix.append(row)
            self.vocab = vocab_index
            return _Array(matrix)
        def transform(self, texts):
            matrix = []
            for t in texts:
                counts = {}
                for w in t.lower().split():
                    counts[w] = counts.get(w,0)+1
                row = [0]*len(self.vocab)
                for w,c in counts.items():
                    if w in self.vocab:
                        row[self.vocab[w]] = c
                matrix.append(row)
            return _Array(matrix)

    class NearestNeighbors:  # type: ignore
        def __init__(self, n_neighbors=10, metric='cosine'):
            self.n_neighbors = n_neighbors
            self.metric = metric
            self._X = None
        def fit(self, X):
            self._X = X
        def kneighbors(self, vec, n_neighbors=None):
            import math
            n = n_neighbors or self.n_neighbors
            dists = []
            for i,row in enumerate(self._X.data):
                d = _cosine_distance(row, vec.data[0])
                dists.append((d,i))
            dists.sort(key=lambda x: x[0])
            chosen = dists[:n]
            return ( [[d for d,_ in chosen]], [[i for _,i in chosen]] )

    class _Array:  # minimal stand-in for numpy array used
        def __init__(self, data):
            self.data = data
        def toarray(self):
            return self.data
        def __getitem__(self, item):
            return self.data[item]

    def _cosine_distance(a,b):
        import math
        dot = sum(x*y for x,y in zip(a,b))
        na = math.sqrt(sum(x*x for x in a)) or 1e-9
        nb = math.sqrt(sum(x*x for x in b)) or 1e-9
        return 1 - (dot/(na*nb))

from ..models import Product, Event
from ..extensions import db
from ..extensions import db


class EmbeddingIndexer:
    """A simple embedding indexer with a transformer fallback.

    If sentence-transformers is not available, we fall back to TF-IDF vectors.
    The index is kept in-memory and can be persisted as a simple JSON cache.
    """

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2', persist_dir: str = None):
        self.model_name = model_name
        self.persist_dir = Path(persist_dir) if persist_dir else None
        self._model = SentenceTransformer(model_name) if has_transformer else None
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.nn = None
        self.ids = []
        self.embeddings = None

    def _texts_from_products(self, products: List[Product]) -> List[str]:
        return [f"{p.name} {p.description or ''}" for p in products]

    def build_index(self, force: bool = False):
        products = Product.query.order_by(Product.id).all()
        texts = self._texts_from_products(products)
        self.ids = [p.id for p in products]
        # Try warm boot from DB cache if available and not forcing rebuild
        if not force and self.ids:
            try:
                from sqlalchemy import text
                rows = db.session.execute(text("SELECT product_id, vector FROM embedding_cache WHERE product_id IN :ids"), {"ids": tuple(self.ids)}).fetchall()  # type: ignore
                if rows and len(rows) == len(self.ids):
                    # Ensure order aligns with self.ids
                    vec_map = {int(r[0]): json.loads(r[1]) for r in rows}
                    vecs = [vec_map[i] for i in self.ids if i in vec_map]
                    if len(vecs) == len(self.ids):
                        # Accept cached vectors
                        if has_sklearn:
                            self.embeddings = vecs
                        else:
                            class _A:
                                def __init__(self, d):
                                    self.data = d
                            self.embeddings = _A(vecs)
                        self.nn = NearestNeighbors(n_neighbors=10, metric='cosine')
                        self.nn.fit(self.embeddings)
                        return
            except Exception:
                try:
                    db.session.rollback()
                except Exception:
                    pass
        if has_transformer and self._model:
            self.embeddings = self._model.encode(texts, show_progress_bar=False)
        else:
            # TF-IDF matrix
            if has_sklearn:
                self.embeddings = self.vectorizer.fit_transform(texts).toarray()
            else:
                # Keep fallback internal array wrapper for our simple NN
                self.embeddings = self.vectorizer.fit_transform(texts)
        # Fit nearest neighbors
        self.nn = NearestNeighbors(n_neighbors=10, metric='cosine')
        self.nn.fit(self.embeddings)
        # Optionally persist small cache
        if self.persist_dir:
            os.makedirs(self.persist_dir, exist_ok=True)
            cache = {'ids': self.ids}
            with open(os.path.join(self.persist_dir, 'meta.json'), 'w', encoding='utf-8') as f:
                json.dump(cache, f)
        # Persist vectors to DB (embedding_cache table) for warm boot (if table exists)
        try:
            from sqlalchemy import text
            # Create table if missing (simple manual DDL to avoid migration complexity here)
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    product_id INTEGER PRIMARY KEY,
                    vector TEXT NOT NULL
                )
            """))
            # Upsert rows
            for pid, vec in zip(self.ids, (self.embeddings if has_transformer or has_sklearn else self.embeddings.data)):
                if not isinstance(vec, (list, tuple)):
                    vec_list = list(vec)
                else:
                    vec_list = list(vec)
                db.session.execute(text("REPLACE INTO embedding_cache(product_id, vector) VALUES (:pid, :vec)"), {"pid": pid, "vec": json.dumps(vec_list)})
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

    def query_by_product(self, product_id: int, k: int = 5) -> List[Tuple[int, float]]:
        if not self.nn:
            self.build_index()
        try:
            idx = self.ids.index(product_id)
        except ValueError:
            return []
        # Normalize slice for whichever backend produced embeddings
        if hasattr(self.embeddings, 'data') and not hasattr(self.embeddings, 'shape'):
            # Fallback array wrapper exposes `.data`; build a tiny adapter for kneighbors
            single = [self.embeddings.data[idx]]
            class _One:
                data = single
            vec = _One()
        else:
            vec = self.embeddings[idx:idx + 1]
            if isinstance(vec, list):  # Warm-cache gives plain lists; ensure 2D structure
                vec = vec if vec and isinstance(vec[0], (list, tuple)) else [vec]
        dists, inds = self.nn.kneighbors(vec, n_neighbors=min(k + 1, len(self.ids)))
        results = []
        for d, i in zip(dists[0], inds[0]):
            pid = self.ids[int(i)]
            if pid == product_id:
                continue
            results.append((pid, float(d)))
            if len(results) >= k:
                break
        return results

    def query(self, text: str, k: int = 5) -> List[Tuple[int, float]]:
        if not self.nn:
            self.build_index()
        if has_transformer and self._model:
            qvec = self._model.encode([text])
        else:
            qvec = self.vectorizer.transform([text]) if not has_sklearn else self.vectorizer.transform([text]).toarray()
        dists, inds = self.nn.kneighbors(qvec, n_neighbors=min(k, len(self.ids)))
        results = [(self.ids[int(i)], float(d)) for d, i in zip(dists[0], inds[0])]
        return results

    def personalized(self, session_id: str, k: int = 8) -> List[int]:
        """Return personalized product IDs using recent event interactions + embeddings similarity aggregation."""
        # Get recent product views/adds
        recent = Event.query.filter(Event.session_id == session_id).order_by(Event.created_at.desc()).limit(25).all()
        base_ids = [e.product_id for e in recent if e.product_id]
        if not base_ids:
            return []
        scores = {}
        for pid in base_ids:
            for rec_id, dist in self.query_by_product(pid, k=5):
                scores[rec_id] = scores.get(rec_id, 0.0) + (1.0 - dist)
        # Remove already seen
        for pid in base_ids:
            scores.pop(pid, None)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [pid for pid,_ in ranked[:k]]
