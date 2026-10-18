"""Model-only download routing. Never infer geography from OS language or LAN IP."""
from __future__ import annotations
import json
import re
import time
from urllib.request import Request, build_opener, ProxyHandler

OFFICIAL = 'https://huggingface.co'
CHINA_MIRROR = 'https://hf-mirror.com'


def detect_country() -> dict:
    # A direct request observes the user's public egress, rather than a configured
    # application proxy. Only an ISO country code is retained, never the IP itself.
    errors = []
    for url, field in [('https://ipapi.co/json/', 'country_code'),
                       ('https://ipwho.is/', 'country_code')]:
        try:
            request = Request(url, headers={'User-Agent': 'Triceratops/1.0 model-source-selection'})
            with build_opener(ProxyHandler({})).open(request, timeout=4) as response:
                data = json.loads(response.read(65536))
            code = data.get(field, '')
            if data.get('success', True) is False or data.get('error') or not re.fullmatch('[A-Z]{2}', code):
                raise ValueError('country unavailable')
            return {'country': code, 'detected_at': int(time.time()), 'geolocation': 'public-egress'}
        except (OSError, ValueError) as exc:
            errors.append(type(exc).__name__)
    return {'country': '', 'detected_at': int(time.time()), 'geolocation': 'unavailable',
            'reason': 'Country lookup failed (' + ', '.join(errors) + '); official model source selected. You can select the China mirror in Settings.'}


def model_sources(mode: str = 'auto', location: dict | None = None) -> dict:
    if mode not in {'auto', 'official', 'china'}:
        raise ValueError('model_source must be auto, official or china')
    region = detect_country() if mode == 'auto' and location is None else (location or {})
    mirror = mode == 'china' or (mode == 'auto' and region.get('country') == 'CN')
    return {'mode': mode, **region, 'hf_endpoint': CHINA_MIRROR if mirror else OFFICIAL,
            'music_models': 'china-mirror' if mirror else 'official',
            'local_chat_models': 'official-model-registry',
            'local_chat_reason': 'No verified byte-identical domestic mirror is configured for the selected GGUF model. The official registry is used.',
            'scope': 'model-downloads-only'}


def resolve_mirror(endpoint: str, repo: str, revision: str, filename: str) -> dict:
    """Confirm that a mirror really serves pinned Hub metadata, not a redirect overseas."""
    if endpoint != CHINA_MIRROR:
        return {'endpoint': endpoint, 'reason': 'selected source'}
    from urllib.request import HTTPRedirectHandler
    from urllib.parse import urlparse
    class Redirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return super().redirect_request(req, fp, 307 if code == 308 else code, msg, headers, newurl)
        http_error_308 = HTTPRedirectHandler.http_error_302
    request = Request(f'{endpoint}/{repo}/resolve/{revision}/{filename}', method='HEAD')
    try:
        with build_opener(Redirects()).open(request, timeout=10) as response:
            host = urlparse(response.url).hostname
            commit = response.headers.get('X-Repo-Commit')
            if host == 'hf-mirror.com' and commit == revision:
                return {'endpoint': endpoint, 'reason': 'pinned mirror metadata verified'}
            reason = 'Domestic mirror redirects overseas or lacks the pinned revision; official source selected.'
    except OSError as exc:
        reason = f'Domestic mirror check failed ({type(exc).__name__}); official source selected.'
    return {'endpoint': OFFICIAL, 'reason': reason}
