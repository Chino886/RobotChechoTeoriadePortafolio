# ESTADO (tablero único)

Formato tomado de `paquete_v2/plantillas/DECISION_Y_APRENDIZAJE.md`. Hitos y pesos de la sección 11.1 de la guía.

Avance verificado v2: 0,0 %. Un hito cuenta solo con toda su evidencia; ninguno la tiene completa todavía porque todos dependen de decisiones del equipo, de una prueba de conexión real o de la defensa. El avance técnico (código y pruebas) está detallado abajo.

| Hito | Peso | Estado | Evidencia comprobable |
|---|---:|---|---|
| M1 Mandato y base | 5 % | En progreso | Regresión v1: 54 pruebas en verde desde `f6ce7d9`. Falta: mandato del equipo (README, sección Mandato). |
| M2 Mercado y pandas | 12 % | En progreso (técnico) | `src/market.py` y `src/data_quality.py`; pruebas P2-4 (20 válidos + 1 inválido, con mocks), P2-5, P2-12 y P2-24. Falta: consultas reales sucesivas con capturas (P2-3). |
| M3 Matrices y riesgo | 13 % | En progreso (técnico) | `src/portfolio.py`, `src/estimators.py`, `src/stress.py`; pruebas P2-6 a P2-11 y Ledoit-Wolf/EWMA/estrés. Falta: cálculo manual reconstruido por el equipo. |
| M4 Portafolios | 15 % | En progreso (técnico) | Pruebas P2-13 a P2-18; optimizador contrastado con una referencia exacta (error ≤ 1e-9 en pesos); cortos con frontera y tangente analíticas. Falta: restricciones, γ y rendimiento objetivo máximo decididos por el equipo; proxy de la CML justificado. |
| M5 Black-Litterman | 12 % | En progreso (técnico) | `src/black_litterman.py`, pruebas P2-19 a P2-23, tabla de sensibilidad. Falta: views propias con su registro completo. |
| M6 Rebalanceo | 12 % | En progreso (técnico) | `src/rebalance.py` (caja mínima, reestimación por ventana conocida, eventos de views, costo-beneficio, duplicados registrados) y `src/backtest.py` (BL con views por fecha, estimadores, selección en validación); pruebas P2-24 a P2-30. Falta: política del equipo y conclusiones del backtest (incluidas las adversas). |
| M7 Beta y CAPM | 10 % | En progreso (técnico) | `src/capm.py`, pruebas P2-31 a P2-33. Falta: benchmark del equipo. |
| M8 Valoración | 8 % | En progreso (técnico) | `src/valuation.py`: proyección (EBIT₀ = 18.000 reproducido), NWC, covenant deuda/EBITDA, meta presupuestal y brecha de EBIT, FCFE vs FCFF, iteración D/E, chequeo g/ROIC y escenarios FX/rezago/tasa variable; pruebas P2-34 y del motor. Falta: regla de CAPEX/capacidad del PDF del caso (pendiente de confirmar), proyección y magnitudes de escenarios del equipo. |
| M9 UX y reproducción | 5 % | En progreso | `src/trace.py` con todas las claves de `trazabilidad.json` (o null con motivo) y prueba P2-35; `requirements-lock.txt` con scikit-learn. Falta: reproducción por otro integrante (P2-36). |
| M10 Defensa individual | 8 % | Pendiente (solo docente) | |

Dependencia y siguiente acción: el equipo define el mandato (preguntas iniciales del prompt tutor), hace la prueba de conexión real en el bot desplegado y reconstruye a mano el caso de dos activos; luego se ajustan los supuestos en la interfaz y se registran las decisiones en BITACORA.
Decisión humana pendiente: mandato, ruta de especialización, universo y benchmark, rf, γ, cotas y topes por sector, rendimiento objetivo máximo con cortos, proxy de la CML, w_ref y views de BL (con fecha de conocimiento), λ de EWMA y candidatos del backtest, política de rebalanceo (banda, calendario, caja mínima, margen costo-beneficio), límite de pérdida del mandato, proyección de la valoración y magnitudes de escenarios; confirmar la regla de CAPEX/capacidad del caso y si Kd está en COP.
Respaldo local/remoto y SHA verificado: repositorio en GitHub **público** (verificado el 2026-10-31 con una consulta anónima a la API: responde 200). El equipo lo mantiene público mientras edita y lo pasará a privado antes de presentar; la guía (sección 13) exige privado para la entrega. El SHA se verifica al integrar cada pull request.
