window.setupIniciadoManualmente = false;

// ═══════════════════════════════════════════════════════
//  EXPOSIÇÃO DE GLOBAIS E CONTROLE DE ESTADOS
// ═══════════════════════════════════════════════════════
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
    if (s === 'home') { 
        if(overlay) overlay.remove(); 
        if (typeof targetPattern !== 'undefined') targetPattern = 'dormindo'; 
    }
    else if (s === 'setup') { 
        if(overlay) overlay.remove(); 
        abrirPortalSetup(); 
    }
    else if (s === 'download') { 
        if(!overlay) abrirPortalSetup(); 
        mudarParaInterfaceDownload(); 
    }
    else if (s === 'sharding') { 
        if(!overlay) abrirPortalSetup(); 
        mudarParaInterfaceSharding(); 
    }
    else if (s === 'graphs') { 
        window.showGraphs(true); 
    }
};

// ═══════════════════════════════════════════════════════
//  ESTADO GLOBAL
// ═══════════════════════════════════════════════════════
const subText = document.getElementById('subtitles');
const label = document.getElementById('status-label');

let targetColor = null;
let targetIntensity = 0.1;
let currentIntensity = 0.1;
let corEstado = '#00ffff';
let falando = false;
let timerVolta = null;

let currentPattern = 'conversa';
let targetPattern = 'conversa';
let patternBlend = 1.0;
let frozenPattern = null;

function initColors() {
    if (typeof THREE !== 'undefined' && !targetColor) {
        targetColor = new THREE.Color('#00ffff');
    }
}

// ═══════════════════════════════════════════════════════
//  PADRÕES DE MOVIMENTO DA ESFERA NEURAL
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
//  WEBSOCKET E SINCRONIZAÇÃO EM TEMPO REAL
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
            if (d.type === "mic_mute_update") {
                atualizarVisualMute(d.muted);
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

            if (d.type === "briefing_start") {
                lidarBriefingStart(d);
                return;
            }
            if (d.type === "briefing_card_focus") {
                lidarBriefingCardFocus(d.card, d.indice, d.total);
                return;
            }
            if (d.type === "briefing_end") {
                lidarBriefingEnd(d);
                return;
            }

            if (d.cor) { 
                corEstado = d.cor; 
                initColors();
                if(targetColor) targetColor.set(d.cor); 
                atualizarCorUI(d.cor); 
            }

            if (d.texto !== undefined) {
                if (subText) {
                    subText.innerText = d.texto;
                    subText.scrollTop = subText.scrollHeight;
                }
                if (d.texto && d.texto.trim()) {
                    adicionarAoHistoricoLog("JARVIS", d.texto);
                }
            }

            if (d.intensidade !== undefined) {
                targetIntensity = d.intensidade;
                if (d.intensidade > 0.15) {
                    falando = true;
                    if (timerVolta) clearTimeout(timerVolta);
                } else if (falando) {
                    falando = false;
                    timerVolta = setTimeout(() => { 
                        if (targetColor) targetColor.set(corEstado); 
                        atualizarCorUI(corEstado); 
                    }, 600);
                }
            }

            if (d.padrao && d.padrao !== targetPattern) {
                const snap = getBlendedPattern(Date.now() * 0.001, currentIntensity);
                frozenPattern = { ...snap }; 
                currentPattern = targetPattern; 
                targetPattern = d.padrao; 
                patternBlend = 0.0;
                atualizarCardAtividade(d.padrao, d.texto);
            }
        } catch(e) { 
            console.error('Erro no processamento do WebSocket:', e); 
        }
    };
    socket.onclose = function() { setTimeout(conectarWS, 2000); };
    socket.onerror = function() { socket.close(); };
}

function atualizarCorUI(hex) {
    if (subText) {
        subText.style.color = hex; 
        subText.style.textShadow = `0 0 15px ${hex}`;
        subText.style.borderColor = `${hex}55`;
    }
    if (label) {
        label.style.color = hex; 
        label.style.textShadow = `0 0 10px ${hex}`;
    }
    const dot = document.getElementById('system-status-dot');
    if (dot) {
        dot.style.background = hex;
        dot.style.boxShadow = `0 0 10px ${hex}`;
    }
}

// ═══════════════════════════════════════════════════════
//  HARDWARE HUD & MINI-BADGES
// ═══════════════════════════════════════════════════════
const historyCpu = []; 
const historyGpu = []; 
const historyRam = [];

function atualizarGraficosHardware(hw) {
    const cpu = Math.round(hw.cpu_usage || 0);
    const gpu = Math.round(hw.gpu_load || 0);
    const ram = Math.round(hw.ram_usage || 0);

    // 1. Atualiza Mini-Badges no Top Bar
    const topCpu = document.getElementById('top-cpu'); if(topCpu) topCpu.innerText = `${cpu}%`;
    const topGpu = document.getElementById('top-gpu'); if(topGpu) topGpu.innerText = `${gpu}%`;
    const topRam = document.getElementById('top-ram'); if(topRam) topRam.innerText = `${ram}%`;

    // 2. Atualiza Dashboard Modal Completo
    const mc = document.getElementById('metric-cpu'); if(mc) mc.innerText = cpu;
    const mg = document.getElementById('metric-gpu'); if(mg) mg.innerText = gpu;
    const mr = document.getElementById('metric-ram'); if(mr) mr.innerText = ram;

    const tc = document.getElementById('cpu-temp'); 
    if(tc && hw.cpu_temp !== "N/A" && hw.cpu_temp !== undefined) tc.innerText = `TEMP: ${hw.cpu_temp}°C`;

    const gs = document.getElementById('gpu-stats'); 
    if(gs && hw.gpu_temp !== "N/A" && hw.gpu_temp !== undefined) {
        gs.innerText = `TEMP: ${hw.gpu_temp}°C | VRAM: ${hw.vram_used_gb || '--'} GB | PWR: ${hw.gpu_power || '--'}W`;
    }

    pushChartData('chart-cpu', historyCpu, cpu);
    pushChartData('chart-gpu', historyGpu, gpu);
    pushChartData('chart-ram', historyRam, ram);
}

function pushChartData(id, history, val) {
    history.push(val); 
    if (history.length > 40) history.shift();
    const c = document.getElementById(id); 
    if (c) c.innerHTML = history.map(v => `<div class="chart-bar" style="height: ${v}%"></div>`).join('');
}

// ═══════════════════════════════════════════════════════
//  GAVETA LATERAL RETRÁTIL & ATIVIDADES
// ═══════════════════════════════════════════════════════
const PATTERN_INFO = {
    'dormindo': { nome: 'Modo de Espera', tag: 'STANDBY', led: '#00ffff', desc: 'Aguardando comandos de voz ou texto...' },
    'conversa': { nome: 'Conversação Neural', tag: 'FALANDO', led: '#00ff88', desc: 'Respondendo interação do usuário.' },
    'ouvindo': { nome: 'Audição & VAD', tag: 'ESCUTANDO', led: '#00ffff', desc: 'Microfone ativo captando comandos.' },
    'tarefa': { nome: 'Executor de Tarefas', tag: 'EXECUÇÃO', led: '#ffaa00', desc: 'Processando fluxo de automação ou scripts.' },
    'codigo': { nome: 'Núcleo de Código', tag: 'ANÁLISE', led: '#00ffff', desc: 'Análise sintática, geração ou execução de scripts.' },
    'memoria': { nome: 'Memória Semântica', tag: 'CHROMA', led: '#aa00ff', desc: 'Consultando ou registrando vetores neurais.' },
    'hardware': { nome: 'Sentinela Térmico', tag: 'TELEMETRIA', led: '#00ffff', desc: 'Coletando métricas e verificando sensores.' },
    'alerta': { nome: 'Sistema de Alerta', tag: 'ALERTA', led: '#ff0055', desc: 'Aviso crítico de proteção ou temperatura elevada.' },
    'app': { nome: 'Controle de Aplicativos', tag: 'SISTEMA', led: '#00ffff', desc: 'Interagindo com sistema operacional e janelas.' }
};

