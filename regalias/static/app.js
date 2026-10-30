// Interfaz de Regalías. Todo el texto que viene de la base de datos pasa por esc()
// antes de insertarse en la página, y no se usan atributos style (la CSP lo bloquea).

const estado = {
  tab: 'personas',
  personas: [],
  canciones: [],
  eventos: [],
  personaReporte: null,
  reporte: null,
  necesitaClave: false,
  borrador: [],
  aviso: '',
  avisoTipo: 'ok',
};

const vista = document.getElementById('vista');

function esc(valor) {
  return String(valor).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function avisar(texto, tipo = 'ok') {
  estado.aviso = texto;
  estado.avisoTipo = tipo;
}

function hoy() {
  return new Date().toISOString().slice(0, 10);
}

// La clave, si el servidor la pide, vive solo en sessionStorage: se borra al cerrar la pestaña.
function claveGuardada() {
  try {
    return sessionStorage.getItem('regaliasClave') || '';
  } catch (error) {
    return '';
  }
}

function cabecerasAutorizacion() {
  const clave = claveGuardada();
  return clave ? { Authorization: `Bearer ${clave}` } : {};
}

async function api(ruta, opciones = {}) {
  const respuesta = await fetch(ruta, {
    ...opciones,
    headers: { 'Content-Type': 'application/json', ...cabecerasAutorizacion(), ...(opciones.headers || {}) },
  });
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) {
    const error = new Error(datos.error || `Error ${respuesta.status}`);
    error.status = respuesta.status;
    throw error;
  }
  return datos;
}

// Los enlaces no pueden enviar la clave, así que las descargas se piden con fetch.
async function descargar(ruta, nombre) {
  const respuesta = await fetch(ruta, { headers: cabecerasAutorizacion() });
  if (!respuesta.ok) {
    throw new Error('No se pudo descargar el reporte.');
  }
  const url = URL.createObjectURL(await respuesta.blob());
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
}

function enviar(ruta, datos) {
  return api(ruta, { method: 'POST', body: JSON.stringify(datos) });
}

async function cargarTodo() {
  const [personas, canciones, eventos] = await Promise.all([
    api('/api/personas'), api('/api/canciones'), api('/api/eventos'),
  ]);
  Object.assign(estado, { personas, canciones, eventos });
  if (!personas.some((p) => p.id === estado.personaReporte)) {
    estado.personaReporte = personas.length ? personas[0].id : null;
  }
  estado.reporte = estado.personaReporte
    ? await api(`/api/reporte?persona=${encodeURIComponent(estado.personaReporte)}`)
    : null;
}

function mensaje() {
  if (!estado.aviso) return '';
  const clase = estado.avisoTipo === 'err' ? 'err' : 'ok';
  return `<p class="msg ${clase}" role="status">${esc(estado.aviso)}</p>`;
}

function opcionesPersonas(seleccionado = '') {
  return estado.personas.map((p) =>
    `<option value="${esc(p.id)}"${p.id === seleccionado ? ' selected' : ''}>${esc(p.nombre)} (${esc(p.id)})</option>`
  ).join('');
}

function vistaPersonas() {
  const filas = estado.personas.map((p) =>
    `<tr><td>${esc(p.nombre)}</td><td>${esc(p.id)}</td></tr>`).join('');
  return `
  <div class="grid">
    <section class="card">
      <h2>Registrar persona</h2>
      <form id="f-persona">
        <label for="p-id">Identificador (correo o código)</label>
        <input id="p-id" name="id" autocomplete="off" required>
        <label for="p-nombre">Nombre</label>
        <input id="p-nombre" name="nombre" autocomplete="off" required>
        <button class="btn" type="submit">Registrar</button>
      </form>
      ${mensaje()}
    </section>
    <section class="card">
      <h2>Personas (${estado.personas.length})</h2>
      <div class="tablewrap"><table>
        <thead><tr><th>Nombre</th><th>Identificador</th></tr></thead>
        <tbody>${filas || '<tr><td colspan="2" class="vacio">Aún no hay personas.</td></tr>'}</tbody>
      </table></div>
    </section>
  </div>`;
}

