"""
Textos de ayuda del bot, en lenguaje muy sencillo, para los signos de interrogación (?).
Están pensados para alguien que nunca ha invertido. Si cambian, cámbienlos aquí.
"""

AYUDA = {
    # ------------------------------------------------------------------ Laboratorio: general
    "laboratorio": """Aquí el bot **reparte el dinero entre varias empresas** (eso es una *cartera* o *portafolio*).

- La idea: si una empresa cae, otra puede compensar, y así se arriesga menos.
- Los números que ves al abrir son un **ejemplo del profesor**; ustedes pueden cambiarlos.
- Es una **simulación**: no compra ni vende nada de verdad.""",
    "supuestos": """Son las **reglas** del ejercicio. Las decide el equipo.

- **Tasa libre de riesgo:** lo que ganarías sin arriesgar nada (por ejemplo, prestándole al gobierno). 0,03 = 3 % al año.
- **Aversión al riesgo (γ):** qué tanto te asusta perder. Número bajo = te arriesgas más; número alto = prefieres ir a la segura.
- **Peso mínimo:** lo menos que puede tener cada empresa. 0 = puede no tener nada.
- **Peso máximo:** lo más que puede tener cada empresa. 1 = puede ser el 100 %; 0,25 = máximo un 25 %.
- **Sin límites:** permite apostar en contra de una empresa o pedir prestado. Es solo para comparar con la teoría.""",
    "cotas": """Opcional. Sirve para poner **reglas especiales** a una empresa o a un grupo.

- **mínimo / máximo:** lo menos y lo más que puede tener esa empresa (0,40 = 40 %).
- **sector:** escribe una palabra para agrupar (por ejemplo *tecnología*). Aparece otra tabla para poner el máximo de todo el grupo.
- Si no la tocas, no pasa nada: se usan las reglas de arriba.""",
    # ------------------------------------------------------------------ Riesgo conjunto
    "cov_corr": """Dos tablas de colores que muestran **si las empresas se mueven juntas**.

- Cada cuadro cruza la empresa de la fila (izquierda) con la de la columna (abajo).
- **Correlación cerca de 1 (verde):** suben y bajan juntas → no ayudan a protegerse.
- **Cerca de 0 (oscuro):** no tienen que ver una con otra → buena mezcla.
- **Cerca de −1 (azul):** cuando una sube la otra baja → se compensan.
- La **covarianza** dice lo mismo pero en otra escala; la diagonal muestra qué tanto se mueve cada empresa sola.""",
    "indicadores": """Qué significa cada número:

- **Rendimiento esperado:** cuánto ganó en promedio al año en el pasado (no es una promesa).
- **Volatilidad:** qué tanto sube y baja. Más alta = más montaña rusa.
- **Sharpe:** ganancia extra por cada unidad de riesgo. Más alto es mejor.
- **Máxima caída (drawdown):** la peor bajada desde un punto alto (−20 % = en algún momento perdió una quinta parte).
- **VaR 95 %:** en un periodo malo, normalmente no pierdes más que esto (falla 1 de cada 20 veces).
- **Pérdida esperada (ES):** cuando sí pasa algo malo, cuánto se pierde en promedio.
- **N efectivo:** a cuántas empresas "iguales" equivale tu mezcla. Si es 2, en la práctica dependes de 2.""",
    "riesgo_cartera": """La **cartera** junta varias empresas. Su riesgo es **menor** que el promedio de cada una cuando no se mueven igual: eso es *diversificar*.

- **Contribución al riesgo:** cuánto del riesgo total pone cada empresa.
- **Concentración:** si casi todo está en pocas empresas, dependes mucho de ellas.
- **VaR y pérdida esperada:** cuánto podrías perder en un periodo malo.""",
    # ------------------------------------------------------------------ Estrés
    "estres": """**Pruebas de estrés:** imaginar cosas malas y ver cuánto perdería la cartera.

- **Una empresa cae de golpe:** cuánto pierde la cartera si una empresa baja, por ejemplo, 20 %.
- **El peor día real:** el periodo más malo que pasó en la historia de los datos.
- **Todo se mueve junto:** en una crisis casi todo cae a la vez; se simula eso.
- **Escenario inverso:** al revés, el bot busca qué tendría que pasar para perder lo máximo que aceptas.
- **Estimadores:** distintas formas de calcular el riesgo con los mismos datos; si dan muy distinto, hay que tener cuidado.""",
    # ------------------------------------------------------------------ Markowitz
    "markowitz": """La gráfica muestra **riesgo** (eje horizontal) contra **ganancia esperada** (eje vertical).

- **Línea verde (frontera eficiente):** las mejores mezclas: no hay otra con más ganancia y el mismo riesgo.
- **Rombo (mínimo riesgo):** la mezcla que menos se mueve.
- **Estrella (tangente):** la que más gana por cada unidad de riesgo.
- **Círculo (óptimo personal):** la mejor para tu nivel de miedo al riesgo (γ).
- **Triángulo (mayor ganancia):** la que más gana, sin importar el riesgo.
- **Línea punteada (CAL):** mezclar la estrella con dinero "seguro" (la tasa libre de riesgo).
- Los puntitos grises son mezclas al azar, solo de referencia.""",
    # ------------------------------------------------------------------ Black-Litterman
    "bl_parametros": """Black-Litterman mezcla **lo que dice el mercado** con **las opiniones del equipo**.

- **Opinión (view):** algo que el equipo cree, por ejemplo "Apple va a ganar 2 % más que Microsoft".
- **Confianza:** qué tan seguros están. Más confianza = la opinión pesa más.
- **Desde / hasta:** las fechas en que la opinión vale.
- Los demás números (δ, τ, pesos de referencia) vienen del ejemplo del profesor; el equipo los puede ajustar.""",
    "bl": """Sin opiniones, el bot usa lo que **"cree" el mercado** según cuánto pesa cada empresa.

- Cuando el equipo agrega una opinión, los resultados se mueven hacia ella.
- Si la opinión es poco segura, casi no cambia nada.
- Sirve para que la cartera no dependa solo de lo que pasó en el pasado.""",
    # ------------------------------------------------------------------ Rebalanceo
    "rebalanceo_parametros": """Cada cuánto y cómo **volver a acomodar** la cartera.

- **Costo:** lo que cobra el intermediario por comprar o vender (0,001 = 0,1 %).
- **Banda:** cuánto se puede desacomodar una empresa antes de corregir (0,05 = 5 puntos).
- **Calendario:** cada cuántos días se revisa.
- **Caja mínima:** dinero que siempre se deja sin invertir.""",
    "rebalanceo": """Con el tiempo, las empresas que suben pesan más y la cartera **se desacomoda**.

- **Rebalancear** es vender un poco de lo que subió y comprar de lo que bajó para volver a la mezcla elegida.
- Cada operación **cuesta**, así que no conviene hacerlo todos los días.
- El bot solo **simula**: no envía órdenes.""",
    "politica": """Las reglas que dicen **cuándo** se rebalancea:

- **Por fecha:** cada cierto tiempo (por ejemplo, cada mes).
- **Por desvío:** cuando una empresa se aleja mucho de su peso.
- **Por noticia:** cuando cambia una opinión del equipo.
- **No hacer nada:** si el beneficio de acomodar es menor que lo que cuesta.""",
    # ------------------------------------------------------------------ Backtest
    "backtest_parametros": """Cómo se hace la prueba con el pasado:

- **Ventana:** cuántos datos del pasado usa para decidir cada vez.
- **Cada cuánto:** cada cuántos periodos vuelve a decidir.
- **Costo:** lo que cuesta cada compra o venta.
- **Estimador:** la forma de calcular el riesgo.""",
    "backtest": """Un **backtest** es preguntarse: *"si hubiera usado esta regla en el pasado, ¿cómo me habría ido?"*

- El bot avanza en el tiempo y en cada momento **solo usa lo que ya se sabía** (no hace trampa mirando el futuro).
- Compara la regla con algo simple: repartir igual entre todas (1/N).
- Que haya funcionado en el pasado **no garantiza** que funcione después.""",
    # ------------------------------------------------------------------ Desempeño y CAPM
    "desempeno": """Cómo le fue a cada cartera **comparada con el mercado** (el benchmark, por ejemplo el S&P 500):

- **Sharpe:** ganancia extra por cada unidad de riesgo total. Más alto es mejor.
- **Treynor:** ganancia extra por cada unidad de riesgo de mercado (beta).
- **Alfa de Jensen:** cuánto ganó **por encima** de lo esperado para su riesgo. Positivo = le fue mejor.
- **Error de seguimiento:** qué tanto se separa del mercado.
- **Razón de información:** ganancia sobre el mercado por cada unidad de esa separación.
- **Riesgo de mercado / propio:** qué parte del riesgo viene del mercado en general y qué parte de la empresa.
- Ojo: las carteras se armaron con estos mismos datos, así que aquí se ven **mejor de lo normal**.""",
    "capm_valoracion": """Palabras clave:

- **Beta:** qué tanto se mueve una empresa cuando se mueve el mercado. Beta 1,5 = si el mercado sube 1 %, ella sube 1,5 %.
- **CAPM:** cuánto *debería* ganar una empresa según su beta: tasa segura + beta × prima del mercado.
- **SML:** la línea que dibuja eso. Si una empresa queda **arriba**, ganó más de lo que su riesgo pedía.
- **Hamada:** separa el riesgo del negocio del riesgo que añade la deuda.
- **Ke / WACC:** lo que cuesta conseguir dinero de los dueños / de los dueños y los bancos juntos.
- **Valoración (DCF):** cuánto vale una empresa sumando el dinero que va a generar, traído a hoy.""",
    "valoracion_entradas": """Datos del caso de la empresa **Alimentos del Norte** (ejemplo del curso):

- **Crecimiento de ventas:** cuánto suben las ventas cada año (0,05 = 5 %).
- **Costo variable:** qué parte de cada venta se va en costos.
- **Gastos fijos:** lo que se paga aunque no se venda nada.
- **CAPEX y depreciación:** inversión en máquinas y su desgaste.
- **Deuda y Kd:** cuánto debe la empresa y qué interés paga.
- **g terminal:** cuánto crecerá para siempre después del año 5.
- **Escenarios:** qué pasa si sube el dólar o la tasa de interés.""",
    # ------------------------------------------------------------------ Preselección: canasta (v1)
    "canasta_parametros": """Opciones de la canasta:

- **Confianza del VaR (95 % o 99 %):** 95 % = "normalmente no pierdo más que esto"; 99 % es más prudente.
- **Costo de compra / venta:** comisión del intermediario (0,0025 = 0,25 %). Pon 0 si no quieres tenerla en cuenta.
- **BR mínimo:** cuánto quieres ganar por cada peso que arriesgas para que haya "señal". 2 = ganar al menos el doble de lo que arriesgas.
- **Caminata aleatoria:** supone que el precio puede subir o bajar con igual probabilidad.
- **Lognormal con deriva:** supone que la tendencia del pasado sigue. Ninguno adivina el futuro.""",
    "canasta_resultados": """Cómo leer cada empresa de la canasta:

- **Valor esperado:** cuánto podría valer lo que invertiste al final del plazo.
- **Rango 90 %:** entre qué valores quedaría casi siempre.
- **VaR:** pérdida que normalmente no se supera en un mal escenario.
- **Pérdida esperada (ES):** si pasa lo malo, cuánto se pierde en promedio.
- **Validación:** qué tan bien le fue al modelo con datos del pasado.
- **Señal:** el bot dice si hay una oportunidad que cumple todas las condiciones; si no, explica por qué. **No es una orden de compra.**""",
}
