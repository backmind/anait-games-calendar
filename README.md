# anait-games-calendar

[![Update Calendar](https://github.com/backmind/anait-games-calendar/actions/workflows/update-calendar.yml/badge.svg)](https://github.com/backmind/anait-games-calendar/actions/workflows/update-calendar.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ICS](https://img.shields.io/badge/Calendario-.ics-blue)](https://backmind.github.io/anait-games-calendar/anait_lanzamientos.ics)

Calendario iCal (`.ics`) suscribible con los **lanzamientos de videojuegos** publicados semanalmente en [AnaitGames](https://www.anaitgames.com/tag/lanzamientos).

**Enlace directo al calendario:** https://backmind.github.io/anait-games-calendar/anait_lanzamientos.ics

## ¿Por qué?

[AnaitGames](https://www.anaitgames.com) es uno de los pocos medios independientes de videojuegos en castellano que cubre lanzamientos semanales de forma consistente. Sin embargo, no ofrece ningún formato máquina-legible: no tiene RSS, ni API pública de lanzamientos, ni calendario.

Este proyecto suple esa carencia: convierte los artículos editoriales semanales en un calendario estándar iCal al que cualquiera puede suscribirse desde Google Calendar, Apple Calendar, Thunderbird u otra aplicación compatible.

## ¿Qué contiene el calendario?

El script parsea cada artículo semanal de lanzamientos de AnaitGames y crea **un evento por juego** con la siguiente información:

- **Nombre del juego** como título del evento. Los juegos que AnaitGames destaca editorialmente llevan el prefijo 🎮 para distinguirlos del resto.
- **Fecha de lanzamiento** como evento de día completo.
- **Descripción** con los metadatos del juego: desarrolladora, distribuidora, plataformas disponibles y enlace a Steam cuando existe.
- **Comentario editorial** — los juegos destacados incluyen además el breve comentario del redactor sobre el juego.
- **Enlace al artículo fuente** — cada evento incluye la URL directa al artículo semanal de AnaitGames del que se extrajo la información, para que puedas leer la cobertura completa.

## Suscribirse al calendario

### Google Calendar

1. Abre [Google Calendar](https://calendar.google.com).
2. En la barra lateral izquierda, junto a **Otros calendarios**, pulsa **+** → **Desde URL**.
3. Pega la siguiente URL y pulsa **Añadir calendario**:

```
https://backmind.github.io/anait-games-calendar/anait_lanzamientos.ics
```

Google Calendar actualizará la suscripción automáticamente cada varias horas. Más detalles en la [ayuda de Google Calendar](https://support.google.com/calendar/answer/37100).

### Apple Calendar (macOS / iOS)

**En Mac:**
1. Abre Calendario → Archivo → **Nueva suscripción de calendario…**
2. Pega la URL del calendario y pulsa **Suscribir**.

**En iPhone/iPad:**
1. Abre Ajustes → Calendario → Cuentas → **Añadir cuenta** → **Otra** → **Añadir calendario suscrito**.
2. Pega la URL del calendario.

### Thunderbird

1. Abre Thunderbird → pestaña Calendario → clic derecho en la lista de calendarios → **Nuevo calendario…**
2. Selecciona **En la red** → pega la URL → **Suscribir**.

### Otros clientes

Cualquier aplicación de calendario compatible con iCal puede suscribirse usando esta URL:

```
https://backmind.github.io/anait-games-calendar/anait_lanzamientos.ics
```

O mediante protocolo webcal (abre directamente la app de calendario):

```
webcal://backmind.github.io/anait-games-calendar/anait_lanzamientos.ics
```

## ¿Cómo funciona?

Cada día a las 10:00 UTC (12:00 CET), un workflow de GitHub Actions:

1. Consulta la [API REST de WordPress](https://www.anaitgames.com/wp-json/wp/v2/posts?tags=6806) para detectar artículos nuevos en el tag `#lanzamientos`.
2. Parsea el contenido HTML de cada artículo nuevo para extraer nombres de juegos, fechas de lanzamiento, plataformas, desarrolladoras y comentarios editoriales.
3. Genera un evento iCal de día completo por cada juego y lo fusiona con el calendario existente, descartando duplicados por UID.
4. Commitea el `.ics` actualizado, que [GitHub Pages](https://backmind.github.io/anait-games-calendar/) sirve como fichero estático.

El parsing es 100% programático — no intervienen LLMs ni servicios externos más allá de la propia web de AnaitGames. Si no hay artículos nuevos, la ejecución termina sin modificar nada.

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
