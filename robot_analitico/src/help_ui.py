"""
Botón flotante «¿Necesitas ayuda?» y su ventana (solo interfaz; los textos están en help_assistant).

Cómo funciona, sin IA ni servicios externos:
- La ventana trae la ayuda de TODAS las secciones y módulos del Laboratorio. Un JavaScript pequeño
  mira qué pestaña está abierta y la anota en <html data-dpst-sec="…" data-dpst-mod="…">; el CSS
  muestra solo el bloque que corresponde. Así no hace falta recargar la app al cambiar de pestaña.
- El «siguiente paso» se calcula en Python con el estado de la sesión (help_assistant.next_steps).
- «Ir a…» reutiliza los atajos [data-dpst-go] de ui_fx; «Buscar» abre el buscador Ctrl/⌘ K.
"""
from __future__ import annotations

import html
import json
import re

import streamlit as st
import streamlit.components.v1 as components

from src import help_assistant as ha

FAB_KEY = "dpst_help_fab"


def _md(text: str) -> str:
    """Escapa el texto y convierte **negrita** en <strong>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text))


def _steps(steps) -> str:
    return "<ol class='hp-steps'>" + "".join(f"<li>{_md(s)}</li>" for s in steps) + "</ol>"


def _faqs(faqs) -> str:
    return "".join(f"<details class='hp-faq'><summary>{_md(q)}</summary><p>{_md(a)}</p></details>" for q, a in faqs)


def _go_attrs(top: str, open_: "str | None" = None, sub: "str | None" = None) -> str:
    out = f'data-dpst-go="{html.escape(top)}" data-dpst-help="go"'
    if open_:
        out += f' data-dpst-open="{html.escape(open_)}"'
    if sub:
        out += f' data-dpst-sub="{html.escape(sub)}"'
    return out


def panel_html(lab_modules, module_titles, summary: dict) -> str:
    """HTML de la ventana de ayuda (orden: dónde estás, qué hacer, siguiente paso, preguntas, accesos, aviso)."""
    parts = ["<div class='dpst-help'>",
             "<div class='hp-head'><span class='hp-title'>Ayuda</span>"
             "<button type='button' class='hp-x' data-dpst-help='close' aria-label='Cerrar la ayuda'>✕</button></div>"]
    for sec in ha.SECTIONS:
        parts.append(f"<section class='hp-sec' data-sec='{sec.slug}'>")
        where = f"<span class='hp-here'>{html.escape(sec.label)}</span>"
        if sec.slug == "lab":
            for i, (easy, _tech) in enumerate(module_titles, start=1):
                where += (f"<span class='hp-mod' data-mod='{i}'> › {html.escape(lab_modules[i - 1])}"
                          f" <em>({html.escape(easy)})</em></span>")
        parts.append(f"<p class='hp-where'><span class='hp-k'>Estás en:</span> {where}</p>")
        parts.append("<h4>Qué puedes hacer aquí</h4>")
        if sec.slug == "lab":
            parts.append(f"<div class='hp-nomod'>{_steps(sec.steps)}</div>")
            for i, (steps, _faq) in enumerate(ha.LAB_MODULE_HELP, start=1):
                parts.append(f"<div class='hp-mod' data-mod='{i}'>{_steps(steps + (sec.steps[0],))}</div>")
        else:
            parts.append(_steps(sec.steps))
        parts.append(f"<p class='hp-path'>Ruta: {html.escape(sec.path)}</p></section>")

    steps = ha.next_steps(**summary)
    label, top, open_, sub = ha.next_target(**summary)
    go = (f"<button type='button' class='hp-btn hp-primary' {_go_attrs(top, open_, sub)}>"
          f"{html.escape(label)} →</button>")
    parts.append(f"<h4>Siguiente paso recomendado</h4><ul class='hp-next'><li>{_md(steps[0])}</li></ul>{go}")
    if steps[1:]:  # después del paso principal solo van avisos del Centro de estados
        parts.append("<ul class='hp-next'>" + "".join(f"<li class='hp-warn'>{_md(s)}</li>" for s in steps[1:]) + "</ul>")

    parts.append("<h4>Preguntas frecuentes</h4>")
    for sec in ha.SECTIONS:
        if sec.slug == "lab":
            parts.append(f"<div class='hp-sec' data-sec='lab'><div class='hp-nomod'>{_faqs(sec.faqs)}</div>")
            for i, (_steps_, faqs) in enumerate(ha.LAB_MODULE_HELP, start=1):
                parts.append(f"<div class='hp-mod' data-mod='{i}'>{_faqs(faqs)}</div>")
            parts.append("</div>")
        else:
            parts.append(f"<div class='hp-sec' data-sec='{sec.slug}'>{_faqs(sec.faqs)}</div>")

    gloss = "".join(f"<dt>{html.escape(t)}</dt><dd>{html.escape(d)}</dd>" for t, d in ha.GLOSSARY)
    parts.append("<div class='hp-tools'>"
                 "<button type='button' class='hp-btn' data-dpst-help='search'>Buscar una sección "
                 "<kbd>Ctrl/⌘ K</kbd></button>"
                 f"<details class='hp-gloss'><summary>Glosario rápido</summary><dl>{gloss}</dl></details></div>")
    parts.append(f"<p class='hp-foot'>{html.escape(ha.DISCLAIMER)}</p></div>")
    return "".join(parts)


def _css() -> str:
    show_sec = ",\n".join(
        [f"html[data-dpst-sec='{s.slug}'] .hp-sec[data-sec='{s.slug}']" for s in ha.SECTIONS]
        + ["html:not([data-dpst-sec]) .hp-sec[data-sec='inicio']"])
    show_mod = ",\n".join(f"html[data-dpst-mod='{i}'] .hp-mod[data-mod='{i}']"
                          for i in range(1, len(ha.LAB_MODULE_HELP) + 1))
    return f"""<style>
