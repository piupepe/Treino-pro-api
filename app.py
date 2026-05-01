#!/usr/bin/env python3
"""
TREINO PRO - API Server com Webhook
Recebe dados do app, armazena, e envia para agente Claude
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
from anthropic import Anthropic
import uuid
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Pegar API Key
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

if not ANTHROPIC_API_KEY:
    print("⚠️ AVISO: ANTHROPIC_API_KEY não configurada!")
else:
    print("✅ ANTHROPIC_API_KEY carregada com sucesso!")

app = Flask(__name__)
CORS(app)

# Inicializar cliente Anthropic
try:
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    print("✅ Cliente Anthropic inicializado!")
except Exception as e:
    print(f"❌ Erro ao inicializar Anthropic: {e}")
    client = None

# Armazenamento em memória (em produção, usar DB)
DATA_STORAGE = {
    "sessions": [],
    "analysis_history": [],
    "user_profile": {
        "age": 43,
        "experience": "4+ anos",
        "weight": 83,
        "situation": "Plantões",
        "goal": "Hipertrofia"
    }
}

# Agente conversa histórico
AGENT_CONVERSATION = []

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "✅ API rodando!",
        "timestamp": datetime.now().isoformat(),
        "sessions_count": len(DATA_STORAGE["sessions"]),
        "analysis_count": len(DATA_STORAGE["analysis_history"]),
        "api_key_configured": bool(ANTHROPIC_API_KEY)
    })

# ============================================================================
# WEBHOOK: Receber dados do app
# ============================================================================

@app.route('/webhook/session', methods=['POST'])
def receive_session():
    """
    Recebe dados de treino do app
    
    POST /webhook/session
    {
        "session_id": "uuid",
        "date": "22/01/2025",
        "workout": "UPPER A",
        "exercises": [...],
        "energy": 8,
        "sleep": 7.5,
        "notes": "..."
    }
    """
    try:
        data = request.json
        
        # Validar dados
        if not data or 'session_id' not in data:
            return jsonify({"error": "Missing session_id"}), 400
        
        # Adicionar timestamp
        data['received_at'] = datetime.now().isoformat()
        data['status'] = 'received'
        
        # Armazenar sessão
        DATA_STORAGE["sessions"].append(data)
        
        # Trigger análise automática
        analysis = analyze_session_async(data)
        
        return jsonify({
            "status": "✅ Sessão recebida!",
            "session_id": data['session_id'],
            "analysis_available": True,
            "analysis": analysis
        }), 202
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================================
# ANÁLISE AUTÔNOMA
# ============================================================================

def analyze_session_async(session_data):
    """
    Analisa sessão com Claude imediatamente
    Roda em paralelo (async)
    """
    try:
        if not client:
            return {"error": "Claude client não inicializado"}
        
        # Preparar contexto
        summary = prepare_analysis_context(session_data)
        
        # Chamar agente Claude
        analysis = run_autonomous_agent(summary)
        
        # Armazenar análise
        analysis_record = {
            "id": str(uuid.uuid4()),
            "session_id": session_data.get('session_id'),
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "status": "completed"
        }
        DATA_STORAGE["analysis_history"].append(analysis_record)
        
        return analysis
        
    except Exception as e:
        return {"error": f"Análise failed: {str(e)}"}

def prepare_analysis_context(session_data):
    """Prepara contexto para análise"""
    
    # Últimas 7 sessões
    recent_sessions = DATA_STORAGE["sessions"][-7:]
    
    # Estatísticas
    total_sessions = len(DATA_STORAGE["sessions"])
    avg_energy = sum(s.get('energy', 5) for s in recent_sessions) / len(recent_sessions) if recent_sessions else 0
    avg_sleep = sum(s.get('sleep', 7) for s in recent_sessions) / len(recent_sessions) if recent_sessions else 0
    
    # Análise de progressão
    progression = analyze_progression(DATA_STORAGE["sessions"])
    
    return f"""
📊 NOVA SESSÃO RECEBIDA - Análise Automática

SESSION DATA:
└─ Data: {session_data.get('date')}
└─ Treino: {session_data.get('workout')}
└─ Energia: {session_data.get('energy')}/10
└─ Sono: {session_data.get('sleep')}h
└─ Notas: {session_data.get('notes', 'N/A')}

