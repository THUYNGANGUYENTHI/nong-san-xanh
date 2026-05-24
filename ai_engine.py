"""
AI Engine - Hệ thống AI hỗ trợ trải nghiệm mua sắm nông sản
=============================================================
Feature 1: Gợi ý sản phẩm thông minh (TF-IDF + Cosine Similarity)
Feature 2: Trợ lý ảo tìm kiếm ngôn ngữ tự nhiên
"""

import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# VIETNAMESE STOPWORDS (rút gọn, phổ biến)
# ============================================================
VIETNAMESE_STOPWORDS = [
    'và', 'của', 'có', 'là', 'được', 'cho', 'trong', 'với', 'các', 'này',
    'đã', 'từ', 'một', 'những', 'không', 'để', 'rất', 'hay', 'hoặc',
    'cũng', 'như', 'nhưng', 'khi', 'bị', 'theo', 'đến', 'tại', 'còn',
    'về', 'do', 'ra', 'lại', 'nên', 'vì', 'thì', 'mà', 'sẽ', 'đang',
    'nếu', 'hơn', 'bởi', 'qua', 'đều', 'sau', 'trên', 'dưới',
]

# ============================================================
# TỪ ĐIỂN MAPPING ngôn ngữ tự nhiên → từ khóa sản phẩm
# (Cho Feature 2: Trợ lý ảo tìm kiếm)
# ============================================================
INTENT_KEYWORDS = {
    # Nấu ăn - Món ăn
    'canh chua': ['cà chua', 'thơm', 'dứa', 'giá đỗ', 'bạc hà', 'me', 'rau muống', 'đậu bắp'],
    'nấu canh': ['rau muống', 'rau ngót', 'bí đỏ', 'cà chua', 'nấm', 'rau dền'],
    'nấu lẩu': ['nấm', 'rau muống', 'sả', 'ớt', 'cà chua', 'giá đỗ', 'rau sống'],
    'salad': ['cà chua', 'rau xà lách', 'dưa chuột', 'bơ', 'xoài'],
    'xào': ['rau muống', 'giá đỗ', 'nấm', 'ớt', 'sả', 'cải ngọt'],
    'nướng': ['khoai lang', 'sả', 'ớt', 'ngô', 'bắp'],
    'sinh tố': ['xoài', 'bơ', 'dâu', 'chuối', 'bưởi', 'cam', 'thơm', 'dứa'],
    'ép nước': ['cà chua', 'cam', 'bưởi', 'thơm', 'dứa', 'xoài', 'dưa hấu'],
    'nấu cơm': ['gạo', 'gạo st25', 'ngũ cốc'],
    'nấu cháo': ['gạo', 'nấm', 'rau mầm'],
    'kho': ['ớt', 'sả', 'gia vị'],
    'muối': ['ớt', 'sả', 'gia vị', 'chanh'],
    'gỏi cuốn': ['giá đỗ', 'rau sống', 'rau muống', 'bún'],
    'nấu chè': ['khoai lang', 'bí đỏ', 'đậu'],

    # Theo công dụng / dinh dưỡng
    'vitamin c': ['bưởi', 'cam', 'cà chua', 'ớt', 'xoài'],
    'giảm cân': ['rau xanh', 'rau muống', 'giá đỗ', 'nấm', 'bưởi'],
    'tăng cường miễn dịch': ['bưởi', 'cà chua', 'ớt', 'nấm'],
    'tốt cho mắt': ['cà chua', 'khoai lang', 'bí đỏ'],
    'chất xơ': ['khoai lang', 'rau muống', 'giá đỗ', 'nấm', 'bí đỏ'],
    'protein': ['nấm', 'giá đỗ', 'đậu'],
    'giải nhiệt': ['bưởi', 'sả', 'chanh', 'dưa hấu', 'rau má'],

    # Theo mùa / loại
    'trái cây ngọt': ['xoài', 'bưởi', 'cam', 'dưa hấu', 'chuối'],
    'rau xanh': ['rau muống', 'rau ngót', 'rau dền', 'cải ngọt', 'rau xà lách'],
    'gia vị': ['ớt', 'sả', 'hành', 'tỏi', 'gừng', 'tiêu'],
    'đồ ăn sáng': ['gạo', 'chuối', 'xoài', 'bưởi'],
    'đồ nhậu': ['xoài', 'ớt', 'sả', 'rau sống'],
}

# Từ đồng nghĩa / biến thể
SYNONYMS = {
    'thơm': ['dứa', 'thơm'],
    'dứa': ['thơm', 'dứa'],
    'khoai': ['khoai lang', 'khoai tây'],
    'nấu': ['nấu canh', 'nấu lẩu', 'xào'],
    'trộn': ['salad', 'gỏi'],
    'uống': ['sinh tố', 'ép nước', 'giải nhiệt'],
    'healthy': ['giảm cân', 'vitamin c', 'chất xơ'],
    'khỏe': ['tăng cường miễn dịch', 'vitamin c'],
    'bổ dưỡng': ['protein', 'vitamin c', 'chất xơ'],
    'cay': ['ớt'],
    'ngọt': ['xoài', 'bưởi', 'khoai lang'],
}