/* Pastilla fija, encima del botón «Ir a… Ctrl K» (#dpst-k). Los dos van más arriba que la barra
   «Manage app» que Streamlit Cloud pone abajo a la derecha. */
.st-key-{FAB_KEY} {{ position: fixed; z-index: 1000000; right: calc(18px + env(safe-area-inset-right, 0px));
  bottom: calc(108px + env(safe-area-inset-bottom, 0px)); width: auto !important; }}
.st-key-{FAB_KEY} [data-testid="stPopover"] button {{ border-radius: 999px; padding: 5px 12px; min-height: 0; font-size: 0.8rem;
  font-weight: 600; color: var(--dp-on-accent); background: var(--dp-accent); border: 1px solid transparent;
  box-shadow: 0 12px 28px rgba(var(--dp-accent-rgb), 0.32); transition: transform .2s cubic-bezier(.2,.8,.2,1), box-shadow .2s; }}
.st-key-{FAB_KEY} [data-testid="stPopover"] button:hover {{ transform: translateY(-2px); color: var(--dp-on-accent);
  box-shadow: 0 16px 34px rgba(var(--dp-accent-rgb), 0.42); border-color: transparent; }}
.st-key-{FAB_KEY} [data-testid="stPopover"] button:focus-visible {{ outline: 2px solid var(--dp-ink); outline-offset: 2px; }}
.st-key-{FAB_KEY} [data-testid="stPopover"] button p, .st-key-{FAB_KEY} [data-testid="stPopover"] button span {{ color: inherit; font-size: 0.8rem; }}
html.dpst-present .st-key-{FAB_KEY} {{ display: none !important; }}
@media print {{ .st-key-{FAB_KEY} {{ display: none !important; }} }}
/* Ventana */
[data-testid="stPopoverBody"]:has(.dpst-help) {{ width: min(380px, calc(100vw - 32px)); max-height: min(72vh, 640px);
  overflow-y: auto; border-radius: 16px; background: var(--dp-surface); border: 1px solid rgba(var(--dp-line-rgb), 0.18);
  box-shadow: 0 24px 60px rgba(var(--dp-shadow-rgb), calc(0.3 * var(--dp-shadow-k))); animation: hp-in .22s cubic-bezier(.2,.8,.2,1); }}
