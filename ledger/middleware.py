from ipaddress import ip_address
from urllib.parse import urlsplit
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
import logging
import re

class RedactClientTokens(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(r'/p/[^/\s?"\']+', '/p/[redacted]', record.getMessage())
        record.args = ()
        return True

class PreviewCsrfMiddleware(CsrfViewMiddleware):
    def _origin_verified(self, request):
        if settings.DEBUG and settings.LOCAL_EMBEDDED_PREVIEW and request.META.get('HTTP_ORIGIN') == 'null' and not request.is_secure():
            try:
                local = ip_address(request.META.get('REMOTE_ADDR', '')).is_loopback
            except ValueError:
                local = False
            if local and urlsplit('//' + request.get_host()).hostname in {'localhost', '127.0.0.1', '::1'}:
                return True
        return super()._origin_verified(request)

class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith('/static/'):
            response['Cache-Control'] = 'private, no-store'
            response['Referrer-Policy'] = 'same-origin'
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
