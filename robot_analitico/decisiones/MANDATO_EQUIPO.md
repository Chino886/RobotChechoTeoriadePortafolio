# Hoja de decisiones del equipo (mandato y supuestos)

Esta hoja la **llena el equipo**. La IA solo armó la estructura: explica cada decisión, dónde se usa en el bot y
qué preguntas del banco la sustentan. No trae respuestas. Cuando una decisión quede tomada:

1. escríbanla aquí (decisión, justificación, quién y fecha);
2. pásenla al README (sección *Mandato del equipo*) y pongan el valor en el bot;
3. abran una entrada en `BITACORA.md` con el cálculo a mano o el contraejemplo y la evidencia adversa;
4. actualicen `ESTADO.md`.

Las preguntas del banco están en `paquete_v2/documentos/BANCO_PREGUNTAS.md` (bloques de 8: el bloque *n* va de
P(8n−7) a P(8n)).

---

## A. Las seis preguntas iniciales del prompt tutor

| # | Pregunta | Banco | Respuesta del equipo |
|---|---|---|---|
| 1 | ¿Qué decisión debe mejorar el bot y quién la tomará? | P1 | |
| 2 | ¿Qué ruta de especialización eligen (técnica, fundamental/proyectos o macro/cuantitativa) y qué evidencia justifica su prioridad? | P2, bloques 17–19 | |
| 3 | Mandato: moneda, horizonte, liquidez, pérdida tolerable y obligaciones del inversionista hipotético | P3, P4 | |
| 4 | Universo y benchmark: ¿qué activos y contra qué índice se comparan?, ¿qué exposición omiten? | bloque 2 (P9–P16) | |
| 5 | Objetivo, límites de pesos y regla preliminar de rebalanceo | P5, P7, bloque 11 | |
| 6 | ¿Qué puede explicar cada integrante sin IA sobre covarianza, frontera, beta y BL? | P6, bloque 20 | |

---

## B. Supuestos que el bot ya pide como entradas

Para cada uno: **Decisión** · **Justificación** (por qué ese valor y no otro) · **Qué la haría cambiar** · **Quién y fecha**.

### B1. Tasa libre de riesgo (rf) — Laboratorio → Supuestos financieros
- Qué es: rendimiento sin riesgo de impago en la moneda del mandato, efectiva anual.
- Fuente posible: pestaña *Tasas soberanas* (FRED) o bono corto del país de la moneda.
- Banco: P57–P62 (bloque 8).
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B2. γ (aversión al riesgo) — Laboratorio → Supuestos financieros
- Qué es: cuánto penaliza el inversionista la varianza en U = μ − (γ/2)σ². No se estima de los precios.
- En el bot se elige por perfil: **Conservador γ = 10, Moderado γ = 5, Agresivo γ = 2** (mapa decidido por el equipo el
  2026-11-09), o «Personalizado» para escribir γ. Falta justificar qué perfil corresponde al inversionista del mandato.
- Banco: P57, P58.
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B3. Pesos mínimo y máximo, topes por sector, cortos — Laboratorio → Supuestos y Cotas
- Qué es: reglas del mandato (¿se permite vender en corto?, ¿cuánto puede pesar un activo o un sector?).
- Si permiten cortos: rendimiento objetivo máximo para dibujar la frontera.
- Banco: P3, P4, bloque 7 (P49–P56).
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B4. Ventana y estimador de μ y Σ — Laboratorio → Estrés y estimadores / Backtest
- Qué es: cuántos datos usar y con qué estimador (muestral, Ledoit-Wolf, EWMA con su λ).
- Banco: bloques 4 y 5 (P25–P40).
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B5. Proxy de la CML — Laboratorio → Markowitz
- Qué es: qué cartera representa "el mercado" para dibujar la CML (el bot usa 1/N del universo solo si el equipo lo activa).
- Banco: P61, P62.
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B6. Prior de Black-Litterman (w_ref, δ, τ) — Laboratorio → Black-Litterman
- Qué es: pesos de referencia del prior, aversión implícita δ y escala τ.
- Banco: bloque 9 (P65–P72).
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B7. Views de Black-Litterman — Laboratorio → Black-Litterman
- Una por fila, con tesis, fuente, fecha de publicación, **fecha en que se conoció**, Q, Ω, vencimiento,
  evidencia contraria e invalidación. Usen la plantilla `decisiones/view_BL_V1.json` (copien una por view).
- Banco: bloque 10 (P73–P80).
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B8. Política de rebalanceo — Laboratorio → Rebalanceo
- Qué es: calendario, banda de pesos, eventos de información, caja mínima, costo por nominal, margen
  costo-beneficio, rotación máxima, regla de no operar. Usen `decisiones/politica_rebalanceo.json`.
- Banco: bloques 11 y 12 (P81–P96).
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B9. Benchmark para beta y CAPM — Laboratorio → Beta, CAPM y valoración
- Qué es: índice contra el que se mide la beta de cada activo.
- Banco: bloque 13 (P97–P104).
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B10. Backtest — Laboratorio → Backtest
- Qué es: estrategias y estimadores candidatos, criterio de selección en validación y conclusiones,
  **incluidas las adversas** (si la estrategia elegida pierde contra 1/N, se dice).
- Banco: bloque 12 (P89–P96).
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

### B11. Valoración del caso Alimentos — Laboratorio → Beta, CAPM y valoración
- Proyección año por año (crecimiento, CAPEX, depreciación, costos), magnitud de los escenarios (FX, rezago de
  traslado, tasa variable).
- **Confirmar con el PDF del caso:** regla de CAPEX por capacidad (`capacidad_ventas` = 155.000,
  `capex_venta_adicional` = 0,6: ¿por peso de venta sobre la capacidad?, ¿una vez o cada año?, ¿se deprecia en
  `vida_depreciacion` = 8 años sumado a 9.000?) y si Kd = 13,5 % está en COP.
- Banco: bloques 14 y 15 (P105–P120).
- Decisión: · Justificación: · Cambiaría si: · Quién/fecha:

---

## C. Cierre

- [ ] Todas las decisiones tienen justificación propia y quién la tomó.
- [ ] Cada decisión está en README, en el bot y con entrada en BITACORA.
- [ ] Cada integrante puede explicar sin IA las decisiones de su parte (defensa individual, M10).
