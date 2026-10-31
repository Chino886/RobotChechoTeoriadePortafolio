# ESTADO (tablero único)

Formato tomado de `paquete_v2/plantillas/DECISION_Y_APRENDIZAJE.md`. Hitos y pesos de la sección 11.1 de la guía.

Avance verificado v2: 0,0 %. Un hito cuenta solo con toda su evidencia; ninguno la tiene completa todavía porque todos dependen de decisiones del equipo, de una prueba de conexión real o de la defensa. El avance técnico (código y pruebas) está detallado abajo.

| Hito | Peso | Estado | Evidencia comprobable |
|---|---:|---|---|
| M1 Mandato y base | 5 % | En progreso | Regresión v1: 54 pruebas en verde desde `f6ce7d9`. Falta: mandato del equipo (README, sección Mandato). |
| M2 Mercado y pandas | 12 % | En progreso (técnico) | `src/market.py` (varios tickers, error aislado, gráfico de 1 minuto, registro de consultas) y `src/data_quality.py` (huecos, calendario, barras completas, COP); pruebas P2-5, P2-12 y P2-24. Falta: consultas reales sucesivas con capturas (P2-3) y 20 válidos + error en línea (P2-4). |
| M3 Matrices y riesgo | 13 % | En progreso (técnico) | `src/portfolio.py`, `src/estimators.py`, `src/stress.py`; pruebas P2-6 a P2-11 y Ledoit-Wolf/EWMA/estrés. Falta: cálculo manual reconstruido por el equipo. |
| M4 Portafolios | 15 % | En progreso (técnico) | Pruebas P2-13 a P2-17 (GMV, tangente, óptimo personal, cotas y topes por sector). Falta: restricciones y γ decididas por el equipo; proxy de la CML justificado. |
| M5 Black-Litterman | 12 % | En progreso (técnico) | `src/black_litterman.py`, pruebas P2-19 a P2-23, tabla de sensibilidad. Falta: views propias con su registro completo. |
| M6 Rebalanceo | 12 % | En progreso (técnico) | `src/rebalance.py` y `src/backtest.py`; pruebas P2-25 a P2-30. Falta: política del equipo y conclusiones del backtest (incluidas las adversas). |
| M7 Beta y CAPM | 10 % | En progreso (técnico) | `src/capm.py`, pruebas P2-31 a P2-33. Falta: benchmark del equipo. |
| M8 Valoración | 8 % | En progreso (técnico) | Prueba P2-34; Ke, WACC y sensibilidad EV(WACC, g) en la interfaz. Falta: proyección de 5 años y escenarios del caso (insumos importados, rezago de margen, tasas, covenant). |
| M9 UX y reproducción | 5 % | En progreso | `src/trace.py` y prueba P2-35; `requirements-lock.txt`. Falta: reproducción por otro integrante (P2-36). |
| M10 Defensa individual | 8 % | Pendiente (solo docente) | |

Dependencia y siguiente acción: el equipo define el mandato (preguntas iniciales del prompt tutor), hace la prueba de conexión real en el bot desplegado y reconstruye a mano el caso de dos activos; luego se ajustan los supuestos en la interfaz y se registran las decisiones en BITACORA.
Decisión humana pendiente: mandato, ruta de especialización, universo y benchmark, rf, γ, cotas y topes por sector, proxy de la CML, w_ref y views de BL, λ de EWMA, política de rebalanceo, límite de pérdida del mandato, supuestos de la proyección (y si Kd del caso está en COP).
Respaldo local/remoto y SHA verificado: repositorio privado en GitHub; el SHA se verifica al integrar cada pull request.
