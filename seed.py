"""
Script khởi tạo database và sinh dữ liệu mẫu (seed data).

Tuân thủ PI 4.2 của đề cương:
  - ≥300 sản phẩm
  - ≥200 người dùng (buyer)
  - ≥500 đơn hàng
  - ≥300 đánh giá (review)
  - ≥200 hội thoại AI

Cách chạy:
  python seed.py            # seed đầy đủ (mặc định)
  python seed.py --reset    # xóa toàn bộ dữ liệu cũ rồi seed lại
  python seed.py --fixed    # dùng random.seed(42) — dữ liệu sinh ra ổn định
  python seed.py --reset --fixed   # seed lại từ đầu, dữ liệu cố định (đề cương)
  python seed.py --small    # seed nhỏ cho test (10 SP, 5 user, 5 đơn)
  python check_data.py      # chỉ kiểm tra đủ ngưỡng đề cương chưa
"""

import argparse
import random
import secrets
from datetime import datetime, timedelta

from config import DE_CUONG_MIN, SEED_TARGETS
from app import app
from models import (
    db, User, Category, Product, Order, OrderItem,
    Payment, Shipment, Review, ReturnRequest, AIConversation,
)

try:
    from faker import Faker
    fake = Faker('vi_VN')
except Exception:
    fake = None


# ============================================================
# DỮ LIỆU NỀN
# ============================================================
CATEGORIES = [
    ('Rau lá', 'Các loại rau ăn lá phổ biến: rau muống, rau dền, cải...'),
    ('Rau củ', 'Các loại củ quả: cà chua, khoai, bí đỏ...'),
    ('Trái cây', 'Trái cây tươi địa phương: xoài, bưởi, cam...'),
    ('Ngũ cốc', 'Gạo, đậu, ngũ cốc các loại'),
    ('Gia vị', 'Ớt, sả, hành, tỏi, gừng, tiêu'),
    ('Nấm', 'Nấm bào ngư, nấm rơm, nấm kim châm'),
    ('Rau mầm', 'Rau mầm các loại: giá đỗ, rau mầm'),
    ('Khác', 'Các sản phẩm nông sản khác'),
]

