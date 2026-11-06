# Cambios

Formato basado en *Keep a Changelog*. Versiones: `MAYOR.MENOR.PARCHE`.

## [2.0.0] — 2026-11-06 (entrega final)

### Agregado
- Laboratorio de portafolios: riesgo conjunto, estrés, estimadores (muestral, Ledoit-Wolf, EWMA), Markowitz y
  fronteras (con y sin cortos), CML con proxy rotulado, Black-Litterman, rebalanceo simulado, backtest walk-forward,
  beta/CAPM, valoración del caso Alimentos y traza exportable verificada.
- Moneda base USD/COP en el laboratorio (`USDCOP=X`), con la conversión en pantalla y en la traza.
- Beta de cada cartera (Σwβ), tabla de betas OLS/Cov/Var con alfa y riesgo sistemático, Hamada sobre un activo real.
- Rendimiento requerido por CAPM y SML con activos y carteras; desempeño frente al benchmark (Sharpe, Treynor, alfa de
  Jensen, error de seguimiento, razón de información).
- Ficha técnica de las carteras con la estructura del Anexo 6 de la Superintendencia Financiera (simulación).
- Pérdida esperada (ES) junto al VaR en activo, canasta y cartera; tablero de señales de la canasta.
- Menú superior, tasas soberanas por lista de países, noticias con enlaces verificados, comprobador de conexiones.
- CI (GitHub Actions), `.env.example`, `.streamlit/secrets.toml.example`, `data/PROCEDENCIA.md`, `docs/` (supuestos y
  límites, ficha del producto, matriz de evolución, anexo con cálculos contrastables), hojas de decisiones del equipo.

### Cambiado
- La conversión de moneda de la Comparación usa el último dato FX disponible en o antes de cada fecha (sin look-ahead).
- Tema visual: acento dorado, sin íconos en títulos.

### Sin cambios
- Pruebas de la v1 (54) y paquete docente `paquete_v2/` (verificado con su manifiesto).

## [1.0.0] — 2026-09-18 (primera versión asignada, base `f6ce7d9`)
- Análisis de un activo: datos, rendimientos logarítmicos, diagnósticos, pronóstico homocedástico con validación
  walk-forward, VaR, entrada/stop-loss/take-profit, comparación de N activos con dominancia y preselección.
