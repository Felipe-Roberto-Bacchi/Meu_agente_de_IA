# 🛠️ Documentação Técnica - Jarvis AI Agent

Este documento fornece uma visão exaustiva da engenharia por trás do Jarvis, detalhando a arquitetura, os módulos e a integração de sistemas.

---

## 🏛️ Arquitetura Geral

O Jarvis é construído sobre uma arquitetura modular orientada a eventos, utilizando **Python** como linguagem base para o núcleo e **FastAPI/WebSocket** para a ponte de interface em tempo real.

### Componentes Core:
- **Inteligência**: Ollama (Local) para LLM e Moondream (Visão).
- **Audição (STT)**: OpenAI Whisper (Tiny/Small) rodando localmente.
- **Fala (TTS)**: Sistema triplo (Qwen3-TTS local, Edge-TTS cloud, pyttsx3 offline).
- **Memória (RAG)**: ChromaDB para persistência de fatos e histórico com busca semântica.
- **Interface**: Three.js para visualização 3D e FastAPI para o servidor de controle.

---

## 📂 Mapeamento de Diretórios e Arquivos

### ⚡ Raiz do Projeto
- `main.py`: O "maestro" do sistema. Gerencia o boot, verifica integridade, inicia o servidor de interface e mantém o loop infinito de escuta e processamento.
- `obsidian_sync.py`: Utilitário de alto nível que espelha a estrutura do projeto e o conteúdo dos arquivos para um cofre do Obsidian, criando uma documentação viva.
- `simulador_interface.py`: Script para testar a comunicação com o frontend sem depender do loop de voz.

### 🧠 MODULOS/ (Serviços e Lógica)
- **`actions_module.py`**: Execução de scripts externos e abertura de aplicativos usando o mapeamento em `DADOS/apps_cache.json`.
- **`airllm_module.py`**: Motor de inferência para modelos massivos (32B/70B) usando técnica de fatiamento (sharded inference) para economizar VRAM.
- **`identity_module.py`**: Serviço de auto-detecção de hardware e OS. Varre o registro e WMI para definir a identidade do Jarvis na máquina local.
- **`nlp_processor.py`**: Camada de correção fonética e normalização. Corrige erros comuns do Whisper (ex: "cepeu" -> "cpu", "gepeu" -> "gpu").
- **`brain/`**: O centro de decisão.
    - `core/router.py`: Roteador de intenções (Hardware, Finance, Vision, etc).
    - `core/conversation.py`: Gerenciador de diálogo e contexto.
    - `core/executor.py`: Processador de tarefas complexas e planos de ação em background.
    - `memory/handler.py`: Interface inteligente que usa LLM para classificar ações de memória (Salvar/Buscar/Apagar).
- **`ear/`**: Todo o processamento de áudio de entrada.
    - `wake_word.py`: Detector do gatilho "Jarvis".
    - `recorder.py`: Gerenciamento de microfone e calibração de ruído.
- **`hardware_module.py`**: Monitoramento térmico e de uso (CPU/GPU) via LHM e NVML.
- **`interface_server.py`**: Servidor FastAPI/WebSocket para atualização da UI 3D.
- **`memory_long.py`**: Implementação ChromaDB para busca semântica persistente.
- **`vision_module.py`**: Captura de tela e análise visual via Moondream (Ollama).
- **`voice_manager.py`**: Orquestrador de fala com fallbacks: Qwen -> Edge -> pyttsx3.

### 📈 monitor/ (LibreHardwareMonitor)
- Instalação local completa do `LibreHardwareMonitor`. O Jarvis utiliza este binário para ler sensores que o `psutil` padrão não alcança (como voltagens e fans).

### 📊 DADOS/ (Persistência e Cache)
- `apps_cache.json`: Dicionário com centenas de caminhos de executáveis mapeados para comandos de voz.
- `jarvis_identity.json`: Perfil do hardware local gerado pelo `identity_module`.
- `vozes/`: Arquivos de referência (`referencia.wav`) para clonagem ou sintonia de voz.
- `model_registry.json`: Configurações de qual modelo LLM usar para cada tarefa.

### 🧪 TESTES/ (Validação e Debug)
- `testar_fala_jarvis.py`: Validação isolada de todos os motores de TTS.
- `teste_fiis.py`: Debug da pipeline de extração de dados financeiros.
- `teste_global.py`: Teste de integração de múltiplos sistemas.
- `teste_ias.py`: Validação de chamadas ao Ollama e Moondream.
- `tmp_teste_cascata.py`: Experimento de memória em cascata histórica.

---

## ⚙️ Fluxo de Processamento de Comando

1. **Captura**: `ear/recorder.py` detecta áudio -> `ear/wake_word.py` valida o gatilho.
2. **Transcrição**: `ear/transcriber.py` usa Whisper para converter em texto.
3. **Roteamento**: `brain/core/router.py` analisa o texto e define a categoria (Ex: HARDWARE).
4. **Execução**:
    - Se **Hardware**: `hardware_module.py` lê sensores.
    - Se **Conversa**: `brain/core/conversation.py` gera resposta com contexto da `memory_long.py`.
5. **Feedback**:
    - `voice_manager.py` gera o áudio.
    - `interface_server.py` envia via WebSocket a cor e o padrão de animação para o `app.js`.

---

## 🌡️ Sistema Sentinela
O sistema monitora constantemente os sensores térmicos. Se a CPU ou GPU ultrapassar 85°C, o Jarvis interrompe as atividades secundárias, muda a cor da interface para vermelho e emite um alerta vocal prioridade 0.

---
*Documentação gerada automaticamente para o projeto Meu-agente-IA-main.*
