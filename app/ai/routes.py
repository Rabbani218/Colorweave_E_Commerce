from flask import Blueprint, request, jsonify, current_app, abort, session
from flask_login import login_required, current_user
from .embeddings import EmbeddingIndexer
from .recommender import Recommender
from .imagery import generate_image
from ..models import Product
import os
from .vision import VisionIndexer
import time
import random
import logging

ai_bp = Blueprint('ai', __name__)


def _get_indexer():
    cfg = current_app.config
    idx = EmbeddingIndexer(
        model_name=cfg.get('EMBEDDING_MODEL'),
        persist_dir=cfg.get('VECTOR_DB_PATH'),
    )
    # build lazily
    return idx


def _get_vision_indexer():
    cfg = current_app.config
    return VisionIndexer(
        static_folder=current_app.static_folder,
        persist_dir=cfg.get('VECTOR_DB_PATH'),
    )


def _audit_log(event: str, detail: dict):
    try:
        logs_dir = os.path.join(os.path.dirname(current_app.root_path), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(logs_dir, 'ai_audit.log'))
        logger = logging.getLogger('ai_audit')
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            logger.addHandler(fh)
        logger.info('%s | %s', event, detail)
    except Exception:
        pass


_RATE_BUCKETS = {}


def _rate_limit(key: str, limit: int = 60, window_sec: int = 300) -> bool:
    now = time.time()
    bucket = _RATE_BUCKETS.get(key, [])
    bucket = [t for t in bucket if now - t < window_sec]
    allowed = len(bucket) < limit
    if allowed:
        bucket.append(now)
        _RATE_BUCKETS[key] = bucket
    return allowed


@ai_bp.route('/recommend', methods=['GET'])
def recommend():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if not _rate_limit(f"rec:{ip}"):
        return jsonify({'error': 'rate limit exceeded'}), 429
    pid = request.args.get('product_id')
    if not pid:
        return jsonify({'error': 'product_id required'}), 400
    try:
        pid = int(pid)
    except Exception:
        return jsonify({'error': 'invalid product_id'}), 400
    idx = _get_indexer()
    rec = Recommender(idx).recommend_for_product(pid, k=5)
    items = [
        {
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'image': p.image,
        }
        for p in rec
    ]
    _audit_log('recommend', {'pid': pid, 'len': len(items), 'ip': ip})
    return jsonify({'items': items})


@ai_bp.route('/recommend_cf', methods=['GET'])
def recommend_cf():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if not _rate_limit(f"recf:{ip}"):
        return jsonify({'error': 'rate limit exceeded'}), 429
    pid = request.args.get('product_id')
    if not pid:
        return jsonify({'error': 'product_id required'}), 400
    try:
        pid = int(pid)
    except Exception:
        return jsonify({'error': 'invalid product_id'}), 400
    idx = _get_indexer()
    r = Recommender(idx)
    pairs = r.cooccurrence_for_product(pid, k=8)
    ids = [pid for pid, _ in pairs]
    products = Product.query.filter(Product.id.in_(ids)).all()
    pmap = {p.id: p for p in products}
    items = [
        {
            'id': i,
            'name': pmap[i].name,
            'price': pmap[i].price,
            'image': pmap[i].image,
        }
        for i in ids
        if i in pmap
    ]
    _audit_log('recommend_cf', {'pid': pid, 'len': len(items)})
    return jsonify({'items': items})


@ai_bp.route('/recommend_hybrid', methods=['GET'])
def recommend_hybrid():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if not _rate_limit(f"rech:{ip}"):
        return jsonify({'error': 'rate limit exceeded'}), 429
    pid = request.args.get('product_id')
    if not pid:
        return jsonify({'error': 'product_id required'}), 400
    try:
        pid = int(pid)
    except Exception:
        return jsonify({'error': 'invalid product_id'}), 400
    idx = _get_indexer()
    rec = Recommender(idx).hybrid_for_product(pid, k=8)
    items = [
        {
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'image': p.image,
        }
        for p in rec
    ]
    _audit_log('recommend_hybrid', {'pid': pid, 'len': len(items)})
    return jsonify({'items': items})