function vistaCanciones() {
  const borrador = estado.borrador.map((d, i) => {
    const persona = estado.personas.find((p) => p.id === d.id);
    return `<span class="pill">${esc(persona ? persona.nombre : d.id)} · ${esc(d.pct)} %
      <button type="button" class="tab" data-quitar="${i}" aria-label="Quitar colaborador">×</button></span>`;
  }).join('');
  const suma = estado.borrador.reduce((total, d) => total + (Number(d.pct) || 0), 0);
  const sumaClase = Math.abs(suma - 100) < 1e-9 ? 'bien' : 'mal';
  const filas = estado.canciones.map((c) => {
    const colaboradores = c.colaboradores.map((r) =>
      `<span class="pill">${esc(r.nombre)} ${esc(r.pct)} %</span>`).join('');
    return `<tr>
      <td>${esc(c.id)}</td><td>${esc(c.titulo)}</td><td>${esc(c.artista)}</td>
      <td>${c.isrc ? esc(c.isrc) : '—'}</td><td>${colaboradores}</td>
      <td class="num total">${esc(c.total)}</td></tr>`;
  }).join('');
  return `
  <div class="grid">
    <section class="card">
      <h2>Registrar canción</h2>
      <form id="f-cancion">
        <label for="c-titulo">Título</label>
        <input id="c-titulo" name="titulo" autocomplete="off" required>
        <label for="c-artista">Artista principal</label>
        <input id="c-artista" name="artista" autocomplete="off" required>
        <label for="c-isrc">ISRC (opcional)</label>
        <input id="c-isrc" name="isrc" autocomplete="off" placeholder="US-RC1-76-07839">

        <label for="c-persona">Colaborador</label>
        <div class="fila">
          <select id="c-persona">${opcionesPersonas()}</select>
          <input class="corto" id="c-pct" inputmode="decimal" placeholder="%">
          <button class="btn sec" type="button" id="c-agregar">Añadir</button>
        </div>
        <div>${borrador || '<p class="vacio">Sin colaboradores todavía.</p>'}</div>
        <p class="suma ${sumaClase}">Suma: ${suma.toFixed(2)} / 100</p>
        <button class="btn" type="submit">Registrar canción</button>
      </form>
      ${mensaje()}
    </section>
    <section class="card">
      <h2>Canciones (${estado.canciones.length})</h2>
      <div class="tablewrap"><table>
        <thead><tr><th>#</th><th>Título</th><th>Artista</th><th>ISRC</th><th>Colaboradores</th><th class="num">Total</th></tr></thead>
        <tbody>${filas || '<tr><td colspan="6" class="vacio">Aún no hay canciones.</td></tr>'}</tbody>
      </table></div>
    </section>
  </div>`;
}

function vistaEventos() {
  const canciones = estado.canciones.map((c) =>
    `<option value="${esc(c.id)}">${esc(c.titulo)}</option>`).join('');
  const filas = estado.eventos.map((e) => {
    const reparto = e.reparto.map((r) =>
      `<span class="pill">${esc(r.nombre)} ${esc(r.monto)}</span>`).join('');
    return `<tr><td>${esc(e.id)}</td><td>${esc(e.cancion)}</td>
      <td>${e.tipo === 'venta' ? 'Venta' : 'Reproducciones'}</td><td>${esc(e.fecha)}</td>
      <td class="num total">${esc(e.monto)}</td><td>${reparto}</td></tr>`;
  }).join('');
  return `
  <div class="grid">
    <section class="card">
      <h2>Registrar ingreso</h2>
      <form id="f-evento">
        <label for="e-cancion">Canción</label>
        <select id="e-cancion">${canciones}</select>
        <label for="e-tipo">Tipo</label>
        <select id="e-tipo">
          <option value="reproduccion">Reproducciones</option>
          <option value="venta">Venta</option>
        </select>
        <label for="e-fecha">Fecha</label>
        <input id="e-fecha" type="date" value="${hoy()}" required>
        <div id="e-rep" class="fila">
          <div><label for="e-cantidad">Cantidad</label><input id="e-cantidad" inputmode="numeric" value="1000"></div>
          <div><label for="e-tarifa">Tarifa por reproducción</label><input id="e-tarifa" inputmode="decimal" value="0.0037"></div>
        </div>
        <div id="e-venta" hidden>
          <label for="e-precio">Precio neto</label>
          <input id="e-precio" inputmode="decimal" value="10.00">
        </div>
        <button class="btn" type="submit">Registrar</button>
      </form>
      ${mensaje()}
    </section>
    <section class="card">
      <h2>Ingresos (${estado.eventos.length})</h2>
      <div class="tablewrap"><table>
        <thead><tr><th>#</th><th>Canción</th><th>Tipo</th><th>Fecha</th><th class="num">Monto</th><th>Reparto</th></tr></thead>
        <tbody>${filas || '<tr><td colspan="6" class="vacio">Aún no hay ingresos.</td></tr>'}</tbody>
      </table></div>
    </section>
  </div>`;
}

