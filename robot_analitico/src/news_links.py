"""
Verificación de enlaces de noticias: solo se muestran los que llevan a una
noticia. Un enlace se descarta si:
- no responde, da error HTTP (4xx/5xx) o se agota el tiempo;
- termina en una página de redirección o de consentimiento (news.google.com,
  consent.google.com, consent.yahoo.com, guce.yahoo.com, www.google.com);
- no es una página web (content-type distinto de HTML);
- es una página de error disfrazada ("404", "not found", "página no encontrada").

Google News (RSS) no entrega el enlace del medio sino uno propio
(news.google.com/rss/articles/<id>) que en el navegador abre una página
intermedia. Se traduce a la URL real del medio:
1. ids antiguos: la URL va codificada en base64 dentro del id;
2. ids nuevos: se leen la firma y la marca de tiempo de la página del artículo
   (data-n-a-sg, data-n-a-ts) y se consulta el servicio batchexecute de Google
   News (mismo procedimiento que la librería googlenewsdecoder).
Si no se puede traducir, el enlace se oculta en vez de mostrarlo roto.
"""
import base64
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urlparse

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}
DEAD_END_HOSTS = {"news.google.com", "consent.google.com", "www.google.com", "google.com",
                  "consent.yahoo.com", "guce.yahoo.com"}
ERROR_TITLE = re.compile(r"(404|not found|page not found|p[aá]gina no encontrada|no existe|error)", re.I)
TIMEOUT = 6


@dataclass
class LinkCheck:
    url: str  # enlace original
    ok: bool
    final_url: Optional[str] = None  # adonde lleva de verdad (se muestra este)
    reason: str = ""


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _google_article_id(url: str) -> Optional[str]:
    parts = urlparse(url)
    if _host(url) != "news.google.com":
        return None
    segs = [s for s in parts.path.split("/") if s]
    if len(segs) >= 2 and segs[-2] in ("articles", "read"):
        return segs[-1]
    return None


def _decode_old_id(article_id: str) -> Optional[str]:
    """Ids antiguos: la URL del medio está en base64 dentro del id."""
    try:
        raw = base64.urlsafe_b64decode(article_id + "=" * (-len(article_id) % 4))
    except Exception:
        return None
    match = re.search(rb"https?://[\x21-\x7e]+", raw)
    if not match:
        return None
    candidate = match.group(0).decode("ascii", errors="ignore")
    # El id nuevo empieza con "AU_yqL": su base64 no trae la URL completa.
    return candidate if _host(candidate) and _host(candidate) != "news.google.com" else None


def decode_google_news(url: str, session) -> Optional[str]:
    """URL real del medio para un enlace de Google News, o None si no se puede obtener."""
    article_id = _google_article_id(url)
    if article_id is None:
        return None
    old = _decode_old_id(article_id)
    if old:
        return old
    try:
        page = session.get(f"https://news.google.com/rss/articles/{article_id}", headers=HEADERS, timeout=TIMEOUT)
        sig = re.search(r'data-n-a-sg="([^"]+)"', page.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page.text)
        if not (sig and ts):
            return None
        req = ["Fbv4je", f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
                         f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{article_id}",{ts.group(1)},"{sig.group(1)}"]']
        resp = session.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data=f"f.req={quote(json.dumps([[req]]))}", timeout=TIMEOUT,
        )
        payload = json.loads(resp.text.split("\n\n")[1])[:-2]
        decoded = json.loads(payload[0][2])[1]
        return decoded if isinstance(decoded, str) and decoded.startswith("http") else None
    except Exception:
        return None


def check_link(url: str, session=None) -> LinkCheck:
    """Abre el enlace (siguiendo redirecciones) y decide si lleva a una noticia."""
    if session is None:
        import requests
        session = requests.Session()
    if not url or not url.startswith(("http://", "https://")):
        return LinkCheck(url, False, reason="enlace vacío o no web")
    target = url
    if _host(url) == "news.google.com":
        target = decode_google_news(url, session)
        if not target:
            return LinkCheck(url, False, reason="Google News no entregó el enlace del medio")
    try:
        resp = session.get(target, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True, stream=True)
        status = resp.status_code
        final = getattr(resp, "url", None) or target
        ctype = (resp.headers.get("Content-Type") or "").lower()
        head = ""
        if status < 400 and "html" in ctype:
            chunk = next(resp.iter_content(65536), b"") if hasattr(resp, "iter_content") else b""
            head = chunk.decode("utf-8", errors="ignore") if isinstance(chunk, bytes) else str(chunk)
        if hasattr(resp, "close"):
            resp.close()
    except Exception as exc:
        return LinkCheck(url, False, reason=f"no respondió ({type(exc).__name__})")
    if status >= 400:
        return LinkCheck(url, False, final, f"error HTTP {status}")
    if _host(final) in DEAD_END_HOSTS:
        return LinkCheck(url, False, final, "termina en una página de redirección o consentimiento")
    if "html" not in ctype:
        return LinkCheck(url, False, final, f"no es una página web ({ctype or 'sin tipo'})")
    title = re.search(r"<title[^>]*>(.*?)</title>", head, re.I | re.S)
    if title and ERROR_TITLE.search(title.group(1)[:120]):
        return LinkCheck(url, False, final, "la página dice que no existe")
    return LinkCheck(url, True, final, "ok")


def verify_items(items: "list[dict]", checker=check_link, max_workers: int = 8) -> "tuple[list[dict], list[dict]]":
    """
    Verifica en paralelo los enlaces de una lista de noticias. Devuelve
    (visibles con el enlace final, ocultas con su motivo).
    """
    if not items:
        return [], []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        checks = list(pool.map(lambda it: checker(it.get("link", "")), items))
    kept, hidden = [], []
    for item, chk in zip(items, checks):
        if chk.ok:
            kept.append({**item, "link": chk.final_url or item.get("link")})
        else:
            hidden.append({**item, "motivo": chk.reason})
    return kept, hidden