@keyframes hp-in {{ from {{ opacity: 0; transform: translateY(8px) scale(.98); }} to {{ opacity: 1; transform: none; }} }}
@media (prefers-reduced-motion: reduce) {{ [data-testid="stPopoverBody"]:has(.dpst-help) {{ animation: none; }} }}
.dpst-help {{ color: var(--dp-ink); font-size: 0.88rem; line-height: 1.45; }}
.dpst-help .hp-head {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }}
.dpst-help .hp-title {{ font-weight: 700; font-size: 1rem; }}
.dpst-help .hp-x {{ width: 30px; height: 30px; border-radius: 8px; border: 1px solid rgba(var(--dp-line-rgb), 0.18);
  background: transparent; color: var(--dp-muted); cursor: pointer; }}
.dpst-help .hp-x:hover {{ color: var(--dp-ink); background: rgba(var(--dp-accent-rgb), 0.08); }}
.dpst-help h4 {{ font-size: 0.72rem; letter-spacing: .1em; text-transform: uppercase; color: var(--dp-muted);
  margin: 14px 0 6px; padding: 0; font-weight: 600; }}
.dpst-help .hp-where {{ margin: 4px 0 0; padding: 8px 10px; border-radius: 10px; background: rgba(var(--dp-accent-rgb), 0.08); }}
.dpst-help .hp-k {{ color: var(--dp-muted); }}
.dpst-help .hp-here {{ font-weight: 600; }}
.dpst-help .hp-where em {{ color: var(--dp-muted); font-style: normal; }}
.dpst-help ol.hp-steps, .dpst-help ul.hp-next {{ margin: 0; padding-left: 1.2rem; }}
.dpst-help li {{ margin: 2px 0; }}
.dpst-help .hp-path {{ margin: 6px 0 0; font-size: 0.78rem; color: var(--dp-muted); }}
.dpst-help li.hp-warn {{ list-style: none; margin-top: 8px; margin-left: -1.2rem; padding: 6px 9px; border-radius: 9px;
  background: rgba(var(--dp-amber-rgb), 0.12); border-left: 3px solid var(--dp-amber); }}
.dpst-help .hp-btn {{ display: inline-flex; align-items: center; gap: 6px; margin-top: 8px; padding: 6px 12px; border-radius: 999px;
  font: inherit; font-size: 0.82rem; font-weight: 600; cursor: pointer; color: var(--dp-ink);
  background: var(--dp-surface-2); border: 1px solid rgba(var(--dp-line-rgb), 0.2); }}
.dpst-help .hp-btn:hover {{ border-color: var(--dp-accent); }}
.dpst-help .hp-primary {{ color: var(--dp-on-accent); background: var(--dp-accent); border-color: transparent; }}
.dpst-help .hp-primary:hover {{ border-color: transparent; filter: brightness(1.06); }}
.dpst-help kbd {{ font: 500 0.7rem 'Geist Mono', ui-monospace, monospace; padding: 1px 5px; border-radius: 5px;
  background: rgba(var(--dp-accent-rgb), 0.12); color: inherit; }}
.dpst-help details {{ border-bottom: 1px solid rgba(var(--dp-line-rgb), 0.12); padding: 5px 0; }}
.dpst-help summary {{ cursor: pointer; font-weight: 500; }}
.dpst-help details p {{ margin: 4px 0 2px; color: var(--dp-text-1); }}
.dpst-help .hp-tools {{ margin-top: 10px; }}
.dpst-help dl {{ margin: 6px 0 0; }}
.dpst-help dt {{ font-weight: 600; margin-top: 4px; }}
.dpst-help dd {{ margin: 0; color: var(--dp-text-1); }}
.dpst-help .hp-foot {{ margin: 12px 0 0; padding-top: 8px; border-top: 1px solid rgba(var(--dp-line-rgb), 0.14);
  font-size: 0.76rem; color: var(--dp-muted); }}
