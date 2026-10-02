# 📡 LeadRadar

**Encuentra a gente que está pidiendo justo lo que tú vendes — en LinkedIn, Reddit, X, Hacker News, Bluesky, Workana, Freelancer.com y cualquier web que le indiques. Claude lee cada publicación, puntúa la intención real de compra, te escribe un primer mensaje útil y te avisa por Telegram.**

> 🇬🇧 [Read in English](README.md)

```
 fuentes ──► sin duplicados ──► Claude puntúa intención ──► Telegram / Discord / Slack
 (10 tipos)  (SQLite)            y redacta respuesta           + leads.html / leads.csv
```

- **Intención, no menciones.** Las herramientas de *social listening* te dicen que alguien escribió "n8n". LeadRadar te dice *"una clínica dental quiere recordatorios de citas por WhatsApp y busca un freelance — aquí tienes una respuesta"*.
- **Solo borradores, nunca envía nada solo.** Tú decides qué sale (y cumples las normas de las plataformas y la ley antispam).
- **Sin baneos.** A LinkedIn y X se llega con buscadores o actores de Apify sin cookies — nunca con tu sesión.
- **Gratis en GitHub Actions.** Copias la plantilla, metes tus claves y listo. Sin servidor, sin Docker, sin base de datos que mantener.
- **En cualquier idioma.** Búsquedas, puntuación y borradores en español, inglés o lo que hablen tus clientes.

## Cómo se ve

Cada lead llega a Telegram como una tarjeta:

```
85/100 · 🎯 Busca proveedor · workana
Chatbot IA para WhatsApp Business con precios, horarios y envíos
📝 Tienda quiere un bot de WhatsApp que responda precios, horarios y envíos, con panel.
💡 Atención al cliente automatizada para un e-commerce pequeño: encaja de lleno.
💰 USD 250 - 500
Borrador de respuesta ▸ (toca para desplegar)
[ Abrir publicación ]
```

…y en cada pasada se genera `output/leads.html`: una página con filtros y botón de "copiar borrador".

## Fuentes

