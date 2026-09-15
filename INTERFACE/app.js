window.setupIniciadoManualmente = false;

// EXPOSE GLOBALS EARLY
window.showGraphs = function(v) {
    const p = document.getElementById('page-graphs');
    if (p) {
        p.style.display = v ? 'flex' : 'none';
        if (typeof targetPattern !== 'undefined') targetPattern = v ? 'codigo' : 'dormindo';
    }
};

window.debugSetState = (s) => {
    window.setupIniciadoManualmente = true;
    const overlay = document.getElementById('setup-overlay');
    if (s === 'home') { if(overlay) overlay.remove(); if (typeof targetPattern !== 'undefined') targetPattern = 'dormindo'; }
    else if (s === 'setup') { if(overlay) overlay.remove(); abrirPortalSetup(); }
    else if (s === 'download') { if(!overlay) abrirPortalSetup(); mudarParaInterfaceDownload(); }
    else if (s === 'sharding') { if(!overlay) abrirPortalSetup(); mudarParaInterfaceSharding(); }
    else if (s === 'graphs') { window.showGraphs(true); }
};

// ═══════════════════════════════════════════════════════
//  ESTADO GLOBAL
// ═══════════════════════════════════════════════════════
const subText = document.getElementById('subtitles');
const label = document.getElementById('status-label');

let targetColor = null; // Inicializado no conectarWS ou animate
let targetIntensity = 0.1;
let currentIntensity = 0.1;
let corEstado = '#1a0033';
let falando = false;
let timerVolta = null;

let currentPattern = 'dormindo';
let targetPattern = 'dormindo';
let patternBlend = 1.0;
let frozenPattern = null;

// Inicializa cores após Three.js carregar
function initColors() {
    if (typeof THREE !== 'undefined' && !targetColor) {
        targetColor = new THREE.Color('#1a0033');
    }
}

// ═══════════════════════════════════════════════════════
//  PADRÕES DE MOVIMENTO (ORIGINAL SOUL GUARD)
// ═══════════════════════════════════════════════════════
function getPatternState(name, t, intensity) {
    switch(name) {
        case 'dormindo': return { rotX: 0.00008, rotY: 0.0003, rotZ: 0.00005, offsetX: 0, offsetY: 0, noiseSpeed: 0.15, noiseScale: 0.3 * intensity };
        case 'ouvindo': return { rotX: 0.0004 + 0.0003 * Math.sin(t * 0.5), rotY: 0.002, rotZ: 0.0001, offsetX: 0.05 * Math.sin(t * 0.3), offsetY: 0.03 * Math.sin(t * 0.2), noiseSpeed: 0.3, noiseScale: 0.6 * intensity };
        case 'conversa': return { rotX: 0.0002, rotY: 0.001, rotZ: 0.0001, offsetX: 0, offsetY: 0, noiseSpeed: 0.4, noiseScale: 2.0 * intensity };
        case 'hardware': return { rotX: 0.0, rotY: 0.006, rotZ: 0.0, offsetX: 0, offsetY: 0, noiseSpeed: 0.2, noiseScale: 0.8 * intensity };
        case 'app': return { rotX: 0.0001, rotY: 0.002, rotZ: 0.004, offsetX: 0, offsetY: 0, noiseSpeed: 0.5, noiseScale: 1.5 * intensity };
        case 'memoria': return { rotX: 0.001, rotY: 0.001, rotZ: 0.001, offsetX: 0.12 * Math.sin(t * 0.8), offsetY: 0.12 * Math.cos(t * 0.8), noiseSpeed: 0.35, noiseScale: 1.2 * intensity };
        case 'codigo': return { rotX: 0.003 * Math.sin(t * 0.4), rotY: 0.004, rotZ: 0.002 * Math.cos(t * 0.3), offsetX: 0, offsetY: 0, noiseSpeed: 0.6, noiseScale: 1.8 * intensity };
        case 'tarefa': return { rotX: 0.0015, rotY: 0.003, rotZ: 0.001, offsetX: 0, offsetY: 0, noiseSpeed: 0.25, noiseScale: 1.0 * intensity };
        case 'alerta': return { rotX: 0.002 * Math.sin(t * 8.0), rotY: 0.008, rotZ: 0.003 * Math.cos(t * 7.0), offsetX: 0.15 * Math.sin(t * 12.0), offsetY: 0.08 * Math.cos(t * 9.0), noiseSpeed: 1.2, noiseScale: 3.0 * intensity };
        default: return { rotX: 0.0002, rotY: 0.001, rotZ: 0.0001, offsetX: 0, offsetY: 0, noiseSpeed: 0.4, noiseScale: 2.0 * intensity };
    }
}