function atualizarCardAtividade(padrao, textoOpcional) {
    const info = PATTERN_INFO[padrao] || PATTERN_INFO['conversa'];
    const nameEl = document.getElementById('current-agent-name');
    const tagEl = document.getElementById('current-agent-tag');
    const ledEl = document.getElementById('current-agent-led');
    const descEl = document.getElementById('current-agent-desc');
    const timeEl = document.getElementById('current-agent-time');

    if (nameEl) nameEl.innerText = info.nome;
    if (tagEl) {
        tagEl.innerText = info.tag;
        tagEl.style.color = info.led;
        tagEl.style.borderColor = `${info.led}55`;
        tagEl.style.background = `${info.led}15`;
    }
    if (ledEl) {
        ledEl.style.background = info.led;
        ledEl.style.boxShadow = `0 0 8px ${info.led}`;
    }
    if (descEl) {
        descEl.innerText = (textoOpcional && textoOpcional.length > 5) ? textoOpcional : info.desc;
    }
    if (timeEl) {
        const d = new Date();
        timeEl.innerText = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
}

window.toggleAgentsDrawer = function(force) {
    const drawer = document.getElementById('agents-drawer');
    const btn = document.getElementById('btn-toggle-drawer');
    if (!drawer) return;
    const currentlyOpen = drawer.classList.contains('open');
    const newState = force !== undefined ? force : !currentlyOpen;
    if (newState) {
        drawer.classList.add('open');
        if (btn) btn.classList.add('active');
    } else {
        drawer.classList.remove('open');
        if (btn) btn.classList.remove('active');
    }
};

function adicionarAoHistoricoLog(remetente, mensagem) {
    const list = document.getElementById('drawer-history-list');
    if (!list || !mensagem || !mensagem.trim()) return;

    const lastItem = list.lastElementChild;
    if (lastItem && lastItem.dataset.msg === mensagem) return;

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const item = document.createElement('div');
    item.className = 'history-item ' + (remetente === 'VOCÊ' ? 'user' : (remetente === 'SISTEMA' ? 'system' : 'jarvis'));
    item.dataset.msg = mensagem;

    item.innerHTML = `<span class="history-time">${timeStr}</span><span class="history-sender">${remetente}:</span><span class="history-body">${mensagem}</span>`;
    list.appendChild(item);
    list.scrollTop = list.scrollHeight;
}

window.limparHistoricoLog = function() {
    const list = document.getElementById('drawer-history-list');
    if (list) {
        list.innerHTML = `<div class="history-item system"><span class="history-time">RESET</span><span class="history-sender">SISTEMA:</span><span class="history-body">Histórico limpo pelo usuário.</span></div>`;
    }
};

// ═══════════════════════════════════════════════════════
//  SISTEMA MENU DROPDOWN
// ═══════════════════════════════════════════════════════
window.toggleSysMenu = function(e) {
    if (e) e.stopPropagation();
    const menu = document.getElementById('sys-dropdown');
    const btn = document.getElementById('btn-sys-menu');
    if (!menu) return;
    const isOpen = menu.classList.contains('open');
    if (isOpen) {
        menu.classList.remove('open');
        if (btn) btn.classList.remove('active');
    } else {
        menu.classList.add('open');
        if (btn) btn.classList.add('active');
    }
};

window.closeSysMenu = function() {
    const menu = document.getElementById('sys-dropdown');
    const btn = document.getElementById('btn-sys-menu');
    if (menu) menu.classList.remove('open');
    if (btn) btn.classList.remove('active');
};

document.addEventListener('click', function(e) {
    const wrapper = document.querySelector('.dropdown-wrapper');
    if (wrapper && !wrapper.contains(e.target)) {
        window.closeSysMenu();
    }
});

// ═══════════════════════════════════════════════════════
//  CONTROLE E SELETOR DE VOZ (TTS) & MODO STARK DSP
// ═══════════════════════════════════════════════════════
window.currentVoiceMotor = 'edge';
window.currentVoiceVoz = 'pt-BR-AntonioNeural';
window.currentVoiceNome = '⚡ Neural: Antonio (Zero CPU - Rápido)';
window.efeitoJarvisAtivo = true;

window.carregarConfigVoz = async function() {
    try {
        const r = await fetch('/api/voice/config');
        const data = await r.json();
        if (data && data.config) {
            window.currentVoiceMotor = data.config.motor || 'edge';
            window.currentVoiceVoz = data.config.voz || 'pt-BR-AntonioNeural';
            window.currentVoiceNome = data.config.nome || '⚡ Neural: Antonio (Zero CPU - Rápido)';
            window.efeitoJarvisAtivo = data.config.efeito_jarvis !== undefined ? !!data.config.efeito_jarvis : true;
            atualizarUISelecaoVoz(window.currentVoiceMotor, window.currentVoiceVoz);
            atualizarUIDsp(window.efeitoJarvisAtivo);
        }
    } catch(e) {
        console.warn("[VOZ] Erro ao obter configuração de voz:", e);
    }
};

window.selecionarVoz = async function(motor, voz, nome) {
    window.currentVoiceMotor = motor;
    window.currentVoiceVoz = voz;
    window.currentVoiceNome = nome;

    // Se for Jarvis Blend, ativa por padrão o Modo Stark
    if (voz === 'blend_jarvis' && window.efeitoJarvisAtivo === undefined) {
        window.efeitoJarvisAtivo = true;
    }

    atualizarUISelecaoVoz(motor, voz);
    atualizarUIDsp(window.efeitoJarvisAtivo);

    try {
        const r = await fetch('/api/voice/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                motor: motor,
                voz: voz,
                nome: nome,
                efeito_jarvis: window.efeitoJarvisAtivo
            })
        });
        const res = await r.json();
        console.log("[VOZ] Configuração atualizada:", res);
    } catch(e) {
        console.error("[VOZ] Falha ao alterar voz:", e);
    }
};

window.alternarEfeitoJarvis = async function() {
    window.efeitoJarvisAtivo = !window.efeitoJarvisAtivo;
    atualizarUIDsp(window.efeitoJarvisAtivo);
    try {
        const r = await fetch('/api/voice/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                motor: window.currentVoiceMotor,
                voz: window.currentVoiceVoz,
                nome: window.currentVoiceNome,
                efeito_jarvis: window.efeitoJarvisAtivo
            })
        });
        const res = await r.json();
        console.log("[VOZ] Modo Stark DSP atualizado:", res);
    } catch(e) {
        console.error("[VOZ] Falha ao alternar Modo Stark DSP:", e);
    }
};