PRODUCT_TEMPLATES = [
    # (name, category, unit, price_range, origin_options, desc)
    ('Cà chua', 'Rau củ', 'kg', (25000, 45000), ['Đà Lạt', 'Lâm Đồng'],
     'Cà chua tươi mọng, trồng theo phương pháp hữu cơ, không thuốc trừ sâu. Thích hợp nấu canh chua, làm salad, xào, ép nước. Giàu vitamin C.'),
    ('Rau muống', 'Rau lá', 'bó', (10000, 18000), ['Củ Chi', 'Long An'],
     'Rau muống xanh giòn, đạt chuẩn VietGAP. Xào tỏi, luộc chấm kho quẹt đều ngon. Giàu chất xơ, sắt.'),
    ('Xoài cát', 'Trái cây', 'kg', (60000, 90000), ['Tiền Giang', 'Đồng Tháp'],
     'Xoài cát Hòa Lộc ngọt thanh, thơm lừng, thịt dày hạt lép. Ăn tươi, sinh tố, mứt đều ngon.'),
    ('Bưởi da xanh', 'Trái cây', 'trái', (35000, 60000), ['Bến Tre'],
     'Bưởi da xanh ruột hồng, vị ngọt thanh không chua. Giàu vitamin C, tăng cường miễn dịch.'),
    ('Khoai lang mật', 'Rau củ', 'kg', (30000, 50000), ['Đà Lạt', 'Vĩnh Long'],
     'Khoai lang mật ruột vàng cam, vị ngọt bùi béo. Nướng, hấp, chiên đều ngon. Giàu beta-carotene.'),
    ('Gạo ST25', 'Ngũ cốc', 'kg', (28000, 38000), ['Sóc Trăng'],
     'Gạo ST25 đặc sản Sóc Trăng - gạo ngon nhất thế giới. Hạt dài, cơm dẻo thơm.'),
    ('Thơm', 'Trái cây', 'trái', (20000, 30000), ['Thanh Hóa', 'Tiền Giang'],
     'Thơm Queen vị ngọt đậm chua nhẹ. Ăn tươi, nấu canh chua, ép nước.'),
    ('Giá đỗ', 'Rau mầm', 'kg', (10000, 15000), ['TP.HCM', 'Đồng Nai'],
     'Giá đỗ xanh ủ sạch, giòn trắng tự nhiên. Xào, nấu canh chua, gỏi cuốn.'),
    ('Ớt sừng', 'Gia vị', 'kg', (45000, 75000), ['Gia Lai', 'Tây Ninh'],
     'Ớt sừng đỏ tươi cay nồng, trồng hữu cơ. Gia vị, xào, muối ớt, nước chấm.'),
    ('Sả tươi', 'Gia vị', 'bó', (15000, 22000), ['Long An', 'Tiền Giang'],
     'Sả tươi thơm nồng. Ướp thịt, nấu lẩu, pha trà sả chanh giải nhiệt.'),
    ('Nấm bào ngư', 'Nấm', 'kg', (45000, 65000), ['Củ Chi'],
     'Nấm bào ngư trắng tươi, trồng nhà kính sạch. Xào, lẩu, nấu cháo. Giàu protein thực vật.'),
    ('Bí đỏ hồ lô', 'Rau củ', 'kg', (18000, 28000), ['Đồng Nai'],
     'Bí đỏ hồ lô ruột vàng cam, bột dẻo ngọt. Canh, chè, hấp, soup.'),
    ('Cam sành', 'Trái cây', 'kg', (35000, 55000), ['Hà Giang', 'Vĩnh Long'],
     'Cam sành ruột đỏ, mọng nước, giàu vitamin C, ngọt thanh.'),
    ('Chuối già', 'Trái cây', 'kg', (15000, 25000), ['Đồng Nai'],
     'Chuối già hương thơm, ngọt vừa, giàu kali, tốt cho tim mạch.'),
    ('Dưa hấu', 'Trái cây', 'trái', (40000, 80000), ['Long An'],
     'Dưa hấu ruột đỏ, ngọt mát, giải nhiệt mùa hè.'),
    ('Dưa lưới', 'Trái cây', 'trái', (60000, 120000), ['Vĩnh Long'],
     'Dưa lưới Nhật, ruột vàng, ngọt thơm, ăn tráng miệng.'),
    ('Cải ngọt', 'Rau lá', 'bó', (8000, 14000), ['Đà Lạt'],
     'Cải ngọt thân giòn, lá xanh, xào tỏi hoặc nấu canh.'),
    ('Cải thìa', 'Rau lá', 'bó', (8000, 14000), ['Đà Lạt'],
     'Cải thìa giòn ngọt, thường dùng xào dầu hào.'),
    ('Rau dền', 'Rau lá', 'bó', (8000, 14000), ['Long An'],
     'Rau dền đỏ giàu chất sắt, nấu canh thanh mát.'),
    ('Xà lách Mỹ', 'Rau lá', 'kg', (30000, 50000), ['Đà Lạt'],
     'Xà lách Mỹ giòn, dùng salad hoặc cuốn thịt.'),
    ('Cà rốt', 'Rau củ', 'kg', (20000, 30000), ['Đà Lạt'],
     'Cà rốt Đà Lạt giòn ngọt, giàu beta-carotene tốt cho mắt.'),
    ('Khoai tây', 'Rau củ', 'kg', (25000, 35000), ['Đà Lạt'],
     'Khoai tây Đà Lạt, dùng chiên, hầm, nấu súp.'),
    ('Củ cải trắng', 'Rau củ', 'kg', (15000, 22000), ['Đà Lạt'],
     'Củ cải trắng giòn ngọt, hầm canh sườn rất ngon.'),
    ('Hành tây', 'Rau củ', 'kg', (18000, 28000), ['Lâm Đồng'],
     'Hành tây tím, vị ngọt thanh, dùng xào, salad.'),
    ('Tỏi', 'Gia vị', 'kg', (60000, 90000), ['Lý Sơn'],
     'Tỏi cô đơn Lý Sơn, thơm nồng, tăng đề kháng.'),
    ('Gừng tươi', 'Gia vị', 'kg', (35000, 55000), ['Cao Bằng'],
     'Gừng tươi cay nồng, ấm bụng, làm trà gừng.'),
    ('Tiêu xanh', 'Gia vị', 'kg', (180000, 280000), ['Phú Quốc'],
     'Tiêu xanh Phú Quốc, vị thơm cay đặc trưng.'),
    ('Đậu xanh', 'Ngũ cốc', 'kg', (30000, 45000), ['An Giang'],
     'Đậu xanh tách vỏ nấu chè, làm bánh.'),
    ('Đậu đen', 'Ngũ cốc', 'kg', (35000, 50000), ['An Giang'],
     'Đậu đen giàu protein, nấu chè, hầm canh.'),
    ('Yến mạch', 'Ngũ cốc', 'gói', (45000, 75000), ['Nhập khẩu'],
     'Yến mạch nguyên cám, ăn sáng healthy.'),
]

