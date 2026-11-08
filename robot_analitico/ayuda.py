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


# Ayudas de cada casilla del laboratorio (clave del widget → texto sencillo).
CASILLAS = {
    "lab_quote_tickers": "Los códigos de las empresas cuyo precio quieres ver ahora mismo, separados por coma. Ej: AAPL, MSFT. "
                         "Búscalos en la pestaña **Tickers**.",
    "lab_quote_every": "Cada cuántos segundos se vuelve a pedir el precio si activas la actualización automática.",
    "lab_quote_auto": "Si lo activas, el precio se actualiza solo cada cierto tiempo, sin pulsar el botón.",
    "lab_window": "Cuántos datos hacia atrás se usan para cada punto de la gráfica móvil. Más datos = línea más suave.",
    "lab_rc_a": "Primera empresa de la pareja que quieres comparar.",
    "lab_rc_b": "Segunda empresa de la pareja. La gráfica muestra si se han movido juntas con el tiempo.",
    "lab_ewma_lambda": "Qué tanto pesan los datos recientes frente a los viejos. Cerca de 1 = todos pesan parecido; "
                       "más bajo = manda lo reciente. 0,94 es el valor clásico para datos diarios.",
    "lab_cml": "Dibuja la línea del mercado usando como 'mercado' la mezcla que reparte igual entre todas las empresas. "
               "Es una aproximación: el equipo decide si la usa.",
    "lab_bl_delta": "Qué tanto le teme al riesgo 'el mercado' en promedio. Se usa para deducir lo que el mercado espera. "
                    "El valor 3 es el del ejemplo del profesor.",
    "lab_bl_tau": "Qué tan poco confiamos en lo que 'espera el mercado'. Número pequeño (0,05) = confiamos bastante.",
    "lab_reb_frac": "Si lo activas, se pueden comprar pedacitos de una acción (por ejemplo 0,5 acciones).",
    "lab_pol_window": "Cuántos datos del pasado mira el bot cada vez que decide.",
    "lab_pol_h": "Cuántos periodos de la historia se usan para probar la regla.",
    "lab_pol_days": "Cada cuántos días se revisa la cartera sí o sí. 0 = no revisar por fecha.",
    "lab_pol_wait": "Días mínimos entre una operación y la siguiente, para no comprar y vender todo el tiempo.",
    "lab_pol_turn": "Lo máximo que se puede mover de la cartera en una sola vez (0,2 = 20 %). 0 = sin tope.",
    "lab_pol_margin": "Cuánto tiene que mejorar la cartera para que valga la pena pagar los costos de acomodarla. "
                      "0 = cualquier mejora sirve.",
    "lab_pol_info": "Si una opinión del equipo vence o empieza a valer, el bot revisa la cartera aunque no toque por fecha.",
    "lab_pol_target": "A qué mezcla se vuelve cada vez que se acomoda la cartera: repartir igual (1/N), la de menor riesgo "
                      "(GMV), la tuya según tu miedo al riesgo, o la que incluye opiniones (BL).",
    "lab_bt_window": "Cuántos datos del pasado usa la prueba para decidir en cada momento.",
    "lab_bt_every": "Cada cuántos periodos la prueba vuelve a decidir los pesos.",
    "lab_bt_cost": "Lo que cobra el intermediario por cada compra o venta. 0,001 = 0,1 % de lo que se negocia.",
    "lab_bt_share": "Qué parte de la historia se usa para escoger la mejor regla. El resto se guarda para probarla "
                    "sin trampa al final.",
    "lab_bt_strats": "Las reglas que se van a comparar en la prueba.",
    "lab_bt_estimators": "Las formas de calcular el riesgo que se van a comparar. Si dan muy distinto, hay que tener cuidado.",
    "lab_bt_lambda": "Para el estimador EWMA: qué tanto pesan los datos recientes. 0,94 es el valor clásico.",
    "lab_bt_criterion": "Con qué medida se escoge la mejor regla: la que más gana por riesgo (Sharpe), la que más crece "
                        "(CAGR) o la que menos cae.",
    "lab_capm_erp_mode": "La **prima de mercado** es cuánto más gana el mercado que una inversión segura. Puedes usar la "
                         "que hubo en estos datos o escribir la que decida el equipo.",
    "lab_beta_bench": "El índice con el que se compara cada empresa, por ejemplo **^GSPC** (S&P 500 de EE. UU.) o "
                      "**^COLCAP** (bolsa de Colombia).",
    "lab_hamada_asset": "La empresa a la que le quieres separar el riesgo del negocio del riesgo que añade la deuda.",
    "lab_val_de": "Cuánta deuda tiene la empresa por cada peso de los dueños. 0,75 = 75 centavos de deuda por cada peso.",
    "lab_val_g": "Cuánto crecerá la empresa cada año, para siempre, después del año 5. Debe ser bajo (2 % a 5 %).",
    "lab_val_share": "Qué parte de los costos se paga en dólares (insumos importados). 0,3 = 30 %.",
    "lab_val_kdshift": "Cuánto sube o baja la tasa de interés de la deuda en este escenario. 0,02 = sube 2 puntos.",
    "lab_val_iterate": "Recalcula la deuda frente al valor de la empresa varias veces hasta que los números cuadran.",
    "lab_val_roic": "Cuánto gana la empresa por cada peso que invierte. Sirve para revisar si el crecimiento supuesto "
                    "es posible. 0 = no revisar.",
    "lab_factsheet_choice": "La cartera de la que quieres ver la ficha técnica (su hoja de vida).",
    "lab_universe": "Las empresas que entran a la cartera. Deben ser al menos 2.",
}


