# ESTADO (tablero único)

Formato tomado de `paquete_v2/plantillas/DECISION_Y_APRENDIZAJE.md`. Hitos y pesos de la sección 11.1 de la guía.

Avance verificado v2: 0,0 %. Un hito cuenta solo con toda su evidencia; ninguno la tiene completa todavía porque todos dependen de decisiones del equipo, de una prueba de conexión real o de la defensa. El avance técnico (código y pruebas) está detallado abajo.

| Hito | Peso | Estado | Evidencia comprobable |
|---|---:|---|---|
| M1 Mandato y base | 5 % | En progreso | Regresión v1: 54 pruebas en verde desde `f6ce7d9`; suite completa: 166 pruebas en verde (las 54 de la v1 sin cambios) y CI en GitHub Actions. Hoja de decisiones lista para llenar: `decisiones/MANDATO_EQUIPO.md`. Falta: mandato del equipo (README, sección Mandato). |
| M2 Mercado y pandas | 12 % | En progreso (técnico) | `src/market.py` y `src/data_quality.py`; pruebas P2-4 (20 válidos + 1 inválido, con mocks), P2-5, P2-12 y P2-24. Moneda base USD/COP en el laboratorio (selector rotulado «decisión del equipo», USD por defecto; USDCOP=X con P_COP = P_USD·FX y el último FX en o antes de cada fecha; moneda y conversión en la traza) y alineación FX sin look-ahead en la Comparación (`align_fx_no_lookahead`; prueba con una fecha FX ausente del activo, que fallaba antes). Comprobador de conexiones reales en Inicio (`src/connectivity.py`: Yahoo cotización e históricos, FRED, Google News, Alpha Vantage; hora UTC, resultado y tiempo; CSV descargable). Falta: hacer las consultas sucesivas en el bot desplegado y guardar CSV y capturas (P2-3). |
| M3 Matrices y riesgo | 13 % | En progreso (técnico) | `src/portfolio.py`, `src/estimators.py`, `src/stress.py`; pruebas P2-6 a P2-11 y Ledoit-Wolf/EWMA/estrés. Hoja `decisiones/CALCULO_MANUAL_DOS_ACTIVOS.md` con pasos y resultados del bot para comparar (GMV 0,8571/0,1429; tangente 0,6341/0,3659; óptimo personal 0,5714/0,4286). Falta: cálculo manual reconstruido por el equipo. |
| M4 Portafolios | 15 % | En progreso (técnico) | Pruebas P2-13 a P2-18; optimizador contrastado con una referencia exacta (error ≤ 1e-9 en pesos); cortos con frontera y tangente analíticas. Falta: restricciones, γ y rendimiento objetivo máximo decididos por el equipo; proxy de la CML justificado. |
| M5 Black-Litterman | 12 % | En progreso (técnico) | `src/black_litterman.py`, pruebas P2-19 a P2-23, tabla de sensibilidad. Falta: views propias con su registro completo. |
| M6 Rebalanceo | 12 % | En progreso (técnico) | `src/rebalance.py` (caja mínima, reestimación por ventana conocida, eventos de views, costo-beneficio, duplicados registrados) y `src/backtest.py` (BL con views por fecha, estimadores, selección en validación); pruebas P2-24 a P2-30. Falta: política del equipo y conclusiones del backtest (incluidas las adversas). |
| M7 Beta y CAPM | 10 % | En progreso (técnico) | `src/capm.py`, pruebas P2-31 a P2-33. Con datos de mercado: tabla de betas con OLS, Cov/Var, diferencia y alfa (P2-31); beta de GMV, tangente, óptimo personal y máximo rendimiento como Σwβ con `portfolio_beta` (P102, P104; error si falta una beta); Hamada sobre un activo real con D/E, impuesto, beta de la deuda y D/E objetivo en cero hasta que el equipo los decida. Validación cruzada con el repositorio de Checho (BITACORA VC-01). Falta: benchmark del equipo y datos de Hamada por empresa. |
| M8 Valoración | 8 % | En progreso (técnico) | `src/valuation.py`: proyección (EBIT₀ = 18.000 reproducido), NWC, covenant deuda/EBITDA, meta presupuestal y brecha de EBIT, FCFE vs FCFF, iteración D/E, chequeo g/ROIC y escenarios FX/rezago/tasa variable; pruebas P2-34 y del motor. Falta: regla de CAPEX/capacidad del PDF del caso (pendiente de confirmar), proyección y magnitudes de escenarios del equipo. |
| M9 UX y reproducción | 5 % | En progreso | `src/trace.py` con todas las claves de `trazabilidad.json` (o null con motivo) y prueba P2-35; `requirements-lock.txt` con scikit-learn. Guía `decisiones/REPRODUCCION_P2-36.md` y `scripts/verify_package.py` (24/24 archivos del paquete coinciden). Falta: reproducción por otro integrante (P2-36). |
| M10 Defensa individual | 8 % | Pendiente (solo docente) | |

