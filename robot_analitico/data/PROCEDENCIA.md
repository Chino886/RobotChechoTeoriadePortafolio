# Datos y procedencia

Esta carpeta (`data/`) la usa la app en ejecución y **no se sube a git**, salvo este archivo: ahí queda el registro
local de accesos (`access_log.sqlite3`, con nombres y correos), que nunca debe publicarse.

## Datos de ejemplo versionados en el repositorio

| Archivo | Procedencia | Uso | SHA-256 (12 primeros) |
|---|---|---|---|
| `paquete_v2/data/dos_activos.json` | Paquete docente v2 (J. E. Restrepo Montoya) | Caso de control de dos activos (Markowitz, CAL) | `0cadc58cb08b` |
| `paquete_v2/data/precios_sinteticos_20.csv` + `_metadata.json` | Paquete docente v2, series **sintéticas** | Laboratorio sintético, estimadores, backtest | `cd34e7826bc5` |
| `paquete_v2/data/black_litterman_control.json` | Paquete docente v2 | Control de Black-Litterman | `1f1e4f0a63ab` |
| `paquete_v2/data/rebalanceo_control.json` | Paquete docente v2 | Control de rebalanceo | `ee1894ee49b4` |
| `paquete_v2/data/caso_alimentos_parametros.json` y `caso_alimentos_retornos.csv` | Paquete docente v2, caso Alimentos del Norte (congelado) | Beta, Hamada, Ke, WACC, valoración | `3d79388afa98`, `7710cc53f927` |
| `paquete_v2/data/banco_preguntas.json` | Paquete docente v2 | Banco de 160 preguntas | `7e80b3c86a17` |
| `tests/fixtures/*.csv` (3 archivos) | Anexo oficial de la v1 (TBS–EIA) | Pruebas T-01 a T-25 | ver `SHA256SUMS.txt` |

La integridad del paquete docente se comprueba con `python scripts/verify_package.py` (compara contra
`paquete_v2/MANIFIESTO_SHA256.json`).

## Datos en vivo (no se guardan en el repositorio)

| Fuente | Qué se pide | Campo usado | Derechos y límites |
|---|---|---|---|
| Yahoo Finance (`yfinance`) | Precios diarios e intradía, `USDCOP=X` | `Close` con `auto_adjust=True` (ajustado por dividendos y splits) | Uso académico; Yahoo no permite redistribuir; publica con retraso según la bolsa |
| FRED (St. Louis Fed) | Tasas de bonos del gobierno | Observaciones mensuales/trimestrales/anuales en % | Clave gratuita; datos públicos |
| Google News (RSS) y Alpha Vantage | Noticias | Título, medio, enlace verificado | Solo informativo; no entra en los cálculos |

## Registros de respaldo

Cada análisis del laboratorio se puede exportar (módulo **Exportar**) como `traza.json` + `snapshot.csv`: la traza
lleva fuente, fechas, moneda, transformaciones, parámetros, resultados, commit y el SHA-256 del snapshot, y la app
verifica que coincidan. Esos dos archivos son el respaldo reproducible de un resultado mostrado en la sustentación.