QUESTION_TEMPLATES = [
    'Tôi muốn mua đồ nấu canh chua', 'Có gì để nấu lẩu không',
    'Trái cây giàu vitamin C có loại nào', 'Tư vấn rau giảm cân giúp mình',
    'Đồ ăn sáng healthy có gì', 'Mua đồ làm salad', 'Có rau hữu cơ không',
    'Có gì để xào tỏi', 'Trái cây ngọt thanh', 'Đồ làm sinh tố',
    'Đồ nấu canh chua cá lóc', 'Mua đồ làm gỏi cuốn', 'Rau mầm có sẵn không',
    'Có gạo ngon không', 'Đồ ướp thịt nướng', 'Trà giải nhiệt',
    'Mình muốn ăn đồ chay', 'Có nấm gì hôm nay', 'Đồ hấp cho trẻ em',
    'Trái cây cho bà bầu', 'Đồ tăng cường miễn dịch', 'Có ớt nồng không',
    'Mua đồ làm bánh', 'Sản phẩm sạch VietGAP có không', 'Tư vấn đồ ăn cho người tiểu đường',
    'Đồ nấu cháo dinh dưỡng', 'Mua xoài cát Hòa Lộc', 'Bưởi da xanh tươi không',
    'Cà chua Đà Lạt còn không', 'Có khoai lang mật không',
]


def reset_all():
    """Xóa toàn bộ dữ liệu cũ. Cẩn thận khi chạy production."""
    print('[!] Reset all data...')
    db.session.execute(db.text('DELETE FROM ai_conversations'))
    db.session.execute(db.text('DELETE FROM return_requests'))
    db.session.execute(db.text('DELETE FROM reviews'))
    db.session.execute(db.text('DELETE FROM shipments'))
    db.session.execute(db.text('DELETE FROM payments'))
    db.session.execute(db.text('DELETE FROM order_items'))
    db.session.execute(db.text('DELETE FROM orders'))
    db.session.execute(db.text('DELETE FROM products'))
    db.session.execute(db.text('DELETE FROM categories'))
    db.session.execute(db.text('DELETE FROM users'))
    db.session.commit()
    print('[OK] Reset done.')


def seed_categories():
    if Category.query.count() > 0:
        return
    for name, desc in CATEGORIES:
        db.session.add(Category(name=name, description=desc))
    db.session.commit()
    print(f'[OK] {len(CATEGORIES)} categories created.')


def seed_default_accounts():
    if not User.query.filter_by(username='admin').first():
        u = User(username='admin', email='admin@nongsan.vn', full_name='Quản Trị Viên',
                 phone='0901234567', address='TP. Hồ Chí Minh', role='admin', is_active=True)
        u.set_password('admin123')
        db.session.add(u)

    if not User.query.filter_by(username='khachhang').first():
        u = User(username='khachhang', email='khach@gmail.com', full_name='Nguyễn Văn A',
                 phone='0912345678', address='123 Đường ABC, Q1, TP.HCM', role='buyer', is_active=True)
        u.set_password('123456')
        db.session.add(u)

    if not User.query.filter_by(username='seller').first():
        u = User(username='seller', email='seller@nongsan.vn', full_name='Người Bán Mẫu',
                 phone='0988888888', address='Thái Nguyên', role='seller', is_active=True)
        u.set_password('seller123')
        db.session.add(u)

    db.session.commit()
    print('[OK] Default accounts ensured (admin/admin123, khachhang/123456, seller/seller123)')


