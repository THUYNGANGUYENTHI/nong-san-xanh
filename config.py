import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

basedir = os.path.abspath(os.path.dirname(__file__))

# PI 4.2 — ngưỡng dữ liệu thử nghiệm (đề cương)
DE_CUONG_MIN = {
    'products': 300,
    'users': 200,
    'orders': 500,
    'reviews': 300,
    'ai_conversations': 200,
}

SEED_TARGETS = {
    'buyers': 210,
    'sellers': 10,
    'products': 320,
    'orders': 520,
    'reviews': 320,
    'ai_conversations': 220,
}


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'nong-san-xanh-secret-key-2026-change-me'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or (
        'sqlite:///' + os.path.join(basedir, 'nongsan.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '').strip()
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '').strip()
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '').strip()
    CLOUDINARY_UPLOAD_PRESET = os.environ.get('CLOUDINARY_UPLOAD_PRESET', '').strip()
    CLOUDINARY_FOLDER = os.environ.get('CLOUDINARY_FOLDER', 'nongsan-products').strip()

    DEBUG = os.environ.get('FLASK_DEBUG', '1') == '1'
    LOG_DIR = os.environ.get('LOG_DIR') or os.path.join(basedir, 'logs')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
