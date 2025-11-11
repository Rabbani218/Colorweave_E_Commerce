from typing import List, Dict, Tuple
from .embeddings import EmbeddingIndexer
from ..models import Product, Event
from ..extensions import db


class Recommender:
    def __init__(self, indexer: EmbeddingIndexer):
        self.indexer = indexer

    def recommend_for_product(self, product_id: int, k: int = 5) -> List[Product]:
        pairs = self.indexer.query_by_product(product_id, k=k)
        ids = [pid for pid, _ in pairs]
        if not ids:
            return []
        products = Product.query.filter(Product.id.in_(ids)).all()
        # Preserve order
        prod_map = {p.id: p for p in products}
        ordered = [prod_map.get(i) for i in ids if prod_map.get(i)]
        return ordered

    def cooccurrence_for_product(self, product_id: int, k: int = 5) -> List[Tuple[int, float]]:
        """Simple co-occurrence based on session-level events: products appearing in the same session."""
        # fetch sessions where product appeared
        sess_rows = db.session.query(Event.session_id).filter(Event.product_id == product_id).distinct().all()
        sess_ids = [r[0] for r in sess_rows if r[0]]
        if not sess_ids:
            return []
        # count other products in these sessions
        counts: Dict[int, int] = {}
        q = db.session.query(Event.product_id).filter(Event.session_id.in_(sess_ids), Event.product_id.isnot(None))
        for (pid,) in q.all():
            if pid and pid != product_id:
                counts[int(pid)] = counts.get(int(pid), 0) + 1
        if not counts:
            return []
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:k]
        # convert to (pid, score) with normalized score
        maxc = float(ranked[0][1]) if ranked else 1.0
        return [(pid, 1.0 - (c/maxc)) for pid, c in ranked]

    def hybrid_for_product(self, product_id: int, k: int = 8) -> List[Product]:
        emb = self.indexer.query_by_product(product_id, k=k)
        coo = self.cooccurrence_for_product(product_id, k=k)
        scores: Dict[int, float] = {}
        for pid, dist in emb:
            scores[pid] = scores.get(pid, 0.0) + (1.0 - dist) * 0.6
        for pid, dist in coo:
            scores[pid] = scores.get(pid, 0.0) + (1.0 - dist) * 0.4
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
        ids = [pid for pid,_ in ranked]
        if not ids:
            return []
        products = Product.query.filter(Product.id.in_(ids)).all()
        pmap = {p.id: p for p in products}
        return [pmap[i] for i in ids if i in pmap]
