from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ============================================================
# BẢNG USER - Quản lý người dùng (Admin / Seller / Buyer)
# ============================================================
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='buyer')  # 'admin' | 'seller' | 'buyer'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    products = db.relationship('Product', backref='seller', lazy='dynamic', foreign_keys='Product.seller_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def is_seller(self):
        return self.role == 'seller'

    def is_buyer(self):
        return self.role == 'buyer'

    def __repr__(self):
        return f'<User {self.username}>'


# ============================================================
# BẢNG CATEGORY - Danh mục sản phẩm (chuẩn hóa)
# ============================================================
class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.String(300), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship('Product', backref='category_ref', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


# ============================================================
# BẢNG PRODUCT - Sản phẩm nông sản
# ============================================================
class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    unit = db.Column(db.String(20), nullable=False, default='kg')
    category = db.Column(db.String(100), nullable=True, index=True)  # giữ tương thích, sẽ đồng bộ với category_id
    image = db.Column(db.String(300), nullable=True, default='default.jpg')
    is_visible = db.Column(db.Boolean, default=True)
    origin = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')

    def __repr__(self):
        return f'<Product {self.name}>'


# ============================================================
# BẢNG ORDER - Đơn hàng
# ============================================================
class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(30), nullable=False, default='Đang xử lý')
    total_amount = db.Column(db.Float, nullable=False, default=0)
    shipping_name = db.Column(db.String(150), nullable=False)
    shipping_phone = db.Column(db.String(20), nullable=False)
    shipping_address = db.Column(db.String(500), nullable=False)
    note = db.Column(db.Text, nullable=True)
    admin_confirmed_at = db.Column(db.DateTime, nullable=True)

    items = db.relationship('OrderItem', backref='order', lazy='joined', cascade='all, delete-orphan')
    payment = db.relationship('Payment', backref='order', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Order #{self.id} - {self.status}>'


# ============================================================
# BẢNG ORDER_ITEM - Chi tiết từng dòng sản phẩm trong đơn
# ============================================================
class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    product_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Float, nullable=False, default=0)
    seller_status = db.Column(db.String(30), nullable=False, default='Đơn mới')
    shipping_code = db.Column(db.String(100), nullable=True)
    shipping_carrier = db.Column(db.String(100), nullable=True)
    shipping_updated_at = db.Column(db.DateTime, nullable=True)

    shipment = db.relationship('Shipment', backref='order_item', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<OrderItem {self.product_name} x{self.quantity}>'


# ============================================================
# BẢNG PAYMENT - Thanh toán đơn hàng (1-1 với Order)
# ============================================================
class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False, unique=True)
    method = db.Column(db.String(30), nullable=False, default='COD')  # COD | Bank | QR
    amount = db.Column(db.Float, nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default='Chờ thanh toán')
    # Chờ thanh toán | Đã thanh toán | Hoàn tiền | Thất bại
    transaction_ref = db.Column(db.String(120), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Payment Order#{self.order_id} {self.method} {self.status}>'


# ============================================================
# BẢNG SHIPMENT - Vận chuyển từng dòng sản phẩm (1-1 với OrderItem)
# ============================================================
class Shipment(db.Model):
    __tablename__ = 'shipments'

    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), nullable=False, unique=True)
    carrier = db.Column(db.String(100), nullable=True)
    tracking_code = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(30), nullable=False, default='Chuẩn bị hàng')
    # Chuẩn bị hàng | Đang giao | Đã giao | Trả về
    shipped_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Shipment Item#{self.order_item_id} {self.status}>'


# ============================================================
# BẢNG REVIEW - Đánh giá sản phẩm và phản hồi seller
# ============================================================
class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), nullable=False, unique=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False, default=5)
    content = db.Column(db.Text, nullable=True)
    seller_reply = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replied_at = db.Column(db.DateTime, nullable=True)

    order_item = db.relationship('OrderItem', backref=db.backref('review', uselist=False))
    product = db.relationship('Product', backref='reviews')
    buyer = db.relationship('User', foreign_keys=[buyer_id], backref='given_reviews')
    seller = db.relationship('User', foreign_keys=[seller_id], backref='received_reviews')


# ============================================================
# BẢNG RETURN_REQUEST - Yêu cầu đổi/trả/hủy sau bán
# ============================================================
class ReturnRequest(db.Model):
    __tablename__ = 'return_requests'

    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), nullable=False, unique=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    request_type = db.Column(db.String(20), nullable=False, default='return')  # return/exchange/cancel
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default='Chờ xử lý')
    seller_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    order_item = db.relationship('OrderItem', backref=db.backref('return_request', uselist=False))
    buyer = db.relationship('User', foreign_keys=[buyer_id], backref='return_requests')
    seller = db.relationship('User', foreign_keys=[seller_id], backref='managed_returns')


# ============================================================
# BẢNG AI_CONVERSATION - Lịch sử hội thoại AI (chatbot/CSKH)
# ============================================================
class AIConversation(db.Model):
    __tablename__ = 'ai_conversations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    session_key = db.Column(db.String(80), nullable=True, index=True)  # cho khách chưa đăng nhập
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(120), nullable=True)
    score = db.Column(db.Float, nullable=True)
    source = db.Column(db.String(30), nullable=False, default='chat')  # chat | search | recommend
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='ai_conversations')

    def __repr__(self):
        return f'<AIConversation #{self.id} {self.source}>'