function vistaAcceso() {
  return `
  <section class="card">
    <h2>Clave de acceso</h2>
    <p class="sub">Este servidor pide una clave. Quien lo inició la define con REGALIAS_CLAVE o --clave.</p>
    <form id="f-clave">
      <label for="k-clave">Clave</label>
      <input id="k-clave" type="password" autocomplete="current-password" required>
      <button class="btn" type="submit">Entrar</button>
    </form>
    ${mensaje()}
  </section>`;
}

function vistaReportes() {
  const r = estado.reporte;
  const filas = r ? r.periodos.map((p) =>
    `<tr><td>${esc(p.periodo)}</td><td class="num total">${esc(p.monto)}</td></tr>`).join('') : '';
  const enlaces = r ? `
    <a class="enlace" href="/api/reporte.csv?persona=${encodeURIComponent(r.id)}" data-descarga="reporte.csv">Descargar CSV</a>
    &nbsp;·&nbsp;
    <a class="enlace" href="/api/reporte.xlsx?persona=${encodeURIComponent(r.id)}" data-descarga="reporte.xlsx">Descargar Excel</a>` : '';
  const cancionesFilas = estado.canciones.map((c) =>
    `<tr><td>${esc(c.titulo)}</td><td class="num">${esc(c.total)}</td></tr>`).join('');
  return `
  <div class="grid">
    <section class="card">
      <h2>Ingresos por colaborador y mes</h2>
      <label for="r-persona">Colaborador</label>
      <select id="r-persona">${opcionesPersonas(estado.personaReporte)}</select>
      <div class="tablewrap"><table>
        <thead><tr><th>Mes</th><th class="num">Ingresos</th></tr></thead>
        <tbody>${filas || '<tr><td colspan="2" class="vacio">Sin ingresos en ningún mes.</td></tr>'}</tbody>
        <tfoot><tr><td class="total">Total</td><td class="num total">${esc(r ? r.total : '0.00')}</td></tr></tfoot>
      </table></div>
      <p>${enlaces}</p>
      ${mensaje()}
    </section>
    <section class="card">
      <h2>Total por canción</h2>
      <div class="tablewrap"><table>
        <thead><tr><th>Canción</th><th class="num">Total</th></tr></thead>
        <tbody>${cancionesFilas || '<tr><td colspan="2" class="vacio">Aún no hay canciones.</td></tr>'}</tbody>
      </table></div>
    </section>
  </div>`;
}

const vistas = {
  personas: vistaPersonas,
  canciones: vistaCanciones,
  eventos: vistaEventos,
  reportes: vistaReportes,
};

// Al repintar se conserva lo que el usuario ya escribió en los campos de la vista.
// Solo se limpian después de un envío exitoso.
function pintar({ limpiar = false } = {}) {
  if (estado.necesitaClave) {
    vista.innerHTML = vistaAcceso();
    conectar();
    return;
  }
  const previos = {};
  if (!limpiar) {
    vista.querySelectorAll('input[id], select[id]').forEach((el) => { previos[el.id] = el.value; });
  }
  document.querySelectorAll('.tab[data-tab]').forEach((b) =>
    b.setAttribute('aria-selected', String(b.dataset.tab === estado.tab)));
  vista.innerHTML = vistas[estado.tab]();
  Object.entries(previos).forEach(([id, valor]) => {
    const el = document.getElementById(id);
    if (el) el.value = valor;
  });
  conectar();
}

