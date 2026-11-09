# Cambios

Formato basado en *Keep a Changelog*. Versiones: `MAYOR.MENOR.PARCHE`.

## [2.0.0] — 2026-11-06 (entrega final)

### Agregado
- Tickers: columnas «País/Bolsa» y «Moneda de cotización», filtro por país o moneda, nota de ADR vs. acción local y
  una lista de 22 acciones internacionales verificadas el 2026-11-09 (se suma a la búsqueda en otras bolsas).
- Comparación: selector de moneda base (USD o COP) y recuadro «Conversión de monedas» con el par usado, la tasa del
  primer y último día, la hora de consulta y el precio original vs. convertido de cada activo.
- Datos del activo: moneda original e interruptor «Ver el precio también en USD» (mismo tipo de cambio y alineación).
- Las cotizaciones en peniques (GBp, Londres) se pasan a libras antes de convertir.
- Botón flotante «¿Necesitas ayuda?» (abajo a la derecha, encima de «Ir a… Ctrl K»): dice en qué sección y módulo
  estás, qué puedes hacer ahí, el siguiente paso de uso según lo que ya hiciste (y los avisos del Centro de estados),
  preguntas frecuentes, glosario y acceso al buscador. Sin IA ni servicios externos; se oculta en Modo presentación.
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
- DPST Insights: «Compara AAPL y MSFT» respeta el orden escrito (antes podía salir «MSFT vs AAPL» al azar).
- Tickers: el aviso «No se pudo cargar el directorio completo» solo sale cuando de verdad falla el directorio.
- Tickers: la búsqueda ignora guiones, tildes y mayúsculas («coca cola» encuentra Coca-Cola) y, si el directorio de
  NASDAQ Trader falla, se reintenta a los 10 minutos en lugar de dejar la lista corta fija por 24 horas.
- La ventana de ayuda ya no muestra como aviso el cupo diario agotado de Alpha Vantage (fuente opcional de noticias).
- Alpha Vantage: la clave se lee en cada consulta; el aviso «Falta configuración» desaparece apenas se agrega
  la clave en Secrets, en vez de quedar guardado hasta 3 horas.
- Los botones flotantes «¿Necesitas ayuda?» e «Ir a… Ctrl K» quedan más pequeños y más arriba, para que no los tape
  la barra «Manage app» de Streamlit Cloud.
- Interfaz pensada para alguien sin formación financiera: las explicaciones pasan de desplegables a signos de
  interrogación (?) con texto muy sencillo (`ayuda.py`); Inicio con guía de 5 pasos; pestaña **Tickers** con el
  directorio de empresas y fondos de EE. UU. (NASDAQ Trader) y botón para usar el ticker en Preselección.
- Noticias en Inicio (economía de la semana y la empresa elegida, solo de los últimos 7 días y con enlaces que abren);
  se quitaron los hitos históricos y la barra lateral de noticias (la barra lateral empieza cerrada).
- La conversión de moneda de la Comparación usa el último dato FX disponible en o antes de cada fecha (sin look-ahead).
- Tema visual: acento dorado, sin íconos en títulos.

### Sin cambios
- Pruebas de la v1 (54) y paquete docente `paquete_v2/` (verificado con su manifiesto).

## [1.0.0] — 2026-09-18 (primera versión asignada, base `f6ce7d9`)
- Análisis de un activo: datos, rendimientos logarítmicos, diagnósticos, pronóstico homocedástico con validación
  walk-forward, VaR, entrada/stop-loss/take-profit, comparación de N activos con dominancia y preselección.
