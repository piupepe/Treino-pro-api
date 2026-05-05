import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
from supabase import create_client, Client
from datetime import datetime

# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = Flask(__name__)
CORS(app)

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bldwvlnorigxqdvdqfsu.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsZHd2bG5vcmlneHFkdmRxZnN1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NDcwMTMsImV4cCI6MjA5MzUyMzAxM30.zKIiRWpWNlD08ugDqqOoaiUuMTnvEmzQFbSSN1z93aQ")

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
        response = supabase.table('users').select('id').limit(1).execute()
        supabase_ok = True
    except Exception as e:
        print(f"❌ Supabase health check falhou: {e}")
        supabase_ok = False
    
    return jsonify({
        "status": "ok",
        "api_key_set": bool(ANTHROPIC_API_KEY),
        "claude_available": True,
        "supabase_connected": supabase_ok,
        "timestamp": datetime.utcnow().isoformat()
    }), 200

# ============================================================
# AUTENTICAÇÃO - ENDPOINTS
# ============================================================

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """Registrar novo usuário"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        
        if not email or not password or not name:
            return jsonify({"error": "email, password, name obrigatórios"}), 400
        
        # Usar Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            # Criar perfil na tabela users
            user_data = {
                "id": auth_response.user.id,
                "email": email,
                "name": name
            }
            
            result = supabase.table('users').insert(user_data).execute()
            
            return jsonify({
                "status": "success",
                "message": "Usuário criado. Acesse a anamnese.",
                "user_id": auth_response.user.id,
                "email": email
            }), 201
        else:
            return jsonify({"error": "Erro ao criar usuário"}), 400
            
    except Exception as e:
        print(f"❌ Erro signup: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Fazer login"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"error": "email e password obrigatórios"}), 400
        
        # Usar Supabase Auth
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            # Buscar dados do usuário
            user_response = supabase.table('users').select('*').eq('id', auth_response.user.id).execute()
            user_data = user_response.data[0] if user_response.data else None
            
            return jsonify({
                "status": "success",
                "user_id": auth_response.user.id,
                "email": email,
                "has_anamnese": user_data and user_data.get('age') is not None,
                "access_token": auth_response.session.access_token
            }), 200
        else:
            return jsonify({"error": "Email ou senha inválidos"}), 401
            
    except Exception as e:
        print(f"❌ Erro login: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# ANAMNESE - ENDPOINTS
# ============================================================

@app.route('/api/anamnese/save', methods=['POST'])
def save_anamnese():
    """Salvar respostas da anamnese"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id obrigatório"}), 400
        
        # Atualizar perfil do usuário com dados da anamnese
        anamnese_data = {
            "age": data.get('age'),
            "weight": data.get('weight'),
            "height": data.get('height'),
            "experience_level": data.get('experience_level'),
            "main_goal": data.get('main_goal'),
            "available_days": data.get('available_days'),
            "session_duration": data.get('session_duration'),
            "equipment": data.get('equipment'),
            "injuries": data.get('injuries'),
            "training_history": data.get('training_history'),
            "preferences": data.get('preferences')
        }
        
        result = supabase.table('users').update(anamnese_data).eq('id', user_id).execute()
        
        return jsonify({
            "status": "success",
            "message": "Anamnese salva com sucesso!",
            "user_id": user_id
        }), 200
        
    except Exception as e:
        print(f"❌ Erro save_anamnese: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/anamnese/get/<user_id>', methods=['GET'])
def get_anamnese(user_id):
    """Obter dados da anamnese"""
    try:
        result = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if result.data:
            user = result.data[0]
            return jsonify(user), 200
        else:
            return jsonify({"error": "Usuário não encontrado"}), 404
            
    except Exception as e:
        print(f"❌ Erro get_anamnese: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# TREINOS - ENDPOINTS
# ============================================================

@app.route('/api/sessions', methods=['GET', 'POST'])
def sessions():
    """GET: listar treinos | POST: salvar novo"""
    try:
        if request.method == 'POST':
            data = request.get_json()
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({"error": "user_id obrigatório"}), 400
            
            session_data = {
                "user_id": user_id,
                "session_id": data.get('session_id'),
                "template_id": data.get('template_id'),
                "date": data.get('date'),
                "time": data.get('time'),
                "workout": data.get('workout'),
                "exercises": data.get('exercises'),
                "energy": data.get('energy'),
                "sleep": data.get('sleep'),
                "notes": data.get('notes')
            }
            
            result = supabase.table('sessions').insert(session_data).execute()
            return jsonify({"status": "success", "data": result.data}), 201
        
        else:  # GET
            user_id = request.args.get('user_id')
            
            if not user_id:
                return jsonify({"error": "user_id obrigatório"}), 400
            
            query = supabase.table('sessions').select('*').eq('user_id', user_id)
            
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
        print(f"❌ Erro sessions: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# ANÁLISES - ENDPOINTS
# ============================================================

@app.route('/api/analyses', methods=['GET', 'POST'])
def analyses():
    """GET: listar análises | POST: salvar nova"""
    try:
        if request.method == 'POST':
            data = request.get_json()
            user_id = data.get('user_id')
            
            if not user_id:
                return jsonify({"error": "user_id obrigatório"}), 400
            
            analysis_data = {
                "user_id": user_id,
                "session_id": data.get('session_id'),
                "date": data.get('date'),
                "workout": data.get('workout'),
                "analysis": data.get('analysis'),
                "model": data.get('model', 'claude-sonnet-4-6'),
                "tokens_used": data.get('tokens_used')
            }
            
            result = supabase.table('analyses').insert(analysis_data).execute()
            return jsonify({"status": "success", "data": result.data}), 201
        
        else:  # GET
            user_id = request.args.get('user_id')
            
            if not user_id:
                return jsonify({"error": "user_id obrigatório"}), 400
            
            query = supabase.table('analyses').select('*').eq('user_id', user_id)
            
            order_by = request.args.get('order_by', 'created_at')
            desc = request.args.get('desc', 'true').lower() == 'true'
            query = query.order(order_by, desc=desc)
            
            limit = int(request.args.get('limit', 10))
            query = query.limit(limit)
            
            result = query.execute()
            return jsonify(result.data), 200
    
    except Exception as e:
        print(f"❌ Erro analyses: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# WEBHOOK - AGENTE IA (ANALISAR TREINO)
# ============================================================

@app.route('/webhook/session', methods=['POST'])
def webhook_session():
    """
    Recebe dados de uma sessão
    Chama agente Claude para analisar
    Salva análise no Supabase
    """
    try:
        data = request.get_json()
        
        user_id = data.get('user_id')
        session_id = data.get('session_id')
        date = data.get('date')
        workout = data.get('workout')
        exercises_str = data.get('exercises', '[]')
        energy = data.get('energy', 5)
        sleep = data.get('sleep', 7)
        notes = data.get('notes', '')
        
        if not user_id or not session_id:
            return jsonify({"error": "user_id e session_id obrigatórios"}), 400
        
        print(f"\n📥 Recebido treino: {workout} (user: {user_id})")
        
        # ============================================================
        # 1. BUSCAR DADOS DO USUÁRIO (ANAMNESE)
        # ============================================================
        
        user_response = supabase.table('users').select('*').eq('id', user_id).execute()
        user_data = user_response.data[0] if user_response.data else {}
        
        print(f"👤 Usuário: {user_data.get('name', 'Desconhecido')}")
        
        # ============================================================
        # 2. FORMATAR EXERCÍCIOS
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
        
        # ============================================================
        # 3. CONSTRUIR PROMPT MELHORADO COM CONTEXTO
        # ============================================================
        
        prompt = f"""
Você é um personal trainer IA especializado em hipertrofia, baseado em ciência
(Schoenfeld, Israetel, Zourdos, Helms).

CONTEXTO DO USUÁRIO:
- Nome: {user_data.get('name', 'N/A')}
- Idade: {user_data.get('age', 'N/A')} anos
- Peso: {user_data.get('weight', 'N/A')} kg
- Altura: {user_data.get('height', 'N/A')} cm
- Experiência: {user_data.get('experience_level', 'N/A')}
- Objetivo: {user_data.get('main_goal', 'N/A')}
- Dias disponíveis: {user_data.get('available_days', 'N/A')}/semana
- Duração: {user_data.get('session_duration', 'N/A')} min
- Equipamentos: {user_data.get('equipment', 'N/A')}
- Lesões/Limitações: {user_data.get('injuries', 'Nenhuma')}

TREINO REALIZADO:
- Data: {date}
- Treino: {workout}
- Energia: {energy}/10
- Sono: {sleep}h
- Notas: {notes if notes else 'Nenhuma'}

EXERCÍCIOS EXECUTADOS:{exercises_text}

ANÁLISE DETALHADA NECESSÁRIA:

1. **Avaliação Geral & RPE**
   - Como foi o treino comparado ao esperado?
   - Estime o RPE (Rate of Perceived Exertion) = taxa de esforço percebido
   - Há sinais de fadiga excessiva ou fraco estímulo?

2. **Volume & Intensidade**
   - Total de séries e reps
   - Está na faixa MEV (Minimum Effective Volume)?
   - Está próximo de MRV (Maximum Recoverable Volume)?
   - Análise por grupo muscular

3. **Padrão de Execução**
   - Quais exercícios tiveram boa performance?
   - Quais mostraram fadiga/queda de reps?
   - Há desequilíbrios entre agonistas/antagonistas?

4. **Recuperação & Contexto**
   - Energia ({energy}/10) + Sono ({sleep}h) = capacidade de recuperação?
   - Sinais de overtraining ou subtreinamento?
   - Recomende ajustes baseado no contexto

5. **Progressão Prescrita**
   - Se completou bem: próxima carga/volume
   - Se ficou pesado: como ajustar
   - Próximo treino: que foco ter?

6. **Recomendações Específicas**
   - Forma técnica (se possível detectar)
   - Tempo de descanso entre séries
   - Necessidade de deload?
   - Inserção de novos exercícios?

7. **Avisos & Prevenção**
   - Sinais de lesão em potencial?
   - Desequilíbrios musculares?
   - Recomendações de mobilidade?

FORMATO:
- Use tabelas, emojis, números para clareza
- Conclusões ANTES de explicações longas
- Sempre feche com PRÓXIMAS AÇÕES concretas
- Seja direto e prescritivo
- Considere o contexto de vida do usuário (sono, energia, experiência)

Análise completa agora:
"""
        
        print(f"🤖 Chamando agente Claude...")
        
        # ============================================================
        # 4. CHAMAR AGENTE CLAUDE
        # ============================================================
        
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        analysis = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        
        print(f"✅ Análise gerada: {tokens_used} tokens")
        
        # ============================================================
        # 5. SALVAR NO SUPABASE
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
                "user_id": user_id,
                "session_id": session_id,
                "date": date,
                "workout": workout,
                "analysis": analysis,
                "model": "claude-sonnet-4-6",
                "tokens_used": tokens_used
            }
            
            print(f"💾 Salvando análise no Supabase...")
            result = supabase.table('analyses').insert(analysis_data).execute()
            print(f"✅ Análise salva")
            
            return jsonify({
                "status": "ok",
                "session_id": session_id,
                "analysis_saved": True,
                "tokens_used": tokens_used,
                "message": "Análise gerada e salva com sucesso"
            }), 200
            
        except Exception as e:
            print(f"❌ Erro ao salvar no Supabase: {e}")
            return jsonify({
                "status": "ok",
                "session_id": session_id,
                "analysis": analysis,
                "tokens_used": tokens_used,
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
    print(f"\n🚀 Iniciando Treino Pro API Premium na porta {port}")
    print(f"✅ Anthropic API Key: {bool(ANTHROPIC_API_KEY)}")
    print(f"🔌 Supabase URL: {SUPABASE_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)