@ai_bp.route('/search', methods=['GET'])
def search():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if not _rate_limit(f"search:{ip}"):
        return jsonify({'error': 'rate limit exceeded'}), 429
    q = request.args.get('q')
    if not q:
        return jsonify({'error': 'q required'}), 400
    idx = _get_indexer()
    pairs = idx.query(q, k=10)
    ids = [pid for pid, _ in pairs]
    products = Product.query.filter(Product.id.in_(ids)).all()
    prod_map = {p.id: p for p in products}
    items = [
        {
            'id': pid,
            'name': prod_map[pid].name,
            'price': prod_map[pid].price,
            'image': prod_map[pid].image,
        }
        for pid in ids
        if pid in prod_map
    ]
    _audit_log('search', {'q': q[:100], 'len': len(items), 'ip': ip})
    return jsonify({'items': items})


@ai_bp.route('/generate_image', methods=['POST'])
@login_required
def generate_image_endpoint():
    # Admin-only
    if not getattr(current_user, 'is_admin', False):
        return abort(403)
    data = request.form or request.json or {}
    prompt = data.get('prompt') or request.form.get('prompt')
    if not prompt:
        return jsonify({'error': 'prompt required'}), 400
    out_dir = os.path.join(
        current_app.static_folder or 'static',
        'images',
        'generated',
    )
    filename = f"gen_{abs(hash(prompt)) % (10**8)}.png"
    path = generate_image(prompt, filename, out_dir)
    rel = os.path.relpath(path, start=current_app.static_folder)
    _audit_log(
        'generate_image',
        {
            'user': getattr(current_user, 'id', None),
            'prompt': (prompt or '')[:80],
        },
    )
    return jsonify({'path': f"/static/{rel}"})


