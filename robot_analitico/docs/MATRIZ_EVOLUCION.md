# Matriz de evolución (guía final, sección 2)

Una fila por cambio relevante entre la primera versión asignada (v1, base `f6ce7d9`) y la versión final (2.0.0).
Las filas de observaciones del docente las completa el equipo con lo que se le haya señalado.

| Aspecto | Primera versión | Versión final | Evidencia y utilidad |
|---|---|---|---|
| **Requisito:** navegación | Una sola página larga con todas las secciones seguidas | Menú superior (Inicio, Preselección, Tasas soberanas, Laboratorio) y secciones desplegables | PR 11–14; capturas. Se muestra solo lo que se explica en la sustentación |
| **Requisito:** carteras | La política de ejecución excluía pesos, covarianzas y frontera eficiente | Laboratorio: Σ válida (PSD), frontera y CML con proxy, GMV, tangente, máximo rendimiento, óptimo personal, BL, rebalanceo, backtest | `tests/unit/test_portfolio_v2.py`, `test_optimizer_precision_v2.py` (error ≤ 1e-9 frente a una referencia exacta) |
| **Requisito:** riesgo | VaR paramétrico de un activo | VaR + pérdida esperada (ES) por activo, canasta y cartera; estrés individual, conjunto, ruptura de correlaciones e inverso | `test_final_guide_v2.py` (ES contra simulación) |
| **Requisito:** moneda | Conversión con el FX reindexado a las fechas del activo (podía usar un dato FX más viejo que el disponible) | FX con el último dato en o antes de cada fecha; moneda base USD/COP en el laboratorio | `test_fx_alignment_v2.py`: falla con el código anterior y pasa con el nuevo |
| **Requisito:** señales | Señal por activo dentro de cada desplegable | Tablero de señales de la canasta (entrada, SL, TP, P_BE, BR_neto, VaR, ES) descargable | `test_lab_currency_beta_ui_v2.py::test_basket_signal_board_and_expected_shortfall` |
| **Observación:** auditoría externa (8 puntos) | Precisión del optimizador ~2e-4, cortos sin frontera analítica, rebalanceo sin caja mínima, backtest sin views por fecha, traza incompleta | Corregidos: conjunto activo certificado, frontera analítica con cortos, caja mínima y reestimación, BL con fecha de conocimiento, traza con todas las claves | PR 11; ESTADO; pruebas `*_v2.py` |
| **Observación:** enlaces de noticias rotos (equipo) | Se mostraban enlaces de Google News que no abrían la noticia | Cada enlace se verifica y se traduce al medio original; los rotos se ocultan | `test_news_links_v2.py` |
| **Observación:** Colombia no aparecía en tasas (equipo) | Búsqueda por texto en FRED, escribiendo el país | Lista de países (OCDE, FMI y búsqueda por nombre), sin repetidos | `test_rates_countries_v2.py`; PR 15–17 |
| **Observación:** revisión cruzada con el repositorio de Checho | Sin moneda base en el laboratorio ni beta de cartera | Moneda base, beta de cada cartera, tabla OLS/Cov/Var con alfa, Hamada sobre un activo real; mismos controles en los dos repositorios | BITACORA VC-01; `test_portfolio_beta_v2.py`; PR 19 |
| **Observación del docente (equipo)** | | | |
| **Nueva aplicación:** ficha técnica | No existía | Ficha técnica de la tangente, mínimo riesgo, mayor rendimiento y óptimo personal con la estructura del Anexo 6 de la SFC | `test_final_guide_v2.py`; módulo «Ficha técnica» |
| **Nueva aplicación:** desempeño y CAPM | Sin benchmark | Sharpe, Treynor, alfa de Jensen, razón de información, riesgo sistemático (R²), rendimiento requerido por CAPM y SML con activos y carteras | `test_final_guide_v2.py`; `test_lab_currency_beta_ui_v2.py` |
| **Nueva aplicación:** evidencia reproducible | Sin traza ni verificación | Traza JSON + snapshot con SHA-256, comprobador de conexiones con CSV, CI, anexo con cálculos contrastables | `test_trace_v2.py`, `test_connectivity_v2.py`, `.github/workflows/tests.yml` |