function atualizarUIDsp(ativo) {
    const btn = document.getElementById('btn-toggle-dsp');
    const label = document.getElementById('dsp-toggle-text');
    const badge = document.getElementById('dsp-badge');
    if (!btn) return;

    if (ativo) {
        btn.classList.remove('inactive');
        btn.classList.add('active');
        if (label) label.textContent = 'Modo Stark (ON)';
        if (badge) {
            badge.textContent = 'ATIVO';
        }
    } else {
        btn.classList.remove('active');
        btn.classList.add('inactive');
        if (label) label.textContent = 'Modo Stark (OFF)';
        if (badge) {
            badge.textContent = 'OFF';
        }
    }
}

function atualizarUISelecaoVoz(motor, voz) {
    document.querySelectorAll('.voice-opt').forEach(el => el.classList.remove('selected'));
    let targetId = '';
    if (motor === 'kokoro') {
        if (voz === 'pm_alex') targetId = 'vopt-kokoro_alex';
        else if (voz === 'pf_dora') targetId = 'vopt-kokoro_dora';
        else if (voz === 'pm_santa') targetId = 'vopt-kokoro_santa';
        else if (voz === 'blend_jarvis') targetId = 'vopt-kokoro_blend';
    } else if (motor === 'edge') {
        if (voz.includes('Antonio')) targetId = 'vopt-edge_antonio';
        else if (voz.includes('Francisca')) targetId = 'vopt-edge_francisca';
    }
    const btn = document.getElementById(targetId);
    if (btn) {
        btn.classList.add('selected');
    }
}

// ═══════════════════════════════════════════════════════
//  BRIEFING EXECUTIVO DE NOTÍCIAS & COTAÇÕES
// ═══════════════════════════════════════════════════════
window.newsConfig = {
    categorias: ['mundo', 'economia', 'brasil', 'tecnologia'],
    incluir_cotacoes: true,
    detalhamento: 'completo'
};

window.carregarConfigNoticias = async function() {
    try {
        const r = await fetch('/api/news/config');
        const data = await r.json();
        if (data && Array.isArray(data.categorias)) {
            window.newsConfig = data;
            atualizarUINoticias();
        }
    } catch(e) {
        console.warn("[NOTÍCIAS] Erro ao carregar preferências de notícias:", e);
    }
};

window.alternarCategoriaNoticia = async function(cat) {
    if (!window.newsConfig.categorias) {
        window.newsConfig.categorias = ['mundo', 'economia', 'brasil', 'tecnologia'];
    }
    const idx = window.newsConfig.categorias.indexOf(cat);
    if (idx >= 0) {
        window.newsConfig.categorias.splice(idx, 1);
    } else {
        window.newsConfig.categorias.push(cat);
    }
    atualizarUINoticias();
    await salvarConfigNoticias();
};

window.alternarCotacoesNoticia = async function() {
    window.newsConfig.incluir_cotacoes = !window.newsConfig.incluir_cotacoes;
    atualizarUINoticias();
    await salvarConfigNoticias();
};

async function salvarConfigNoticias() {
    try {
        const r = await fetch('/api/news/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(window.newsConfig)
        });
        const res = await r.json();
        console.log("[NOTÍCIAS] Preferências salvas:", res);
    } catch(e) {
        console.error("[NOTÍCIAS] Falha ao salvar preferências:", e);
    }
}

function atualizarUINoticias() {
    const cats = window.newsConfig.categorias || [];
    const setBtn = (id, active) => {
        const el = document.getElementById(id);
        if (!el) return;
        const check = el.querySelector('.toggle-check');
        if (active) {
            el.classList.add('active');
            el.classList.remove('inactive');
            if (check) check.textContent = '✓';
        } else {
            el.classList.remove('active');
            el.classList.add('inactive');
            if (check) check.textContent = '';
        }
    };
    setBtn('news-toggle-mundo', cats.includes('mundo'));
    setBtn('news-toggle-cotacoes', !!window.newsConfig.incluir_cotacoes);
    setBtn('news-toggle-brasil', cats.includes('brasil'));
    setBtn('news-toggle-tecnologia', cats.includes('tecnologia'));
}

// ═══════════════════════════════════════════════════════
//  SETUP / DOWNLOAD / SHARDING
// ═══════════════════════════════════════════════════════
async function verificarSetup() {
    try {
        const r = await fetch('/system/status'); 
        const data = await r.json();
        if (!data.configurado) abrirPortalSetup();
        else if (data.download && data.download.ativo) { 
            abrirPortalSetup(); 
            mudarParaInterfaceDownload(); 
        }
    } catch(e) { 
        setTimeout(verificarSetup, 2000); 
    }
}

async function selecionarPasta(id) {
    try { 
        const r = await fetch('/system/pick_folder'); 
        const d = await r.json(); 
        if (d.path) document.getElementById(id).value = d.path; 
    } catch(e) {}
}

window.baixarModelosPesados = async function() {
    if (!confirm("Deseja iniciar o download dos modelos pesados (AirLLM 32B/72B)? Isso exigirá bastante espaço em disco e tempo.")) {
        return;
    }
    const btn = document.getElementById('btn-download-heavy');
    if (btn) btn.disabled = true;
    try {
        const r = await fetch('/system/download_heavy', { method: 'POST' });
        const d = await r.json();
        if (d.status === 'iniciado') {
            abrirPortalSetup();
            mudarParaInterfaceDownload();
        } else {
            alert(d.mensagem || "Status: " + d.status);
        }
    } catch(e) {
        alert("Erro ao solicitar download dos modelos pesados: " + e);
    } finally {
        if (btn) btn.disabled = false;
    }
};

async function abrirPortalSetup() {
    if (document.getElementById('setup-overlay')) return;
    let modelosHTML = "Carregando núcleos...";
    try {
        const r = await fetch('/system/proposed_models'); 
        const d = await r.json(); 
        const m = d.modelos;
        modelosHTML = `<div style="font-size:11px; color:#7799aa; margin-bottom:15px; text-align:left;"><b style="color:#00ffff">PERFIL:</b> ${d.perfil}<div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; margin-top:8px; border:1px solid rgba(0,255,255,0.1);">• Roteador: ${m.ROTEADOR[0]}<br>• Visão: ${m.VISAO[0]}<br>• Conversa: ${m.CONVERSA[0]}</div></div>`;
    } catch(e) {}

    const html = `<div id="setup-overlay"><div class="setup-box" id="setup-content"><h1 style="letter-spacing:10px; margin-bottom:10px; color:#00ffff; text-shadow:0 0 20px #00ffff; text-align:center; font-family:'Orbitron', sans-serif;">JARVIS SETUP</h1><p style="color:#7799aa; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">CONFIGURAÇÃO DE DIRETÓRIOS NEURAIS</p>${modelosHTML}<div class="setup-input-group"><label>SSD (Modelos Leves)</label><div class="setup-input-row"><input type="text" id="path-ssd" class="setup-input" placeholder="C:\\Jarvis\\Ollama"><button onclick="selecionarPasta('path-ssd')" class="setup-btn-sel">PROCURAR</button></div></div><div class="setup-input-group"><label>HD (Modelos Pesados)</label><div class="setup-input-row"><input type="text" id="path-hd" class="setup-input" placeholder="D:\\ModelosIA"><button onclick="selecionarPasta('path-hd')" class="setup-btn-sel">PROCURAR</button></div></div><button onclick="confirmarSetup()" class="setup-btn-main">CONECTAR NÚCLEOS</button><button onclick="baixarModelosPesados()" class="setup-btn-main" style="margin-top:10px; border-color:#ffaa00; color:#ffaa00;">BAIXAR MODELOS PESADOS (OPCIONAL 32B/72B)</button></div></div>`;
    document.body.insertAdjacentHTML('beforeend', html);
}