def seed_users(target_buyers=210, target_sellers=10):
    """Sinh thêm user buyer + seller."""
    existing_buyers = User.query.filter_by(role='buyer').count()
    existing_sellers = User.query.filter_by(role='seller').count()

    new_sellers = []
    for i in range(max(0, target_sellers - existing_sellers)):
        username = f'seller{i+2:03d}'
        if User.query.filter_by(username=username).first():
            continue
        full_name = fake.name() if fake else f'Seller {i+2}'
        u = User(
            username=username,
            email=f'{username}@nongsan.vn',
            full_name=full_name,
            phone=f'09{random.randint(10000000, 99999999)}',
            address=fake.address().replace('\n', ', ') if fake else 'Việt Nam',
            role='seller',
            is_active=True,
        )
        u.set_password('seller123')
        db.session.add(u)
        new_sellers.append(u)

    new_buyers = []
    for i in range(max(0, target_buyers - existing_buyers)):
        username = f'buyer{i+1:04d}'
        if User.query.filter_by(username=username).first():
            continue
        full_name = fake.name() if fake else f'Khách {i+1}'
        u = User(
            username=username,
            email=f'{username}@gmail.com',
            full_name=full_name,
            phone=f'09{random.randint(10000000, 99999999)}',
            address=fake.address().replace('\n', ', ') if fake else 'Việt Nam',
            role='buyer',
            is_active=True,
        )
        u.set_password('123456')
        db.session.add(u)
        new_buyers.append(u)

    db.session.commit()
    print(f'[OK] +{len(new_sellers)} sellers, +{len(new_buyers)} buyers')


def seed_products(target=320):
    """Sinh sản phẩm cho đến khi đạt target."""
    existing = Product.query.count()
    if existing >= target:
        print(f'[SKIP] Already {existing} products (>= {target}).')
        return

    sellers = User.query.filter_by(role='seller', is_active=True).all()
    if not sellers:
        print('[!] No sellers found. Skipping products.')
        return

    cats_map = {c.name: c.id for c in Category.query.all()}

    need = target - existing
    created = 0
    for _ in range(need):
        tpl = random.choice(PRODUCT_TEMPLATES)
        name_base, cat_name, unit, price_range, origins, desc = tpl
        # variations
        variant_suffixes = ['', ' loại 1', ' đặc biệt', ' organic', ' VietGAP', ' Đà Lạt', ' tuyển chọn',
                            ' nhà vườn', ' sạch']
        name = (name_base + random.choice(variant_suffixes)).strip()
        seller = random.choice(sellers)
        price = random.randint(price_range[0] // 1000, price_range[1] // 1000) * 1000
        stock = random.randint(20, 500)
        origin = random.choice(origins)

        p = Product(
            seller_id=seller.id,
            category_id=cats_map.get(cat_name),
            name=name,
            description=desc,
            price=price,
            stock=stock,
            unit=unit,
            category=cat_name,
            origin=origin,
            is_visible=True,
            image='default.jpg',
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 120)),
        )
        db.session.add(p)
        created += 1
        if created % 100 == 0:
            db.session.commit()
            print(f'  ... committed {created} products')

    db.session.commit()
    print(f'[OK] +{created} products. Total = {Product.query.count()}')