CONTEXTO (Últimos 7 dias):
├─ Total de sessões: {total_sessions}
├─ Sessões recentes: {len(recent_sessions)}
├─ Energia média: {avg_energy:.1f}/10
├─ Sono médio: {avg_sleep:.1f}h

PROGRESSO (por exercício):
{progression}

TAREFA:
1. Analise a sessão de hoje
2. Compare com histórico
3. Identifique anomalias/problemas
4. Dê recomendações
5. Sinalize alertas se houver
6. Sugira próximos passos

Faça análise COMPLETA e AUTÔNOMA!
"""

def analyze_progression(sessions):
    """Analisa progressão de exercícios"""
    
    exercise_stats = {}
    for session in sessions[-14:]:  # Últimas 2 semanas
        for exercise in session.get('exercises', []):
            name = exercise.get('name', '')
            if name not in exercise_stats:
                exercise_stats[name] = []
            exercise_stats[name].append({
                'date': session.get('date'),
                'weight': exercise.get('weight'),
                'reps': exercise.get('sets', [])
            })
    
    result = ""
    for exercise, records in list(exercise_stats.items())[:5]:  # Top 5
        if len(records) >= 2:
            first = records[0]
            last = records[-1]
            weight_diff = last['weight'] - first['weight']
            badge = "↑" if weight_diff > 0 else "↓" if weight_diff < 0 else "="
            result += f"\n  • {exercise}: {first['weight']}kg → {last['weight']}kg ({badge})"
    
    return result if result else "  • Dados insuficientes"

# ============================================================================
# AGENTE CLAUDE AUTÔNOMO
# ============================================================================

def run_autonomous_agent(analysis_context):
    """
    Agente autônomo que analisa dados
    Roda continuamente no console
    """
    
    if not client:
        return "❌ Claude client não disponível"
    
    system_prompt = """Você é um AGENTE AUTÔNOMO de Performance especializado em:
- Fisiologia do exercício (Schoenfeld, Zourdos, Israetel, etc)
- Análise MEV/MRV e volume ótimal
- Frequência muscular e recuperação
- Correlação sono/performance/ganho

CONTEXTO DO CLIENTE:
- 43 anos, 4+ anos de experiência
- Peso: 83kg, Objetivo: Hipertrofia
- Situação: Plantões (recuperação irregular)
- Protocolo: Upper/Lower 2x/semana, 116 séries

QUANDO RECEBER DADOS:

1️⃣ ANÁLISE IMEDIATA:
   ├─ Valide qualidade da sessão
   ├─ Compare com histórico
   ├─ Calcule métricas (volume, frequência)
   └─ Identifique anomalias

2️⃣ ALERTAS (Se houver problemas):
   ├─ ⚠️ Sono muito baixo (< 6h)
   ├─ ⚠️ Energia muito baixa (< 4/10)
   ├─ ⚠️ Queda de performance (-10%+)
   ├─ ⚠️ Desequilíbrio volume (>1.5:1)
   └─ 🚨 Risco de lesão (ROM excessivo, etc)

3️⃣ RECOMENDAÇÕES ACIONÁVEIS:
   ├─ Progressão linear (próximos pesos)
   ├─ Ajustes de volume
   ├─ Recuperação (sono, nutrição)
   ├─ Quando fazer deload
   └─ Mudanças de exercício

4️⃣ ESTUDOS APLICADOS:
   └─ Sempre referencie 1-2 papers relevantes

FORMATO DE RESPOSTA:
─────────────────────
📊 RESUMO DA SESSÃO
├─ Treino: [nome]
├─ Volume: [séries x reps]
├─ Comparação: [vs última vez]
└─ Status: ✅ OK / ⚠️ ATENÇÃO / 🚨 CRÍTICO

✅ PONTOS POSITIVOS
├─ [ponto 1]
├─ [ponto 2]
└─ [ponto 3]

⚠️ ALERTAS (Se houver)
├─ [alerta 1]
├─ [alerta 2]
└─ [ação recomendada]

🎯 RECOMENDAÇÕES
├─ Progressão: [próximos pesos/reps]
├─ Volume: [ajustes necessários]
├─ Recuperação: [sono/nutrição/deload]
└─ Próximo treino: [o que fazer]

📚 BASE CIENTÍFICA
└─ [Estudo et al. Ano]: [aplicação]