async function confirmarSetup() {
    const ssd = document.getElementById('path-ssd').value; 
    const hd = document.getElementById('path-hd').value;
    if(!ssd || !hd) return alert("Senhor, indique os caminhos dos diretórios.");
    try { 
        const r = await fetch('/system/setup', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({ ssd_path: ssd, hd_path: hd }) 
        }); 
        if((await r.json()).status === "success") mudarParaInterfaceDownload(); 
    } catch(e) { 
        alert("Erro ao confirmar setup: " + e); 
    }
}

function mudarParaInterfaceDownload() {
    const box = document.getElementById('setup-content'); 
    if (!box) return;
    box.innerHTML = `<h1 style="letter-spacing:10px; margin-bottom:10px; color:#00ffff; text-shadow:0 0 20px #00ffff; text-align:center; font-family:'Orbitron', sans-serif;">SINC NEURAL</h1><p id="dl-msg" style="color:#7799aa; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">TRANSFERINDO PACOTES...</p><div id="donuts-container"></div><div class="progress-global"><div id="dl-bar-global" class="progress-bar"></div></div><div style="display:flex; justify-content:space-between; margin-top:8px; font-size:10px; color:#00ffff; font-family:'Orbitron', sans-serif;"><span>PROGRESSO</span><span id="dl-pct-total">0%</span></div>`;
    donutsInstanciados = false;
}

function mudarParaInterfaceSharding() {
    const box = document.getElementById('setup-content'); 
    if (!box) return;
    box.innerHTML = `<h1 style="letter-spacing:10px; margin-bottom:10px; color:#ff00ff; text-shadow:0 0 20px #ff00ff; text-align:center; font-family:'Orbitron', sans-serif;">FATIAMENTO</h1><p id="shard-msg" style="color:#7799aa; margin-bottom:30px; letter-spacing:2px; font-size:11px; text-align:center;">REORGANIZANDO CAMADAS NEURAIS...</p><div id="sharding-visual"></div><div class="progress-global"><div id="shard-bar" class="progress-bar" style="background:#ff00ff;"></div></div><div style="display:flex; justify-content:space-between; margin-top:8px; font-size:10px; color:#ff00ff; font-family:'Orbitron', sans-serif;"><span>SHARDS</span><span id="shard-pct">0%</span></div>`;
}

let donutsInstanciados = false; 
const coresDonuts = ["#00ffff", "#ff00ff", "#00ff00", "#ffff00", "#ff8800", "#9d00ff", "#00ff88"];

function atualizarProgressoVisual(stat) {
    if (!stat || !stat.ativo) return;
    if (!document.getElementById('donuts-container')) { 
        abrirPortalSetup(); 
        mudarParaInterfaceDownload(); 
    }
    const bar = document.getElementById('dl-bar-global'); if(bar) bar.style.width = stat.progresso_total + "%";
    const pct = document.getElementById('dl-pct-total'); if(pct) pct.innerText = stat.progresso_total + "%";
    const msg = document.getElementById('dl-msg'); if(msg) msg.innerText = stat.mensagem.toUpperCase();
    if (stat.modelos && Object.keys(stat.modelos).length > 0) {
        const container = document.getElementById('donuts-container');
        if (!donutsInstanciados) {
            container.innerHTML = ""; 
            let idx = 0;
            for (const mid in stat.modelos) {
                const cor = coresDonuts[idx % coresDonuts.length]; 
                const short = mid.split('/').pop().split(':').shift();
                container.innerHTML += `<div class="donut-item"><div style="position:relative; width:60px; height:60px;"><svg width="60" height="60" viewBox="0 0 80 80"><circle cx="40" cy="40" r="34" stroke="#111" stroke-width="8" fill="none" /><circle id="circle-${mid}" cx="40" cy="40" r="34" stroke="${cor}" stroke-width="8" fill="none" stroke-dasharray="213.6" stroke-dashoffset="213.6" style="transition:0.4s; filter:drop-shadow(0 0 3px ${cor});" /></svg><div id="pct-${mid}" style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:10px; font-weight:bold; color:${cor}; font-family:'Orbitron', sans-serif;">0%</div></div><div class="donut-label">${short}</div></div>`;
                idx++;
            }
            donutsInstanciados = true;
        }
        for (const mid in stat.modelos) {
            const circle = document.getElementById(`circle-${mid}`);
            if (circle) { 
                circle.style.strokeDashoffset = 213.6 - (213.6 * stat.modelos[mid] / 100); 
                document.getElementById(`pct-${mid}`).innerText = Math.round(stat.modelos[mid]) + "%"; 
            }
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
            const layer = document.createElement('div'); 
            layer.style.width = (80 + Math.random() * 20) + "%"; 
            layer.style.height = "4px"; 
            layer.style.background = "#ff00ff"; 
            layer.style.boxShadow = "0 0 10px #ff00ff"; 
            layer.style.opacity = "0"; 
            layer.style.transition = "0.5s"; 
            visual.appendChild(layer);
            setTimeout(() => layer.style.opacity = "1", 10);
        }
    }
}

// ═══════════════════════════════════════════════════════
//  THREE.JS CORE (OTIMIZAÇÃO PESADA DE PERFORMANCE)
// ═══════════════════════════════════════════════════════
const simplex = new SimplexNoise(); 
const scene = new THREE.Scene(); 
const camera = new THREE.PerspectiveCamera(75, innerWidth / innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" }); 
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
document.getElementById('canvas-container').appendChild(renderer.domElement);

// Geometria otimizada (detalhe 5 em vez de 10 reduz vértices em mais de 75%)
const geometry = new THREE.IcosahedronGeometry(2, 5); 
const originalPositions = geometry.attributes.position.array.slice();

// Pré-cálculo dos vetores normais unitários fora do loop para eliminar Math.sqrt a cada frame
const dirNormals = new Float32Array(originalPositions.length);
for (let i = 0; i < originalPositions.length; i += 3) {
    const vx = originalPositions[i];
    const vy = originalPositions[i + 1];
    const vz = originalPositions[i + 2];
    const len = Math.sqrt(vx * vx + vy * vy + vz * vz) || 1.0;
    dirNormals[i] = vx / len;
    dirNormals[i + 1] = vy / len;
    dirNormals[i + 2] = vz / len;
}

const pointsMat = new THREE.PointsMaterial({ 
    color: 0x00ffff, 
    size: 0.055, 
    transparent: true, 
    blending: THREE.AdditiveBlending, 
    depthWrite: false 
});

const wireMat = new THREE.MeshBasicMaterial({ 
    color: 0x00ffff, 
    wireframe: true, 
    transparent: true, 
    opacity: 0.11, 
    blending: THREE.AdditiveBlending, 
    depthWrite: false 
});

function criarTexturaGlow() { 
    const size = 128; 
    const canvas = document.createElement('canvas'); 
    canvas.width = canvas.height = size; 
    const ctx = canvas.getContext('2d'); 
    const grad = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2); 
    grad.addColorStop(0, 'rgba(255,255,255,1)'); 
    grad.addColorStop(0.3, 'rgba(255,255,255,0.4)'); 
    grad.addColorStop(1, 'rgba(255,255,255,0)'); 
    ctx.fillStyle = grad; 
    ctx.fillRect(0, 0, size, size); 
    return new THREE.CanvasTexture(canvas); 
}