def seed_orders(target=520):
    """Sinh đơn hàng + order_items + payment + shipment."""
    existing = Order.query.count()
    if existing >= target:
        print(f'[SKIP] Already {existing} orders (>= {target}).')
        return

    buyers = User.query.filter_by(role='buyer').all()
    products = Product.query.filter_by(is_visible=True).all()
    if not buyers or not products:
        print('[!] No buyers or products. Skipping orders.')
        return

    statuses_pool = ['Đã hoàn thành'] * 6 + ['Đang giao'] * 2 + ['Đang xử lý'] * 1 + ['Đã hủy'] * 1
    seller_status_map = {
        'Đã hoàn thành': 'Đã giao',
        'Đang giao': 'Đang giao',
        'Đang xử lý': 'Đơn mới',
        'Đã hủy': 'Đơn mới',
    }
    payment_methods = ['COD', 'Bank', 'QR']
    carriers = ['GHN', 'Viettel Post', 'J&T Express', 'Ninja Van', 'GHTK']

    need = target - existing
    created = 0
    for _ in range(need):
        buyer = random.choice(buyers)
        order_status = random.choice(statuses_pool)
        order_date = datetime.utcnow() - timedelta(days=random.randint(0, 90),
                                                    hours=random.randint(0, 23))

        order = Order(
            user_id=buyer.id,
            order_date=order_date,
            status=order_status,
            total_amount=0,
            shipping_name=buyer.full_name,
            shipping_phone=buyer.phone or '0900000000',
            shipping_address=buyer.address or 'Việt Nam',
            note='',
        )
        db.session.add(order)
        db.session.flush()

        n_items = random.randint(1, 4)
        chosen = random.sample(products, k=min(n_items, len(products)))
        total = 0
        for prod in chosen:
            qty = random.randint(1, 5)
            sub = qty * prod.price
            total += sub
            seller_st = seller_status_map[order_status]
            item = OrderItem(
                order_id=order.id,
                product_id=prod.id,
                product_name=prod.name,
                product_price=prod.price,
                quantity=qty,
                subtotal=sub,
                seller_status=seller_st,
            )
            if seller_st in ('Đang giao', 'Đã giao'):
                item.shipping_carrier = random.choice(carriers)
                item.shipping_code = secrets.token_hex(5).upper()
                item.shipping_updated_at = order_date + timedelta(days=random.randint(0, 4))
            db.session.add(item)
            db.session.flush()

            if seller_st in ('Đang giao', 'Đã giao'):
                ship = Shipment(
                    order_item_id=item.id,
                    carrier=item.shipping_carrier,
                    tracking_code=item.shipping_code,
                    status='Đã giao' if seller_st == 'Đã giao' else 'Đang giao',
                    shipped_at=order_date + timedelta(days=random.randint(0, 1)),
                    delivered_at=(order_date + timedelta(days=random.randint(2, 5))) if seller_st == 'Đã giao' else None,
                )
                db.session.add(ship)

        order.total_amount = total
        method = random.choice(payment_methods)
        pay_status = 'Đã thanh toán' if order_status == 'Đã hoàn thành' or method != 'COD' else 'Chờ thanh toán'
        if order_status == 'Đã hủy':
            pay_status = 'Hoàn tiền' if method != 'COD' else 'Chờ thanh toán'
        payment = Payment(
            order_id=order.id,
            method=method,
            amount=total,
            status=pay_status,
            transaction_ref=f'TXN{order.id}-{secrets.token_hex(3).upper()}',
            paid_at=(order_date + timedelta(days=random.randint(0, 2))) if pay_status == 'Đã thanh toán' else None,
        )
        db.session.add(payment)

        created += 1
        if created % 100 == 0:
            db.session.commit()
            print(f'  ... committed {created} orders')

    db.session.commit()
    print(f'[OK] +{created} orders. Total = {Order.query.count()}')


