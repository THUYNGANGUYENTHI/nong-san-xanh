import os
import logging
import secrets
import threading
from datetime import datetime
from functools import wraps
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse

from flask import (
    Flask, render_template, redirect, url_for, flash, request, session, jsonify, abort,
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user,
)
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect

from config import Config, DE_CUONG_MIN
from models import (
    db, User, Category, Product, Order, OrderItem,
    Payment, Shipment, Review, ReturnRequest, AIConversation,
)
from forms import LoginForm, RegisterForm, ProductForm, CheckoutForm, ChatForm, ProfileForm
from ai_engine import ai_engine

try:
    import cloudinary
    import cloudinary.uploader
except Exception:
    cloudinary = None

# ============================================================
# KHỞI TẠO APP
# ============================================================
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Vui lòng đăng nhập để tiếp tục.'
login_manager.login_message_category = 'warning'


# ============================================================
# LOGGING (NFR: ghi log thao tác và lỗi)
# ============================================================
def setup_logging():
    level = getattr(logging, str(app.config.get('LOG_LEVEL', 'INFO')).upper(), logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s - %(message)s')
    app.logger.handlers.clear()

    # Ghi ra console để thấy lỗi trên Render Logs
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    app.logger.addHandler(stream_handler)

    try:
        log_dir = app.config.get('LOG_DIR')
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        if log_dir:
            file_handler = RotatingFileHandler(
                os.path.join(log_dir, 'app.log'), maxBytes=2_000_000, backupCount=5, encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            app.logger.addHandler(file_handler)
    except OSError as exc:
        app.logger.warning('File logging disabled: %s', exc)

    app.logger.setLevel(level)
    app.logger.propagate = False


setup_logging()

if cloudinary and app.config.get('CLOUDINARY_CLOUD_NAME'):
    cloudinary.config(
        cloud_name=app.config.get('CLOUDINARY_CLOUD_NAME'),
        api_key=app.config.get('CLOUDINARY_API_KEY'),
        api_secret=app.config.get('CLOUDINARY_API_SECRET'),
        secure=True,
    )


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ============================================================
# DECORATORS PHÂN QUYỀN
# ============================================================
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def seller_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_seller():
            abort(403)
        if not current_user.is_active:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def can_manage_product_crud(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_admin():
        return True
    return user.is_seller() and bool(user.is_active)


# ============================================================
# HELPER: Upload ảnh
# ============================================================
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_external_image_url(value):
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def build_image_url(image_value):
    if is_external_image_url(image_value):
        return image_value
    image_name = image_value or 'default.jpg'
    return url_for('static', filename=f'uploads/{image_name}')


def upload_to_cloudinary(file):
    if not cloudinary:
        return None
    cloud_name = app.config.get('CLOUDINARY_CLOUD_NAME')
    api_key = app.config.get('CLOUDINARY_API_KEY')
    api_secret = app.config.get('CLOUDINARY_API_SECRET')
    if not (cloud_name and api_key and api_secret):
        return None

    upload_options = {
        'folder': app.config.get('CLOUDINARY_FOLDER') or 'nongsan-products',
        'resource_type': 'image',
    }
    upload_preset = app.config.get('CLOUDINARY_UPLOAD_PRESET')
    if upload_preset:
        upload_options['upload_preset'] = upload_preset

    result = cloudinary.uploader.upload(file, **upload_options)
    return result.get('secure_url')


def save_image(file):
    if not can_manage_product_crud(current_user):
        abort(403)
    if file and file.filename and allowed_file(file.filename):
        try:
            cloudinary_url = upload_to_cloudinary(file)
            if cloudinary_url:
                return cloudinary_url
        except Exception as exc:
            app.logger.warning(f'Cloudinary upload failed, fallback to local: {exc}')
            file.stream.seek(0)

        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_name = f"{name}_{secrets.token_hex(8)}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        file.save(filepath)
        return unique_name
    return None


def has_uploaded_file(file_data):
    return hasattr(file_data, 'filename') and bool(file_data.filename)


# ============================================================
# MIGRATION: Bổ sung cột/bảng cho DB SQLite cũ
# ============================================================
def ensure_sqlite_schema():
    products_cols = db.session.execute(db.text("PRAGMA table_info(products)")).fetchall()
    product_col_names = {col[1] for col in products_cols}
    if 'seller_id' not in product_col_names:
        db.session.execute(db.text("ALTER TABLE products ADD COLUMN seller_id INTEGER"))
        db.session.commit()
    if 'category_id' not in product_col_names:
        db.session.execute(db.text("ALTER TABLE products ADD COLUMN category_id INTEGER"))
        db.session.commit()

    order_items_cols = db.session.execute(db.text("PRAGMA table_info(order_items)")).fetchall()
    order_item_col_names = {col[1] for col in order_items_cols}
    for col, ddl in [
        ('seller_status', "ALTER TABLE order_items ADD COLUMN seller_status VARCHAR(30) DEFAULT 'Đơn mới'"),
        ('shipping_code', "ALTER TABLE order_items ADD COLUMN shipping_code VARCHAR(100)"),
        ('shipping_carrier', "ALTER TABLE order_items ADD COLUMN shipping_carrier VARCHAR(100)"),
        ('shipping_updated_at', "ALTER TABLE order_items ADD COLUMN shipping_updated_at DATETIME"),
    ]:
        if col not in order_item_col_names:
            db.session.execute(db.text(ddl))
            db.session.commit()

    orders_cols = db.session.execute(db.text("PRAGMA table_info(orders)")).fetchall()
    order_col_names = {col[1] for col in orders_cols}
    if 'admin_confirmed_at' not in order_col_names:
        db.session.execute(db.text("ALTER TABLE orders ADD COLUMN admin_confirmed_at DATETIME"))
        db.session.commit()


# Shopee-style: hủy khi seller chưa chuẩn bị/gửi; chặn khi admin HOẶC seller bắt đầu giao hàng.
SELLER_PREP_OR_SHIP_STATUSES = frozenset(['Đang chuẩn bị', 'Đang giao', 'Đã giao'])


def order_is_cancelled(order):
    return order.status == 'Đã hủy'


def order_admin_confirmed(order):
    return order.admin_confirmed_at is not None


def buyer_can_cancel_item(item, order):
    if order.status in ('Đã hủy', 'Đã hoàn thành'):
        return False
    item_status = item.seller_status or 'Đơn mới'
    if item_status in SELLER_PREP_OR_SHIP_STATUSES:
        return False
    if order_admin_confirmed(order):
        return False
    return item_status in ('Đơn mới', 'Đã xác nhận')


def buyer_can_cancel_order(order):
    if not order.items:
        return False
    return all(buyer_can_cancel_item(item, order) for item in order.items)


def buyer_cancel_block_reason(order):
    if order.status == 'Đã hủy':
        return 'Đơn hàng đã được hủy.'
    if order.status == 'Đã hoàn thành':
        return 'Đơn hàng đã hoàn thành.'
    if order_admin_confirmed(order):
        return 'Admin đã xác nhận nhận đơn — không thể hủy.'
    for item in order.items:
        status = item.seller_status or 'Đơn mới'
        if status in SELLER_PREP_OR_SHIP_STATUSES:
            return 'Seller đang chuẩn bị hoặc đang giao hàng — không thể hủy.'
    return None


def sync_order_status_from_items(order):
    if order.status == 'Đã hủy':
        return
    item_statuses = [item.seller_status for item in order.items]
    if not item_statuses:
        return
    if all(status == 'Đã giao' for status in item_statuses):
        order.status = 'Đã hoàn thành'
    elif any(status in ('Đang giao', 'Đã giao') for status in item_statuses):
        order.status = 'Đang giao'
    else:
        order.status = 'Đang xử lý'


def get_seller_order_items_query():
    return (
        OrderItem.query.join(Product, OrderItem.product_id == Product.id)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Product.seller_id == current_user.id)
    )


# ============================================================
# AI INDEX
# ============================================================
def rebuild_ai_index():
    products = Product.query.filter_by(is_visible=True).all()
    ai_engine.build_index(products)


_bootstrap_lock = threading.Lock()
_bootstrapped = False


def bootstrap_database():
    """Tạo bảng + seed đủ ngưỡng đề cương khi chạy production (Render)."""
    global _bootstrapped
    with _bootstrap_lock:
        if _bootstrapped:
            return
        with app.app_context():
            db.create_all()
            try:
                ensure_sqlite_schema()
            except Exception as exc:
                app.logger.warning('Schema migration skipped: %s', exc)

            product_count = Product.query.count()
            if product_count == 0:
                app.logger.warning(
                    'DB trong — can chay seed luc build: python seed.py --reset --fixed'
                )
            else:
                app.logger.info('DB co %s san pham', product_count)

            try:
                if product_count > 0:
                    rebuild_ai_index()
            except Exception as exc:
                app.logger.warning('AI index skipped: %s', exc)

        _bootstrapped = True


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/health')
def health():
    """Kiểm tra DB + đủ ngưỡng đề cương PI 4.2."""
    try:
        from seed import data_meets_de_cuong
        counts = {
            'users': User.query.count(),
            'products': Product.query.count(),
            'orders': Order.query.count(),
            'reviews': Review.query.count(),
            'ai_conversations': AIConversation.query.count(),
        }
        de_cuong = {
            key: {
                'current': counts[key],
                'required': DE_CUONG_MIN[key],
                'ok': counts[key] >= DE_CUONG_MIN[key],
            }
            for key in DE_CUONG_MIN
        }
        return jsonify({
            'status': 'ok' if data_meets_de_cuong() else 'incomplete',
            'de_cuong': de_cuong,
            'counts': counts,
        })
    except Exception as exc:
        app.logger.exception('Health check failed')
        return jsonify({'status': 'error', 'message': str(exc)}), 500


def log_ai_conversation(question, answer, source='chat', intent=None, score=None):
    """Lưu hội thoại AI để phục vụ thống kê và yêu cầu PI 4.2."""
    try:
        conv = AIConversation(
            user_id=current_user.id if current_user.is_authenticated else None,
            session_key=session.get('_id') or session.get('csrf_token', '')[:32],
            question=question[:1000] if question else '',
            answer=answer[:2000] if answer else '',
            intent=intent,
            score=score,
            source=source,
        )
        db.session.add(conv)
        db.session.commit()
    except Exception as exc:
        app.logger.warning(f'Cannot log AIConversation: {exc}')
        db.session.rollback()


# ============================================================
# CONTEXT PROCESSOR
# ============================================================
@app.context_processor
def inject_cart_count():
    cart = session.get('cart', {})
    count = sum(item['quantity'] for item in cart.values())
    return dict(cart_count=count, image_url=build_image_url)


# ============================================================
# TRANG CHỦ
# ============================================================
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    query = request.args.get('q', '')

    products_query = Product.query.filter_by(is_visible=True)

    if category:
        products_query = products_query.filter_by(category=category)

    if query:
        all_visible = Product.query.filter_by(is_visible=True).all()
        ai_results = ai_engine.smart_search(query, all_visible, top_n=50)
        if ai_results:
            matched_ids = [p.id for p, score in ai_results]
            products_query = Product.query.filter(
                Product.id.in_(matched_ids),
                Product.is_visible == True,
            )
            top_summary = ', '.join([p.name for p, _ in ai_results[:5]]) or '(không có)'
            log_ai_conversation(
                question=query,
                answer=f'Tìm được {len(ai_results)} sản phẩm. Top: {top_summary}',
                source='search',
            )
        else:
            products_query = products_query.filter(
                db.or_(
                    Product.name.ilike(f'%{query}%'),
                    Product.description.ilike(f'%{query}%'),
                )
            )

    products = products_query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    categories = db.session.query(Product.category).filter(
        Product.is_visible == True, Product.category.isnot(None)
    ).distinct().all()
    categories = [c[0] for c in categories]

    return render_template('index.html', products=products, categories=categories,
                           current_category=category, search_query=query)


# ============================================================
# CHI TIẾT SẢN PHẨM
# ============================================================
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.is_visible and (not current_user.is_authenticated or not current_user.is_admin()):
        abort(404)
    return render_template('product_detail.html', product=product)


# ============================================================
# AUTHENTICATION
# ============================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Tên đăng nhập đã tồn tại!', 'danger')
            return render_template('register.html', form=form)
        if User.query.filter_by(email=form.email.data).first():
            flash('Email đã được sử dụng!', 'danger')
            return render_template('register.html', form=form)

        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            phone=form.phone.data,
            address=form.address.data,
            role='buyer',
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        app.logger.info(f'New user registered: {user.username}')
        flash('Đăng ký thành công! Hãy đăng nhập.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Tài khoản đã bị khóa.', 'danger')
                return render_template('login.html', form=form)
            login_user(user)
            app.logger.info(f'User login: {user.username} role={user.role}')
            flash(f'Chào mừng {user.full_name}!', 'success')
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            if user.is_admin():
                return redirect(url_for('admin_dashboard'))
            if user.is_seller():
                return redirect(url_for('seller_dashboard'))
            return redirect(url_for('index'))
        else:
            app.logger.warning(f'Login failed: username={form.username.data}')
            flash('Sai tên đăng nhập hoặc mật khẩu!', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    app.logger.info(f'User logout: {current_user.username}')
    logout_user()
    session.pop('cart', None)
    flash('Đã đăng xuất thành công.', 'info')
    return redirect(url_for('index'))


# ============================================================
# PROFILE: Xem / Cập nhật hồ sơ người dùng
# ============================================================
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        existing_email = User.query.filter(
            User.email == form.email.data,
            User.id != current_user.id
        ).first()
        if existing_email:
            flash('Email đã được sử dụng bởi tài khoản khác.', 'danger')
            return render_template('profile_edit.html', form=form)

        current_user.full_name = form.full_name.data.strip()
        current_user.email = form.email.data.strip().lower()
        current_user.phone = (form.phone.data or '').strip() or None
        current_user.address = (form.address.data or '').strip() or None
        db.session.commit()
        flash('Cập nhật hồ sơ thành công.', 'success')
        return redirect(url_for('profile'))
    return render_template('profile_edit.html', form=form)


# ============================================================
# GIỎ HÀNG (Session-based)
# ============================================================
@app.route('/cart')
def cart():
    cart_data = session.get('cart', {})
    items = []
    total = 0
    for product_id, item in cart_data.items():
        product = db.session.get(Product, int(product_id))
        if product:
            subtotal = product.price * item['quantity']
            items.append({
                'product': product,
                'quantity': item['quantity'],
                'subtotal': subtotal,
            })
            total += subtotal
    return render_template('cart.html', items=items, total=total)


@app.route('/cart/add/<int:product_id>', methods=['POST'])
def cart_add(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = request.form.get('quantity', 1, type=int)
    if quantity < 1:
        quantity = 1

    cart = session.get('cart', {})
    pid = str(product_id)

    if pid in cart:
        new_qty = cart[pid]['quantity'] + quantity
    else:
        new_qty = quantity

    if new_qty > product.stock:
        flash(f'Chỉ còn {product.stock} {product.unit} trong kho!', 'warning')
        new_qty = product.stock

    if new_qty > 0:
        cart[pid] = {'quantity': new_qty}
    session['cart'] = cart
    flash(f'Đã thêm "{product.name}" vào giỏ hàng!', 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/cart/update/<int:product_id>', methods=['POST'])
def cart_update(product_id):
    product = db.session.get(Product, product_id)
    quantity = request.form.get('quantity', 1, type=int)
    cart = session.get('cart', {})
    pid = str(product_id)

    if quantity <= 0:
        cart.pop(pid, None)
        flash('Đã xóa sản phẩm khỏi giỏ hàng.', 'info')
    else:
        if product and quantity > product.stock:
            quantity = product.stock
            flash(f'Chỉ còn {product.stock} sản phẩm trong kho!', 'warning')
        cart[pid] = {'quantity': quantity}

    session['cart'] = cart
    return redirect(url_for('cart'))


@app.route('/cart/remove/<int:product_id>')
def cart_remove(product_id):
    cart = session.get('cart', {})
    pid = str(product_id)
    if pid in cart:
        del cart[pid]
        session['cart'] = cart
        flash('Đã xóa sản phẩm khỏi giỏ hàng.', 'info')
    return redirect(url_for('cart'))


# ============================================================
# CHECKOUT - Tạo đơn + Payment
# ============================================================
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_data = session.get('cart', {})
    if not cart_data:
        flash('Giỏ hàng trống!', 'warning')
        return redirect(url_for('cart'))

    form = CheckoutForm()
    if request.method == 'GET':
        form.shipping_name.data = current_user.full_name
        form.shipping_phone.data = current_user.phone or ''
        form.shipping_address.data = current_user.address or ''

    items = []
    total = 0
    for product_id, item in cart_data.items():
        product = db.session.get(Product, int(product_id))
        if product:
            subtotal = product.price * item['quantity']
            items.append({
                'product': product,
                'quantity': item['quantity'],
                'subtotal': subtotal,
            })
            total += subtotal

    if form.validate_on_submit():
        order = Order(
            user_id=current_user.id,
            total_amount=total,
            shipping_name=form.shipping_name.data,
            shipping_phone=form.shipping_phone.data,
            shipping_address=form.shipping_address.data,
            note=form.note.data,
            status='Đang xử lý',
        )
        db.session.add(order)
        db.session.flush()

        for product_id, item in cart_data.items():
            product = db.session.get(Product, int(product_id))
            if product:
                qty = item['quantity']
                if product.stock >= qty:
                    product.stock -= qty
                else:
                    flash(f'Sản phẩm "{product.name}" không đủ hàng!', 'danger')
                    db.session.rollback()
                    return redirect(url_for('cart'))

                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    product_price=product.price,
                    quantity=qty,
                    subtotal=product.price * qty,
                )
                db.session.add(order_item)

        # Tạo payment record (UC Thanh toán)
        payment = Payment(
            order_id=order.id,
            method=form.payment_method.data,
            amount=total,
            status='Chờ thanh toán' if form.payment_method.data != 'COD' else 'Chờ thanh toán',
            transaction_ref=f'TXN{order.id}-{secrets.token_hex(4).upper()}',
        )
        db.session.add(payment)

        db.session.commit()
        session.pop('cart', None)
        app.logger.info(
            f'Order #{order.id} created by user={current_user.username} '
            f'total={total} payment={payment.method}'
        )
        flash(f'Đặt hàng thành công! Mã đơn hàng: #{order.id}', 'success')
        return redirect(url_for('order_payment', order_id=order.id))

    return render_template('checkout.html', form=form, items=items, total=total)


# ============================================================
# UC THANH TOÁN - Trang xác nhận thanh toán
# ============================================================
@app.route('/orders/<int:order_id>/payment', methods=['GET', 'POST'])
@login_required
def order_payment(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin():
        abort(403)

    payment = order.payment
    if not payment:
        payment = Payment(order_id=order.id, method='COD', amount=order.total_amount,
                          status='Chờ thanh toán')
        db.session.add(payment)
        db.session.commit()

    if request.method == 'POST' and payment.status == 'Chờ thanh toán':
        action = request.form.get('action')
        if action == 'confirm':
            payment.status = 'Đã thanh toán'
            payment.paid_at = datetime.utcnow()
            db.session.commit()
            app.logger.info(
                f'Payment confirmed: order={order.id} method={payment.method} '
                f'ref={payment.transaction_ref}'
            )
            flash('Đã xác nhận thanh toán (demo).', 'success')
            return redirect(url_for('order_detail', order_id=order.id))
        if action == 'change_method':
            new_method = request.form.get('method')
            if new_method in ('COD', 'Bank', 'QR'):
                payment.method = new_method
                db.session.commit()
                flash(f'Đã đổi phương thức thanh toán sang: {new_method}', 'info')
                return redirect(url_for('order_payment', order_id=order.id))

    return render_template('payment.html', order=order, payment=payment)


# ============================================================
# LỊCH SỬ ĐƠN HÀNG (Buyer)
# ============================================================
@app.route('/orders')
@login_required
def order_history():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.order_date.desc()).all()
    return render_template('order_history.html', orders=orders)


@app.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin():
        abort(403)
    return render_template('order_detail.html',
                           order=order,
                           review_types=['1', '2', '3', '4', '5'],
                           return_types=[
                               ('return', 'Trả hàng'),
                               ('exchange', 'Đổi hàng'),
                               ('cancel', 'Hủy sản phẩm'),
                           ],
                           buyer_can_cancel=buyer_can_cancel_order(order),
                           cancel_block_reason=buyer_cancel_block_reason(order))


@app.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def buyer_cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)
    if not buyer_can_cancel_order(order):
        reason = buyer_cancel_block_reason(order) or 'Không thể hủy đơn lúc này.'
        flash(reason, 'warning')
        return redirect(url_for('order_detail', order_id=order.id))

    for item in order.items:
        product = db.session.get(Product, item.product_id)
        if product:
            product.stock += item.quantity

    order.status = 'Đã hủy'
    if order.payment and order.payment.status == 'Đã thanh toán':
        order.payment.status = 'Hoàn tiền'

    db.session.commit()
    app.logger.info(f'Buyer {current_user.username} cancelled order #{order.id}')
    flash('Đã hủy đơn hàng thành công.', 'success')
    return redirect(url_for('order_detail', order_id=order.id))


@app.route('/orders/<int:order_id>/tracking')
@login_required
def order_tracking(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin():
        abort(403)
    return render_template('tracking.html', order=order)


@app.route('/orders/<int:order_id>/review/<int:item_id>', methods=['POST'])
@login_required
def submit_review(order_id, item_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)

    item = OrderItem.query.get_or_404(item_id)
    if item.order_id != order.id:
        abort(403)
    if item.review:
        flash('Bạn đã đánh giá sản phẩm này rồi.', 'warning')
        return redirect(url_for('order_detail', order_id=order.id))

    rating = request.form.get('rating', type=int)
    content = request.form.get('content', '').strip()
    if rating not in [1, 2, 3, 4, 5]:
        flash('Số sao không hợp lệ.', 'danger')
        return redirect(url_for('order_detail', order_id=order.id))
    if not item.product or not item.product.seller_id:
        flash('Không xác định được người bán của sản phẩm.', 'danger')
        return redirect(url_for('order_detail', order_id=order.id))

    review = Review(
        order_item_id=item.id,
        product_id=item.product_id,
        buyer_id=current_user.id,
        seller_id=item.product.seller_id,
        rating=rating,
        content=content,
    )
    db.session.add(review)
    db.session.commit()
    flash('Gửi đánh giá thành công.', 'success')
    return redirect(url_for('order_detail', order_id=order.id))


@app.route('/orders/<int:order_id>/return/<int:item_id>', methods=['POST'])
@login_required
def submit_return_request(order_id, item_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)

    item = OrderItem.query.get_or_404(item_id)
    if item.order_id != order.id:
        abort(403)
    if item.return_request:
        flash('Sản phẩm này đã có yêu cầu sau bán.', 'warning')
        return redirect(url_for('order_detail', order_id=order.id))
    if not item.product or not item.product.seller_id:
        flash('Không xác định được người bán của sản phẩm.', 'danger')
        return redirect(url_for('order_detail', order_id=order.id))

    request_type = request.form.get('request_type', 'return')
    reason = request.form.get('reason', '').strip()
    valid_types = ['return', 'exchange', 'cancel']
    if request_type not in valid_types or not reason:
        flash('Thông tin yêu cầu chưa hợp lệ.', 'danger')
        return redirect(url_for('order_detail', order_id=order.id))

    item_status = item.seller_status or 'Đơn mới'
    if request_type in ['return', 'exchange'] and item_status != 'Đã giao':
        flash('Chỉ được yêu cầu đổi/trả sau khi sản phẩm đã giao thành công.', 'warning')
        return redirect(url_for('order_detail', order_id=order.id))
    if request_type == 'cancel':
        if not buyer_can_cancel_item(item, order):
            flash(buyer_cancel_block_reason(order) or 'Không thể hủy sản phẩm lúc này.', 'warning')
            return redirect(url_for('order_detail', order_id=order.id))

    ret = ReturnRequest(
        order_item_id=item.id,
        buyer_id=current_user.id,
        seller_id=item.product.seller_id,
        request_type=request_type,
        reason=reason,
        status='Chờ xử lý',
    )
    db.session.add(ret)
    db.session.commit()
    flash('Đã gửi yêu cầu sau bán tới người bán.', 'success')
    return redirect(url_for('order_detail', order_id=order.id))


# ============================================================
# AI CHATBOT (CSKH cho Buyer) - lưu AIConversation
# ============================================================
@app.route('/chat', methods=['GET', 'POST'])
def buyer_chat():
    form = ChatForm()
    answer = None
    suggestions = []

    if form.validate_on_submit():
        question = form.message.data.strip()
        all_products = Product.query.filter_by(is_visible=True).all()
        results = ai_engine.smart_search(question, all_products, top_n=5)

        if results:
            suggestions = [p for p, _ in results]
            top_score = float(results[0][1])
            top_names = ', '.join(p.name for p, _ in results[:3])
            answer = (
                f'Mình tìm được {len(results)} sản phẩm phù hợp. '
                f'Gợi ý hàng đầu: {top_names}. '
                f'Bạn có thể bấm vào sản phẩm để xem chi tiết hoặc thêm vào giỏ hàng.'
            )
            log_ai_conversation(question, answer, source='chat',
                                intent='product_search', score=top_score)
        else:
            answer = (
                'Hiện chưa tìm thấy sản phẩm phù hợp. Bạn thử mô tả khác (ví dụ: '
                '"đồ nấu canh chua", "trái cây giàu vitamin C")?'
            )
            log_ai_conversation(question, answer, source='chat', intent='no_match')

    history = []
    if current_user.is_authenticated:
        history = (
            AIConversation.query.filter_by(user_id=current_user.id, source='chat')
            .order_by(AIConversation.created_at.desc())
            .limit(20)
            .all()
        )

    return render_template('chat.html', form=form, answer=answer,
                           suggestions=suggestions, history=history)


# ============================================================
# ADMIN: DASHBOARD
# ============================================================
@app.route('/admin')
@admin_required
def admin_dashboard():
    total_products = Product.query.count()
    total_orders = Order.query.count()
    total_users = User.query.filter_by(role='buyer').count()
    total_sellers = User.query.filter_by(role='seller').count()
    pending_orders = Order.query.filter_by(status='Đang xử lý').count()

    recent_orders = Order.query.order_by(Order.order_date.desc()).limit(5).all()

    revenue = db.session.query(db.func.sum(Order.total_amount)).filter(
        Order.status != 'Đã hủy'
    ).scalar() or 0

    total_conversations = AIConversation.query.count()

    return render_template('admin/dashboard.html',
                           total_products=total_products,
                           total_orders=total_orders,
                           total_users=total_users,
                           total_sellers=total_sellers,
                           pending_orders=pending_orders,
                           recent_orders=recent_orders,
                           revenue=revenue,
                           total_conversations=total_conversations)


# ============================================================
# ADMIN: QUẢN LÝ SELLER
# ============================================================
@app.route('/admin/sellers')
@admin_required
def admin_sellers():
    sellers = User.query.filter_by(role='seller').order_by(User.created_at.desc()).all()
    return render_template('admin/sellers.html', sellers=sellers)


@app.route('/admin/sellers/<int:user_id>/approve', methods=['POST'])
@admin_required
def admin_seller_approve(user_id):
    user = User.query.get_or_404(user_id)
    user.role = 'seller'
    user.is_active = True
    db.session.commit()
    flash(f'Đã duyệt seller: {user.full_name}', 'success')
    return redirect(url_for('admin_sellers'))


@app.route('/admin/sellers/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def admin_seller_toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if not user.is_seller():
        flash('Tài khoản này không phải seller.', 'warning')
        return redirect(url_for('admin_sellers'))
    user.is_active = not user.is_active
    db.session.commit()
    status = 'mở khóa' if user.is_active else 'khóa'
    flash(f'Đã {status} seller: {user.full_name}', 'info')
    return redirect(url_for('admin_sellers'))


# ============================================================
# ADMIN: QUẢN LÝ SẢN PHẨM
# ============================================================
@app.route('/admin/products')
@admin_required
def admin_products():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=products)


@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_product_add():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            stock=form.stock.data,
            unit=form.unit.data,
            category=form.category.data,
            origin=form.origin.data,
            is_visible=form.is_visible.data,
        )
        if has_uploaded_file(form.image.data):
            saved_name = save_image(form.image.data)
            if saved_name:
                product.image = saved_name
        db.session.add(product)
        db.session.commit()
        rebuild_ai_index()
        flash('Thêm sản phẩm thành công!', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/product_form.html', form=form, title='Thêm sản phẩm')


@app.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product)

    if form.validate_on_submit():
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.stock = form.stock.data
        product.unit = form.unit.data
        product.category = form.category.data
        product.origin = form.origin.data
        product.is_visible = form.is_visible.data

        if has_uploaded_file(form.image.data):
            saved_name = save_image(form.image.data)
            if saved_name:
                product.image = saved_name

        db.session.commit()
        rebuild_ai_index()
        flash('Cập nhật sản phẩm thành công!', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/product_form.html', form=form,
                           title='Sửa sản phẩm', product=product)


@app.route('/admin/products/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    rebuild_ai_index()
    flash(f'Đã xóa sản phẩm "{product.name}".', 'info')
    return redirect(url_for('admin_products'))


@app.route('/admin/products/toggle/<int:product_id>', methods=['POST'])
@admin_required
def admin_product_toggle(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_visible = not product.is_visible
    db.session.commit()
    rebuild_ai_index()
    status = 'hiển thị' if product.is_visible else 'ẩn'
    flash(f'Sản phẩm "{product.name}" đã được {status}.', 'info')
    return redirect(url_for('admin_products'))


# ============================================================
# ADMIN: QUẢN LÝ ĐƠN HÀNG
# ============================================================
@app.route('/admin/orders')
@admin_required
def admin_orders():
    status_filter = request.args.get('status', '')
    query = Order.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    orders = query.order_by(Order.order_date.desc()).all()
    return render_template('admin/orders.html', orders=orders, current_status=status_filter)


@app.route('/admin/orders/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('admin/order_detail.html', order=order)


@app.route('/admin/orders/<int:order_id>/update', methods=['POST'])
@admin_required
def admin_order_update(order_id):
    order = Order.query.get_or_404(order_id)
    if order_is_cancelled(order):
        flash('Đơn hàng đã bị khách hủy — không thể cập nhật trạng thái.', 'warning')
        return redirect(url_for('admin_order_detail', order_id=order.id))
    new_status = request.form.get('status')
    valid_statuses = ['Đang xử lý', 'Đang giao', 'Đã hoàn thành', 'Đã hủy']
    if new_status in valid_statuses:
        order.status = new_status
        db.session.commit()
        app.logger.info(f'Admin updated order #{order.id} -> {new_status}')
        flash(f'Đơn hàng #{order.id} đã cập nhật: {new_status}', 'success')
    else:
        flash('Trạng thái không hợp lệ!', 'danger')
    return redirect(url_for('admin_order_detail', order_id=order.id))


@app.route('/admin/orders/<int:order_id>/confirm', methods=['POST'])
@admin_required
def admin_order_confirm(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status == 'Đã hủy':
        flash('Đơn hàng đã hủy, không thể xác nhận.', 'warning')
        return redirect(url_for('admin_order_detail', order_id=order.id))
    if order.admin_confirmed_at:
        flash('Admin đã xác nhận nhận đơn này trước đó.', 'info')
        return redirect(url_for('admin_order_detail', order_id=order.id))

    order.admin_confirmed_at = datetime.utcnow()
    db.session.commit()
    app.logger.info(f'Admin confirmed receipt of order #{order.id}')
    flash(f'Đã xác nhận nhận đơn hàng #{order.id}.', 'success')
    return redirect(url_for('admin_order_detail', order_id=order.id))


# ============================================================
# SELLER: DASHBOARD
# ============================================================
@app.route('/seller')
@seller_required
def seller_dashboard():
    total_products = Product.query.filter_by(seller_id=current_user.id).count()
    visible_products = Product.query.filter_by(seller_id=current_user.id, is_visible=True).count()
    new_order_items = (
        OrderItem.query.join(Product, OrderItem.product_id == Product.id)
        .filter(
            Product.seller_id == current_user.id,
            OrderItem.seller_status == 'Đơn mới',
        )
        .count()
    )
    return render_template('seller/dashboard.html',
                           total_products=total_products,
                           visible_products=visible_products,
                           new_order_items=new_order_items)


@app.route('/seller/products')
@seller_required
def seller_products():
    products = Product.query.filter_by(seller_id=current_user.id).order_by(Product.created_at.desc()).all()
    return render_template('seller/products.html', products=products)


@app.route('/seller/products/add', methods=['GET', 'POST'])
@seller_required
def seller_product_add():
    form = ProductForm()
    if form.validate_on_submit():
        product = Product(
            seller_id=current_user.id,
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            stock=form.stock.data,
            unit=form.unit.data,
            category=form.category.data,
            origin=form.origin.data,
            is_visible=form.is_visible.data,
        )
        if has_uploaded_file(form.image.data):
            saved_name = save_image(form.image.data)
            if saved_name:
                product.image = saved_name
        db.session.add(product)
        db.session.commit()
        rebuild_ai_index()
        flash('Seller: thêm sản phẩm thành công!', 'success')
        return redirect(url_for('seller_products'))

    return render_template('seller/product_form.html', form=form, title='Thêm sản phẩm')


@app.route('/seller/products/edit/<int:product_id>', methods=['GET', 'POST'])
@seller_required
def seller_product_edit(product_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != current_user.id:
        abort(403)

    form = ProductForm(obj=product)
    if form.validate_on_submit():
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.stock = form.stock.data
        product.unit = form.unit.data
        product.category = form.category.data
        product.origin = form.origin.data
        product.is_visible = form.is_visible.data

        if has_uploaded_file(form.image.data):
            saved_name = save_image(form.image.data)
            if saved_name:
                product.image = saved_name

        db.session.commit()
        rebuild_ai_index()
        flash('Seller: cập nhật sản phẩm thành công!', 'success')
        return redirect(url_for('seller_products'))

    return render_template('seller/product_form.html', form=form,
                           title='Sửa sản phẩm', product=product)


@app.route('/seller/products/delete/<int:product_id>', methods=['POST'])
@seller_required
def seller_product_delete(product_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != current_user.id:
        abort(403)
    db.session.delete(product)
    db.session.commit()
    rebuild_ai_index()
    flash(f'Seller: đã xóa sản phẩm "{product.name}".', 'info')
    return redirect(url_for('seller_products'))


@app.route('/seller/products/toggle/<int:product_id>', methods=['POST'])
@seller_required
def seller_product_toggle(product_id):
    product = Product.query.get_or_404(product_id)
    if product.seller_id != current_user.id:
        abort(403)
    product.is_visible = not product.is_visible
    db.session.commit()
    rebuild_ai_index()
    status = 'hiển thị' if product.is_visible else 'ẩn'
    flash(f'Seller: sản phẩm "{product.name}" đã được {status}.', 'info')
    return redirect(url_for('seller_products'))


# ============================================================
# SELLER: QUẢN LÝ ĐƠN HÀNG
# ============================================================
@app.route('/seller/orders')
@seller_required
def seller_orders():
    seller_items = get_seller_order_items_query().order_by(Order.order_date.desc()).all()

    grouped_orders = {}
    for item in seller_items:
        order = item.order
        if order.id not in grouped_orders:
            grouped_orders[order.id] = {
                'order': order,
                'items': [],
                'seller_total': 0,
            }
        grouped_orders[order.id]['items'].append(item)
        grouped_orders[order.id]['seller_total'] += item.subtotal

    return render_template('seller/orders.html', grouped_orders=grouped_orders)


@app.route('/seller/orders/<int:order_id>')
@seller_required
def seller_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    seller_items = (
        OrderItem.query.join(Product, OrderItem.product_id == Product.id)
        .filter(
            OrderItem.order_id == order.id,
            Product.seller_id == current_user.id,
        )
        .all()
    )
    if not seller_items:
        abort(403)

    seller_total = sum(item.subtotal for item in seller_items)
    return render_template('seller/order_detail.html',
                           order=order,
                           seller_items=seller_items,
                           seller_total=seller_total)


@app.route('/seller/order-items/<int:item_id>/update', methods=['POST'])
@seller_required
def seller_order_item_update(item_id):
    item = OrderItem.query.get_or_404(item_id)
    if not item.product or item.product.seller_id != current_user.id:
        abort(403)
    if order_is_cancelled(item.order):
        flash('Đơn hàng đã bị khách hủy — không thể cập nhật trạng thái.', 'warning')
        return redirect(url_for('seller_order_detail', order_id=item.order_id))

    new_status = request.form.get('seller_status')
    valid_statuses = ['Đơn mới', 'Đã xác nhận', 'Đang chuẩn bị', 'Đang giao', 'Đã giao']
    if new_status not in valid_statuses:
        flash('Trạng thái seller không hợp lệ!', 'danger')
        return redirect(url_for('seller_order_detail', order_id=item.order_id))

    item.seller_status = new_status

    # Đồng bộ sang Shipment
    shipment = item.shipment
    if not shipment:
        shipment = Shipment(order_item_id=item.id, status='Chuẩn bị hàng')
        db.session.add(shipment)
    if new_status == 'Đang giao':
        shipment.status = 'Đang giao'
        if not shipment.shipped_at:
            shipment.shipped_at = datetime.utcnow()
    elif new_status == 'Đã giao':
        shipment.status = 'Đã giao'
        shipment.delivered_at = datetime.utcnow()
    elif new_status in ('Đơn mới', 'Đã xác nhận', 'Đang chuẩn bị'):
        shipment.status = 'Chuẩn bị hàng'

    sync_order_status_from_items(item.order)
    db.session.commit()
    app.logger.info(
        f'Seller {current_user.username} updated item#{item.id} -> {new_status}'
    )
    flash(f'Đã cập nhật trạng thái sản phẩm "{item.product_name}" thành "{new_status}".', 'success')
    return redirect(url_for('seller_order_detail', order_id=item.order_id))


@app.route('/seller/order-items/<int:item_id>/shipping', methods=['POST'])
@seller_required
def seller_order_item_shipping_update(item_id):
    item = OrderItem.query.get_or_404(item_id)
    if not item.product or item.product.seller_id != current_user.id:
        abort(403)
    if order_is_cancelled(item.order):
        flash('Đơn hàng đã bị khách hủy — không thể cập nhật vận chuyển.', 'warning')
        return redirect(url_for('seller_order_detail', order_id=item.order_id))

    carrier = request.form.get('shipping_carrier', '').strip()
    code = request.form.get('shipping_code', '').strip()
    if not carrier or not code:
        flash('Vui lòng nhập đủ đơn vị vận chuyển và mã vận đơn.', 'warning')
        return redirect(url_for('seller_order_detail', order_id=item.order_id))

    item.shipping_carrier = carrier
    item.shipping_code = code
    item.shipping_updated_at = datetime.utcnow()
    if item.seller_status in ['Đơn mới', 'Đã xác nhận', 'Đang chuẩn bị']:
        item.seller_status = 'Đang giao'

    # Đồng bộ Shipment
    shipment = item.shipment
    if not shipment:
        shipment = Shipment(order_item_id=item.id)
        db.session.add(shipment)
    shipment.carrier = carrier
    shipment.tracking_code = code
    shipment.status = 'Đang giao'
    if not shipment.shipped_at:
        shipment.shipped_at = datetime.utcnow()

    sync_order_status_from_items(item.order)
    db.session.commit()
    flash(f'Đã cập nhật vận đơn cho "{item.product_name}".', 'success')
    return redirect(url_for('seller_order_detail', order_id=item.order_id))


@app.route('/seller/reports')
@seller_required
def seller_reports():
    seller_items = get_seller_order_items_query().all()
    total_revenue = sum(item.subtotal for item in seller_items if item.seller_status == 'Đã giao')
    total_orders = len({item.order_id for item in seller_items})

    sold_by_product = {}
    for item in seller_items:
        sold_by_product.setdefault(item.product_name, 0)
        sold_by_product[item.product_name] += item.quantity
    best_sellers = sorted(sold_by_product.items(), key=lambda x: x[1], reverse=True)[:5]

    low_stock_products = (
        Product.query.filter_by(seller_id=current_user.id)
        .filter(Product.stock <= 10)
        .order_by(Product.stock.asc())
        .all()
    )

    return render_template('seller/reports.html',
                           total_revenue=total_revenue,
                           total_orders=total_orders,
                           best_sellers=best_sellers,
                           low_stock_products=low_stock_products)


@app.route('/seller/after-sales')
@seller_required
def seller_after_sales():
    reviews = Review.query.filter_by(seller_id=current_user.id).order_by(Review.created_at.desc()).all()
    returns = ReturnRequest.query.filter_by(seller_id=current_user.id).order_by(ReturnRequest.created_at.desc()).all()
    return render_template('seller/after_sales.html', reviews=reviews, returns=returns)


@app.route('/seller/reviews/<int:review_id>/reply', methods=['POST'])
@seller_required
def seller_review_reply(review_id):
    review = Review.query.get_or_404(review_id)
    if review.seller_id != current_user.id:
        abort(403)
    reply = request.form.get('seller_reply', '').strip()
    if not reply:
        flash('Nội dung phản hồi không được để trống.', 'warning')
        return redirect(url_for('seller_after_sales'))
    review.seller_reply = reply
    review.replied_at = datetime.utcnow()
    db.session.commit()
    flash('Đã phản hồi đánh giá.', 'success')
    return redirect(url_for('seller_after_sales'))


@app.route('/seller/returns/<int:return_id>/update', methods=['POST'])
@seller_required
def seller_return_update(return_id):
    ret = ReturnRequest.query.get_or_404(return_id)
    if ret.seller_id != current_user.id:
        abort(403)
    new_status = request.form.get('status')
    note = request.form.get('seller_note', '').strip()
    valid_status = ['Chờ xử lý', 'Chấp nhận', 'Từ chối', 'Hoàn tất']
    if new_status not in valid_status:
        flash('Trạng thái yêu cầu không hợp lệ.', 'danger')
        return redirect(url_for('seller_after_sales'))
    ret.status = new_status
    ret.seller_note = note
    ret.resolved_at = datetime.utcnow() if new_status in ['Chấp nhận', 'Từ chối', 'Hoàn tất'] else None
    db.session.commit()
    flash('Đã cập nhật yêu cầu sau bán.', 'success')
    return redirect(url_for('seller_after_sales'))


@app.route('/seller/ai', methods=['GET', 'POST'])
@seller_required
def seller_ai():
    seller_products = Product.query.filter_by(seller_id=current_user.id).all()
    seller_items = get_seller_order_items_query().all()

    sales_by_product = {}
    for item in seller_items:
        sales_by_product.setdefault(item.product_name, 0)
        sales_by_product[item.product_name] += item.quantity

    restock_suggestions = [p for p in seller_products if p.stock <= 10]
    boost_candidates = sorted(
        seller_products,
        key=lambda p: sales_by_product.get(p.name, 0)
    )[:5]

    faq_answer = None
    faq_query = ''
    if request.method == 'POST':
        faq_query = request.form.get('question', '').strip()
        if faq_query:
            results = ai_engine.smart_search(faq_query, seller_products, top_n=3)
            if results:
                lines = []
                for p, score in results:
                    lines.append(f"- {p.name}: giá {int(p.price):,}đ/{p.unit}, tồn {p.stock}, độ phù hợp {score:.2f}")
                faq_answer = "Gợi ý cho khách từ shop của bạn:\n" + "\n".join(lines)
                log_ai_conversation(faq_query, faq_answer, source='chat',
                                    intent='seller_faq')
            else:
                faq_answer = "Hiện chưa tìm thấy sản phẩm phù hợp trong shop của bạn."
                log_ai_conversation(faq_query, faq_answer, source='chat',
                                    intent='seller_faq_no_match')
        else:
            faq_answer = "Vui lòng nhập câu hỏi để AI hỗ trợ."

    return render_template('seller/ai_assistant.html',
                           restock_suggestions=restock_suggestions,
                           boost_candidates=boost_candidates,
                           faq_answer=faq_answer,
                           faq_query=faq_query)


# ============================================================
# API: TÌM KIẾM THÔNG MINH
# ============================================================
@app.route('/api/search', methods=['GET'])
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    all_products = Product.query.filter_by(is_visible=True).all()
    ai_results = ai_engine.smart_search(query, all_products, top_n=10)

    results = [{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'unit': p.unit,
        'image': build_image_url(p.image),
        'category': p.category,
        'score': round(score, 3),
    } for p, score in ai_results if p.is_visible]

    if results:
        log_ai_conversation(
            question=query,
            answer=f'API search: {len(results)} kết quả, top: {results[0]["name"]}',
            source='search',
            score=results[0]['score'],
        )

    return jsonify(results)


@app.route('/api/recommendations/<int:product_id>')
def api_recommendations(product_id):
    if ai_engine.tfidf_matrix is None:
        rebuild_ai_index()

    recommendations = ai_engine.get_recommendations(product_id, top_n=4)

    results = [{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'unit': p.unit,
        'image': build_image_url(p.image),
        'category': p.category,
        'origin': p.origin,
        'stock': p.stock,
    } for p in recommendations]

    return jsonify(results)


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(500)
def server_error(e):
    app.logger.exception('Internal server error')
    return render_template('errors/500.html'), 500


# ============================================================
# KHỞI TẠO DB (sau khi load xong app — tránh import vòng với seed.py)
# ============================================================
bootstrap_database()


# ============================================================
# CHẠY APP
# ============================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_sqlite_schema()
        rebuild_ai_index()
        app.logger.info('App started, AI index built')
        print('[AI] TF-IDF index built successfully.')
    app.run(debug=app.config.get('DEBUG', True), port=5000)