function lerpPattern(a, b, alpha) {
    const l = (x, y, t) => x + (y - x) * t;
    return {
        rotX: l(a.rotX, b.rotX, alpha), rotY: l(a.rotY, b.rotY, alpha), rotZ: l(a.rotZ, b.rotZ, alpha),
        offsetX: l(a.offsetX, b.offsetX, alpha), offsetY: l(a.offsetY, b.offsetY, alpha),
        noiseSpeed: l(a.noiseSpeed, b.noiseSpeed, alpha), noiseScale: l(a.noiseScale, b.noiseScale, alpha),
    };
}

function getBlendedPattern(t, intensity) {
    const pB = getPatternState(targetPattern, t, intensity);
    if (patternBlend >= 1.0) return pB;
    const pA = frozenPattern || getPatternState(currentPattern, t, intensity);
    return lerpPattern(pA, pB, patternBlend);
}

// ═══════════════════════════════════════════════════════
//  WEBSOCKET E UI UPDATES
// ═══════════════════════════════════════════════════════
let socket;
function conectarWS() {
    socket = new WebSocket('ws://' + window.location.host + '/ws');
    socket.onmessage = function(event) {
        try {
            const d = JSON.parse(event.data);
            if (d.type === "hardware_update") {
                atualizarGraficosHardware(d.hardware);
                return;
            }
            if (d.type === "download_update") {
                if (document.getElementById('donuts-container')) {
                    atualizarProgressoVisual(d.download);
                } else if (d.download.ativo && !window.setupIniciadoManualmente) {
                    atualizarProgressoVisual(d.download);
                }
                return;
            }
            if (d.type === "sharding_update") {
                if (d.sharding.ativo) {
                    if (!document.getElementById('shard-msg')) {
                        if (!document.getElementById('setup-overlay')) abrirPortalSetup();
                        mudarParaInterfaceSharding();
                    }
                    atualizarShardingVisual(d.sharding);
                } else if (document.getElementById('setup-overlay') && !window.setupIniciadoManualmente) {
                    setTimeout(() => { const o = document.getElementById('setup-overlay'); if(o) o.remove(); }, 2000);
                }
                return;
            }
            if (d.cor) { 
                corEstado = d.cor; 
                initColors();
                if(targetColor) targetColor.set(d.cor); 
                atualizarCorUI(d.cor); 
            }
            if (d.texto !== undefined) subText.innerText = d.texto;
            if (d.intensidade !== undefined) {
                targetIntensity = d.intensidade;
                if (d.intensidade > 0.15) {
                    falando = true;
                    if (timerVolta) clearTimeout(timerVolta);
                } else if (falando) {
                    falando = false;
                    timerVolta = setTimeout(() => { targetColor.set(corEstado); atualizarCorUI(corEstado); }, 600);
                }
            }
            if (d.padrao && d.padrao !== targetPattern) {
                const snap = getBlendedPattern(Date.now() * 0.001, currentIntensity);
                frozenPattern = { ...snap }; currentPattern = targetPattern; targetPattern = d.padrao; patternBlend = 0.0;
            }
        } catch(e) { console.error(e); }
    };
    socket.onclose = function() { setTimeout(conectarWS, 2000); };
    socket.onerror = function() { socket.close(); };
}

function atualizarCorUI(hex) {
    subText.style.color = hex; subText.style.textShadow = `0 0 15px ${hex}`;
    label.style.color = hex; label.style.textShadow = `0 0 10px ${hex}`;
}

// ═══════════════════════════════════════════════════════
//  HARDWARE HUD
// ═══════════════════════════════════════════════════════
// (Função movida para o topo)