def seed_reviews(target=320):
    """Sinh review cho các order_items đã giao."""
    existing = Review.query.count()
    if existing >= target:
        print(f'[SKIP] Already {existing} reviews (>= {target}).')
        return

    delivered_items = (
        OrderItem.query.filter(OrderItem.seller_status == 'Đã giao')
        .filter(~OrderItem.id.in_(db.session.query(Review.order_item_id)))
        .all()
    )
    if not delivered_items:
        print('[!] No delivered items eligible for review.')
        return

    pos_comments = [
        'Sản phẩm tươi, đóng gói cẩn thận.',
        'Giao hàng nhanh, chất lượng tốt.',
        'Rất hài lòng, sẽ ủng hộ tiếp.',
        'Hàng đúng mô tả, giá hợp lý.',
        'Tươi ngon, gia đình rất thích.',
        'Đáng đồng tiền bát gạo.',
        'Shop tư vấn nhiệt tình.',
        'Sản phẩm chất lượng, đóng gói chắc chắn.',
    ]
    neutral_comments = [
        'Tạm ổn, lần sau mua thử lại.',
        'Bình thường, không có gì nổi bật.',
        'Giao hàng hơi chậm nhưng sản phẩm ổn.',
    ]
    neg_comments = [
        'Sản phẩm chưa được tươi như mong đợi.',
        'Đóng gói hơi sơ sài.',
        'Chất lượng không đồng đều.',
    ]

    need = target - existing
    random.shuffle(delivered_items)
    delivered_items = delivered_items[:need]

    for item in delivered_items:
        if not item.product or not item.product.seller_id:
            continue
        rating = random.choices([5, 4, 3, 2, 1], weights=[55, 25, 12, 5, 3])[0]
        if rating >= 4:
            comment = random.choice(pos_comments)
        elif rating == 3:
            comment = random.choice(neutral_comments)
        else:
            comment = random.choice(neg_comments)

        rev = Review(
            order_item_id=item.id,
            product_id=item.product_id,
            buyer_id=item.order.user_id,
            seller_id=item.product.seller_id,
            rating=rating,
            content=comment,
            seller_reply=random.choice(['Cảm ơn bạn đã ủng hộ shop!', None, None, 'Shop ghi nhận góp ý của bạn.']),
            replied_at=datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            created_at=item.shipping_updated_at or datetime.utcnow() - timedelta(days=random.randint(0, 60)),
        )
        db.session.add(rev)

    db.session.commit()
    print(f'[OK] Reviews total = {Review.query.count()}')


def seed_ai_conversations(target=220):
    """Sinh hội thoại AI mẫu."""
    existing = AIConversation.query.count()
    if existing >= target:
        print(f'[SKIP] Already {existing} AI conversations (>= {target}).')
        return

    buyers = User.query.filter_by(role='buyer').all()
    products = Product.query.filter_by(is_visible=True).all()
    if not products:
        print('[!] No products. Skipping AI conversations.')
        return

    sources = ['chat'] * 6 + ['search'] * 4
    intents = ['product_search', 'product_search', 'no_match', 'recipe', 'health']

    need = target - existing
    for i in range(need):
        question = random.choice(QUESTION_TEMPLATES)
        sample = random.sample(products, k=min(3, len(products)))
        names = ', '.join(p.name for p in sample)
        answer = (
            f'Mình tìm được {len(sample)} sản phẩm phù hợp. Gợi ý: {names}.'
            ' Bạn có thể bấm vào để xem chi tiết.'
        )
        score = round(random.uniform(0.15, 0.95), 3)
        conv = AIConversation(
            user_id=random.choice(buyers).id if buyers and random.random() < 0.85 else None,
            session_key=secrets.token_hex(8),
            question=question,
            answer=answer,
            intent=random.choice(intents),
            score=score,
            source=random.choice(sources),
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 60),
                                                     minutes=random.randint(0, 1440)),
        )
        db.session.add(conv)
        if (i + 1) % 100 == 0:
            db.session.commit()
            print(f'  ... committed {i + 1} conversations')

    db.session.commit()
    print(f'[OK] AI conversations total = {AIConversation.query.count()}')


def ensure_schema_compat():
    """Bổ sung cột thiếu khi DB cũ."""
    try:
        cols = db.session.execute(db.text("PRAGMA table_info(products)")).fetchall()
        names = {c[1] for c in cols}
        if 'seller_id' not in names:
            db.session.execute(db.text("ALTER TABLE products ADD COLUMN seller_id INTEGER"))
        if 'category_id' not in names:
            db.session.execute(db.text("ALTER TABLE products ADD COLUMN category_id INTEGER"))
        cols = db.session.execute(db.text("PRAGMA table_info(order_items)")).fetchall()
        names = {c[1] for c in cols}
        for col, ddl in [
            ('seller_status', "ALTER TABLE order_items ADD COLUMN seller_status VARCHAR(30) DEFAULT 'Đơn mới'"),
            ('shipping_code', "ALTER TABLE order_items ADD COLUMN shipping_code VARCHAR(100)"),
            ('shipping_carrier', "ALTER TABLE order_items ADD COLUMN shipping_carrier VARCHAR(100)"),
            ('shipping_updated_at', "ALTER TABLE order_items ADD COLUMN shipping_updated_at DATETIME"),
        ]:
            if col not in names:
                db.session.execute(db.text(ddl))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'[WARN] schema compat: {e}')


