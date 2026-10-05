document.addEventListener('DOMContentLoaded', () => {
  const phone = document.getElementById('phone');
  const label = document.getElementById('label');
  const sub = document.getElementById('sub');
  const hint = document.getElementById('hint');
  const orb = document.getElementById('orb');
  const cardsContainer = document.getElementById('cardsContainer');
  const tag1 = document.getElementById('tag1');
  const phrase1 = document.getElementById('phrase1');
  const phraseConsejo = document.getElementById('phraseConsejo');
  const tag2 = document.getElementById('tag2');
  const phrase2 = document.getElementById('phrase2');
  let mediaRecorder;
  let autoStopTimer;
  let audioChunks = [];
  let isRecording = false;
  let nombreUsuarioActual = "Santi";
  const audioPlayer = new Audio(); // se reutiliza para poder "desbloquearlo" en el toque inicial (necesario en móvil)

  // Textos e ícono del orbe para cada estado del flujo de voz.
  const states = {
    reposo: { label: 'Toca para escuchar', sub: 'Voy a escuchar lo que pasa cerca tuyo', hint: 'Un toque para empezar', orb: '👂', card: false },
    escuchando: { label: 'Escuchando...', sub: 'No hay apuro', hint: 'Toca de nuevo cuando quieras parar', orb: '👂', card: false },
    pensando: { label: 'Pensando...', sub: 'Analizando el entorno', hint: 'Por favor espera un momento', orb: '👂', card: false },
    hablando: { label: 'Esto te puede ayudar', sub: '', hint: 'Toca el botón arriba si quieres empezar de nuevo', orb: '🔊', card: true }
  };

  // Cambia la pantalla al estado indicado (reposo/escuchando/pensando/hablando).
  function setState(name) {
    phone.className = 'phone state-' + name;
    const s = states[name];
    label.textContent = s.label;
    sub.textContent = s.sub;
    hint.textContent = s.hint;
    orb.textContent = s.orb;
    cardsContainer.classList.toggle('show', s.card);
  }

  // Un toque sobre el orbe empieza a grabar; otro toque mientras graba, para.
  orb.addEventListener('click', async () => {
    // Desbloquea la reproducción de audio en móvil: el toque tiene que
    // "tocar" el elemento de audio de forma inmediata; la respuesta real
    // llega varios segundos después y los navegadores móviles bloquean
    // el audio si se reproduce fuera de este gesto.
    audioPlayer.play().catch(() => {});
    audioPlayer.pause();

    if (phone.classList.contains('state-reposo') || phone.classList.contains('state-hablando')) {
        iniciarGrabacion();
    } else if (phone.classList.contains('state-escuchando')) {
        detenerGrabacionYProcesar();
    }
  });

  // Pide permiso de micrófono y empieza a grabar; se detiene sola a los 4s
  // si el usuario no la para antes.
  async function iniciarGrabacion() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.addEventListener("dataavailable", event => {
            if (event.data.size > 0) audioChunks.push(event.data);
        });

        mediaRecorder.addEventListener("stop", () => {
            const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
            enviarAudioAlServidor(audioBlob);
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        });

        mediaRecorder.start();
        isRecording = true;
        setState('escuchando');

        autoStopTimer = setTimeout(() => {
            detenerGrabacionYProcesar();
        }, 4000);

    } catch (err) {
        alert("Santi, necesito permiso para usar el micrófono para poder escucharte.");
    }
  }

  // Detiene la grabación; el evento "stop" del MediaRecorder dispara el envío al servidor.
  function detenerGrabacionYProcesar() {
    if (mediaRecorder && isRecording) {
        setState('pensando');

        if (autoStopTimer) {
            clearTimeout(autoStopTimer);
            autoStopTimer = null;
        }

        mediaRecorder.stop();
        isRecording = false;
    }
  }

    // Sube el audio grabado a /procesar_audio y pinta la respuesta (o el error) en pantalla.
    async function enviarAudioAlServidor(blob) {
    const formData = new FormData();
    formData.append("audio", blob, "grabacion.webm");

    try {
        const response = await fetch('/procesar_audio', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if ('error' in data) {
            setState('reposo');
            sub.textContent = data.error || "Hubo un problema al escucharte. Intenta de nuevo.";
            return;
        }

        // 1. Mostrar resultados en las tres tarjetas
        tag1.textContent = `${nombreUsuarioActual}: esto está pasando`;
        phrase1.textContent = `"${data.texto_escuchado}"`;

        phraseConsejo.textContent = data.consejo;

        tag2.textContent = `${nombreUsuarioActual}: di esto`;
        phrase2.textContent = data.frase;
        
        setState('hablando');

        // 2. Reproducir el audio devuelto por el servidor (mismo elemento
        // desbloqueado en el toque inicial, así también suena en móvil)
        audioPlayer.src = data.audio_url + "?t=" + new Date().getTime();
        audioPlayer.play().catch(err => {
            console.error("El navegador bloqueó la reproducción automática del audio:", err);
        });

    } catch (error) {
        console.error(error);
        setState('reposo');
        sub.textContent = "Error de conexión. Intenta de nuevo.";
    }
  }

});

