# Supuestos y límites del bot

Resumen para la sustentación (guía final, sección 7: «docs/ supuestos y límites»). Lo que aquí se declara es lo que el
bot hace; las decisiones financieras del equipo están en `decisiones/MANDATO_EQUIPO.md` y en el README (Mandato).

## Alcance
- Herramienta **académica de preselección y simulación**. No es asesoría financiera, no recomienda invertir y **no
  ejecuta órdenes** (no hay conexión con brókeres).
- Posición larga en la preselección (v1). El laboratorio permite cortos solo si el usuario quita los límites.

## Datos
| Supuesto | Cómo se aplica | Límite |
|---|---|---|
| Precio | Cierre ajustado (`auto_adjust=True`) de Yahoo Finance | Yahoo publica con retraso según la bolsa y no garantiza el dato |
| Fechas y calendario | Se ordena, se quitan duplicados y precios no positivos; muestra común entre activos | Los huecos largos anulan el rendimiento que los cruza (no se rellenan) |
| Frecuencia | Diaria, semanal o mensual; se remuestrea **antes** de calcular rendimientos | Anualización con 252 / 52 / 12 periodos |
| Moneda | Comparación en una moneda base; laboratorio en USD o COP con `USDCOP=X` | FX alineado con el último dato publicado en o antes de cada fecha; solo USD ↔ COP |
| Rendimientos | Logarítmicos para un activo (v1); simples para la cartera (R_p = Σ wᵢRᵢ) | Las dos convenciones no se mezclan en un mismo cálculo |

## Modelos
| Modelo | Supuesto | Límite |
|---|---|---|
| Pronóstico (v1) | Caminata aleatoria y lognormal con deriva, **homocedásticos** | Si los diagnósticos muestran volatilidad variable o colas gruesas, los intervalos subestiman el riesgo |
| Validación | Walk-forward con orígenes sucesivos, sin datos futuros; referencia simple = caminata aleatoria | Pocos orígenes = validación débil (regla de suficiencia de la guía 5.5) |
| VaR y pérdida esperada (ES) | Paramétricos (normal/lognormal) e históricos | No cubren cambios de régimen; la ES depende de la cola supuesta |
| Markowitz | μ y Σ muestrales (ddof = 1) en la ventana elegida; también Ledoit-Wolf y EWMA | Los pesos óptimos son sensibles a μ; la cartera "óptima" es óptima **en la muestra** |
| CML | Se dibuja solo con un proxy de mercado rotulado | El proxy (1/N o benchmark) no es el portafolio de mercado teórico |
| Black-Litterman | Prior π = δΣw_ref; views con fecha de conocimiento y vencimiento | Las views y su confianza (Ω) son del equipo |
| Rebalanceo | Simulación con costos por nominal, banda, calendario y caja mínima | Sin impuestos, sin deslizamiento por liquidez; no ejecuta órdenes |
| Beta y CAPM | OLS de excesos contra el benchmark elegido; ERP histórica de la ventana o escrita por el equipo | La beta cambia con la ventana, la frecuencia y el benchmark; Σwβ solo vale con la misma muestra |
| Desempeño | Sharpe, Treynor, alfa de Jensen, error de seguimiento y razón de información en la misma muestra | Para las carteras óptimas es **dentro de muestra** (optimista); la prueba fuera de muestra está en Backtest |
| Valoración (caso Alimentos) | Datos congelados del caso docente; FCFF/FCFE, WACC, Hamada | La regla de CAPEX por capacidad del PDF del caso está pendiente de confirmar |
| Ficha técnica | Estructura del Anexo 6 de la SFC para una cartera simulada | No es un FIC: valor del fondo, comisiones, calificación y custodio «no aplican» |

## Límites operativos
- Las fuentes en línea (Yahoo, FRED, Google News, Alpha Vantage) pueden fallar o limitar consultas; el bot lo informa
  y no inventa datos. Inicio → *Comprobar conexiones reales* deja evidencia con hora.
- El login OIDC está en modo desarrollo (`DEV_MODE = True`): nombre y correo simulados.
- El registro de accesos es local (`data/access_log.sqlite3`) y no se publica.
