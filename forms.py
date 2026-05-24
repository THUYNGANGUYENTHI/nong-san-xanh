from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField, TextAreaField,
    FloatField, IntegerField, SelectField, BooleanField, HiddenField,
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Optional
from flask_wtf.file import FileField, FileAllowed


# ============================================================
# FORM ĐĂNG KÝ
# ============================================================
class RegisterForm(FlaskForm):
    username = StringField('Tên đăng nhập', validators=[
        DataRequired(message='Vui lòng nhập tên đăng nhập.'),
        Length(min=3, max=80, message='Tên đăng nhập từ 3 đến 80 ký tự.'),
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Vui lòng nhập email.'),
        Email(message='Email không hợp lệ.'),
    ])
    full_name = StringField('Họ và tên', validators=[
        DataRequired(message='Vui lòng nhập họ tên.'),
        Length(max=150),
    ])
    phone = StringField('Số điện thoại', validators=[Optional(), Length(max=20)])
    address = StringField('Địa chỉ', validators=[Optional(), Length(max=300)])
    password = PasswordField('Mật khẩu', validators=[
        DataRequired(message='Vui lòng nhập mật khẩu.'),
        Length(min=6, message='Mật khẩu tối thiểu 6 ký tự.'),
    ])
    confirm_password = PasswordField('Xác nhận mật khẩu', validators=[
        DataRequired(message='Vui lòng xác nhận mật khẩu.'),
        EqualTo('password', message='Mật khẩu không khớp.'),
    ])
    submit = SubmitField('Đăng Ký')


# ============================================================
# FORM ĐĂNG NHẬP
# ============================================================
class LoginForm(FlaskForm):
    username = StringField('Tên đăng nhập', validators=[
        DataRequired(message='Vui lòng nhập tên đăng nhập.'),
    ])
    password = PasswordField('Mật khẩu', validators=[
        DataRequired(message='Vui lòng nhập mật khẩu.'),
    ])
    submit = SubmitField('Đăng Nhập')


# ============================================================
# FORM HỒ SƠ NGƯỜI DÙNG
# ============================================================
class ProfileForm(FlaskForm):
    full_name = StringField('Họ và tên', validators=[
        DataRequired(message='Vui lòng nhập họ tên.'),
        Length(max=150),
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Vui lòng nhập email.'),
        Email(message='Email không hợp lệ.'),
    ])
    phone = StringField('Số điện thoại', validators=[Optional(), Length(max=20)])
    address = StringField('Địa chỉ', validators=[Optional(), Length(max=300)])
    submit = SubmitField('Cập nhật hồ sơ')


# ============================================================
# FORM SẢN PHẨM (Admin / Seller dùng thêm/sửa)
# ============================================================
class ProductForm(FlaskForm):
    name = StringField('Tên sản phẩm', validators=[
        DataRequired(message='Vui lòng nhập tên sản phẩm.'),
        Length(max=200),
    ])
    description = TextAreaField('Mô tả', validators=[Optional()])
    price = FloatField('Giá (VNĐ)', validators=[
        DataRequired(message='Vui lòng nhập giá.'),
        NumberRange(min=0, message='Giá phải >= 0.'),
    ])
    stock = IntegerField('Số lượng tồn', validators=[
        DataRequired(message='Vui lòng nhập số lượng.'),
        NumberRange(min=0, message='Số lượng phải >= 0.'),
    ])
    unit = SelectField('Đơn vị', choices=[
        ('kg', 'Kilogram (kg)'),
        ('bó', 'Bó'),
        ('trái', 'Trái'),
        ('gói', 'Gói'),
        ('hộp', 'Hộp'),
        ('lít', 'Lít'),
    ], validators=[DataRequired()])
    category = SelectField('Danh mục', choices=[
        ('Rau lá', 'Rau lá'),
        ('Rau củ', 'Rau củ'),
        ('Trái cây', 'Trái cây'),
        ('Ngũ cốc', 'Ngũ cốc'),
        ('Gia vị', 'Gia vị'),
        ('Nấm', 'Nấm'),
        ('Rau mầm', 'Rau mầm'),
        ('Khác', 'Khác'),
    ], validators=[DataRequired()])
    origin = StringField('Xuất xứ', validators=[Optional(), Length(max=150)])
    image = FileField('Hình ảnh', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Chỉ chấp nhận file ảnh!'),
    ])
    is_visible = BooleanField('Hiển thị sản phẩm', default=True)
    submit = SubmitField('Lưu sản phẩm')


# ============================================================
# FORM THANH TOÁN (Checkout) - tách riêng UC Thanh toán
# ============================================================
class CheckoutForm(FlaskForm):
    shipping_name = StringField('Họ tên người nhận', validators=[
        DataRequired(message='Vui lòng nhập tên người nhận.'),
        Length(max=150),
    ])
    shipping_phone = StringField('Số điện thoại', validators=[
        DataRequired(message='Vui lòng nhập số điện thoại.'),
        Length(max=20),
    ])
    shipping_address = TextAreaField('Địa chỉ giao hàng', validators=[
        DataRequired(message='Vui lòng nhập địa chỉ.'),
        Length(max=500),
    ])
    payment_method = SelectField('Phương thức thanh toán', choices=[
        ('COD', 'Thanh toán khi nhận hàng (COD)'),
        ('Bank', 'Chuyển khoản ngân hàng (demo)'),
        ('QR', 'Quét mã QR / Ví điện tử (demo)'),
    ], validators=[DataRequired()], default='COD')
    note = TextAreaField('Ghi chú', validators=[Optional()])
    submit = SubmitField('Đặt hàng')


# ============================================================
# FORM CHATBOT AI
# ============================================================
class ChatForm(FlaskForm):
    message = StringField('Câu hỏi', validators=[
        DataRequired(message='Vui lòng nhập câu hỏi.'),
        Length(max=500),
    ])
    submit = SubmitField('Gửi')