| Fuente | ¿Clave? | Notas |
|---|---|---|
| `hackernews` | – | API de Algolia. Posts y comentarios. |
| `bluesky` | – | Búsqueda pública, filtro por idioma. |
| `freelancer` | – | Proyectos abiertos de Freelancer.com. |
| `workana` | – | Proyectos de España y Latinoamérica. Necesita el extra `stealth` (Scrapling). |
| `reddit` | opcional | RSS público (muy limitado). Usa `REDDIT_CLIENT_ID`/`SECRET` si ya los tienes (Reddit cerró el alta libre de claves de API a finales de 2025). |
| `web` | opcional | Búsquedas `site:` en LinkedIn, X, Quora, Indie Hackers, foros… con `ddgs` (gratis, resultados flojos), **Serper** (Google, 2.500 búsquedas gratis — recomendado), Brave o Exa (semántico). |
| `apify` | `APIFY_API_TOKEN` | **Búsqueda de posts de LinkedIn sin cookies**, fiable (~2 $ / 1.000 posts), y cualquier otro actor de Apify (X, Instagram, grupos de Facebook…) con un mapeo de campos. |
| `agentreach` | tu sesión | Reddit + X con las herramientas que instala [Agent-Reach](https://github.com/Panniantong/Agent-Reach) (`rdt-cli`, `twitter-cli`), que reutilizan **tus cookies con sesión iniciada**. La mejor cobertura, pero va contra las normas de automatización de esas plataformas — cuenta secundaria, poco volumen y solo en local. Desactivada por defecto. |
| `rss` | – | Cualquier feed RSS/Atom: portales de empleo, Google Alerts, foros. |
| `scrape` | – | Cualquier página de listados con selectores CSS, con [Scrapling](https://github.com/D4Vinci/Scrapling) (incluye navegador sigiloso para webs con Cloudflare). |

Añadir una fuente es un archivo con una función `collect(conf, ctx) -> list[Item]` — mira `leadradar/sources/`.

## Sirve para cualquier oficio

No está atado a ningún nicho. Describe tu negocio en una frase y Claude escribe toda la configuración — frases de compradores para cada fuente, subreddits, filtros de ruido y tono de las respuestas:

```bash
leadradar init --describe "SEO freelance para negocios locales y tiendas Shopify en España y Latam"
leadradar init --describe "Email marketing con Klaviyo para tiendas online"
```

Ejemplos listos (generados exactamente así): [`examples/seo.yaml`](examples/seo.yaml), [`examples/email-marketing.yaml`](examples/email-marketing.yaml). En una prueba, la config de SEO encontró una gestoría de Madrid, un médico deportivo y una marca de cacao en Shopify buscando SEO — entre 339 publicaciones.

## Empezar en tu ordenador

Necesitas Python 3.10+.

```bash
git clone https://github.com/Daaviid3792/leadradar && cd leadradar
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[stealth]"

# pon tu ANTHROPIC_API_KEY en .env (lo crea init) y luego:
leadradar init --describe "qué vendes y a quién"   # o `leadradar init` a secas para editarlo a mano

leadradar run --no-llm       # gratis: ver qué encuentra cada fuente (--sources web,workana para elegir)
leadradar run --dry-run      # puntúa con Claude y muestra los leads sin avisar
leadradar run                # en serio
```

### Telegram en 2 minutos

1. En Telegram, habla con **@BotFather** → `/newbot` → copia el token en `TELEGRAM_BOT_TOKEN`.
2. Abre tu bot nuevo y mándale cualquier mensaje.
3. `leadradar telegram-setup` te muestra tu `TELEGRAM_CHAT_ID`. Pégalo en `.env`.
4. `leadradar test-notify` — te debería llegar una tarjeta de prueba.

(¿Lo quieres en un grupo con tu equipo? Añade el bot al grupo, escribe algo allí y vuelve a ejecutar `telegram-setup`.)

## Ejecutarlo en GitHub Actions (gratis, sin servidor)

1. Pulsa **Use this template → Create a new repository** y hazlo **privado**. (Tu config describe tu negocio y los artefactos de cada pasada contienen los leads — en un repo público cualquiera puede descargarlos. Un fork de un repo público no puede ser privado, y GitHub desactiva los workflows programados en los forks hasta que los activas.)
2. Copia `config.example.yaml` a `config.yaml`, edítalo y haz commit.
3. **Settings → Secrets and variables → Actions**: añade `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` y las claves opcionales que uses.
4. Pestaña **Actions** → activa los workflows → lanza **LeadRadar** a mano una vez.

A partir de ahí se ejecuta 3 veces al día (cambia el cron en `.github/workflows/leadradar.yml`). La base de datos de "ya visto" se guarda en la caché de Actions, así nunca recibes el mismo lead dos veces, y cada pasada sube `leads.html` como artefacto.

> Reddit suele bloquear las IPs de GitHub en la vía sin claves. En Actions, cubre Reddit con `reddit.com` en `web.sites` (mejor con Serper o Exa). La fuente `agentreach` es solo para uso local.

## Configuración

Todo está en `config.yaml` — el [ejemplo](config.example.yaml) está comentado línea a línea. Lo más importante:

- **`profile.offer` / `ideal_client` / `not_a_fit`** — Claude puntúa cada publicación contra esto. Sé concreto.
- **`queries`** — frases que escriben de verdad tus clientes (*"busco a alguien que automatice"*, *"recomendáis alguna agencia de IA"*). Las APIs por palabra clave (Bluesky, HN, Workana…) funcionan mejor con sus propias `queries` cortas; Claude filtra la intención después.
- **`notify.min_score`** — 70 es buen punto de partida; 85+ = está contratando explícitamente.
- **`scoring.model`** — por defecto `claude-opus-5-5` con `effort: low`: medido en **~0,16 $ por 45 publicaciones** (≈ 0,50 $ por una pasada completa de 150). `claude-haiku-4-5` sale unas 4 veces más barato. `max_items_per_run` limita el gasto, y cada pasada muestra tokens y coste estimado.

Si existe `config.local.yaml` (ignorado por git) tiene prioridad sobre `config.yaml` — útil para pruebas en local.

## Cómo puntúa

Las publicaciones van a Claude por lotes, con un prompt de sistema cacheado que contiene tu oferta. Claude devuelve JSON estructurado por publicación (validado con Pydantic): `score` (0–100), `intent` (busca proveedor / herramienta / pregunta cómo / frustrado / oferta de trabajo), un resumen y un motivo de una línea en tu idioma, y — si es lead — un borrador **en el idioma de la publicación** que empieza aportando algo útil en vez de vender. El contenido de las publicaciones se trata como datos no fiables (se ignoran instrucciones escritas dentro).

## Úsalo con cabeza

- **No hagas spam.** LeadRadar nunca escribe a nadie; responder es cosa tuya. Contesta en público donde preguntaron, o escribe en privado de forma breve y personal.
- **Las normas de email/DM en frío dependen del país** (RGPD + LSSI en España, CAN-SPAM en EE. UU.…). Conoce las tuyas.
- **Respeta los términos de cada web.** Usa APIs oficiales y claves cuando existan, mantén volúmenes bajos (los valores por defecto son prudentes) y no scrapees detrás de un login.

## Proyectos relacionados

LeadRadar toma ideas de [LeadEcho](https://github.com/rohansx/leadecho), [OpenOutreach](https://github.com/eracle/OpenOutreach) y [upwork-job-alerts](https://github.com/janglewood/upwork-job-alerts). Para investigación con agentes en plataformas que piden login, mira [Agent-Reach](https://github.com/Panniantong/Agent-Reach).

## Licencia

MIT