# --- Simple AI shopping assistant (session memory, retrieval-augmented) ---
@ai_bp.route('/chat', methods=['POST'])
def chat():
    """Minimal chat endpoint that answers product questions.

    Responses leverage semantic retrieval for product recall.

    Request JSON:
        { "message": "string" }
    Response JSON:
        { "reply": "string", "suggestions": [ {id,name,price,image} ] }
    """
    data = request.get_json(silent=True) or {}
    msg = (data.get('message') or '').strip()
    if not msg:
        return jsonify({"error": "message required"}), 400

    # Keep a tiny rolling history in session
    history = session.get('ai_chat_history', [])
    history.append({"role": "user", "content": msg})
    history = history[-10:]

    # Use embedding indexer to retrieve relevant products
    idx = _get_indexer()
    pairs = idx.query(msg, k=5)
    ids = [pid for pid, _ in pairs]
    products = Product.query.filter(Product.id.in_(ids)).all() if ids else []
    prod_map = {p.id: p for p in products}
    items = [
        {
            "id": pid,
            "name": prod_map[pid].name,
            "price": prod_map[pid].price,
            "image": prod_map[pid].image,
        }
        for pid in ids
        if pid in prod_map
    ]

    # Compose a varied, CS-style reply (simple template-based, no external LLM)
    def _intent(msg: str) -> str:
        m = msg.lower()
        if any(
            k in m
            for k in ['harga', 'murah', 'mahal', 'budget', 'kisaran', 'berapa']
        ):
            return 'price'
        if any(
            k in m
            for k in [
                'warna',
                'color',
                'biru',
                'merah',
                'hitam',
                'putih',
                'emas',
                'silver',
                'pink',
                'hijau',
                'ungu',
                'orange',
                'teal',
            ]
        ):
            return 'color'
        if any(
            k in m
            for k in [
                'gelang',
                'kalung',
                'cincin',
                'anting',
                'bracelet',
                'necklace',
                'ring',
                'earring',
                'aksesoris',
                'perhiasan',
            ]
        ):
            return 'type'
        if any(
            k in m
            for k in [
                'rekomendasi',
                'saran',
                'cocok',
                'suggest',
                'rekomen',
                'bagus',
            ]
        ):
            return 'recommend'
        if any(
            k in m
            for k in [
                'halo',
                'hai',
                'hi',
                'hello',
                'pagi',
                'siang',
                'malam',
                'hey',
            ]
        ):
            return 'greeting'
        if any(k in m for k in ['bahan', 'material', 'kualitas', 'terbuat']):
            return 'material'
        if any(
            k in m for k in ['beli', 'order', 'pesan', 'checkout', 'bayar']
        ):
            return 'purchase'
        if any(
            k in m
            for k in ['info', 'tentang', 'apa itu', 'jelaskan', 'ceritakan']
        ):
            return 'info'
        return 'general'

    intent = _intent(msg)

    def vary(sentence_list):
        random.shuffle(sentence_list)
        # Pick 2 sentences to form a natural reply
        picked = sentence_list[:2]
        # Occasionally pick 3 for more warmth
        if random.random() < 0.15 and len(sentence_list) >= 3:
            picked = sentence_list[:3]
        return ' '.join(picked)

    # Small talk openers to make it feel like CS assistant
    opener_pool = [
        "Tentu, aku bantu ya.",
        "Siap, aku cekkan untukmu.",
        "Baik, aku bantu carikan pilihan terbaik.",
        "Boleh, aku bantu rekomendasikan.",
        "Siap bantu!",
        "Oke, mari kita cari yang cocok.",
    ]

    # Handle greetings specially
    if intent == 'greeting':
        greet_responses = [
            (
                "Halo! 👋 Selamat datang di ColorWeave! "
                "Aku di sini untuk membantu kamu menemukan gelang yang "
                "sempurna. Mau cari yang warna apa atau model gimana?"
            ),
            (
                "Hai! Senang bisa bantu kamu hari ini. "
                "ColorWeave punya banyak koleksi gelang handmade yang unik. "
                "Ada yang mau dicari?"
            ),
            (
                "Halo! Aku ColorWeave Assistant. "
                "Kamu bisa tanya tentang produk, harga, warna, "
                "atau apapun seputar gelang kami. Mau mulai dari mana?"
            ),
        ]
        reply = random.choice(greet_responses)
        history.append({"role": "assistant", "content": reply})
        session['ai_chat_history'] = history
        _audit_log(
            'chat',
            {
                'msg': msg[:120],
                'suggestions': [],
                'intent': 'greeting',
            },
        )
        return jsonify({"reply": reply, "suggestions": []})

    # Handle info/general questions
    if intent == 'info' and not items:
        info_responses = [
            ("ColorWeave adalah brand aksesoris handmade yang menghadirkan "
             "gelang berkualitas dengan berbagai warna dan desain. "
             "Setiap produk dibuat dengan detail dan cinta! "
             "Mau lihat koleksinya?"),
            ("Kami spesialisasi dalam gelang handmade dengan berbagai tema - "
             "dari elegan, bohemian, hingga modern. "
             "Harga mulai dari Rp 4.500 hingga Rp 150.000. "
             "Ada yang mau dicari spesifik?"),
            ("ColorWeave menawarkan gelang dengan berbagai pilihan warna: "
             "biru, merah, hijau, ungu, emas, silver, pink, hitam, orange, "
             "dan teal. Semuanya handcrafted dengan kualitas terbaik. Mau "
             "coba cari berdasarkan warna favorit?"),
        ]
        reply = random.choice(info_responses)
        history.append({"role": "assistant", "content": reply})
        session['ai_chat_history'] = history
        _audit_log(
            'chat',
            {
                'msg': msg[:120],
                'suggestions': [],
                'intent': 'info',
            },
        )
        return jsonify({"reply": reply, "suggestions": []})

    # Handle purchase questions
    if intent == 'purchase':
        purchase_responses = [
            (
                "Untuk membeli, kamu bisa klik 'Add to Cart' "
                "pada produk yang kamu suka. Lanjutkan ke halaman Cart "
                "untuk checkout. Mudah kok! Ada produk tertentu yang mau "
                "kamu beli?"
            ),
            (
                "Cara belinya gampang: pilih produk → Add to Cart → "
                "Checkout. Kami siap bantu proses pemesananmu! Mau aku "
                "carikan produk dulu?"
            ),
            (
                "Tinggal pilih gelang favorit, masukkan ke cart, "
                "dan checkout. Kalau butuh rekomendasi dulu, aku bisa "
                "bantu carikan yang cocok!"
            ),
        ]
        reply = random.choice(purchase_responses)
        if items:
            top_names = [it['name'] for it in items[:3]]
            names = ', '.join(top_names)
            reply += f" Btw, produk ini mungkin cocok: {names}."
        history.append({"role": "assistant", "content": reply})
        session['ai_chat_history'] = history
        _audit_log(
            'chat',
            {'msg': msg[:120], 'suggestions': [it['id'] for it in items]},
        )
        return jsonify({"reply": reply, "suggestions": items})

    opener = random.choice(opener_pool)

    if items:
        top_names = [it['name'] for it in items[:3]]
        names = ', '.join(top_names)
        followups = [
            "Mau aku bandingkan dari segi bahan, warna, atau harga?",
            "Kalau mau, aku bisa tampilkan lebih banyak opsi serupa.",
            "Butuh info lebih detail tentang salah satunya?",
            "Aku juga bisa jelaskan perbedaan tiap produk dengan singkat.",
            "Atau mau lihat pilihan warna lain?",
        ]
        if intent == 'price':
            price_range = [it['price'] for it in items]
            min_price = min(price_range)
            max_price = max(price_range)
            core = (
                f"{opener} Untuk budget yang kamu cari, ada beberapa pilihan "
                f"dari Rp {min_price:,} - Rp {max_price:,}. "
                f"Yang paling populer: {names}."
            )
        elif intent == 'color':
            core = (
                f"{opener} Untuk warna yang kamu mau, ini yang paling cocok: "
                f"{names}."
            )
        elif intent == 'type':
            core = f"{opener} Ini koleksi {intent} yang sesuai: {names}."
        elif intent == 'material':
            core = (
                f"{opener} Produk kami handmade dengan bahan berkualitas. "
                f"Beberapa yang mungkin cocok: {names}."
            )
        else:
            core = (
                f"{opener} Berdasarkan yang kamu cari, yang paling cocok: "
                f"{names}."
            )
        reply = core + " " + random.choice(followups)
    else:
        # Better no-results responses
        empathy_pool = [
            "Hmm, aku belum menemukan yang pas dari kata kunci itu.",
            (
                "Sepertinya pencarian itu terlalu spesifik. "
                "Coba kata kunci yang lebih umum?"
            ),
            "Belum ketemu yang cocok nih.",
        ]
        tips_pool = [
            (
                "Coba sebutkan warna favorit (biru, merah, emas, pink, dll), "
                "tipe yang diinginkan, atau rentang harga."
            ),
            (
                "Misalnya coba ketik: 'gelang biru', 'yang elegan', "
                "'budget 100 ribu', atau 'bohemian style'."
            ),
            (
                "Aku bisa bantu kalau kamu kasih detail seperti: warna, gaya "
                "(elegan/casual/bohemian), atau untuk acara apa."
            ),
            (
                "Coba keyword seperti: 'gelang emas luxury', "
                "'pink romantic', atau 'silver modern'."
            ),
            (
                "Ketik contoh: 'gelang biru di bawah 150 ribu' atau "
                "'yang cocok untuk hadiah'."
            ),
        ]
        reply = vary([random.choice(empathy_pool), random.choice(tips_pool)])

    history.append({"role": "assistant", "content": reply})
    session['ai_chat_history'] = history
    _audit_log(
        'chat',
        {
            'msg': msg[:120],
            'suggestions': [it['id'] for it in items],
        },
    )
    return jsonify({"reply": reply, "suggestions": items})


