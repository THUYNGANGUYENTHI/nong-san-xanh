# Nông Sản Xanh — Nền tảng bán nông sản trực tuyến tích hợp AI

Đồ án tốt nghiệp KTPM K21C — Nguyễn Thị Thúy Nga (DTC225180233).

Hệ thống thương mại điện tử chuyên nông sản:
- 3 vai trò: **Admin / Seller / Buyer**
- Quản lý sản phẩm, giỏ hàng, đặt hàng, **thanh toán (COD/Bank/QR demo)**, vận chuyển
- **AI gợi ý sản phẩm** (TF-IDF + Cosine Similarity)
- **AI tư vấn / chatbot CSKH** (NLP intent + smart search), lưu lịch sử hội thoại
- Đánh giá sản phẩm, xử lý sau bán (đổi/trả/hủy)
- Logging hệ thống, phân quyền, validation

## Stack
- Python 3.11+ / Flask 3 / SQLAlchemy / SQLite
- scikit-learn (TF-IDF + Cosine Similarity)
- Flask-Login, Flask-WTF (CSRF), Werkzeug security (hash password)
- TailwindCSS (CDN) / FontAwesome
- Gunicorn (production)

## Cấu trúc thư mục
```
deadlineNguyenThuyNga/
├── app.py                # Routes + business logic
├── models.py             # ORM models
├── forms.py              # WTForms
├── ai_engine.py          # TF-IDF + Cosine + intent NLP
├── config.py             # Config từ env
├── seed.py               # Sinh dữ liệu mẫu lớn
├── requirements.txt
├── Procfile              # Deploy gunicorn
├── .env.example          # Mẫu env vars
├── templates/            # HTML
│   ├── base.html
│   ├── index.html, product_detail.html
│   ├── cart.html, checkout.html, payment.html
│   ├── order_history.html, order_detail.html, tracking.html
│   ├── chat.html         # AI chatbot buyer
│   ├── login.html, register.html
│   ├── admin/...
│   ├── seller/...
│   └── errors/...
├── static/uploads/       # Ảnh sản phẩm (do admin/seller upload)
├── logs/                 # File log (sinh khi chạy)
└── nongsan.db            # SQLite DB (sinh khi chạy)
```

Chi tiết vận hành: xem `HUONG_DAN_CHAY.md` và `LUONG_CHAY.md`.

## Tài khoản mặc định (sau khi seed)
| Vai trò | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Seller | `seller` | `seller123` |
| Buyer | `khachhang` | `123456` |

## Deploy Render (bắt buộc commit mới nhất, không phải `first commit`)

1. GitHub `main` phải là commit mới (có `/health`, seed khi build).
2. Render Dashboard → **Manual Deploy** → **Deploy latest commit** (không Rollback).
3. **Build Command:** `pip install -r requirements.txt && python seed.py --reset --fixed` (≥320 SP, ≥200 user, ≥500 đơn — mất ~5–15 phút)
4. **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
5. Env: `FLASK_DEBUG=0`, `PYTHON_VERSION=3.11.9`
6. Sau deploy, kiểm tra: `https://<ten-service>.onrender.com/health` → `{"status":"ok",...}`

## Cách chạy nhanh
```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
python seed.py                     # sinh dữ liệu mẫu lớn (≥300 SP, ≥200 user, ≥500 đơn, ≥300 review, ≥200 hội thoại AI)
python app.py                      # chạy dev server tại http://localhost:5000
```

## Yêu cầu đề cương đáp ứng
| PI | Yêu cầu | Trạng thái |
|---|---|---|
| 1.2 FR | catalog, cart, order, theo dõi đơn, đánh giá, AI gợi ý/CSKH | OK |
| 1.2 NFR | bảo mật demo, hiệu năng, chống spam | CSRF + hash password + logging |
| 1.3 UC≥5 | SP, đặt hàng, thanh toán, theo dõi, AI tư vấn | OK |
| 2.1 ERD | Product, Category, Cart, Order, OrderItem, Payment, Shipment, Review | OK |
| 2.2 Kiến trúc | core + recommendation + chat | OK |
| 3.1 CSDL + seed | có | OK (`seed.py`) |
| 3.2 Backend + AI | TF-IDF + smart search + chatbot | OK |
| 3.3 ≥5 UC chính | OK | OK |
| 3.4 NFR phân quyền + logging | admin/seller/buyer + logs/app.log | OK |
| 4.1 Deploy | Procfile + gunicorn + env | Sẵn sàng |
| 4.2 Dữ liệu thử | ≥300 SP, ≥200 user, ≥500 đơn, ≥300 review, ≥200 hội thoại AI | OK qua `seed.py` |
