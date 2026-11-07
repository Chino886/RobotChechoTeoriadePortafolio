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
    assert out.count('class="nv-row') == 2       # lista de titulares
    assert out.count('class="nv-pip ') + out.count('class="nv-pip"') == 2   # indicadores de posición
    assert out.count('data-go="') == 4           # filas + indicadores saltan a una noticia
    assert "<b>01</b> / 02" in out


def test_escapa_titulos_y_rechaza_enlaces_no_http():
    out = news_carousel_html(ITEMS, "Economía", _fmt)
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert "javascript:" not in out
    assert 'href="https://example.com/a"' in out
    assert "Medio N/D" in out and "fecha N/D" in out


def test_sin_lineas_en_blanco_para_markdown():
    assert "\n\n" not in news_carousel_html(ITEMS, "Economía", _fmt)


def test_resumen_imagen_y_categoria_solo_si_la_fuente_los_trae():
    items = [
        {"title": "Con todo", "link": "https://example.com/a", "publisher": "Alpha", "published": "x",
         "summary": "Resumen real.", "image": "https://img.example.com/a.jpg", "category": "Mercados"},
        {"title": "Sin extras", "link": "https://example.com/b", "publisher": "Google", "published": "y"},
        {"title": "Imagen mala", "link": "https://example.com/c", "publisher": "Y", "published": "z",
         "image": "javascript:alert(1)"},
    ]
    out = news_carousel_html(items, "Economía", _fmt)
    assert out.count('class="nv-sum"') == 1 and "Resumen real." in out
    assert out.count("<img ") == 1 and 'src="https://img.example.com/a.jpg"' in out
    assert '<span class="nv-cat">Mercados</span>' in out
    assert out.count('<span class="nv-cat">Economía</span>') == 2   # sin tema propio: la pestaña
    assert "javascript:" not in out