@ai_bp.route('/visual_search', methods=['POST'])
def visual_search():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if not _rate_limit(f"vsearch:{ip}"):
        return jsonify({'error': 'rate limit exceeded'}), 429
    """Find visually similar products by uploaded image.

    Accepts multipart/form-data with field 'image'.
    """
    if 'image' not in request.files:
        return jsonify({'error': 'image file required'}), 400
    f = request.files['image']
    try:
        from PIL import Image  # lazy import
        img = Image.open(f.stream).convert('RGB')
    except Exception:
        return jsonify({'error': 'invalid image'}), 400

    v = _get_vision_indexer()
    pairs = v.query_image(img, k=12)
    ids = [pid for pid, _ in pairs]
    if not ids:
        return jsonify({'items': []})
    products = Product.query.filter(Product.id.in_(ids)).all()
    pmap = {p.id: p for p in products}
    items = [
        {
            'id': pid,
            'name': pmap[pid].name,
            'price': pmap[pid].price,
            'image': pmap[pid].image,
        }
        for pid in ids
        if pid in pmap
    ]
    _audit_log('visual_search', {'ip': ip, 'len': len(items)})
    return jsonify({'items': items})


@ai_bp.route('/recommend_for_user', methods=['GET'])
def recommend_for_user():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if not _rate_limit(f"recu:{ip}"):
        return jsonify({'error': 'rate limit exceeded'}), 429
    sid = session.get('sid')
    if not sid:
        return jsonify({'items': []})
    idx = _get_indexer()
    ids = idx.personalized(sid, k=8)
    if not ids:
        return jsonify({'items': []})
    products = Product.query.filter(Product.id.in_(ids)).all()
    pmap = {p.id: p for p in products}
    items = [
        {
            'id': i,
            'name': pmap[i].name,
            'price': pmap[i].price,
            'image': pmap[i].image,
        }
        for i in ids
        if i in pmap
    ]
    _audit_log(
        'recommend_for_user',
        {'ip': ip, 'sid': sid, 'len': len(items)},
    )
    return jsonify({'items': items})