/* Solo se ve la ayuda de la pestaña abierta (la anota el JavaScript en <html>). */
.dpst-help .hp-sec, .dpst-help .hp-mod {{ display: none; }}
{show_sec} {{ display: block; }}
{show_mod} {{ display: inline; }}
{",".join(f"html[data-dpst-mod='{i}'] div.hp-mod[data-mod='{i}']" for i in range(1, len(ha.LAB_MODULE_HELP) + 1))} {{ display: block; }}
html[data-dpst-mod] .dpst-help .hp-nomod {{ display: none; }}
</style>"""


_JS = """<script>
(function () {
  const P = window.parent, D = P.document;
  if (P.__dpstHelp) return; P.__dpstHelp = 1;
  const SEC = __SEC__, MODS = __MODS__;
  const pick = s => { const a = D.querySelector(s + ' > [data-testid="stTabs"] > div > [role="tablist"] > [role="tab"][aria-selected="true"]'); return a ? a.textContent.trim() : null; };
  function sync() {
    const r = D.documentElement, top = pick('.st-key-dpst_nav'), slug = SEC[top] || 'inicio';
    r.setAttribute('data-dpst-sec', slug);
    const i = MODS.indexOf(pick('.st-key-lab_nav'));
    if (slug === 'lab' && i >= 0) r.setAttribute('data-dpst-mod', String(i + 1)); else r.removeAttribute('data-dpst-mod');
  }
  let t = null;
  new P.MutationObserver(() => { clearTimeout(t); t = setTimeout(sync, 80); })
    .observe(D.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['aria-selected'] });
  sync();
  function clickTab(scope, label) {
    for (const x of D.querySelectorAll(scope + ' > [data-testid="stTabs"] > div > [role="tablist"] > [role="tab"]'))
      if (x.textContent.trim() === label) { x.click(); return x; }
    return null;
  }
  function closePanel() {
    if (!D.querySelector('.dpst-help')) return;
    const b = D.querySelector('.st-key-__FAB__ [data-testid="stPopover"] button');
    if (b) b.click();
  }
  D.addEventListener('click', e => {
    const el = e.target && e.target.closest ? e.target.closest('[data-dpst-help]') : null;
    if (!el) return;
    const act = el.dataset.dpstHelp;
    if (act === 'close') { closePanel(); return; }
    if (act === 'search') { closePanel(); setTimeout(() => { const k = D.getElementById('dpst-k'); if (k) k.click(); }, 150); return; }
    if (act === 'go') {   // la navegación la hace ui_fx con data-dpst-go; aquí solo el módulo y el cierre
      closePanel();
      if (el.dataset.dpstSub) setTimeout(() => clickTab('.st-key-lab_nav', el.dataset.dpstSub), 500);
    }
  });
})();
</script>"""


def open_help_fab():
    """Dibuja la pastilla (llamar justo después de aceptar los consentimientos) y devuelve su ventana vacía."""
    st.markdown(_css(), unsafe_allow_html=True)
    with st.container(key=FAB_KEY):
        pop = st.popover("¿Necesitas ayuda?", icon=":material/help:")
    return pop


def fill_help_fab(pop, *, lab_modules, module_titles, summary: dict) -> None:
    """Llena la ventana al final de la ejecución, cuando ya se sabe qué se calculó y qué avisos hay."""
    with pop:
        st.markdown(panel_html(lab_modules, module_titles, summary), unsafe_allow_html=True)
    sec = json.dumps({s.label: s.slug for s in ha.SECTIONS}, ensure_ascii=False)
    mods = json.dumps(list(lab_modules), ensure_ascii=False)
    components.html(_JS.replace("__SEC__", sec).replace("__MODS__", mods).replace("__FAB__", FAB_KEY), height=0)
