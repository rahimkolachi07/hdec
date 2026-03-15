from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'solar-cmms-secret-key-change-in-production-2026'
DEBUG = True
ALLOWED_HOSTS = ['*']
INSTALLED_APPS = [
    'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes',
    'django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles',
    'maintenance',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'solar_cmms.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.debug','django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'solar_cmms.wsgi.application'
DATABASES = {'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Riyadh'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── NO LOGIN REQUIRED — dashboard is open ─────────────────────────────────────
# LOGIN_URL and LOGIN_REDIRECT_URL are not needed since we removed authentication

# ── Google Sheet config ────────────────────────────────────────────────────────
GOOGLE_SHEET_ID = "1EKrRePyskWHJOPIljD7GCGAvyO4B9OMz80o8X4Cr1Ik"
SHEET_DOWNLOAD_INTERVAL_MINUTES = 5
SHEET_LOCAL_PATH = str(BASE_DIR / "solar_plant_data.xlsx")

LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'simple': {'format': '[%(levelname)s] %(name)s: %(message)s'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'}},
    'loggers': {'maintenance': {'handlers': ['console'], 'level': 'INFO', 'propagate': False}},
}
