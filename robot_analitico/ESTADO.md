# ESTADO (tablero único)

Formato tomado de `paquete_v2/plantillas/DECISION_Y_APRENDIZAJE.md`. Hitos y pesos de la sección 11.1 de la guía.

Avance verificado v2: 0,0 %. Un hito cuenta solo con toda su evidencia; ninguno la tiene completa todavía porque todos dependen de decisiones del equipo, de una prueba de conexión real o de la defensa. Hay avance técnico (código y pruebas), detallado abajo.

| Hito | Peso | Estado | Evidencia comprobable |
|---|---:|---|---|
| M1 Mandato y base | 5 % | En progreso | Regresión v1: 54 pruebas en verde en `f6ce7d9`. Falta: mandato del equipo (README, sección Mandato). |
| M2 Mercado y pandas | 12 % | En progreso (técnico) | `src/market.py` + `tests/unit/test_market_quote_v2.py` (mocks). Falta: consultas reales sucesivas con capturas (P2-3) y prueba de 20 válidos + error en modo mercado. |
| M3 Matrices y riesgo | 13 % | En progreso (técnico) | `src/portfolio.py` + pruebas P2-6 a P2-11 en verde. Falta: cálculo manual reconstruido por el equipo. |
| M4 Portafolios | 15 % | En progreso (técnico) | Pruebas P2-13 a P2-17 en verde (GMV, tangente y óptimo personal contra controles analíticos). Falta: restricciones y γ decididas por el equipo. |
| M5 Black-Litterman | 12 % | En progreso (técnico) | `src/black_litterman.py` + pruebas P2-19 a P2-23. Falta: views propias defendidas y sensibilidad. |
| M6 Rebalanceo | 12 % | En progreso (técnico) | `src/rebalance.py` + pruebas P2-25 a P2-28. Falta: política del equipo y evaluación walk-forward de estrategias (P2-29, P2-30). |
| M7 Beta y CAPM | 10 % | En progreso (técnico) | `src/capm.py` + pruebas P2-31 a P2-33. Falta: benchmark del equipo y CML con proxy justificado. |
| M8 Valoración | 8 % | En progreso (técnico) | Prueba P2-34; Ke y WACC del caso en la interfaz. Falta: proyección de 5 años y sensibilidad del equipo. |
| M9 UX y reproducción | 5 % | En progreso | Traza JSON con analysis_id, snapshot SHA-256 y commit. Falta: P2-35 y reproducción por otro integrante. |
| M10 Defensa individual | 8 % | Pendiente (solo docente) | |

Dependencia y siguiente acción: el equipo define el mandato (preguntas iniciales del prompt tutor) y valida el caso de dos activos a mano; luego se hace la prueba de conexión real y se ajustan los supuestos en la interfaz.
Decisión humana pendiente: mandato, ruta de especialización, universo y benchmark, rf, γ, cotas de pesos, w_ref y views de BL, política de rebalanceo, supuestos de la proyección (y si Kd del caso está en COP).
Respaldo local/remoto y SHA verificado: repositorio privado en GitHub; el SHA se verifica al integrar cada pull request.