// ==========================================
// LÓGICA DEL MENÚ LATERAL (SIDEBAR)
// ==========================================
const menuBtn = document.getElementById('menuBtn');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const closeSidebar = document.getElementById('closeSidebar');
const saveConfigBtn = document.getElementById('saveConfigBtn');
const userNameDisplay = document.getElementById('userNameDisplay');

const inputUsuario = document.getElementById('inputUsuario');
const inputFamilia = document.getElementById('inputFamilia');
const inputPalabras = document.getElementById('inputPalabras');
const inputInstrucciones = document.getElementById('inputInstrucciones');
const saveFeedback = document.getElementById('saveFeedback');
const historialLista = document.getElementById('historialLista');

function toggleSidebar() {
    const isActive = sidebar.classList.contains('active');

    // Si se va a abrir, cargamos los datos frescos desde el servidor
    if (!isActive) {
        cargarConfiguracion();
        cargarHistorial();
    }

    sidebar.classList.toggle('active');
    sidebarOverlay.classList.toggle('active');
}

menuBtn.addEventListener('click', toggleSidebar);
closeSidebar.addEventListener('click', toggleSidebar);
sidebarOverlay.addEventListener('click', toggleSidebar);

// Trae la configuración guardada y precarga el formulario del sidebar.
async function cargarConfiguracion() {
    try {
        const response = await fetch('/configuracion');
        const data = await response.json();

        inputUsuario.value = data.usuario || "";
        inputFamilia.value = data.familia || ""; // NUEVO
        inputPalabras.value = data.palabras_prohibidas || "";
        inputInstrucciones.value = data.instrucciones_ia || "";

        nombreUsuarioActual = data.usuario || "Usuario";
        userNameDisplay.textContent = "Hola, " + (data.usuario || "Usuario");
    } catch (error) {
        console.error("Error al cargar configuración", error);
    }
}

saveConfigBtn.addEventListener('click', async () => {
    saveConfigBtn.textContent = "Guardando...";
    saveFeedback.textContent = "";
    
    try {
        const payload = {
            usuario: inputUsuario.value,
            familia: inputFamilia.value,
            palabras_prohibidas: inputPalabras.value,
            instrucciones_ia: inputInstrucciones.value
        };

        const response = await fetch('/configuracion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            saveFeedback.textContent = "Cambios guardados con éxito.";
            saveFeedback.style.color = "var(--sage)";
            nombreUsuarioActual = inputUsuario.value;
            userNameDisplay.textContent = "Hola, " + inputUsuario.value;
            
            // Ocultar mensaje de éxito tras 3 segundos
            setTimeout(() => { saveFeedback.textContent = ""; }, 3000);
        } else {
            throw new Error("Respuesta no OK");
        }
    } catch (error) {
        saveFeedback.textContent = "Error al guardar.";
        saveFeedback.style.color = "red";
    } finally {
        saveConfigBtn.textContent = "Guardar Cambios";
    }
});

// Trae las últimas interacciones desde /historial y las pinta en el sidebar.
async function cargarHistorial() {
    try {
        const response = await fetch('/historial');
        const data = await response.json();
        const entradas = (data.historial || []).slice().reverse();

        historialLista.textContent = "";

        if (entradas.length === 0) {
            const vacio = document.createElement('p');
            vacio.className = 'historial-vacio';
            vacio.textContent = 'Todavía no hay interacciones registradas.';
            historialLista.appendChild(vacio);
            return;
        }

        entradas.forEach(entrada => {
            const item = document.createElement('div');
            item.className = 'historial-item';

            const fecha = document.createElement('div');
            fecha.className = 'historial-fecha';
            fecha.textContent = new Date(entrada.fecha).toLocaleString();

            const situacion = document.createElement('div');
            situacion.className = 'historial-situacion';
            situacion.textContent = `"${entrada.situacion}"`;

            const consejo = document.createElement('div');
            consejo.className = 'historial-consejo';
            consejo.textContent = `Consejo: ${entrada.consejo}`;

            item.appendChild(fecha);
            item.appendChild(situacion);
            item.appendChild(consejo);
            historialLista.appendChild(item);
        });
    } catch (error) {
        console.error("Error al cargar historial", error);
    }
}

// Cargar la configuración al iniciar la app para configurar el nombre de usuario
cargarConfiguracion();