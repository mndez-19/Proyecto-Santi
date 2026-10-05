import os
import json
import logging
import subprocess
import uuid
import tempfile
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, send_file
import speech_recognition as sr
from google import genai
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024  # 15 MB por subida de audio

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("No se encontró GEMINI_API_KEY. Revisa tu archivo .env")

PATH_MEMORIA = 'asistente_santi_memoria.json'
MAX_NOTAS_HISTORIAL = 8

def cargar_memoria():
    if os.path.exists(PATH_MEMORIA):
        with open(PATH_MEMORIA, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "usuario": "Santi", 
        "familia": ["Lorena", "Felipe", "Nicolás"], 
        "ejemplos": [], 
        "notas_nuevas": [],
        "palabras_prohibidas": [],
        "instrucciones_ia": ""
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/configuracion', methods=['GET'])
def obtener_configuracion():
    memoria = cargar_memoria()
    return jsonify({
        "usuario": memoria.get("usuario", "Santi"),
        "familia": ", ".join(memoria.get("familia", [])), 
        "palabras_prohibidas": ", ".join(memoria.get("palabras_prohibidas", [])),
        "instrucciones_ia": memoria.get("instrucciones_ia", "")
    })

@app.route('/configuracion', methods=['POST'])
def guardar_configuracion():
    try:
        datos = request.json
        memoria = cargar_memoria()

        memoria["usuario"] = datos.get("usuario", "Santi").strip()
        memoria["instrucciones_ia"] = datos.get("instrucciones_ia", "").strip()

        # Procesar lista de palabras prohibidas
        palabras_crudas = datos.get("palabras_prohibidas", "")
        memoria["palabras_prohibidas"] = [p.strip() for p in palabras_crudas.split(",") if p.strip()]

        # NUEVO: Procesar lista de familiares
        familia_cruda = datos.get("familia", "")
        memoria["familia"] = [f.strip() for f in familia_cruda.split(",") if f.strip()]

        with open(PATH_MEMORIA, 'w', encoding='utf-8') as f:
            json.dump(memoria, f, ensure_ascii=False, indent=4)

        return jsonify({"status": "ok"})
    except Exception:
        app.logger.exception("Error al guardar configuración")
        return jsonify({"error": "No se pudo guardar la configuración."}), 500

@app.route('/historial', methods=['GET'])
def obtener_historial():
    memoria = cargar_memoria()
    return jsonify({"historial": memoria.get("notas_nuevas", [])})

@app.route('/procesar_audio', methods=['POST'])
def procesar_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No se envió audio"}), 400

    audio_file = request.files['audio']
    
    try:
        directorio_temp = tempfile.gettempdir()
        id_unico = str(uuid.uuid4())
        tmp_in_path = os.path.join(directorio_temp, f"{id_unico}_in.tmp")
        tmp_wav_path = os.path.join(directorio_temp, f"{id_unico}_out.wav")

        audio_file.save(tmp_in_path)

        proceso = subprocess.run(['ffmpeg', '-i', tmp_in_path, '-ar', '16000', '-ac', '1', '-y', tmp_wav_path], capture_output=True)
        if proceso.returncode != 0:
            raise Exception("No se pudo decodificar el formato del audio.")

        r = sr.Recognizer()
        with sr.AudioFile(tmp_wav_path) as source:
            audio_data = r.record(source)
            duracion = len(audio_data.frame_data) / (audio_data.sample_rate * audio_data.sample_width)
            app.logger.info(
                f"Audio recibido: {os.path.getsize(tmp_in_path)} bytes originales, "
                f"{duracion:.2f}s decodificados a 16kHz mono"
            )
            texto_escuchado = r.recognize_google(audio_data, language="es-ES")

        client = genai.Client(api_key=api_key)
        memoria = cargar_memoria()

        # EXTRAER NUEVAS CONFIGURACIONES
        nombre_usuario = memoria.get('usuario', 'Santi')
        instrucciones = memoria.get('instrucciones_ia', 'Sé directo y calmado.')
        palabras_vetadas = ", ".join(memoria.get('palabras_prohibidas', []))
        ejemplos = "\n".join([f"- Sit: {e['situacion']} -> Consejo: {e['consejo']} Di: '{e['frase']}'" for e in memoria.get('ejemplos', [])])
        notas_recientes = "\n".join([f"- Sit: {n['situacion']} -> Consejo: {n['consejo']} Dijo: '{n['frase']}'" for n in memoria.get('notas_nuevas', [])])

        # PROMPT ACTUALIZADO CON LOS NUEVOS PARÁMETROS
        prompt = f"""
        Eres el Mentor de {nombre_usuario} (autismo). Familia: {', '.join(memoria['familia'])}.
        INSTRUCCIONES DE COMPORTAMIENTO: {instrucciones}
        PALABRAS PROHIBIDAS (NUNCA LAS USES): {palabras_vetadas}
        BASE: {ejemplos}
        INTERACCIONES RECIENTES: {notas_recientes}
        REGLA: Consejo breve (máx 6 palabras). Formato estricto: Consejo: [X]. Di: '[Y]'.
        SITUACIÓN ACTUAL: "{texto_escuchado}"
        """

        respuesta = client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text.strip()

        if "Di:" in respuesta:
            partes = respuesta.split("Di:")
            consejo = partes[0].replace("Consejo:", "").strip()
            frase = partes[1].replace("'", "").strip()
        else:
            consejo = "Tranquilo."
            frase = respuesta

        texto_tts = f"{consejo}. Ahora di: {frase}"
        tts = gTTS(text=texto_tts, lang='es', slow=False)
        audio_respuesta_path = os.path.join(directorio_temp, f"{id_unico}_respuesta.mp3")
        tts.save(audio_respuesta_path)

        # Guardar la interacción como contexto vivo para futuras consultas
        memoria.setdefault("notas_nuevas", []).append({
            "fecha": datetime.now(timezone.utc).isoformat(),
            "situacion": texto_escuchado,
            "consejo": consejo,
            "frase": frase
        })
        memoria["notas_nuevas"] = memoria["notas_nuevas"][-MAX_NOTAS_HISTORIAL:]
        with open(PATH_MEMORIA, 'w', encoding='utf-8') as f:
            json.dump(memoria, f, ensure_ascii=False, indent=4)

        if os.path.exists(tmp_in_path): os.remove(tmp_in_path)
        if os.path.exists(tmp_wav_path): os.remove(tmp_wav_path)

        return jsonify({
            "texto_escuchado": texto_escuchado,
            "consejo": consejo,
            "frase": frase,
            "audio_url": f"/obtener_audio/{id_unico}"
        })

    except sr.UnknownValueError:
        app.logger.warning("Google Speech no pudo transcribir el audio recibido")
        return jsonify({"error": "No pude entender el audio. ¿Puedes repetirlo?"}), 400
    except Exception:
        app.logger.exception("Error al procesar audio")
        return jsonify({"error": "Hubo un problema al procesar el audio. Intenta de nuevo."}), 500

@app.route('/obtener_audio/<uuid:id_unico>')
def obtener_audio(id_unico):
    audio_path = os.path.join(tempfile.gettempdir(), f"{id_unico}_respuesta.mp3")
    if not os.path.exists(audio_path):
        return jsonify({"error": "Audio no encontrado."}), 404
    return send_file(audio_path, mimetype="audio/mpeg")

if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    puerto = int(os.getenv("PORT", "5000"))
    app.run(debug=debug_mode, host="0.0.0.0", port=puerto)
import os
import json
import logging
import subprocess
import uuid
import tempfile
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, send_file
import speech_recognition as sr
from google import genai
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024  # 15 MB por subida de audio

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("No se encontró GEMINI_API_KEY. Revisa tu archivo .env")

PATH_MEMORIA = 'asistente_santi_memoria.json'
MAX_NOTAS_HISTORIAL = 8

def cargar_memoria():
    if os.path.exists(PATH_MEMORIA):
        with open(PATH_MEMORIA, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "usuario": "Santi", 
        "familia": ["Lorena", "Felipe", "Nicolás"], 
        "ejemplos": [], 
        "notas_nuevas": [],
        "palabras_prohibidas": [],
        "instrucciones_ia": ""
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/configuracion', methods=['GET'])
def obtener_configuracion():
    memoria = cargar_memoria()
    return jsonify({
        "usuario": memoria.get("usuario", "Santi"),
        "familia": ", ".join(memoria.get("familia", [])), 
        "palabras_prohibidas": ", ".join(memoria.get("palabras_prohibidas", [])),
        "instrucciones_ia": memoria.get("instrucciones_ia", "")
    })

@app.route('/configuracion', methods=['POST'])
def guardar_configuracion():
    try:
        datos = request.json
        memoria = cargar_memoria()

        memoria["usuario"] = datos.get("usuario", "Santi").strip()
        memoria["instrucciones_ia"] = datos.get("instrucciones_ia", "").strip()

        # Procesar lista de palabras prohibidas
        palabras_crudas = datos.get("palabras_prohibidas", "")
        memoria["palabras_prohibidas"] = [p.strip() for p in palabras_crudas.split(",") if p.strip()]

        # NUEVO: Procesar lista de familiares
        familia_cruda = datos.get("familia", "")
        memoria["familia"] = [f.strip() for f in familia_cruda.split(",") if f.strip()]

        with open(PATH_MEMORIA, 'w', encoding='utf-8') as f:
            json.dump(memoria, f, ensure_ascii=False, indent=4)

        return jsonify({"status": "ok"})
    except Exception:
        app.logger.exception("Error al guardar configuración")
        return jsonify({"error": "No se pudo guardar la configuración."}), 500

@app.route('/historial', methods=['GET'])
def obtener_historial():
    memoria = cargar_memoria()
    return jsonify({"historial": memoria.get("notas_nuevas", [])})

@app.route('/procesar_audio', methods=['POST'])
def procesar_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No se envió audio"}), 400

    audio_file = request.files['audio']
    
    try:
        directorio_temp = tempfile.gettempdir()
        id_unico = str(uuid.uuid4())
        tmp_in_path = os.path.join(directorio_temp, f"{id_unico}_in.tmp")
        tmp_wav_path = os.path.join(directorio_temp, f"{id_unico}_out.wav")

        audio_file.save(tmp_in_path)

        proceso = subprocess.run(['ffmpeg', '-i', tmp_in_path, '-ar', '16000', '-ac', '1', '-y', tmp_wav_path], capture_output=True)
        if proceso.returncode != 0:
            raise Exception("No se pudo decodificar el formato del audio.")

        r = sr.Recognizer()
        with sr.AudioFile(tmp_wav_path) as source:
            audio_data = r.record(source)
            duracion = len(audio_data.frame_data) / (audio_data.sample_rate * audio_data.sample_width)
            app.logger.info(
                f"Audio recibido: {os.path.getsize(tmp_in_path)} bytes originales, "
                f"{duracion:.2f}s decodificados a 16kHz mono"
            )
            texto_escuchado = r.recognize_google(audio_data, language="es-ES")

        client = genai.Client(api_key=api_key)
        memoria = cargar_memoria()

        # EXTRAER NUEVAS CONFIGURACIONES
        nombre_usuario = memoria.get('usuario', 'Santi')
        instrucciones = memoria.get('instrucciones_ia', 'Sé directo y calmado.')
        palabras_vetadas = ", ".join(memoria.get('palabras_prohibidas', []))
        ejemplos = "\n".join([f"- Sit: {e['situacion']} -> Consejo: {e['consejo']} Di: '{e['frase']}'" for e in memoria.get('ejemplos', [])])
        notas_recientes = "\n".join([f"- Sit: {n['situacion']} -> Consejo: {n['consejo']} Dijo: '{n['frase']}'" for n in memoria.get('notas_nuevas', [])])

        # PROMPT ACTUALIZADO CON LOS NUEVOS PARÁMETROS
        prompt = f"""
        Eres el Mentor de {nombre_usuario} (autismo). Familia: {', '.join(memoria['familia'])}.
        INSTRUCCIONES DE COMPORTAMIENTO: {instrucciones}
        PALABRAS PROHIBIDAS (NUNCA LAS USES): {palabras_vetadas}
        BASE: {ejemplos}
        INTERACCIONES RECIENTES: {notas_recientes}
        REGLA: Consejo breve (máx 6 palabras). Formato estricto: Consejo: [X]. Di: '[Y]'.
        SITUACIÓN ACTUAL: "{texto_escuchado}"
        """

        respuesta = client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text.strip()

        if "Di:" in respuesta:
            partes = respuesta.split("Di:")
            consejo = partes[0].replace("Consejo:", "").strip()
            frase = partes[1].replace("'", "").strip()
        else:
            consejo = "Tranquilo."
            frase = respuesta

        texto_tts = f"{consejo}. Ahora di: {frase}"
        tts = gTTS(text=texto_tts, lang='es', slow=False)
        audio_respuesta_path = os.path.join(directorio_temp, f"{id_unico}_respuesta.mp3")
        tts.save(audio_respuesta_path)

        # Guardar la interacción como contexto vivo para futuras consultas
        memoria.setdefault("notas_nuevas", []).append({
            "fecha": datetime.now(timezone.utc).isoformat(),
            "situacion": texto_escuchado,
            "consejo": consejo,
            "frase": frase
        })
        memoria["notas_nuevas"] = memoria["notas_nuevas"][-MAX_NOTAS_HISTORIAL:]
        with open(PATH_MEMORIA, 'w', encoding='utf-8') as f:
            json.dump(memoria, f, ensure_ascii=False, indent=4)

        if os.path.exists(tmp_in_path): os.remove(tmp_in_path)
        if os.path.exists(tmp_wav_path): os.remove(tmp_wav_path)

        return jsonify({
            "texto_escuchado": texto_escuchado,
            "consejo": consejo,
            "frase": frase,
            "audio_url": f"/obtener_audio/{id_unico}"
        })

    except sr.UnknownValueError:
        app.logger.warning("Google Speech no pudo transcribir el audio recibido")
        return jsonify({"error": "No pude entender el audio. ¿Puedes repetirlo?"}), 400
    except Exception:
        app.logger.exception("Error al procesar audio")
        return jsonify({"error": "Hubo un problema al procesar el audio. Intenta de nuevo."}), 500

@app.route('/obtener_audio/<uuid:id_unico>')
def obtener_audio(id_unico):
    audio_path = os.path.join(tempfile.gettempdir(), f"{id_unico}_respuesta.mp3")
    if not os.path.exists(audio_path):
        return jsonify({"error": "Audio no encontrado."}), 404
    return send_file(audio_path, mimetype="audio/mpeg")

if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    puerto = int(os.getenv("PORT", "5000"))
    app.run(debug=debug_mode, host="0.0.0.0", port=puerto)