"""Loopback Host/Origin and process-secret CSRF protection for Flask editor.
GET CSRF token uses same-origin SOP; POST/PUT/PATCH/DELETE must send header.
Old Flask pytest fixtures intentionally bypass only token check, not host/origin.
Never print process token or expose it to foreign origins.
"""
import secrets
from urllib.parse import urlparse

_MUTATE = frozenset(('POST','PUT','PATCH','DELETE'))
_TOKEN = secrets.token_urlsafe(36)
_ALLOWED_HOSTS = frozenset(('127.0.0.1','localhost','[::1]'))

def check(request, *, testing=False):
    host = request.host.split(':',1)[0].lower()
    if request.host.startswith('['):
        host = request.host.split(']',1)[0].lower()+']'
    if host not in _ALLOWED_HOSTS:
        return 'LOOPBACK_HOST_FORBIDDEN'
    origin = request.headers.get('Origin')
    if origin:
        try:
            parsed=urlparse(origin)
            if (parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1')
                    or parsed.netloc.lower()!=request.host.lower()):
                return 'CROSS_ORIGIN_FORBIDDEN'
        except (ValueError, TypeError):
            return 'CROSS_ORIGIN_FORBIDDEN'
    if request.headers.get('Sec-Fetch-Site') in ('cross-site','same-site'):
        return 'CROSS_SITE_FORBIDDEN'
    if request.method in _MUTATE and not testing:
        supplied=request.headers.get('X-V47-CSRF','')
        if not supplied or not secrets.compare_digest(supplied,_TOKEN):
            return 'CSRF_HEADER_REQUIRED'
    return None

def token():
    return _TOKEN