⏰ MONITORAMENTO
└─ Próxima check-in: [quando]
─────────────────────
"""
    
    try:
        # Adicionar contexto ao histórico
        AGENT_CONVERSATION.append({
            "role": "user",
            "content": analysis_context
        })
        
        # Chamar Claude com contexto completo
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            system=system_prompt,
            messages=AGENT_CONVERSATION
        )
        
        assistant_message = response.content[0].text
        
        # Armazenar resposta no histórico
        AGENT_CONVERSATION.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        return assistant_message
    
    except Exception as e:
        return f"❌ Erro na análise: {str(e)}"

# ============================================================================
# ENDPOINTS ADICIONAIS
# ============================================================================

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Retorna todas as sessões"""
    return jsonify({
        "total": len(DATA_STORAGE["sessions"]),
        "sessions": DATA_STORAGE["sessions"][-10:]  # Últimas 10
    })

@app.route('/api/analysis', methods=['GET'])
def get_analysis():
    """Retorna análises recentes"""
    return jsonify({
        "total": len(DATA_STORAGE["analysis_history"]),
        "analyses": DATA_STORAGE["analysis_history"][-5:]  # Últimas 5
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Retorna estatísticas gerais"""
    sessions = DATA_STORAGE["sessions"]
    if not sessions:
        return jsonify({"error": "Nenhuma sessão registrada"}), 404
    
    recent = sessions[-7:]
    avg_energy = sum(s.get('energy', 5) for s in recent) / len(recent) if recent else 0
    avg_sleep = sum(s.get('sleep', 7) for s in recent) / len(recent) if recent else 0
    
    return jsonify({
        "total_sessions": len(sessions),
        "last_session": sessions[-1].get('date') if sessions else None,
        "avg_energy_7d": round(avg_energy, 1),
        "avg_sleep_7d": round(avg_sleep, 1),
        "analysis_count": len(DATA_STORAGE["analysis_history"]),
        "last_analysis": DATA_STORAGE["analysis_history"][-1].get('timestamp') if DATA_STORAGE["analysis_history"] else None
    })

@app.route('/api/latest-analysis', methods=['GET'])
def get_latest_analysis():
    """Retorna última análise completa"""
    if not DATA_STORAGE["analysis_history"]:
        return jsonify({"error": "Nenhuma análise disponível"}), 404
    
    return jsonify(DATA_STORAGE["analysis_history"][-1])

# ============================================================================
# TESTE LOCAL
# ============================================================================

@app.route('/test/simulate-session', methods=['POST'])
def test_simulate():
    """
    Simula envio de sessão (para teste)
    POST com JSON de sessão
    """
    test_data = {
        "session_id": str(uuid.uuid4()),
        "date": datetime.now().strftime("%d/%m/%Y"),
        "time": datetime.now().strftime("%H:%M"),
        "workout": "UPPER A",
        "exercises": [
            {
                "name": "Supino Reto",
                "planned": "4x6-8",
                "weight": 45,
                "sets": [8, 7, 6, 6]
            },
            {
                "name": "Remada Curvada",
                "planned": "4x6-8",
                "weight": 40,
                "sets": [8, 8, 7, 6]
            }
        ],
        "energy": 8,
        "sleep": 7.5,
        "notes": "Treino sólido, ótima bomba"
    }
    
    return receive_session_data(test_data)

def receive_session_data(data):
    """Helper para processar sessão"""
    data['received_at'] = datetime.now().isoformat()
    data['status'] = 'received'
    
    DATA_STORAGE["sessions"].append(data)
    analysis = analyze_session_async(data)
    
    return jsonify({
        "status": "✅ Sessão processada!",
        "session_id": data['session_id'],
        "analysis": analysis
    }), 200

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║        🎯 TREINO PRO - API SERVER COM WEBHOOK           ║
    ╚══════════════════════════════════════════════════════════╝
    
    ✅ API KEY: Configurada
    📍 Server rodando em: http://0.0.0.0:{}
    
    ENDPOINTS DISPONÍVEIS:
    
    ✅ Health Check:
       GET /health
    
    🎯 Webhook (Receber dados):
       POST /webhook/session
       Body: JSON da sessão
    
    📊 Dados:
       GET /api/sessions
       GET /api/analysis
       GET /api/stats
       GET /api/latest-analysis
    
    🧪 Teste:
       POST /test/simulate-session
    
    ═════════════════════════════════════════════════════════
    """.format(port))
    
    app.run(host='0.0.0.0', port=port, debug=False)
