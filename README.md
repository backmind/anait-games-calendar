# anait-games-calendar

[![Update Calendar](https://github.com/backmind/anait-games-calendar/actions/workflows/update-calendar.yml/badge.svg)](https://github.com/backmind/anait-games-calendar/actions/workflows/update-calendar.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Calendario iCal (`.ics`) suscribible con los **lanzamientos de videojuegos** publicados semanalmente en [AnaitGames](https://www.anaitgames.com/tag/lanzamientos).

## ¿Por qué?

[AnaitGames](https://www.anaitgames.com) es uno de los pocos medios independientes de videojuegos en castellano que cubre lanzamientos semanales de forma consistente. Sin embargo, no ofrece ningún formato máquina-legible: no tiene RSS, ni API pública de lanzamientos, ni calendario.

Este proyecto suple esa carencia: convierte los artículos editoriales semanales en un calendario estándar iCal al que cualquiera puede suscribirse desde Google Calendar, Apple Calendar, Thunderbird u otra aplicación compatible.

## Suscribirse

**Suscripción directa** (abre tu app de calendario):

```
webcal://backmind.github.io/anait-games-calendar/anait_lanzamientos.ics
```

**URL HTTPS** (para añadir manualmente como "suscripción por URL"):

```
https://backmind.github.io/anait-games-calendar/anait_lanzamientos.ics
```

### Google Calendar

1. Abre [Google Calendar](https://calendar.google.com)
2. Otros calendarios → **+** → **Desde URL**
3. Pega la URL HTTPS y pulsa **Añadir calendario**

### Apple Calendar

1. Archivo → **Nueva suscripción de calendario…**
2. Pega la URL HTTPS

## ¿Cómo funciona?

Cada lunes a las 10:00 UTC, un workflow de GitHub Actions:

1. Consulta la [API REST de WordPress](https://www.anaitgames.com/wp-json/wp/v2/posts?tags=6806) para detectar artículos nuevos en el tag `#lanzamientos`
2. Parsea el contenido HTML de cada artículo para extraer nombres, fechas, plataformas y desarrolladoras
3. Genera eventos iCal de día completo y los fusiona con el calendario existente
4. Commitea el `.ics` actualizado, que GitHub Pages sirve como fichero estático

El parsing es 100% programático — no intervienen LLMs ni servicios externos más allá de la propia web de AnaitGames.

## Desarrollo local

```bash
git clone https://github.com/backmind/anait-games-calendar.git
cd anait-games-calendar

# Instalar dependencias (requiere uv: https://docs.astral.sh/uv/)
uv sync

# Primera ejecución (más histórico)
uv run python anait_lanzamientos.py --seed-pages 5 --verbose

# Ejecuciones sucesivas (incremental)
uv run python anait_lanzamientos.py --verbose
```

## Atribución

Los datos de lanzamientos proceden de [AnaitGames](https://www.anaitgames.com). Este proyecto no está afiliado a AnaitGames. El calendario incluye nombre del juego, fecha, metadatos técnicos y un enlace al artículo fuente.

## Licencia

[MIT](LICENSE)
