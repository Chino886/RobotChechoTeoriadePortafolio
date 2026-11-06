# Cálculo a mano del caso de dos activos (M3 y M4)

El prompt tutor pide que la primera demostración use dos activos y un **cálculo manual**. Esta hoja trae los pasos
y, en la última columna, lo que da el bot, **para comparar al final**. El cálculo lo hace el equipo, a mano o en
calculadora, sin mirar primero la columna del bot. Si algo no coincide, se anota en `BITACORA.md`.

Datos: `paquete_v2/data/dos_activos.json` (también es la fuente **Caso docente de dos activos** del laboratorio).

- μ_A = 0,08 · μ_B = 0,14 (anuales, simples)
- σ²_A = 0,01 · σ²_B = 0,04 · σ_AB = 0,004
- rf = 0,03 · γ = 5 · pesos entre 0 y 1, suman 1

| Paso | Fórmula | Resultado del equipo | Bot |
|---|---|---|---|
| 1. Volatilidades | σ = √σ² | σ_A = · σ_B = | 0,10 · 0,20 |
| 2. Correlación | ρ = σ_AB / (σ_A σ_B) | | 0,20 |
| 3. Cartera 50/50: rendimiento | μ_p = w_A μ_A + w_B μ_B | | 0,1100 |
| 4. Cartera 50/50: varianza y volatilidad | σ²_p = w_A²σ²_A + w_B²σ²_B + 2 w_A w_B σ_AB | | 0,0145 · 0,1204 |
| 5. Mínima varianza global (GMV) | w_A = (σ²_B − σ_AB) / (σ²_A + σ²_B − 2σ_AB) | | w_A = 0,8571 · w_B = 0,1429 |
| 6. GMV: rendimiento y volatilidad | pasos 3 y 4 con esos pesos | | 0,0886 · 0,0956 |
| 7. Tangente (máximo Sharpe) | z = Σ⁻¹(μ − rf); w = z / (z_A + z_B) | | w_A = 0,6341 · w_B = 0,3659 |
| 8. Tangente: rendimiento, volatilidad y Sharpe | Sharpe = (μ_p − rf) / σ_p | | 0,1020 · 0,1060 · 0,6789 |
| 9. Óptimo personal (γ = 5) | w_A = [(μ_A − μ_B) + γ(σ²_B − σ_AB)] / [γ(σ²_A + σ²_B − 2σ_AB)] | | w_A = 0,5714 · w_B = 0,4286 |
| 10. Óptimo personal: rendimiento, volatilidad y utilidad | U = μ_p − (γ/2) σ²_p | | 0,1057 · 0,1121 · U = 0,0743 |
| 11. CAL | pendiente de la CAL = Sharpe de la tangente | | 0,6789 |

Ayuda para el paso 7: con dos activos,
Σ⁻¹ = 1/(σ²_A σ²_B − σ_AB²) · [[σ²_B, −σ_AB], [−σ_AB, σ²_A]] y μ − rf = (0,05; 0,11).

Para comprobar las interiores: en los pasos 5, 7 y 9 los pesos quedan entre 0 y 1, así que las cotas no se activan
y las fórmulas cerradas valen. Si el equipo cambia las cotas, por ejemplo máximo 0,5, las fórmulas ya no sirven y el
bot recorta los pesos: comprueben cuál cota queda activa.

Preguntas del banco que esta hoja ayuda a sustentar: bloques 5 a 8 (P33–P64).

| Integrante | Pasos que reconstruyó | ¿Coincide con el bot? | Fecha |
|---|---|---|---|
| | | | |
| | | | |
| | | | |
| | | | |
