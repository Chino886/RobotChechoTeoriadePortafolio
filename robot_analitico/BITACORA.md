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
