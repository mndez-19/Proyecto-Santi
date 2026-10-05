    # Mentor de Santi

Un asistente de voz que ayuda, en el momento, a personas neurodivergentes que requieren apoyo y manejo de situaciones sociales o sensoriales difíciles. Por medio de la escucha de lo que pasa en su entorno, el sistema ayuda a identificar y verbalizar lo que ocurre, ofreciendo en segundos un consejo breve y una frase concreta para responder adecuadamente a la situación.

## El problema que resuelve

En situaciones de sobrecarga sensorial o conflicto social, el usuario puede no reconocer o no saber *qué* sienten y por ende les cuesta encontrar, en el momento, *qué decir* o *qué hacer*. 
Pedir ayuda externa (a un familiar, terapeuta) no siempre es posible en tiempo real. 
Mentor de Santi funciona como un apoyo de bolsillo: escucha la situación en voz alta y responde con una guía corta y accionable, adaptada a la familia y las reglas de comunicación del usuario.

## Cómo funciona

1. **Tocas el botón y hablas** — describes en voz alta lo que está pasando (p. ej. "mis hermanos entraron a mi pieza sin avisar").

2. **La app transcribe y consulta a la IA** — el audio se transcribe y se envía a Gemini junto con el contexto personal guardado: quién es la familia, qué palabras evitar, instrucciones de comportamiento, ejemplos previos y el historial reciente de interacciones.

3. **Responde con un consejo y una frase para decir**, cada uno en su propia tarjeta, en texto y en voz.

4. **Cada interacción queda registrada** en un historial reciente, que a su vez se usa como contexto en las próximas consultas — el mentor se ajusta con el uso real, no solo con ejemplos cargados a mano.

Desde el menú lateral (☰) se puede personalizar: nombre del usuario, familia, palabras que no debe usar la IA, e instrucciones específicas de comportamiento.

## Demo

🔗 **[Link a la demo desplegada]** _(agregar aquí la URL una vez desplegado — ver sección "Despliegue")_

> El micrófono requiere HTTPS o `localhost` para funcionar — en la demo desplegada el navegador pedirá permiso de micrófono la primera vez.

## Stack técnico

- **Backend**: Flask (Python)
- **IA conversacional**: Gemini (`google-genai`)
- **Reconocimiento de voz**: `SpeechRecognition` (Google Speech API) + `ffmpeg` para decodificar el audio grabado en el navegador
- **Texto a voz**: `gTTS`
- **Frontend**: HTML/CSS/JS vanilla, sin frameworks — grabación de audio vía `MediaRecorder`

## Instalación local

Requisitos: Python 3.11+, [`ffmpeg`](https://ffmpeg.org/download.html) instalado y disponible en el `PATH`, y una API key de Gemini ([Google AI Studio](https://aistudio.google.com/)).

```bash
git clone <url-del-repo>
cd "Mentor Santi"
pip install -r requirements.txt
```

Crea un archivo `.env` en la raíz del proyecto:

```
GEMINI_API_KEY=tu_api_key_aquí
```

Y ejecuta:

```bash
python app.py
```

La app queda disponible en `http://localhost:5000`. Ábrela en un navegador real (no en un navegador embebido/automatizado) para poder otorgar permiso de micrófono.

## Despliegue (Render.com)

El proyecto incluye un `Dockerfile` listo para desplegar en cualquier plataforma que soporte contenedores (Render, Railway, Fly.io, etc.). Pasos para Render:

1. Crear cuenta en [render.com](https://render.com) y conectar el repositorio de GitHub.
2. Crear un **Web Service** nuevo, eligiendo "Docker" como entorno (detecta el `Dockerfile` automáticamente).
3. Configurar la variable de entorno `GEMINI_API_KEY` en el panel de Render (nunca en el repo).
4. Desplegar — Render construye la imagen, instala `ffmpeg` y expone la app por HTTPS automáticamente (necesario para que el navegador permita usar el micrófono).

**Limitación conocida**: en el plan gratuito, el archivo `asistente_santi_memoria.json` (incluido el historial de interacciones) puede no persistir entre redeploys, ya que el disco no es permanente. Para una demo puntual no es un problema; para uso real continuo convendría mover esa persistencia a una base de datos o a un disco persistente.

## Estado actual y próximos pasos

- [x] Flujo completo de voz → consejo → voz, con contexto familiar personalizable — probado de punta a punta con audio real
- [x] Historial de interacciones que retroalimenta las respuestas futuras de la IA
- [ ] Persistencia de datos en una base de datos (hoy es un archivo JSON local)
- [ ] Soporte multi-usuario (hoy está pensado para una sola persona por instancia)
- [ ] Modo offline / respuesta local para cuando no hay conexión a internet

**Nota sobre el reconocimiento de voz**: se usa la API gratuita de Google Speech a través de `SpeechRecognition`, que ocasionalmente no logra transcribir una grabación (ruido de fondo, pronunciación poco clara). Cuando eso pasa, la app lo muestra en pantalla y pide repetir — no es un error del sistema, es una limitación conocida del servicio gratuito.

## Créditos

Proyecto personal creado por Nicolás, para y con Santi.