async function refrescar() {
  try {
    await cargarTodo();
    estado.necesitaClave = false;
  } catch (error) {
    if (error.status === 401) {
      estado.necesitaClave = true;
      if (claveGuardada()) avisar('Clave incorrecta.', 'err');
    } else {
      avisar(error.message, 'err');
    }
  }
  pintar();
}

function leerForm(form) {
  return Object.fromEntries(new FormData(form).entries());
}

// Cada acción envía al servidor y, si funciona, vuelve a cargar todos los datos.
async function accion(fn, textoOk) {
  try {
    await fn();
    if (textoOk) avisar(textoOk);
    await cargarTodo();
    pintar({ limpiar: true });
  } catch (error) {
    avisar(error.message, 'err');
    pintar();
  }
}

function conectar() {
  const form = (id) => document.getElementById(id);

  form('f-clave')?.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const clave = document.getElementById('k-clave').value;
    try {
      sessionStorage.setItem('regaliasClave', clave);
    } catch (error) {
      avisar('Este navegador no permite guardar la clave; no se podrá entrar.', 'err');
    }
    avisar('');
    refrescar();
  });

  document.querySelectorAll('a[data-descarga]').forEach((enlace) =>
    enlace.addEventListener('click', (ev) => {
      ev.preventDefault();
      descargar(enlace.getAttribute('href'), enlace.dataset.descarga)
        .catch((error) => avisar(error.message, 'err'));
    }));

  form('f-persona')?.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const datos = leerForm(ev.target);
    accion(() => enviar('/api/personas', datos), 'Persona registrada.');
  });

  form('c-agregar')?.addEventListener('click', () => {
    const pct = document.getElementById('c-pct').value.trim();
    const id = document.getElementById('c-persona').value;
    if (estado.borrador.some((d) => d.id === id)) {
      avisar('Esa persona ya está en la canción.', 'err');
    } else if (!/^\d+(\.\d{1,2})?$/.test(pct)) {
      avisar('El porcentaje debe ser un número con hasta dos decimales.', 'err');
    } else {
      estado.borrador.push({ id, pct });
      avisar('');
    }
    pintar();
  });

  document.querySelectorAll('[data-quitar]').forEach((b) =>
    b.addEventListener('click', () => {
      estado.borrador.splice(Number(b.dataset.quitar), 1);
      pintar();
    }));

  form('f-cancion')?.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const datos = leerForm(ev.target);
    accion(async () => {
      await enviar('/api/canciones', {
        titulo: datos.titulo,
        artista: datos.artista,
        isrc: datos.isrc || null,
        colaboradores: estado.borrador.map((d) => ({ id: d.id, pct: d.pct })),
      });
      estado.borrador = [];
    }, 'Canción registrada.');
  });

  const tipo = form('e-tipo');
  if (tipo) {
    const mostrar = () => {
      const venta = tipo.value === 'venta';
      document.getElementById('e-rep').hidden = venta;
      document.getElementById('e-venta').hidden = !venta;
    };
    tipo.addEventListener('change', mostrar);
    mostrar();
  }

  form('f-evento')?.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const cancionId = Number(document.getElementById('e-cancion').value);
    const datos = {
      cancionId,
      tipo: document.getElementById('e-tipo').value,
      fecha: document.getElementById('e-fecha').value,
    };
    if (datos.tipo === 'venta') {
      datos.precio = document.getElementById('e-precio').value.trim();
    } else {
      datos.cantidad = Number(document.getElementById('e-cantidad').value);
      datos.tarifa = document.getElementById('e-tarifa').value.trim();
    }
    accion(async () => {
      const { monto } = await enviar('/api/eventos', datos);
      avisar(`Ingreso registrado por ${monto}.`);
    }, null);
  });

  form('r-persona')?.addEventListener('change', (ev) => {
    estado.personaReporte = ev.target.value;
    refrescar();
  });
}

// La vista se pinta al instante para que lo que el usuario escribe no se pierda
// por un repintado tardío; después se actualizan los datos desde el servidor.
document.querySelectorAll('.tab[data-tab]').forEach((b) =>
  b.addEventListener('click', () => {
    estado.tab = b.dataset.tab;
    avisar('');
    pintar();
    refrescar();
  }));

refrescar();
