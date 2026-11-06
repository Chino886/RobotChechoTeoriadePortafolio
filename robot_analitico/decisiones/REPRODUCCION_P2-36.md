# Reproducción por otro integrante (prueba P2-36)

Objetivo: que un integrante distinto de quien programó clone el repositorio en **su** computador, instale las
mismas versiones, corra las pruebas y obtenga los mismos resultados. Se llena una fila por integrante.

## Pasos

1. Clonar: `git clone https://github.com/Chino886/RobotChechoTeoriadePortafolio.git` y entrar a
   `RobotChechoTeoriadePortafolio/robot_analitico`. Si el repositorio ya es privado, el dueño debe invitarlo antes
   como colaborador (GitHub → Settings → Collaborators).
2. Anotar el commit: `git rev-parse HEAD`.
3. Entorno con versiones exactas (Python 3.11 o superior):
   - `python -m venv .venv`
   - activar: `source .venv/bin/activate` (Mac/Linux) o `.venv\Scripts\activate` (Windows)
   - `pip install -r requirements-lock.txt`
4. Verificar el paquete docente sin cambios: `python scripts/verify_package.py` → debe decir que todos los
   archivos coinciden con el manifiesto.
5. Pruebas: `python -m pytest tests/` → anotar cuántas pasan (debe coincidir con `ESTADO.md`).
6. App: `streamlit run app.py`, abrir el laboratorio con **Caso docente de dos activos** y comprobar los pesos de la
   hoja `CALCULO_MANUAL_DOS_ACTIVOS.md` (GMV 0,8571/0,1429; tangente 0,6341/0,3659; personal 0,5714/0,4286).
7. Laboratorio → Exportar: descargar el paquete de traza y verificarlo en la misma pestaña (hash y commit).
8. Inicio → *Comprobar conexiones reales*: dos consultas separadas por unos minutos, descargar el CSV (P2-3).

## Registro

| Integrante | Fecha | Sistema y versión de Python | Commit | Pruebas que pasan | Pesos de control coinciden | Traza verificada | Problemas encontrados |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
| | | | | | | | |

Si algo falla, no se corrige en silencio: se anota en la última columna y en `BITACORA.md`.
