"""No networking during source registration. Exact supported URL shapes only."""
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit, parse_qsl

EVENT_HOSTS = frozenset({'novacvernovka.eu', 'staratrznica.sk', 'visitbratislava.com', 'goout.net'})
RESERVED = {'p','reel','tv','profile.php','dialog','oauth','plugins','photo.php','story.php','permalink.php','video.php','groups','accounts', 'login', 'logout', 'signup', 'challenge', 'direct', 'explore', 'stories', 'share', 'sharer', 'watch', 'reels', 'legal', 'about', 'api', 'graphql', 'privacy', 'settings', 'help'}

@dataclass(frozen=True)
class Target:
    platform: str
    url: str
    external_id: str
    target_type: str


def normalize_target(value: str) -> Target:
    if not isinstance(value, str) or len(value) > 1024 or re.search(r'[\x00-\x20\\%]', value):
        raise ValueError('Use a direct public HTTPS profile or post URL')
    if re.fullmatch(r'@?[A-Za-z0-9_][A-Za-z0-9_.]{0,29}',value):
        value='https://www.instagram.com/'+value.lstrip('@')+'/'
    try:
        p = urlsplit(value)
        host = (p.hostname or '').lower()
        if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443) or p.fragment:
            raise ValueError('HTTPS without credentials or fragments is required')
    except ValueError:
        raise ValueError('Invalid source URL') from None
    host = host.removeprefix('www.')
    path = p.path.rstrip('/')
    params = parse_qsl(p.query, keep_blank_values=True)
    if host == 'facebook.com' and path == '/profile.php' and len(params) == 1 and params[0][0] == 'id' and re.fullmatch(r'\d{5,30}', params[0][1]):
        return Target('facebook', 'https://www.facebook.com/profile.php?id='+params[0][1], params[0][1], 'profile')
    if any(k.lower() not in {'utm_source','utm_medium','utm_campaign','igsh','igshid','fbclid'} for k, _ in params):
        raise ValueError('Use the direct URL without query credentials or redirects')
    if host == 'instagram.com':
        match = re.fullmatch(r'/(p|reel)/([A-Za-z0-9_-]{3,100})', path)
        if match:
            return Target('instagram', f'https://www.instagram.com/{match[1]}/{match[2]}/', match[2], 'post')
        if re.fullmatch(r'/[A-Za-z0-9_][A-Za-z0-9_.]{0,29}', path) and path[1:].lower() not in RESERVED and '..' not in path and not path.endswith('.'):
            handle = path[1:].lower()
            return Target('instagram', f'https://www.instagram.com/{handle}/', handle, 'profile')
    elif host == 'facebook.com':
        match = re.fullmatch(r'/(events)/(\d{5,30})', path)
        post = re.fullmatch(r'/([A-Za-z0-9.]{2,100})/posts/([A-Za-z0-9]{5,150})', path)
        if match:
            return Target('facebook', 'https://www.facebook.com'+path+'/', match[2], 'post')
        if post and post[1].lower() not in RESERVED:
            return Target('facebook', f'https://www.facebook.com/{post[1].lower()}/posts/{post[2]}/', post[2], 'post')
        if re.fullmatch(r'/[A-Za-z0-9.]{2,100}', path) and path[1:].lower() not in RESERVED:
            return Target('facebook', 'https://www.facebook.com'+path.lower()+'/', path[1:].lower(), 'profile')
    elif host == 'tiktok.com':
        match = re.fullmatch(r'/@([A-Za-z0-9_.]{2,30})(?:/video/(\d{10,30}))?', path)
        if match and '..' not in match[1] and not match[1].endswith('.'):
            handle, post = match[1].lower(), match[2]
            return Target('tiktok', f'https://www.tiktok.com/@{handle}'+('/video/'+post if post else ''), post or handle, 'post' if post else 'profile')
    elif host in EVENT_HOSTS:
        if len(path)>200 or not path or '..' in path or '//' in path or not re.fullmatch(r'/[A-Za-z0-9_./~-]+', path):
            raise ValueError('Use a direct event page on a supported publisher website')
        return Target('event_url', urlunsplit(('https', host, path, '', '')), path, 'post')
    raise ValueError('This URL or platform route is not supported')