const glowMat = new THREE.SpriteMaterial({ 
    map: criarTexturaGlow(), 
    color: 0x00ffff, 
    transparent: true, 
    opacity: 0.65, 
    blending: THREE.AdditiveBlending 
});

const points = new THREE.Points(geometry, pointsMat); 
const sphere = new THREE.Mesh(geometry, wireMat); 
const glow = new THREE.Sprite(glowMat); 
glow.scale.set(6, 6, 1);

scene.add(points); 
scene.add(sphere); 
scene.add(glow); 
camera.position.z = 6;

let frameCount = 0;

function animate() {
    requestAnimationFrame(animate); 
    frameCount++;
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

    // Controle de framerate inteligente:
    // Em estado 'dormindo' e sem falar, atualiza o ruído/deformação apenas a cada 2 frames
    const devePularDeformacao = (targetPattern === 'dormindo' && !falando && (frameCount % 2 !== 0));
    
    if (!devePularDeformacao) {
        const pos = geometry.attributes.position.array;
        const speed = t * p.noiseSpeed;
        const scale = p.noiseScale;
        for (let i = 0; i < pos.length; i += 3) {
            const vX = originalPositions[i];
            const vY = originalPositions[i + 1];
            const vZ = originalPositions[i + 2];
            const off = simplex.noise3D(vX + speed, vY + speed, vZ + speed) * scale;
            pos[i] = vX + dirNormals[i] * off; 
            pos[i + 1] = vY + dirNormals[i + 1] * off; 
            pos[i + 2] = vZ + dirNormals[i + 2] * off;
        }
        geometry.attributes.position.needsUpdate = true;
    }

    if (targetColor) {
        pointsMat.color.lerp(targetColor, 0.06); 
        wireMat.color.copy(pointsMat.color); 
        glowMat.color.copy(pointsMat.color);
    }

    const gs = 5 + (currentIntensity * 4); 
    glow.scale.set(gs, gs, 1); 
    renderer.render(scene, camera);
}

window.addEventListener('resize', () => { 
    camera.aspect = innerWidth / innerHeight; 
    camera.updateProjectionMatrix(); 
    renderer.setSize(innerWidth, innerHeight); 
});

animate(); 
conectarWS(); 
verificarSetup(); 
checarStatusMuteMic();

// ═══════════════════════════════════════════════════════
//  CONTROLE MANUAL DE ÁUDIO E COMANDOS (BOTÕES HUD)
// ═══════════════════════════════════════════════════════
async function pararGravacaoMic() {
    const btn = document.getElementById('btn-stop-mic');
    if (btn) {
        btn.classList.add('btn-active');
        btn.innerHTML = '<span class="btn-icon">⚡</span><span class="btn-text">ENVIANDO...</span>';
    }
    
    if (subText) {
        subText.innerText = "Interrompendo microfone e transcrevendo áudio...";
        subText.style.color = "#00ffff";
    }

    try {
        await fetch('/api/mic/stop', { method: 'POST' });
        console.log('[MIC] Parada manual solicitada via HUD.');
    } catch(e) {
        console.error('Erro ao parar gravação:', e);
    }

    setTimeout(() => {
        if (btn) {
            btn.innerHTML = '<span class="btn-icon">⏹️</span><span class="btn-text">PARAR E ENVIAR</span>';
            btn.classList.remove('btn-active');
        }
    }, 2500);
}

async function enviarComandoManual() {
    const input = document.getElementById('input-comando');
    if (!input) return;
    const texto = input.value.trim();
    if (!texto) return;

    input.value = '';
    if (subText) {
        subText.innerText = `"${texto}"`;
        subText.style.color = "#00ffff";
        subText.scrollTop = subText.scrollHeight;
    }

    adicionarAoHistoricoLog("VOCÊ", texto);
    atualizarCardAtividade("tarefa", `Processando comando: "${texto}"`);

    try {
        await fetch('/api/comando_manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto: texto })
        });
        console.log('[CMD] Comando manual enviado:', texto);
    } catch(e) {
        console.error('Erro ao enviar comando manual:', e);
    }
}

async function alternarMuteMic() {
    const btn = document.getElementById('btn-mute-mic');
    if (btn) btn.disabled = true;
    try {
        const r = await fetch('/api/mic/toggle_mute', { method: 'POST' });
        const d = await r.json();
        atualizarVisualMute(d.muted);
    } catch(e) {
        console.error('Erro ao alternar microfone:', e);
    } finally {
        if (btn) btn.disabled = false;
    }
}

function atualizarVisualMute(isMuted) {
    const btn = document.getElementById('btn-mute-mic');
    const icon = document.getElementById('mute-icon');
    const text = document.getElementById('mute-text');
    if (!btn) return;

    if (isMuted) {
        btn.classList.add('mic-muted');
        if (icon) icon.innerText = '🔇';
        if (text) text.innerText = 'MUTADO';
        btn.title = 'Microfone Mutado (Clique para Ativar)';
    } else {
        btn.classList.remove('mic-muted');
        if (icon) icon.innerText = '🎤';
        if (text) text.innerText = 'MIC ATIVO';
        btn.title = 'Microfone Ativo (Clique para Mutar)';
    }
}

async function checarStatusMuteMic() {
    try {
        const r = await fetch('/api/mic/status');
        const d = await r.json();
        atualizarVisualMute(d.muted);
    } catch(e) {}
}

// ═══════════════════════════════════════════════════════
//  SISTEMA DE BRIEFING MATINAL COREOGRAFADO & CARDS HUD
// ═══════════════════════════════════════════════════════
let briefingCards = [];
let cardAtualHero = null;
let briefingTimerEncerramento = null;
let briefingPillsTimer = null;
const BRIEFING_AUTO_FECHAR_MS = 60000;

// ── MODO DE LAYOUT: esfera Mini-Core no canto quando há conteúdo no centro ──
function atualizarModoLayoutBriefing() {
    const stage = document.getElementById('briefing-stage');
    const dock = document.getElementById('briefing-dock');
    const canvas = document.getElementById('canvas-container');

    const stageVisivel = !!(stage && !stage.classList.contains('hidden') && stage.children.length > 0);
    const dockVisivel = !!(dock && !dock.classList.contains('hidden'));

    // Esfera encolhe para o canto enquanto existe um card em destaque no centro
    if (canvas) canvas.classList.toggle('canvas-mini-corner', stageVisivel);
    // Legenda inferior some enquanto houver qualquer holograma (centro ou dock)
    document.body.classList.toggle('briefing-ativo', stageVisivel || dockVisivel);
}

function agendarAutoFechamentoBriefing() {
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);
    briefingTimerEncerramento = setTimeout(fecharBriefingDock, BRIEFING_AUTO_FECHAR_MS);
}

function pararPillsTelemetria() {
    if (briefingPillsTimer) {
        clearInterval(briefingPillsTimer);
        briefingPillsTimer = null;
    }
}