Dependencia y siguiente acción (en este orden):
1. Inicio → *Comprobar conexiones reales*: dos consultas separadas por unos minutos, CSV y captura (P2-3, M2).
2. Llenar `decisiones/MANDATO_EQUIPO.md` (sección A primero) y pasar cada decisión al README.
3. Reconstruir a mano `decisiones/CALCULO_MANUAL_DOS_ACTIVOS.md`, cada integrante su parte (M3, M4).
4. Poner los supuestos en el bot, llenar las copias de `decisiones/politica_rebalanceo.json` y `decisiones/view_BL_V1.json`, y abrir una entrada en BITACORA por decisión.
5. Otro integrante sigue `decisiones/REPRODUCCION_P2-36.md` (M9).
6. Confirmar con el PDF del caso la regla de CAPEX/capacidad y si Kd está en COP (M8).
7. Pasar el repositorio a privado antes de entregar.
Decisión humana pendiente: moneda base del mandato (USD o COP), datos de Hamada de cada empresa (D/E actual, impuesto, beta de la deuda, D/E objetivo), mandato, ruta de especialización, universo y benchmark, rf, γ, cotas y topes por sector, rendimiento objetivo máximo con cortos, proxy de la CML, w_ref y views de BL (con fecha de conocimiento), λ de EWMA y candidatos del backtest, política de rebalanceo (banda, calendario, caja mínima, margen costo-beneficio), límite de pérdida del mandato, proyección de la valoración y magnitudes de escenarios; confirmar la regla de CAPEX/capacidad del caso y si Kd está en COP.
Respaldo local/remoto y SHA verificado: repositorio en GitHub **público** (verificado el 2026-10-31 con una consulta anónima a la API: responde 200). El equipo lo mantiene público mientras edita y lo pasará a privado antes de presentar; la guía (sección 13) exige privado para la entrega. El SHA se verifica al integrar cada pull request.


## Cobertura de la guía final de sustentación (sesión del 9 de noviembre de 2026)

Sección 4, núcleo financiero mínimo:

| Componente | Dónde está en el bot | Estado |
|---|---|---|
| Datos y rendimientos | Preselección → Datos del activo, Análisis histórico | Cubierto (v1) |
| Historia y supuestos (normalidad, autocorrelación, homocedasticidad) | Análisis histórico → Diagnósticos (Jarque-Bera, Ljung-Box, Brown-Forsythe, ARCH) | Cubierto (v1) |
| Pronóstico y validación (homocedástico, walk-forward, referencia simple) | Preselección → Pronóstico | Cubierto (v1) |
| Riesgo y probabilidades (VaR, **pérdida esperada**, drawdown, niveles terminales) | Pronóstico → Riesgo; canasta; Laboratorio → Riesgo conjunto | Cubierto; **ES agregada** |
| Comparación de activos | Preselección → Comparación | Cubierto (v1); FX sin look-ahead |
| Portafolios y frontera (Σ PSD, frontera, CML, **R² sistemático/no sistemático**, **ficha técnica** de tangente, mínimo riesgo y mayor rendimiento) | Laboratorio → Riesgo conjunto, Markowitz, Beta/CAPM, **Ficha técnica** | Cubierto; **R² y ficha técnica (estructura SFC) agregados** |
| Betas y rendimiento requerido (**CAPM por activo y cartera, SML**, proxy, rf y ventana declarados) | Laboratorio → Beta, CAPM y valoración | Cubierto; **CAPM/SML con datos de mercado agregados** |
| Desempeño y benchmark (**Sharpe, Treynor, alfa de Jensen, razón de información**) | Laboratorio → Beta, CAPM y valoración | **Agregado** |
| Rebalanceo y señales (costos, rotación, **tablero de señales**, sin ejecutar órdenes) | Laboratorio → Rebalanceo y Backtest; Preselección → canasta | Cubierto; **tablero de señales agregado** |

Sección 7, entregables del repositorio: README (instalación paso a paso), `requirements.txt` + `requirements-lock.txt`,
`.env.example` y `.streamlit/secrets.toml.example`, `tests/` + CI, `CHANGELOG.md`, `docs/` (supuestos y límites, ficha
del producto, matriz de evolución, anexo `calculos_contrastables.ipynb`), `data/PROCEDENCIA.md`, `CONTRIBUTIONS.md`,
`AI_USAGE.md`, aviso académico, versión y commit visibles en Inicio.

Pendiente del equipo para la sustentación: usuario, problema, oferta de valor y dirección futura
(`docs/FICHA_PRODUCTO.md`); observaciones del docente en la matriz de evolución; benchmark y ERP; diapositivas (7) y
guion de la demostración en vivo; etiqueta `v2.0.0` sobre el commit que se sustenta; enviar el enlace antes del
domingo 8 de noviembre; repositorio privado con acceso para el docente.
