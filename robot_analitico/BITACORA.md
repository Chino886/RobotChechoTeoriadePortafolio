# BITACORA

Formato tomado de `paquete_v2/plantillas/DECISION_Y_APRENDIZAJE.md`. Una entrada por decisión sustantiva. La IA no llena estas respuestas como si fueran conocimiento del equipo.

## Plantilla de entrada

ID y fecha:
Pregunta del banco:
Decisión y justificación propias del estudiante:
Cálculo manual o contraejemplo:
Evidencia adversa y supuesto frágil:
Aporte de la IA y herramienta declarada:
Corrección y validación de cada integrante:
Prueba, comando, resultado, snapshot y commit:
Revisión cruzada y defensa pendiente:

Para preparar cada entrada: `decisiones/MANDATO_EQUIPO.md` (decisiones pendientes),
`decisiones/CALCULO_MANUAL_DOS_ACTIVOS.md` (cálculo a mano) y `decisiones/REPRODUCCION_P2-36.md`.

## Entradas

### VC-01 · 2026-11-06 · Validación cruzada con el repositorio de Checho

ID y fecha: VC-01, 2026-11-06.
Pregunta del banco: P2-31 a P2-33 (beta, Hamada, Ke), P2-19 a P2-23 (Black-Litterman) y P2-25 a P2-27 (rebalanceo de control).
Decisión y justificación propias del estudiante:
Cálculo manual o contraejemplo: los mismos controles de `paquete_v2/data/` dan el mismo resultado en este repositorio y en
`Chech-d/robot-analitico-tbs-eia` (rama `main`, commit `cb42233`), implementados por separado:
- beta del comparable = 1,5143 (OLS de excesos; Cov/Var coincide);
- βL de la empresa = 1,6205 (Hamada: D/E comparable 0,6 → D/E empresa 0,75, t = 35 %, β deuda = 0);
- Ke USD = 16,41 % y Ke COP = 18,68 % (paridad de inflación);
- μ_BL en exceso = [0,0285; 0,0450];
- rebalanceo de control: V_pre = 10.400, nominal 2.800, costos 2,8, V_post = 10.397,2; operaciones −1.401,4 (A) y +1.398,6 (B).
Evidencia adversa y supuesto frágil: coincidir entre dos implementaciones prueba la aritmética, no los supuestos. Los
valores del caso Alimentos (D/E 0,6 y 0,75, impuesto 35 %, β deuda 0) son del caso docente y no se trasladan a otros activos.
Aporte de la IA y herramienta declarada: Claude Code comparó los dos repositorios y escribió la prueba
`tests/unit/test_portfolio_beta_v2.py::test_cross_validation_with_checho_repository` (ver AI_USAGE, 2026-11-06).
Corrección y validación de cada integrante:
Prueba, comando, resultado, snapshot y commit: `python -m pytest tests/unit/test_portfolio_beta_v2.py` → pasa.
Revisión cruzada y defensa pendiente: cada integrante reconstruye a mano al menos uno de estos controles.

### VC-02 · 2026-11-09 · Prueba real: acciones fuera de EE. UU. convertidas a USD y COP

ID y fecha: VC-02, 2026-11-09 17:20 UTC.
Pregunta del banco: conversión de monedas en la comparación (RF-20 ampliado; P_USD = P_COP / (COP por USD) y
1 + R_USD = (1 + R_COP)(1 + R_FX)).
Decisión y justificación propias del estudiante:
Cálculo manual o contraejemplo: consulta real a Yahoo Finance (yfinance), del 2024-01-01 al 2026-11-07, frecuencia semanal,
con el mismo código de la app (`fetch_many` → `normalize_minor_units` → `fx_to_base` → `build_comparison`).
Tickers y moneda que informó Yahoo:
- AAPL: moneda USD, con datos (149 semanas)
- MSFT: moneda USD, con datos (149 semanas)
- EC: moneda USD, con datos (149 semanas)
- ECOPETROL.CL: moneda COP, con datos (149 semanas)
- GRUPOSURA.CL: moneda COP, con datos (149 semanas)
- PETR4.SA: moneda BRL, con datos (149 semanas)
- SAP.DE: moneda EUR, con datos (149 semanas)
- HSBA.L: moneda GBp, con datos (149 semanas)
Base USD: ventana común 2024-01-07 a 2026-11-08 (149 semanas); 8 activos válidos, 0 excluidos.
- ECOPETROL.CL: COP → USD con COPUSD=X; tasa 0.000254639 (2024-01-07) → 0.000308796 (2026-11-08); último precio 2,720.00 → 0.8399 USD
- GRUPOSURA.CL: COP → USD con COPUSD=X; tasa 0.000254639 (2024-01-07) → 0.000308796 (2026-11-08); último precio 67,500.00 → 20.8438 USD
- PETR4.SA: BRL → USD con BRLUSD=X; tasa 0.204265 (2024-01-07) → 0.181703 (2026-11-08); último precio 45.30 → 8.2311 USD
- SAP.DE: EUR → USD con EURUSD=X; tasa 1.09474 (2024-01-07) → 1.12283 (2026-11-08); último precio 210.75 → 236.6356 USD
- HSBA.L: GBP (de subunidad ÷ 100) → USD con GBPUSD=X; tasa 1.26841 (2024-01-07) → 1.34561 (2026-11-08); último precio 13.05 → 17.5548 USD
Base COP: ventana común 2024-01-07 a 2026-11-08; 8 activos válidos, 0 excluidos. Los activos en USD usan
USDCOP=X (COP por 1 USD) y los de BRL, EUR y GBP el cruce (moneda→USD) × USDCOP=X.
Control de cordura: ECOPETROL.CL a 2.720 COP ≈ 0,84 USD; el ADR EC (15,55 USD) representa 20 acciones locales (≈ 0,78 USD
por acción), del mismo orden.
Evidencia adversa y supuesto frágil: ese día Yahoo publicó el par directo COPUSD=X, así que la app lo usó sin invertir
(la tabla lo dice). Si Yahoo deja de publicarlo, `fetch_fx_to_usd` usa USDCOP=X invertido (probado sin red). HSBA.L cotiza en
peniques (GBp): se divide entre 100 antes de convertir; sin eso el precio saldría 100 veces más alto. Al verificar la lista de
acciones internacionales, PFBCOLOM.CL y BCOLOMBIA.CL no trajeron datos (Yahoo: «possibly delisted») y quedaron fuera.
Aporte de la IA y herramienta declarada: Claude Code corrió la consulta y escribió el registro (ver AI_USAGE, 2026-11-09).
Corrección y validación de cada integrante:
Prueba, comando, resultado, snapshot y commit: `python -m pytest tests/unit/test_fx_view_v2.py` → 9 pruebas sin red en verde.
Revisión cruzada y defensa pendiente: un integrante recalcula a mano un precio convertido (precio original × tasa del último día).