// Move o card atual para o dock com animação FLIP (o card "encolhe e encaixa" na fileira)
function arquivarCardNoDock(card, heroEl) {
    const dock = document.getElementById('briefing-dock');
    const dockRow = document.getElementById('briefing-dock-row');
    if (!card || !dockRow) return;
    if (dock) dock.classList.remove('hidden');

    let mini = document.getElementById(`mini-${card.id}`);
    const jaExistia = !!mini;
    if (!mini) {
        mini = criarElementoMiniCard(card);
        dockRow.appendChild(mini);
    }
    dockRow.querySelectorAll('.briefing-card-mini').forEach(m => m.classList.remove('mini-ativo'));
    mini.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });

    if (!heroEl || jaExistia || typeof heroEl.animate !== 'function') {
        mini.classList.add('mini-arrived');
        return;
    }

    const from = heroEl.getBoundingClientRect();
    const to = mini.getBoundingClientRect();
    if (!from.width || !to.width) {
        mini.classList.add('mini-arrived');
        return;
    }

    const ghost = heroEl.cloneNode(true);
    ghost.removeAttribute('id');
    ghost.classList.add('hero-ghost');
    Object.assign(ghost.style, {
        left: `${from.left}px`,
        top: `${from.top}px`,
        width: `${from.width}px`,
        height: `${from.height}px`
    });
    document.body.appendChild(ghost);
    mini.style.opacity = '0';

    const dx = to.left - from.left;
    const dy = to.top - from.top;
    const sx = to.width / from.width;
    const sy = to.height / from.height;

    const anim = ghost.animate([
        { transform: 'translate(0px, 0px) scale(1, 1)', opacity: 1, filter: 'blur(0px)' },
        { transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`, opacity: 0.15, filter: 'blur(1px)' }
    ], { duration: 650, easing: 'cubic-bezier(0.22, 1, 0.36, 1)', fill: 'forwards' });

    anim.onfinish = () => {
        ghost.remove();
        mini.style.opacity = '';
        mini.classList.add('mini-arrived');
    };
}

function lidarBriefingStart(dados) {
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);
    pararPillsTelemetria();
    briefingCards = [];
    cardAtualHero = null;

    const dock = document.getElementById('briefing-dock');
    const dockRow = document.getElementById('briefing-dock-row');
    const stage = document.getElementById('briefing-stage');

    if (dockRow) dockRow.innerHTML = '';
    if (dock) dock.classList.add('hidden');

    if (stage) {
        stage.classList.remove('hidden');
        stage.innerHTML = `
            <div class="briefing-card-hero" id="hero-card-telemetry">
                <div class="card-header-row">
                    <div class="card-cat-badge">📡 TELEMETRIA MATINAL // JARVIS HUD</div>
                    <div class="card-counter-badge">${dados.hora || 'SISTEMA ATIVO'}</div>
                </div>
                <div class="telemetry-card-content">
                    <div class="telemetry-header-title">CONSOLIDANDO RADAR DE SISTEMAS...</div>
                    <p class="card-body-text">Iniciando varredura multi-fontes de sensores de meteorologia, agenda pessoal, indicadores do mercado financeiro e notícias prioritárias globais.</p>
                    <div class="telemetry-radar-pills">
                        ${(dados.etapas || []).map((etapa, idx) => `
                            <div class="radar-pill ${idx === 0 ? 'active' : ''}" id="radar-pill-${idx}">
                                <span class="pill-dot"></span>
                                <span>${etapa}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="card-footer-row">
                    <span class="card-source-tag"><span class="card-live-dot"></span>Varredura Multimodal Ativa</span>
                    <span style="font-family: var(--font-display); font-size: 9px; color: rgba(0, 255, 255, 0.7);">MARK VII OS</span>
                </div>
            </div>
        `;

        // Pílulas acendem em sequência enquanto o Jarvis fala a introdução
        let pillIdx = 0;
        const totalPills = (dados.etapas || []).length;
        briefingPillsTimer = setInterval(() => {
            pillIdx++;
            const pill = document.getElementById(`radar-pill-${pillIdx}`);
            if (!pill || pillIdx >= totalPills) {
                pararPillsTelemetria();
                return;
            }
            pill.classList.add('active');
        }, 650);
    }
    atualizarModoLayoutBriefing();
}

function lidarBriefingCardFocus(card, indice, total) {
    if (!card) return;
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);
    pararPillsTelemetria();

    const stage = document.getElementById('briefing-stage');
    const heroAnterior = stage ? stage.querySelector('.briefing-card-hero') : null;

    // O card que acabou de ser falado encolhe e encaixa na fileira inferior
    if (cardAtualHero && cardAtualHero.id !== card.id) {
        arquivarCardNoDock(cardAtualHero, heroAnterior);
    }

    cardAtualHero = card;
    if (!briefingCards.some(c => c.id === card.id)) {
        briefingCards.push(card);
    }

    // Renderiza o novo card hero no centro da tela
    if (stage) {
        stage.classList.remove('hidden');
        stage.innerHTML = renderHeroCardHtml(card, indice, total);
    }
    atualizarModoLayoutBriefing();
}

function lidarBriefingEnd(dados) {
    pararPillsTelemetria();
    const stage = document.getElementById('briefing-stage');
    const heroAtual = stage ? stage.querySelector('.briefing-card-hero') : null;

    // Ao terminar, o último card também encolhe para o dock e o centro é liberado
    if (cardAtualHero) {
        arquivarCardNoDock(cardAtualHero, heroAtual);
        cardAtualHero = null;
    }
    if (stage) {
        stage.classList.add('hidden');
        stage.innerHTML = '';
    }
    atualizarModoLayoutBriefing();

    // Cards permanecem enfileirados e clicáveis por 60s (ou até o usuário limpar a tela)
    agendarAutoFechamentoBriefing();
}

function escapeHtmlBriefing(txt) {
    return String(txt ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderHeroCardHtml(card, indice, total, isExpanded = false) {
    const numAtual = (indice !== undefined && indice !== null) ? indice + 1 : 1;
    const numTotal = total || briefingCards.length || 7;
    const badge = card.categoria || 'RADAR MATINAL';

    let corpo = '';

    if (card.tipo === 'clima') {
        corpo = `
            <div class="weather-hero-block">
                <div>
                    <div class="weather-main-temp">${card.temp_atual || '--'}</div>
                    <div class="weather-condition-text">${card.condicao || 'Estável'}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-family: var(--font-display); font-size: 13px; color: var(--cyan); font-weight: 700;">${card.cidade || 'Passo Fundo'}</div>
                    <div style="font-size: 11px; color: rgba(255,255,255,0.7); margin-top: 4px;">Sensação: ${card.sensacao || card.temp_atual}</div>
                </div>
            </div>
            <div class="weather-stats-grid">
                <div class="weather-stat-box">
                    <span class="weather-stat-label">FAIXA TÉRMICA</span>
                    <span class="weather-stat-val">${card.min_max || '--'}</span>
                </div>
                <div class="weather-stat-box">
                    <span class="weather-stat-label">UMIDADE DO AR</span>
                    <span class="weather-stat-val">${card.umidade || '--'}</span>
                </div>
                <div class="weather-stat-box">
                    <span class="weather-stat-label">VENTO</span>
                    <span class="weather-stat-val">${card.vento || '--'}</span>
                </div>
                <div class="weather-stat-box">
                    <span class="weather-stat-label">SENSORES</span>
                    <span class="weather-stat-val" style="color: var(--green-active);">ONLINE</span>
                </div>
            </div>
        `;
    } else if (card.tipo === 'agenda') {
        const itens = card.itens || [];
        corpo = `
            <div class="card-title-text">${card.titulo || 'Agenda & Lembretes do Dia'}</div>
            <div class="agenda-items-list">
                ${itens.length > 0 ? itens.map(it => `
                    <div class="agenda-item-row">
                        <span class="agenda-time-pill">${it.horario || '--:--'}</span>
                        <span class="agenda-text-desc">${it.texto}</span>
                    </div>
                `).join('') : `
                    <div style="padding: 16px; text-align: center; color: rgba(255,255,255,0.6); font-style: italic; background: rgba(0,0,0,0.3); border-radius: 8px;">
                        Nenhum compromisso pendente registrado para hoje. Agenda livre.
                    </div>
                `}
            </div>
        `;
    } else if (card.tipo === 'mercado') {
        const cotacoes = card.cotacoes || [];
        corpo = `
            <div class="card-title-text">${card.titulo || 'Cotações & Mercado Financeiro'}</div>
            <div class="market-tickers-list">
                ${cotacoes.map(c => `
                    <div class="market-ticker-row">
                        <div class="ticker-name-box">
                            <span class="ticker-name">${c.nome}</span>
                            <span class="ticker-symbol">${c.simbolo}</span>
                        </div>
                        <div class="ticker-val-box">
                            <span class="ticker-price">${c.valor}</span>
                            <span class="ticker-var-badge ${c.alta ? 'alta' : 'baixa'}">${c.var}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        const img = card.imagem || 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80';
        const textoCorpo = card.conteudo_completo || card.resumo || '';
        const paragrafos = textoCorpo.split('\n\n').filter(p => p && p.trim().length > 0);
        const htmlParagrafos = paragrafos.length > 0 
            ? paragrafos.map(p => `<p>${escapeHtmlBriefing(p.trim())}</p>`).join('')
            : `<p>${escapeHtmlBriefing(textoCorpo)}</p>`;

        corpo = `
            <div class="card-img-wrapper">
                <img src="${escapeHtmlBriefing(img)}" alt="${escapeHtmlBriefing(card.titulo)}" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80'">
                <div class="card-img-overlay"></div>
            </div>
            <div class="card-title-text">${escapeHtmlBriefing(card.titulo)}</div>
            <div class="card-scrollable-body">
                ${htmlParagrafos}
            </div>
        `;
    }

    return `
        <div class="briefing-card-hero ${isExpanded ? 'expanded-reading' : ''}" id="hero-${card.id}">
            <div class="card-header-row">
                <div class="card-cat-badge">${badge}</div>
                <div style="display:flex; align-items:center;">
                    <div class="card-counter-badge">${numAtual} / ${numTotal}</div>
                    <button class="hero-close-btn" onclick="fecharHeroCard()" title="Recolher card para a fileira">✕</button>
                </div>
            </div>
            ${corpo}
            <div class="card-footer-row">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="card-source-tag"><span class="card-live-dot"></span>${escapeHtmlBriefing(card.fonte || card.cidade || 'JARVIS RADAR')}</span>
                    <span style="font-family: var(--font-display); font-size: 9px; color: rgba(0, 255, 255, 0.7);">${card.tipo.toUpperCase()}</span>
                </div>
                ${card.tipo === 'noticia' ? `
                    <div class="card-footer-actions">
                        <button class="btn-card-action" onclick="ouvirDetalhesCard('${escapeHtmlBriefing(card.id)}')" title="Ouvir matéria narrada em detalhes pelo Jarvis">🔊 Ouvir Detalhes</button>
                        ${card.link ? `<button class="btn-card-action btn-card-link" onclick="window.open('${escapeHtmlBriefing(card.link)}', '_blank')" title="Abrir artigo original na fonte">🌐 Ler na Fonte ↗</button>` : ''}
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

function criarElementoMiniCard(card) {
    const mini = document.createElement('div');
    mini.className = 'briefing-card-mini';
    mini.id = `mini-${card.id}`;
    mini.onclick = () => reabrirCardHero(card.id);

    const catCurta = card.categoria ? card.categoria.replace('RADAR // ', '').replace('// ', '') : card.tipo.toUpperCase();

    let thumbHtml = '';
    if (card.imagem) {
        thumbHtml = `
            <div class="mini-img-thumb">
                <img src="${escapeHtmlBriefing(card.imagem)}" alt="${escapeHtmlBriefing(card.titulo)}" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80'">
            </div>
        `;
    } else if (card.tipo === 'clima') {
        thumbHtml = `
            <div class="mini-data-thumb">
                <div class="mini-data-main">${card.temp_atual || '--'}</div>
                <div class="mini-data-sub">${escapeHtmlBriefing(card.condicao || card.cidade || 'Clima')}</div>
            </div>
        `;
    } else if (card.tipo === 'mercado') {
        const prim = card.cotacoes && card.cotacoes.length > 0 ? card.cotacoes[0] : null;
        const corVar = prim && !prim.alta ? 'var(--red-alert)' : 'var(--green-active)';
        thumbHtml = `
            <div class="mini-data-thumb">
                <div class="mini-data-main" style="font-size: 15px;">${prim ? prim.valor : 'MERCADO'}</div>
                <div class="mini-data-sub">${prim ? prim.simbolo : ''} <span style="color:${corVar}; font-weight:700;">${prim ? prim.var : ''}</span></div>
            </div>
        `;
    } else if (card.tipo === 'agenda') {
        const qtd = card.itens ? card.itens.length : 0;
        thumbHtml = `
            <div class="mini-data-thumb">
                <div class="mini-data-main">${qtd}</div>
                <div class="mini-data-sub">${qtd === 1 ? 'compromisso pendente' : 'compromissos pendentes'}</div>
            </div>
        `;
    }

    mini.innerHTML = `
        <span class="mini-cat-label">${escapeHtmlBriefing(catCurta)}</span>
        ${thumbHtml}
        <div class="mini-title">${escapeHtmlBriefing(card.titulo)}</div>
        <div class="mini-footer">
            <span>${escapeHtmlBriefing(card.fonte || card.cidade || 'Jarvis')}</span>
            <span style="color: var(--cyan); font-weight: 700;">EXPANDIR ↗</span>
        </div>
    `;
    return mini;
}

function reabrirCardHero(cardId) {
    const card = briefingCards.find(c => c.id === cardId);
    if (!card) return;
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);

    // Se havia um card em destaque que ainda não está na fileira, guarda ele antes
    const stage = document.getElementById('briefing-stage');
    if (cardAtualHero && cardAtualHero.id !== card.id && !document.getElementById(`mini-${cardAtualHero.id}`)) {
        arquivarCardNoDock(cardAtualHero, stage ? stage.querySelector('.briefing-card-hero') : null);
    }

    cardAtualHero = card;
    if (stage) {
        stage.classList.remove('hidden');
        stage.innerHTML = renderHeroCardHtml(card, briefingCards.indexOf(card), briefingCards.length, true);
    }
    document.querySelectorAll('#briefing-dock-row .briefing-card-mini').forEach(m => {
        m.classList.toggle('mini-ativo', m.id === `mini-${card.id}`);
    });
    atualizarModoLayoutBriefing();
    agendarAutoFechamentoBriefing();
}

window.ouvirDetalhesCard = async function(cardId) {
    const card = briefingCards.find(c => c.id === cardId);
    if (!card) return;

    const textoComando = `Jarvis, me detalhe a notícia: "${card.titulo}"`;
    adicionarAoHistoricoLog("VOCÊ", textoComando);
    atualizarCardAtividade("tarefa", `Lendo detalhes: "${card.titulo}"`);
    if (subText) {
        subText.innerText = `Lendo detalhes de: "${card.titulo}"...`;
        subText.style.color = "#00ffff";
    }

    try {
        await fetch('/api/comando_manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto: textoComando })
        });
    } catch(e) {
        console.error("Erro ao solicitar detalhes da notícia:", e);
    }
};

// Recolhe apenas o card central (a esfera volta ao centro, a fileira continua visível)
function fecharHeroCard() {
    const stage = document.getElementById('briefing-stage');
    if (cardAtualHero) {
        arquivarCardNoDock(cardAtualHero, stage ? stage.querySelector('.briefing-card-hero') : null);
        cardAtualHero = null;
    }
    if (stage) {
        stage.classList.add('hidden');
        stage.innerHTML = '';
    }
    document.querySelectorAll('#briefing-dock-row .briefing-card-mini').forEach(m => m.classList.remove('mini-ativo'));
    atualizarModoLayoutBriefing();
    agendarAutoFechamentoBriefing();
}

// Limpa todos os hologramas e devolve a esfera majestosa ao centro
function fecharBriefingDock() {
    const dock = document.getElementById('briefing-dock');
    const stage = document.getElementById('briefing-stage');
    if (dock) dock.classList.add('hidden');
    if (stage) {
        stage.classList.add('hidden');
        stage.innerHTML = '';
    }
    document.querySelectorAll('.hero-ghost').forEach(g => g.remove());
    pararPillsTelemetria();
    cardAtualHero = null;
    if (briefingTimerEncerramento) clearTimeout(briefingTimerEncerramento);
    briefingTimerEncerramento = null;
    atualizarModoLayoutBriefing();
}

async function iniciarBriefingManual() {
    const btn = document.getElementById('btn-trigger-briefing');
    if (btn) {
        btn.classList.add('briefing-pulse');
        btn.disabled = true;
    }

    try {
        const resp = await fetch('/api/briefing/start', { method: 'POST' });
        const data = await resp.json();
        console.log('[BRIEFING] Solicitado via HUD:', data);
    } catch(e) {
        console.error('Erro ao disparar briefing:', e);
    } finally {
        setTimeout(() => {
            if (btn) {
                btn.classList.remove('briefing-pulse');
                btn.disabled = false;
            }
        }, 3000);
    }
}

// ═══════════════════════════════════════════════════════
//  SISTEMA DE AGENDA & LEMBRETES (DRAWER & MODAL)
// ═══════════════════════════════════════════════════════

async function carregarLembretes() {
    const listEl = document.getElementById('drawer-reminders-list');
    if (!listEl) return;

    try {
        const resp = await fetch('/api/reminders');
        const data = await resp.json();
        const lista = data.reminders || [];

        if (lista.length === 0) {
            listEl.innerHTML = '<div class="reminder-empty">Nenhum lembrete registrado no momento.</div>';
            return;
        }

        listEl.innerHTML = lista.map(rem => `
            <div class="reminder-item ${rem.concluido ? 'concluido' : ''}" id="rem-${rem.id}">
                <span class="reminder-check" onclick="toggleLembrete('${rem.id}')" title="Marcar como ${rem.concluido ? 'pendente' : 'concluído'}">
                    ${rem.concluido ? '☑' : '☐'}
                </span>
                <span class="reminder-texto" onclick="toggleLembrete('${rem.id}')" title="Clique para alternar status">
                    ${rem.texto}
                </span>
                ${rem.horario ? `<span class="reminder-horario">${rem.horario}</span>` : ''}
                <button class="reminder-del-btn" onclick="deletarLembrete('${rem.id}')" title="Excluir lembrete">✕</button>
            </div>
        `).join('');
    } catch(e) {
        console.error('Erro ao carregar lembretes:', e);
        listEl.innerHTML = '<div class="reminder-empty">Falha ao carregar lembretes.</div>';
    }
}

function abrirModalLembrete() {
    const modal = document.getElementById('modal-lembrete');
    if (modal) {
        modal.classList.remove('hidden');
        const input = document.getElementById('input-rem-texto');
        if (input) {
            input.value = '';
            setTimeout(() => input.focus(), 100);
        }
        const inputHora = document.getElementById('input-rem-horario');
        if (inputHora) inputHora.value = '';
    }
}

function fecharModalLembrete() {
    const modal = document.getElementById('modal-lembrete');
    if (modal) modal.classList.add('hidden');
}

async function salvarNovoLembrete() {
    const inputTexto = document.getElementById('input-rem-texto');
    const inputHora = document.getElementById('input-rem-horario');
    if (!inputTexto) return;

    const texto = inputTexto.value.trim();
    const horario = inputHora ? inputHora.value.trim() : '';

    if (!texto) {
        inputTexto.focus();
        return;
    }

    try {
        await fetch('/api/reminders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texto, horario })
        });
        fecharModalLembrete();
        await carregarLembretes();
    } catch(e) {
        console.error('Erro ao salvar lembrete:', e);
    }
}

async function toggleLembrete(remId) {
    try {
        await fetch(`/api/reminders/${remId}/toggle`, { method: 'POST' });
        await carregarLembretes();
    } catch(e) {
        console.error('Erro ao alternar lembrete:', e);
    }
}

async function deletarLembrete(remId) {
    try {
        await fetch(`/api/reminders/${remId}`, { method: 'DELETE' });
        await carregarLembretes();
    } catch(e) {
        console.error('Erro ao deletar lembrete:', e);
    }
}

// ═══════════════════════════════════════════════════════
//  EXPOSIÇÃO DE MÉTODOS GLOBAIS AO WINDOW
// ═══════════════════════════════════════════════════════
window.selecionarPasta = selecionarPasta; 
window.confirmarSetup = confirmarSetup;
window.pararGravacaoMic = pararGravacaoMic;
window.enviarComandoManual = enviarComandoManual;
window.alternarMuteMic = alternarMuteMic;
window.selecionarVoz = selecionarVoz;
window.carregarConfigVoz = carregarConfigVoz;
window.alternarEfeitoJarvis = alternarEfeitoJarvis;
window.carregarConfigNoticias = carregarConfigNoticias;
window.alternarCategoriaNoticia = alternarCategoriaNoticia;
window.alternarCotacoesNoticia = alternarCotacoesNoticia;

window.lidarBriefingStart = lidarBriefingStart;
window.lidarBriefingCardFocus = lidarBriefingCardFocus;
window.lidarBriefingEnd = lidarBriefingEnd;
window.reabrirCardHero = reabrirCardHero;
window.fecharBriefingDock = fecharBriefingDock;
window.fecharHeroCard = fecharHeroCard;
window.iniciarBriefingManual = iniciarBriefingManual;
window.carregarLembretes = carregarLembretes;
window.abrirModalLembrete = abrirModalLembrete;
window.fecharModalLembrete = fecharModalLembrete;
window.salvarNovoLembrete = salvarNovoLembrete;
window.toggleLembrete = toggleLembrete;
window.deletarLembrete = deletarLembrete;

// Inicialização imediata de voz, microfone, lembretes e briefing de notícias
window.carregarConfigVoz();
window.carregarConfigNoticias();
window.carregarLembretes();
checarStatusMuteMic();


