import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from supabase import create_client, Client

# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = Flask(__name__)
CORS(app)

# ANTHROPIC
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# SUPABASE - NOVO PROJETO
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bldwvlnorigxqdvdqfsu.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsZHd2bG5vcmlneHFkdmRxZnN1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NDcwMTMsImV4cCI6MjA5MzUyMzAxM30.zKIiRWpWNlD08ugDqqOoaiUuMTnvEmzQFbSSN1z93aQ")

# Conectar ao Supabase
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase conectado")
except Exception as e:
    print(f"❌ Erro ao conectar Supabase: {e}")
    supabase = None

# ============================================================
# HEALTH CHECK
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    """Verifica status da API"""
    supabase_ok = False
    try:
        response = supabase.table('sessions').select('id').limit(1).execute()
        supabase_ok = True
    except Exception as e:
        print(f"❌ Supabase health check falhou: {e}")
        supabase_ok = False
    
    return jsonify({
        "status": "ok",
        "api_key_set": bool(ANTHROPIC_API_KEY),
        "claude_available": True,
        "supabase_connected": supabase_ok,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    }), 200

# ============================================================
# PROXY PARA SUPABASE - SESSIONS
# ============================================================

@app.route('/api/sessions', methods=['GET', 'POST'])
def proxy_sessions():
    """Proxy para operações na tabela sessions"""
    try:
        if not supabase:
            return jsonify({"error": "Supabase not connected"}), 500
        
        if request.method == 'POST':
            # INSERT
            data = request.get_json()
            result = supabase.table('sessions').insert(data).execute()
            return jsonify(result.data), 201
        else:
            # SELECT com filtros opcionais
            query = supabase.table('sessions').select('*')
            
            # Aplicar order se informado
            order_by = request.args.get('order_by', 'created_at')
            desc = request.args.get('desc', 'true').lower() == 'true'
            query = query.order(order_by, desc=desc)
            
            # Aplicar limit
            limit = int(request.args.get('limit', 10))
            query = query.limit(limit)
            
            result = query.execute()
            return jsonify(result.data), 200
    
    except Exception as e:
        print(f"❌ Erro em proxy_sessions: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# PROXY PARA SUPABASE - ANALYSES
# ============================================================

@app.route('/api/analyses', methods=['GET', 'POST'])
def proxy_analyses():
    """Proxy para operações na tabela analyses"""
    try:
        if not supabase:
            return jsonify({"error": "Supabase not connected"}), 500
        
        if request.method == 'POST':
            # INSERT
            data = request.get_json()
            result = supabase.table('analyses').insert(data).execute()
            return jsonify(result.data), 201
        else:
            # SELECT com filtros
            query = supabase.table('analyses').select('*')
            
            # Aplicar order
            order_by = request.args.get('order_by', 'created_at')
            desc = request.args.get('desc', 'true').lower() == 'true'
            query = query.order(order_by, desc=desc)
            
            # Aplicar limit
            limit = int(request.args.get('limit', 10))
            query = query.limit(limit)
            
            result = query.execute()
            return jsonify(result.data), 200
    
    except Exception as e:
        print(f"❌ Erro em proxy_analyses: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# WEBHOOK PARA RECEBER TREINO E CHAMAR AGENTE
# ============================================================

@app.route('/webhook/session', methods=['POST'])
def webhook_session():
    """
    Recebe dados de uma sessão de treino
    Chama o agente Claude para analisar
    Salva a análise no Supabase
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        session_id = data.get('session_id')
        date = data.get('date')
        workout = data.get('workout')
        exercises_str = data.get('exercises', '[]')
        energy = data.get('energy', 5)
        sleep = data.get('sleep', 7)
        notes = data.get('notes', '')
        
        print(f"\n📥 Recebido treino: {workout} (session_id: {session_id})")
        
        # ============================================================
        # 1. FORMATAR PROMPT PARA O AGENTE
        # ============================================================
        
        exercises = exercises_str
        if isinstance(exercises_str, str):
            try:
                exercises = json.loads(exercises_str)
            except:
                exercises = exercises_str
        
        exercises_text = ""
        if isinstance(exercises, list):
            for ex in exercises:
                if isinstance(ex, dict):
                    name = ex.get('name', 'Desconhecido')
                    weight = ex.get('weight', '?')
                    sets = ex.get('sets', [])
                    sets_str = " | ".join([str(s) for s in sets]) if sets else "?"
                    exercises_text += f"\n  • {name}: {weight}kg - {sets_str} reps"
                else:
                    exercises_text += f"\n  • {ex}"
        else:
            exercises_text = str(exercises)
        
        prompt = f"""
Você é um personal trainer IA especializado em programas de hipertrofia.

Um cliente registrou o seguinte treino:

**TREINO:** {workout}
**DATA:** {date}
**ENERGIA:** {energy}/10
**SONO:** {sleep}h
**OBSERVAÇÕES:** {notes if notes else "Nenhuma"}

**EXERCÍCIOS EXECUTADOS:**
{exercises_text}

Por favor, fornça uma análise detalhada e feedback personalizado sobre este treino, incluindo:

1. **Avaliação Geral**: Como foi o treino?
2. **Volume de Treino**: Quantas séries e reps foram feitas?
3. **Intensidade**: Comparado com o plano, como foi?
4. **Recuperação**: Considerando energia ({energy}/10) e sono ({sleep}h), está adequado?
5. **Recomendações**: O que melhorar no próximo treino?
6. **Motivação**: Uma mensagem motivacional

Seja direto, objetivo e prático. Use linguagem coloquial.
"""
        
        print(f"🤖 Chamando agente Claude...")
        
        # ============================================================
        # 2. CHAMAR AGENTE CLAUDE
        # ============================================================
        
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        analysis = response.content[0].text
        print(f"✅ Análise gerada: {len(analysis)} caracteres")
        
        # ============================================================
        # 3. SALVAR NO SUPABASE
        # ============================================================
        
        if not supabase:
            print("⚠️ Supabase não conectado")
            return jsonify({
                "status": "ok",
                "analysis": analysis,
                "warning": "Supabase not connected"
            }), 200
        
        try:
            analysis_data = {
                "session_id": session_id,
                "date": date,
                "workout": workout,
                "analysis": analysis,
                "model": "claude-sonnet-4-6"
            }
            
            print(f"💾 Salvando análise no Supabase...")
            result = supabase.table('analyses').insert(analysis_data).execute()
            print(f"✅ Análise salva no Supabase")
            
            return jsonify({
                "status": "ok",
                "session_id": session_id,
                "analysis_saved": True,
                "message": "Análise gerada e salva com sucesso"
            }), 200
            
        except Exception as e:
            print(f"❌ Erro ao salvar no Supabase: {e}")
            return jsonify({
                "status": "ok",
                "session_id": session_id,
                "analysis": analysis,
                "warning": f"Análise gerada mas não foi salva: {str(e)}"
            }), 200
    
    except Exception as e:
        print(f"❌ Erro ao processar webhook: {e}")
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"\n🚀 Iniciando Treino Pro API na porta {port}")
    print(f"✅ Anthropic API Key: {bool(ANTHROPIC_API_KEY)}")
    print(f"🔌 Supabase URL: {SUPABASE_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)
