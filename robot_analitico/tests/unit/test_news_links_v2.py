"""
Verificación de enlaces de noticias (sin red, con una sesión simulada):
solo se muestran los enlaces que llevan a una noticia.
"""
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.news_links import check_link, decode_google_news, verify_items  # noqa: E402


class _Resp:
    def __init__(self, status=200, url="", ctype="text/html; charset=utf-8", body="<title>Nota</title>", text=""):
        self.status_code, self.url, self.headers, self._body, self.text = status, url, {"Content-Type": ctype}, body, text

    def iter_content(self, n):
        yield self._body.encode()

    def close(self):
        pass


class FakeSession:
    """Mapa url -> respuesta; simula redirecciones devolviendo otra url final."""

    def __init__(self, gets, post_text=""):
        self.gets, self.post_text, self.calls = gets, post_text, []

    def get(self, url, **kw):
        self.calls.append(url)
        if url not in self.gets:
            raise TimeoutError("sin respuesta")
        return self.gets[url]

    def post(self, url, **kw):
        return _Resp(text=self.post_text)


def test_good_link_is_kept_with_its_final_url():
    s = FakeSession({"https://medio.co/nota": _Resp(url="https://medio.co/nota?ref=1")})
    chk = check_link("https://medio.co/nota", s)
    assert chk.ok and chk.final_url == "https://medio.co/nota?ref=1"


def test_broken_links_are_hidden():
    s = FakeSession({
        "https://a.co/404": _Resp(status=404, url="https://a.co/404"),
        "https://b.co/pdf": _Resp(url="https://b.co/pdf", ctype="application/pdf"),
        "https://c.co/soft404": _Resp(url="https://c.co/soft404", body="<title>Página no encontrada</title>"),
        "https://d.co/consent": _Resp(url="https://consent.yahoo.com/v2/collectConsent"),
    })
    reasons = {u: check_link(u, s) for u in ["https://a.co/404", "https://b.co/pdf", "https://c.co/soft404",
                                              "https://d.co/consent", "https://e.co/timeout", "", "ftp://x"]}
    assert not any(c.ok for c in reasons.values())
    assert "404" in reasons["https://a.co/404"].reason
    assert "no es una página web" in reasons["https://b.co/pdf"].reason
    assert "no existe" in reasons["https://c.co/soft404"].reason
    assert "consentimiento" in reasons["https://d.co/consent"].reason
    assert "no respondió" in reasons["https://e.co/timeout"].reason


def test_google_news_old_id_is_decoded_to_the_publisher():
    raw = b"\x08\x13\x22\x2bhttps://www.portafolio.co/mercados/nota-123\xd2\x01\x00"
    article_id = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    url = f"https://news.google.com/rss/articles/{article_id}?oc=5"
    s = FakeSession({"https://www.portafolio.co/mercados/nota-123": _Resp(url="https://www.portafolio.co/mercados/nota-123")})
    assert decode_google_news(url, s) == "https://www.portafolio.co/mercados/nota-123"
    chk = check_link(url, s)
    assert chk.ok and chk.final_url == "https://www.portafolio.co/mercados/nota-123"


def test_google_news_new_id_uses_signature_and_batchexecute():
    article_id = "AU_yqLNUEVO"
    page = '<c-wiz><div jscontroller="x" data-n-a-sg="FIRMA" data-n-a-ts="1730000000"></div></c-wiz>'
    inner = json.dumps(["garturlres", "https://www.larepublica.co/finanzas/nota", 1])
    post = ")]}'\n\n" + json.dumps([["wrb.fr", "Fbv4je", inner, None, None, None, "generic"], ["di", 10], ["af.httprm", 9]])
    s = FakeSession({f"https://news.google.com/rss/articles/{article_id}": _Resp(text=page),
                     "https://www.larepublica.co/finanzas/nota": _Resp(url="https://www.larepublica.co/finanzas/nota")},
                    post_text=post)
    chk = check_link(f"https://news.google.com/rss/articles/{article_id}?oc=5", s)
    assert chk.ok and chk.final_url == "https://www.larepublica.co/finanzas/nota"


def test_google_news_that_cannot_be_decoded_is_hidden():
    s = FakeSession({"https://news.google.com/rss/articles/AU_yqLSINFIRMA": _Resp(text="<html>sin datos</html>")})
    chk = check_link("https://news.google.com/rss/articles/AU_yqLSINFIRMA", s)
    assert not chk.ok and "Google News" in chk.reason


def test_verify_items_keeps_only_working_links_and_reports_hidden():
    s = FakeSession({"https://ok.co/1": _Resp(url="https://ok.co/1"), "https://ok.co/2": _Resp(url="https://ok.co/2b")})
    items = [{"title": "A", "link": "https://ok.co/1"}, {"title": "B", "link": "https://roto.co/x"},
             {"title": "C", "link": "https://ok.co/2"}]
    kept, hidden = verify_items(items, checker=lambda u: check_link(u, s))
    assert [k["title"] for k in kept] == ["A", "C"] and kept[1]["link"] == "https://ok.co/2b"
    assert [h["title"] for h in hidden] == ["B"] and hidden[0]["motivo"]
