# AGENTS

El repositorio no tenía AGENTS.md antes de la fase 2 (verificado en el commit b383c46). Las reglas de la v1 siguen en README.md, TRACEABILITY.md, AI_USAGE.md y CONTRIBUTIONS.md.

## Fase 2 (bloque docente, copiado de paquete_v2/plantillas/AGENTS_V2.md)

Incorporar este bloque al AGENTS existente sin borrar la línea base ni controles de seguridad.

La ampliación docente v2 requiere Python/pandas, mercado en línea, covarianza/correlación, pesos, Markowitz, fronteras, Black-Litterman, rebalanceo simulado, beta, CAPM y valoración. Las exclusiones de estas funciones en v1 quedan sustituidas para esta etapa.

Conservar los logs y modelos individuales A/B. Añadir retornos simples para la agregación de cartera y la nueva capa financiera; no promediar logs como retorno exacto de una cartera ni cambiar silenciosamente el módulo heredado.

Leer prompts/PROMPT_TUTOR_V2.md y documentos/GUIA_V2.md del paquete. La IA implementa con pruebas; el estudiante decide supuestos, restricciones, views, política de rebalanceo y conclusión. Ninguna aprobación humana se presume.

Mantener una sola versión del estado en README, BITACORA y ESTADO. Usar fixtures sin red para tests y verificar por separado descarga de mercado, despliegue, respaldo privado y defensa.

La ejecución es simulada. No usar cuentas de producción del profesor, publicar datos o repositorios, enviar órdenes, contratar recursos o alterar permisos sin autorización específica.

## Ubicación del paquete en este repositorio

El paquete está en `paquete_v2/` con su estructura original (`prompts/`, `documentos/`, `plantillas/`, `data/`, `cuadernos/`). Las rutas citadas arriba son relativas a esa carpeta. `paquete_v2/data/` contiene datos sintéticos y del caso docente; es distinta de `data/` en la raíz, que la app genera en ejecución y no se versiona.

## Registro de la ampliación v2 en el código

- Convención: la capa individual v1 sigue con g = ln(P_t/P_{t-1}) (`src/analytics.py`, sin cambios). La capa de cartera usa R = exp(g) − 1 y R_p = Σ w_i R_i (`src/portfolio.py`); el log de la cartera es ln(1 + R_p).
- Módulos nuevos, aislados de la v1: `src/portfolio.py`, `src/black_litterman.py`, `src/rebalance.py`, `src/capm.py`, `src/market.py`, `src/backtest.py`, `src/stress.py`, `src/estimators.py`, `src/data_quality.py`, `src/trace.py`, `src/valuation.py` y la interfaz `laboratorio_v2.py`. Pruebas en `tests/unit/test_*_v2.py`, sin red, con los datos de `paquete_v2/data/`.
- Los valores iniciales de la interfaz (rf, gamma, cotas, delta, tau, w_ref, views, banda de rebalanceo) son los del caso docente de control y están rotulados así; no son decisiones del equipo.