def seed_de_cuong(*, reset=False, small=False, fixed=False):
    """Sinh dữ liệu theo PI 4.2 (gọi từ CLI, Render build, hoặc bootstrap app)."""
    if fixed:
        random.seed(42)
        print('[OK] Fixed seed: random.seed(42)')

    db.create_all()
    ensure_schema_compat()
    print('[OK] Tables ready.')

    if reset:
        reset_all()

    seed_categories()
    seed_default_accounts()

    if small:
        seed_users(target_buyers=10, target_sellers=3)
        seed_products(target=15)
        seed_orders(target=15)
        seed_reviews(target=10)
        seed_ai_conversations(target=10)
    else:
        if fake is None:
            print('[WARN] Faker chưa cài. Chạy: pip install Faker')
        t = SEED_TARGETS
        seed_users(target_buyers=t['buyers'], target_sellers=t['sellers'])
        seed_products(target=t['products'])
        seed_orders(target=t['orders'])
        seed_reviews(target=t['reviews'])
        seed_ai_conversations(target=t['ai_conversations'])

    counts = {
        'users': User.query.count(),
        'products': Product.query.count(),
        'orders': Order.query.count(),
        'reviews': Review.query.count(),
        'ai_conversations': AIConversation.query.count(),
    }

    print('\n[SUMMARY]')
    print(f'  Users:           {counts["users"]} (buyers={User.query.filter_by(role="buyer").count()}, sellers={User.query.filter_by(role="seller").count()})')
    print(f'  Categories:      {Category.query.count()}')
    print(f'  Products:        {counts["products"]}')
    print(f'  Orders:          {counts["orders"]}')
    print(f'  Order Items:     {OrderItem.query.count()}')
    print(f'  Payments:        {Payment.query.count()}')
    print(f'  Shipments:       {Shipment.query.count()}')
    print(f'  Reviews:         {counts["reviews"]}')
    print(f'  AI Conversations:{counts["ai_conversations"]}')
    print('\n[DE CUONG]')
    for label, key in [
        ('Users', 'users'),
        ('Products', 'products'),
        ('Orders', 'orders'),
        ('Reviews', 'reviews'),
        ('AI Conversations', 'ai_conversations'),
    ]:
        val = counts[key]
        need = DE_CUONG_MIN[key]
        ok = 'DAT' if val >= need else 'CHUA DAT'
        print(f'  {label}: {val} (yeu cau >= {need}) -> {ok}')
    print('\n[DONE] Seed completed!')
    return counts


def data_meets_de_cuong():
    """True nếu DB đã đủ ngưỡng đề cương."""
    try:
        return (
            Product.query.count() >= DE_CUONG_MIN['products']
            and User.query.count() >= DE_CUONG_MIN['users']
            and Order.query.count() >= DE_CUONG_MIN['orders']
            and Review.query.count() >= DE_CUONG_MIN['reviews']
            and AIConversation.query.count() >= DE_CUONG_MIN['ai_conversations']
        )
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reset', action='store_true', help='Xóa toàn bộ dữ liệu cũ')
    parser.add_argument('--small', action='store_true', help='Seed nhỏ cho test')
    parser.add_argument(
        '--fixed', action='store_true',
        help='Sinh dữ liệu ổn định (random.seed=42), phù hợp nộp đồ án',
    )
    args = parser.parse_args()

    with app.app_context():
        seed_de_cuong(reset=args.reset, small=args.small, fixed=args.fixed)


if __name__ == '__main__':
    main()