class AIEngine:
    """
    Engine AI sử dụng TF-IDF và Cosine Similarity
    để gợi ý sản phẩm và tìm kiếm thông minh.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),  # Unigram + Bigram
            stop_words=VIETNAMESE_STOPWORDS,
        )
        self.tfidf_matrix = None
        self.products = []

    def build_index(self, products):
        """
        Xây dựng TF-IDF index từ danh sách sản phẩm.
        Gọi hàm này khi khởi động app hoặc khi có thay đổi sản phẩm.

        Args:
            products: list of Product objects (SQLAlchemy)
        """
        self.products = list(products)
        if not self.products:
            self.tfidf_matrix = None
            return

        # Tạo corpus: gộp tên + mô tả + category + origin
        corpus = []
        for p in self.products:
            text = ' '.join(filter(None, [
                p.name or '',
                p.description or '',
                p.category or '',
                p.origin or '',
                # Lặp tên để tăng trọng số tên SP
                p.name or '',
            ]))
            corpus.append(text.lower())

        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def get_recommendations(self, product_id, top_n=4):
        """
        Feature 1: Gợi ý sản phẩm tương tự dựa trên TF-IDF Cosine Similarity.

        Args:
            product_id: ID sản phẩm đang xem
            top_n: Số sản phẩm gợi ý (mặc định 4)

        Returns:
            list of Product objects tương tự
        """
        if self.tfidf_matrix is None or not self.products:
            return []

        # Tìm index của product trong danh sách
        target_idx = None
        for i, p in enumerate(self.products):
            if p.id == product_id:
                target_idx = i
                break

        if target_idx is None:
            return []

        # Tính cosine similarity giữa SP target và tất cả SP khác
        cosine_sim = cosine_similarity(
            self.tfidf_matrix[target_idx:target_idx + 1],
            self.tfidf_matrix
        ).flatten()

        # Sắp xếp theo độ tương đồng giảm dần, bỏ chính nó
        similar_indices = cosine_sim.argsort()[::-1]

        recommendations = []
        for idx in similar_indices:
            if idx == target_idx:
                continue
            product = self.products[idx]
            # Chỉ gợi ý SP đang hiển thị và còn hàng
            if product.is_visible and product.stock > 0:
                recommendations.append(product)
            if len(recommendations) >= top_n:
                break

        return recommendations

    def smart_search(self, query, all_products, top_n=10):
        """
        Feature 2: Trợ lý ảo tìm kiếm ngôn ngữ tự nhiên.
        Hiểu intent của người dùng và trả về sản phẩm phù hợp.

        VD: "Tôi muốn mua đồ nấu canh chua" → trả về cà chua, thơm, giá đỗ...

        Args:
            query: Câu hỏi / yêu cầu tìm kiếm từ user
            all_products: Tất cả sản phẩm (visible)
            top_n: Số kết quả tối đa

        Returns:
            list of (product, score) tuples
        """
        query_lower = query.lower().strip()

        # --- Bước 1: Phân tích intent từ từ điển ---
        matched_keywords = set()
        for intent, keywords in INTENT_KEYWORDS.items():
            if intent in query_lower:
                matched_keywords.update(keywords)

        # Kiểm tra từ đồng nghĩa
        for word, synonyms in SYNONYMS.items():
            if word in query_lower:
                for syn in synonyms:
                    # Nếu synonym khớp với intent
                    if syn in INTENT_KEYWORDS:
                        matched_keywords.update(INTENT_KEYWORDS[syn])
                    else:
                        matched_keywords.add(syn)

        # --- Bước 2: TF-IDF search trên toàn bộ sản phẩm ---
        scored_products = {}

        if all_products:
            # Tạo corpus cho tất cả sản phẩm
            corpus = []
            product_list = list(all_products)
            for p in product_list:
                text = ' '.join(filter(None, [
                    p.name or '', p.description or '',
                    p.category or '', p.origin or '', p.name or '',
                ]))
                corpus.append(text.lower())

            # Thêm query vào corpus (ở cuối) để vectorize cùng
            corpus.append(query_lower)

            search_vectorizer = TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                stop_words=VIETNAMESE_STOPWORDS,
            )
            tfidf_mat = search_vectorizer.fit_transform(corpus)

            # Cosine similarity giữa query (phần tử cuối) và tất cả SP
            query_vec = tfidf_mat[-1:]
            product_vecs = tfidf_mat[:-1]
            similarities = cosine_similarity(query_vec, product_vecs).flatten()

            for i, score in enumerate(similarities):
                if score > 0.01:  # Ngưỡng tối thiểu
                    scored_products[product_list[i].id] = {
                        'product': product_list[i],
                        'score': float(score),
                    }

        # --- Bước 3: Boost score cho các SP khớp intent ---
        if matched_keywords:
            for p in all_products:
                p_name = (p.name or '').lower()
                p_desc = (p.description or '').lower()
                p_combined = p_name + ' ' + p_desc

                for kw in matched_keywords:
                    if kw.lower() in p_combined:
                        if p.id in scored_products:
                            scored_products[p.id]['score'] += 0.5  # Boost
                        else:
                            scored_products[p.id] = {
                                'product': p,
                                'score': 0.5,
                            }
                        break  # 1 keyword match là đủ boost

        # --- Bước 4: Sắp xếp theo score giảm dần ---
        results = sorted(
            scored_products.values(),
            key=lambda x: x['score'],
            reverse=True,
        )[:top_n]

        return [(r['product'], r['score']) for r in results]


# Singleton instance
ai_engine = AIEngine()