const historyCpu = []; const historyGpu = []; const historyRam = [];
function atualizarGraficosHardware(hw) {
    const mc = document.getElementById('metric-cpu'); if(mc) mc.innerText = Math.round(hw.cpu_usage || 0);
    const mg = document.getElementById('metric-gpu'); if(mg) mg.innerText = Math.round(hw.gpu_load || 0);
    const mr = document.getElementById('metric-ram'); if(mr) mr.innerText = Math.round(hw.ram_usage || 0);

    const tc = document.getElementById('cpu-temp'); if(tc && hw.cpu_temp !== "N/A") tc.innerText = `TEMP: ${hw.cpu_temp}°C`;
    const gs = document.getElementById('gpu-stats'); 
    if(gs && hw.gpu_temp !== "N/A") gs.innerText = `TEMP: ${hw.gpu_temp}°C | VRAM: ${hw.vram_used_gb || '--'} GB | PWR: ${hw.gpu_power || '--'}W`;

    pushChartData('chart-cpu', historyCpu, hw.cpu_usage);
    pushChartData('chart-gpu', historyGpu, hw.gpu_load || 0);
    pushChartData('chart-ram', historyRam, hw.ram_usage);
}

function pushChartData(id, history, val) {
    history.push(val); if (history.length > 40) history.shift();
    const c = document.getElementById(id); if (c) c.innerHTML = history.map(v => `<div class="chart-bar" style="height: ${v}%"></div>`).join('');
}

// ═══════════════════════════════════════════════════════
//  SETUP / DOWNLOAD / SHARDING (ORIGINAL UX)
// ═══════════════════════════════════════════════════════
async function verificarSetup() {
    try {
        const r = await fetch('/system/status'); const data = await r.json();
        if (!data.configurado) abrirPortalSetup();
        else if (data.download && data.download.ativo) { abrirPortalSetup(); mudarParaInterfaceDownload(); }
    } catch(e) { setTimeout(verificarSetup, 2000); }
}

async function selecionarPasta(id) {
    try { const r = await fetch('/system/pick_folder'); const d = await r.json(); if (d.path) document.getElementById(id).value = d.path; } catch(e) {}
}

async function abrirPortalSetup() {
    if (document.getElementById('setup-overlay')) return;
    let modelosHTML = "Carregando núcleos...";
    try {
        const r = await fetch('/system/proposed_models'); const d = await r.json(); const m = d.modelos;
        modelosHTML = `<div style="font-size:11px; color:#555; margin-bottom:15px; text-align:left;"><b style="color:#00ffff">PERFIL:</b> ${d.perfil}<div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; margin-top:8px; border:1px solid rgba(0,255,255,0.05);">• Roteador: ${m.ROTEADOR[0]}<br>• Visão: ${m.VISAO[0]}<br>• Conversa: ${m.CONVERSA[0]}</div></div>`;
    } catch(e) {}

    const html = `<div id="setup-overlay"><div class="setup-box" id="setup-content"><h1 style="letter-spacing:10px; margin-bottom:10px; color:#00ffff; text-shadow:0 0 20px #00ffff; text-align:center;">JARVIS SETUP</h1><p style="color:#666; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">CONFIGURAÇÃO DE DIRETÓRIOS NEURAIS</p>${modelosHTML}<div class="setup-input-group"><label>SSD (Leves)</label><div class="setup-input-row"><input type="text" id="path-ssd" class="setup-input" placeholder="C:\\Jarvis\\Ollama"><button onclick="selecionarPasta('path-ssd')" class="setup-btn-sel">...</button></div></div><div class="setup-input-group"><label>HD (Altas)</label><div class="setup-input-row"><input type="text" id="path-hd" class="setup-input" placeholder="D:\\ModelosIA"><button onclick="selecionarPasta('path-hd')" class="setup-btn-sel">...</button></div></div><button onclick="confirmarSetup()" class="setup-btn-main">CONECTAR NÚCLEOS</button></div></div>`;
    document.body.insertAdjacentHTML('beforeend', html);
}

async function confirmarSetup() {
    const ssd = document.getElementById('path-ssd').value; const hd = document.getElementById('path-hd').value;
    if(!ssd || !hd) return alert("Senhor, indique os caminhos.");
    try { const r = await fetch('/system/setup', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ssd_path: ssd, hd_path: hd }) }); if((await r.json()).status === "success") mudarParaInterfaceDownload(); } catch(e) { alert("Erro."); }
}