# Cómo leer cada gráfica y tabla del laboratorio (aparece en el "?" arriba a la derecha de cada una).
GUIA = {
    "cotizaciones": "Una fila por empresa: su **último precio**, a qué hora fue y si la bolsa está abierta. "
                    "El precio puede llegar con unos minutos de retraso.",
    "cotizacion_grafica": "Cómo se movió el precio minuto a minuto hoy. La última barra puede estar incompleta.",
    "cotizacion_registro": "Historial de las consultas que hiciste, con la hora de cada una.",
    "calidad_dato": "Problemas encontrados en los datos: días que faltan, fechas repetidas o precios que no cambian. "
                    "Si está vacía, los datos están bien.",
    "heatmap_cov": "Tabla de colores: cada cuadro cruza dos empresas. Color más fuerte = se mueven más (o más juntas). "
                   "La diagonal es el riesgo de cada empresa sola.",
    "heatmap_corr": "Cada cuadro dice si dos empresas se mueven juntas: **1** = igual, **0** = no tienen que ver, "
                    "**−1** = al revés. Más cerca de 0 = mejor para protegerse.",
    "contribucion": "Cada barra es cuánto del riesgo total de la cartera pone esa empresa. Si una barra es muy alta, "
                    "la cartera depende mucho de ella.",
    "vol_movil": "Cómo ha cambiado el riesgo (qué tanto sube y baja) con el tiempo. La línea gruesa es la cartera; "
                 "si va por debajo de las demás, mezclar está ayudando.",
    "corr_movil": "La línea de arriba: si las dos empresas se movieron juntas en cada momento (1 = igual). "
                  "La de abajo: cuánto llegó a caer la cartera desde su mejor punto.",
    "estres_barras": "Cada barra: cuánto perdería la cartera si **solo** esa empresa cae de golpe lo que pusiste arriba.",
    "estres_tabla": "Qué pasa con el riesgo si en una crisis todo empieza a moverse junto: antes → después.",
    "estres_inverso": "Lo que tendría que caer cada empresa, al mismo tiempo, para perder lo máximo que aceptas. "
                      "Números negativos = caídas.",
    "estimadores_tabla": "El mismo riesgo calculado de varias formas. Si las filas se parecen, el resultado es confiable; "
                         "si son muy distintas, hay que tener cuidado.",
    "estimadores_grafica": "Cómo repartiría el dinero la cartera de menor riesgo según cada forma de calcular el riesgo.",
    "markowitz_tabla": "Cada columna es una cartera: cuánto ganaría al año, cuánto se mueve, su Sharpe (ganancia por "
                       "riesgo) y **qué porcentaje** del dinero va a cada empresa.",
    "markowitz_grafica": "Eje horizontal = riesgo; eje vertical = ganancia esperada. Mejor = **arriba y a la izquierda**. "
                         "La curva verde son las mejores mezclas posibles; los símbolos son las carteras de la tabla.",
    "bl_tabla": "Lo que se espera ganar con cada empresa: lo que dice el mercado, lo que dicen los datos y la mezcla "
                "con las opiniones del equipo (Black-Litterman).",
    "bl_grafica": "Cómo cambia el reparto del dinero según qué expectativa se use. Si cambia mucho, las opiniones pesan mucho.",
    "bl_sensibilidad": "Qué pasa con el reparto si la opinión del equipo fuera más o menos segura.",
    "reb_pesos": "Cómo se desacomodó la cartera porque unos precios subieron y otros bajaron.",
    "reb_operaciones": "Qué habría que comprar (positivo) o vender (negativo) para volver a la mezcla elegida, y cuánto cuesta.",
    "reb_registro": "Cada fila es una revisión de la cartera: la fecha, si se compró/vendió o no, por qué y cuánto costó.",
    "bt_grafica": "Cuánto valdría hoy cada peso invertido al inicio con cada regla, ya restando costos. Más arriba = mejor.",
    "bt_metricas": "Resumen de cada regla en la prueba con el pasado: cuánto creció al año, cuánto se movió y su peor caída.",
    "bt_seleccion": "La regla escogida con una parte de la historia y cómo le fue en la parte que se guardó para probarla.",
    "capm_tabla": "Para cada empresa y cartera: su **beta**, lo que **debería** ganar según el CAPM y lo que ganó. "
                  "Diferencia positiva = ganó más de lo que su riesgo pedía.",
    "capm_grafica": "La línea es lo que debería ganar cada nivel de riesgo de mercado (beta). Puntos **arriba** de la línea "
                    "ganaron más de lo esperado; **abajo**, menos.",
    "desempeno_tabla": "Cada fila es una cartera comparada con el mercado: Sharpe, Treynor, alfa de Jensen y razón de "
                       "información. En general, **más alto es mejor**.",
    "betas_tabla": "Para cada empresa: su beta calculada de dos formas (deben dar igual), cuánto de su riesgo viene del "
                   "mercado y cuánto es propio.",
    "betas_cartera": "La beta de cada cartera: el promedio de las betas de sus empresas según cuánto pesa cada una.",
    "caso_capm": "Los pasos del ejemplo de la empresa Alimentos del Norte: su beta, cómo se quita y se pone la deuda, "
                 "y lo que deberían ganar los dueños (Ke) en dólares y en pesos.",
    "valoracion_tabla": "Las cuentas de la empresa año por año: ventas, ganancias y el dinero libre que genera (FCFF, FCFE).",
    "meta_tabla": "Cuánta ganancia le falta (o le sobra) a la empresa cada año para cumplir la meta de los dueños.",
    "iteracion_tabla": "Cada fila recalcula deuda y valor hasta que los números cuadran entre sí.",
    "sensibilidad_ev": "Cuánto valdría la empresa con distintas tasas (WACC) y crecimientos (g). Si cambia mucho, el "
                       "resultado depende mucho de esos supuestos.",
    "sml_caso": "La línea es lo que debería ganar cada nivel de beta. Los puntos son la empresa con y sin deuda, y su "
                "comparable: **más deuda = más beta = deben ganar más**.",
    "ficha_rentabilidad": "Cuánto habría ganado la cartera, pasado a tasa al año, en cada periodo (último mes, 6 meses, "
                          "año, 2 y 3 años), y cuánto se movió.",
    "ficha_evolucion": "Si hubieras puesto 100.000 al inicio, cuánto tendrías en cada fecha.",
    "ficha_composicion": "Qué parte del dinero va a cada empresa, moneda o sector.",
    "ficha_principales": "Las empresas con más peso en la cartera.",
}
