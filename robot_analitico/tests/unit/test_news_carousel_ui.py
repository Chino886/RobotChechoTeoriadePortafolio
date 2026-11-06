"""Recuadro de noticias de Inicio (src/ui_fx.news_carousel_html): solo presentación."""
from src.ui_fx import news_carousel_html


def _fmt(raw):
    return raw or "fecha N/D"


ITEMS = [
    {"title": "Bancos centrales mantienen tasas", "link": "https://example.com/a", "publisher": "Reuters",
     "published": "2026-11-05 10:00"},
    {"title": "<script>alert(1)</script> & otra", "link": "javascript:alert(1)", "publisher": "",
     "published": None},
]


def test_una_diapositiva_y_una_fila_por_noticia():
    out = news_carousel_html(ITEMS, "Economía", _fmt)
    assert out.count('class="nv-slide"') == 2
    assert out.count('data-go="') == 2
    assert "<b>01</b> / 02" in out


def test_escapa_titulos_y_rechaza_enlaces_no_http():
    out = news_carousel_html(ITEMS, "Economía", _fmt)
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert "javascript:" not in out
    assert 'href="https://example.com/a"' in out
    assert "Medio N/D" in out and "fecha N/D" in out


def test_sin_lineas_en_blanco_para_markdown():
    assert "\n\n" not in news_carousel_html(ITEMS, "Economía", _fmt)