function mudarParaInterfaceDownload() {
    const box = document.getElementById('setup-content'); if (!box) return;
    box.innerHTML = `<h1 style="letter-spacing:10px; margin-bottom:10px; color:#00ffff; text-shadow:0 0 20px #00ffff; text-align:center;">SINC NEURAL</h1><p id="dl-msg" style="color:#666; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">TRANSFERINDO PACOTES...</p><div id="donuts-container"></div><div class="progress-global"><div id="dl-bar-global" class="progress-bar"></div></div><div style="display:flex; justify-content:space-between; margin-top:8px; font-size:10px; color:#00ffff;"><span>PROGRESSO</span><span id="dl-pct-total">0%</span></div>`;
    donutsInstanciados = false;
}

function mudarParaInterfaceSharding() {
    const box = document.getElementById('setup-content'); if (!box) return;
    box.innerHTML = `<h1 style="letter-spacing:10px; margin-bottom:10px; color:#ff00ff; text-shadow:0 0 20px #ff00ff; text-align:center;">FATIAMENTO</h1><p id="shard-msg" style="color:#666; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">REORGANIZANDO CAMADAS NEURAIS...</p><div id="sharding-visual"></div><div class="progress-global"><div id="shard-bar" class="progress-bar" style="background:#ff00ff;"></div></div><div style="display:flex; justify-content:space-between; margin-top:8px; font-size:10px; color:#ff00ff;"><span>SHARDS</span><span id="shard-pct">0%</span></div>`;
}

let donutsInstanciados = false; const coresDonuts = ["#00ffff", "#ff00ff", "#00ff00", "#ffff00", "#ff8800", "#9d00ff", "#00ff88"];
function atualizarProgressoVisual(stat) {
    if (!stat || !stat.ativo) return;
    if (!document.getElementById('donuts-container')) { abrirPortalSetup(); mudarParaInterfaceDownload(); }
    const bar = document.getElementById('dl-bar-global'); if(bar) bar.style.width = stat.progresso_total + "%";
    const pct = document.getElementById('dl-pct-total'); if(pct) pct.innerText = stat.progresso_total + "%";
    const msg = document.getElementById('dl-msg'); if(msg) msg.innerText = stat.mensagem.toUpperCase();
    if (stat.modelos && Object.keys(stat.modelos).length > 0) {
        const container = document.getElementById('donuts-container');
        if (!donutsInstanciados) {
            container.innerHTML = ""; let idx = 0;
            for (const mid in stat.modelos) {
                const cor = coresDonuts[idx % coresDonuts.length]; const short = mid.split('/').pop().split(':').shift();
                container.innerHTML += `<div class="donut-item"><div style="position:relative; width:60px; height:60px;"><svg width="60" height="60" viewBox="0 0 80 80"><circle cx="40" cy="40" r="34" stroke="#111" stroke-width="8" fill="none" /><circle id="circle-${mid}" cx="40" cy="40" r="34" stroke="${cor}" stroke-width="8" fill="none" stroke-dasharray="213.6" stroke-dashoffset="213.6" style="transition:0.4s; filter:drop-shadow(0 0 3px ${cor});" /></svg><div id="pct-${mid}" style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:10px; font-weight:bold; color:${cor};">0%</div></div><div class="donut-label">${short}</div></div>`;
                idx++;
            }
            donutsInstanciados = true;
        }
        for (const mid in stat.modelos) {
            const circle = document.getElementById(`circle-${mid}`);
            if (circle) { circle.style.strokeDashoffset = 213.6 - (213.6 * stat.modelos[mid] / 100); document.getElementById(`pct-${mid}`).innerText = Math.round(stat.modelos[mid]) + "%"; }
        }
    }
}

