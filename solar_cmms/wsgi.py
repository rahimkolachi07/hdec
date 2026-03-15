import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solar_cmms.settings')
application = get_wsgi_application()