function atualizarShardingVisual(stat) {
    const bar = document.getElementById('shard-bar'); if(bar) bar.style.width = stat.progresso + "%";
    const pct = document.getElementById('shard-pct'); if(pct) pct.innerText = Math.round(stat.progresso) + "%";
    const msg = document.getElementById('shard-msg'); if(msg) msg.innerText = (stat.mensagem || "FATIANDO...").toUpperCase();
    const visual = document.getElementById('sharding-visual');
    if (visual) {
        const target = Math.floor((stat.progresso / 100) * 20);
        for (let i = visual.children.length; i < target; i++) {
            const layer = document.createElement('div'); layer.style.width = (80 + Math.random() * 20) + "%"; layer.style.height = "4px"; layer.style.background = "#ff00ff"; layer.style.boxShadow = "0 0 10px #ff00ff"; layer.style.opacity = "0"; layer.style.transition = "0.5s"; visual.appendChild(layer);
            setTimeout(() => layer.style.opacity = "1", 10);
        }
    }
}

// ═══════════════════════════════════════════════════════
//  THREE.JS Core (ORIGINAL)
// ═══════════════════════════════════════════════════════
const simplex = new SimplexNoise(); const scene = new THREE.Scene(); const camera = new THREE.PerspectiveCamera(75, innerWidth / innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); renderer.setSize(innerWidth, innerHeight);
document.getElementById('canvas-container').appendChild(renderer.domElement);
const geometry = new THREE.IcosahedronGeometry(2, 10); const originalPositions = geometry.attributes.position.array.slice();
const pointsMat = new THREE.PointsMaterial({ color: 0x00ffff, size: 0.06, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false });
const wireMat = new THREE.MeshBasicMaterial({ color: 0x00ffff, wireframe: true, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false });
function criarTexturaGlow() { const size = 128; const canvas = document.createElement('canvas'); canvas.width = canvas.height = size; const ctx = canvas.getContext('2d'); const grad = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2); grad.addColorStop(0, 'rgba(255,255,255,1)'); grad.addColorStop(0.3, 'rgba(255,255,255,0.4)'); grad.addColorStop(1, 'rgba(255,255,255,0)'); ctx.fillStyle = grad; ctx.fillRect(0, 0, size, size); return new THREE.CanvasTexture(canvas); }
const glowMat = new THREE.SpriteMaterial({ map: criarTexturaGlow(), color: 0x00ffff, transparent: true, opacity: 0.65, blending: THREE.AdditiveBlending });
const points = new THREE.Points(geometry, pointsMat); const sphere = new THREE.Mesh(geometry, wireMat); const glow = new THREE.Sprite(glowMat); glow.scale.set(6, 6, 1);
scene.add(points); scene.add(sphere); scene.add(glow); camera.position.z = 6;

function animate() {
    requestAnimationFrame(animate); 
    const t = Date.now() * 0.001; 
    initColors();
    if (!targetColor) return; 

    currentIntensity += (targetIntensity - currentIntensity) * 0.08; 
    patternBlend = Math.min(1.0, patternBlend + 0.08); 
    const p = getBlendedPattern(t, currentIntensity);

    points.rotation.x += p.rotX; 
    points.rotation.y += p.rotY; 
    points.rotation.z += p.rotZ; 
    sphere.rotation.copy(points.rotation);

    points.position.set(p.offsetX, p.offsetY, 0); 
    sphere.position.copy(points.position);

    const pos = geometry.attributes.position.array;
    for (let i = 0; i < pos.length; i += 3) {
        const vX = originalPositions[i], vY = originalPositions[i+1], vZ = originalPositions[i+2];
        const off = simplex.noise3D(vX + t * p.noiseSpeed, vY + t * p.noiseSpeed, vZ + t * p.noiseSpeed) * p.noiseScale; 
        const len = Math.sqrt(vX*vX + vY*vY + vZ*vZ);
        pos[i] = vX + (vX/len) * off; 
        pos[i+1] = vY + (vY/len) * off; 
        pos[i+2] = vZ + (vZ/len) * off;
    }
    geometry.attributes.position.needsUpdate = true;

    if (targetColor) {
        pointsMat.color.lerp(targetColor, 0.06); 
        wireMat.color.copy(pointsMat.color); 
        glowMat.color.copy(pointsMat.color);
    }

    const gs = 5 + (currentIntensity * 4); 
    glow.scale.set(gs, gs, 1); 
    renderer.render(scene, camera);
}

window.addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
animate(); conectarWS(); verificarSetup();

// EXPOSE GLOBALS
window.selecionarPasta = selecionarPasta; window.confirmarSetup = confirmarSetup;
// debugSetState e showGraphs já movidos para o topo
