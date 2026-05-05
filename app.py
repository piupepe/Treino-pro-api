#!/usr/bin/env python3
# ============================================================
# TREINO PRO - BACKEND COMPLETO
# Autenticação + Anamnese + Gerador de Treinos com QA
# ============================================================

import os
import json
import uuid
import hashlib
import secrets
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import anthropic
from supabase import create_client, Client
from datetime import datetime

# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = Flask(__name__)

# ⚠️ CORS - HABILITADO EXPLICITAMENTE
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    }
})

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
@cross_origin()
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

@app.route('/api/auth/signup', methods=['POST', 'OPTIONS'])
@cross_origin()
def signup():
    """Registrar novo usuário - SEM usar Supabase Auth (evita rate limit)"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        if not email or not password or not name:
            return jsonify({"error": "email, password, name obrigatórios"}), 400
        
        if len(password) < 6:
            return jsonify({"error": "Senha deve ter mínimo 6 caracteres"}), 400
        
        if len(email) < 5 or '@' not in email:
            return jsonify({"error": "Email inválido"}), 400
        
        # Verificar se email já existe
        try:
            existing = supabase.table('users').select('id').eq('email', email).execute()
            if existing.data and len(existing.data) > 0:
                return jsonify({"error": "📧 Este email já está cadastrado"}), 409
        except Exception as e:
            print(f"⚠️ Erro ao verificar email: {e}")
        
        # Criar novo usuário
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        user_data = {
            "id": user_id,
            "email": email,
            "name": name,
            "password_hash": password_hash,
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            result = supabase.table('users').insert(user_data).execute()
            
            print(f"✅ Usuário criado: {email}")
            
            return jsonify({
                "status": "success",
                "message": "Conta criada! Prosseguindo para anamnese.",
                "user_id": user_id,
                "email": email
            }), 201
            
        except Exception as db_error:
            print(f"❌ Erro ao inserir usuario: {db_error}")
            error_str = str(db_error)
            
            if "row-level security" in error_str.lower() or "rls" in error_str.lower():
                return jsonify({"error": "Erro de permissão. Contate o admin."}), 403
            elif "unique" in error_str.lower():
                return jsonify({"error": "📧 Este email já está cadastrado"}), 409
            else:
                return jsonify({"error": "Erro ao criar conta: " + error_str}), 500
            
    except Exception as e:
        print(f"❌ Erro signup geral: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
@cross_origin()
def login():
    """Fazer login - verificando hash de senha"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({"error": "email e password obrigatórios"}), 400
        
        # Buscar usuário
        try:
            result = supabase.table('users').select('*').eq('email', email).execute()
            
            if not result.data or len(result.data) == 0:
                return jsonify({"error": "❌ Email ou senha incorretos"}), 401
            
            user = result.data[0]
            user_id = user.get('id')
            password_hash_stored = user.get('password_hash')
            
            # Verificar senha
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if password_hash != password_hash_stored:
                return jsonify({"error": "❌ Email ou senha incorretos"}), 401
            
            # Gerar token
            access_token = secrets.token_urlsafe(32)
            
            # Verificar se tem anamnese
            has_anamnese = (
                user.get('age') is not None and 
                user.get('experience_level') is not None
            )
            
            print(f"✅ Login bem-sucedido: {email}")
            
            return jsonify({
                "status": "success",
                "user_id": user_id,
                "email": email,
                "name": user.get('name'),
                "has_anamnese": has_anamnese,
                "access_token": access_token
            }), 200
            
        except Exception as db_error:
            print(f"❌ Erro ao buscar usuário: {db_error}")
            return jsonify({"error": "Erro ao processar login"}), 500
            
    except Exception as e:
        print(f"❌ Erro login geral: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# ANAMNESE - ENDPOINTS
# ============================================================

@app.route('/api/anamnese/save', methods=['POST', 'OPTIONS'])
@cross_origin()
def save_anamnese():
    """Salvar respostas da anamnese"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id obrigatório"}), 400
        
        # Dados da anamnese
        anamnese_data = {
            "age": data.get('age'),
            "gender": data.get('gender'),
            "weight": data.get('weight'),
            "height": data.get('height'),
            "body_fat": data.get('body_fat'),
            "experience_level": data.get('experience_level'),
            "strongest_phase": data.get('strongest_phase'),
            "training_history": data.get('training_history'),
            "main_goal": data.get('main_goal'),
            "muscle_gain_goal": data.get('muscle_gain_goal'),
            "fat_loss_goal": data.get('fat_loss_goal'),
            "available_days": data.get('available_days'),
            "session_duration": data.get('session_duration'),
            "best_training_time": data.get('best_training_time'),
            "equipment": data.get('equipment'),
            "injuries": data.get('injuries', 'Nenhuma'),
            "injury_history": data.get('injury_history', ''),
            "medications": data.get('medications', 'Nenhuma'),
            "sleep_hours": data.get('sleep_hours'),
            "sleep_quality": data.get('sleep_quality'),
            "diet": data.get('diet'),
            "supplements": data.get('supplements'),
            "stress_level": data.get('stress_level'),
            "cardio_frequency": data.get('cardio_frequency', 'nao'),
            "split_preference": data.get('split_preference'),
            "observations": data.get('observations', '')
        }
        
        result = supabase.table('users').update(anamnese_data).eq('id', user_id).execute()
        
        print(f"✅ Anamnese salva: {user_id}")
        
        return jsonify({
            "status": "success",
            "message": "Anamnese salva com sucesso!",
            "user_id": user_id
        }), 200
        
    except Exception as e:
        print(f"❌ Erro save_anamnese: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/anamnese/get/<user_id>', methods=['GET', 'OPTIONS'])
@cross_origin()
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
# SESSÕES - ENDPOINTS
# ============================================================

@app.route('/api/sessions', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin()
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
            
            order_by = request.args.get('order_by', 'created_at')
            desc = request.args.get('desc', 'true').lower() == 'true'
            query = query.order(order_by, desc=desc)
            
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

@app.route('/api/analyses', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin()
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
# PROMPTS PARA GERAÇÃO E VALIDAÇÃO DE TREINOS
# ============================================================

def get_prompt_gerar_treino(anamnese: dict, split: str, focus: str, tentativa: int = 1) -> str:
    """Gera prompt para Claude criar treino baseado em anamnese"""
    
    correcoes_prev = ""
    if tentativa > 1:
        correcoes_prev = f"\n⚠️ TENTATIVA {tentativa}/3 - Aplicar correções da validação anterior se houver.\n"
    
    prompt = f"""{correcoes_prev}
VOCÊ É UM COACH DE MUSCULAÇÃO ESPECIALIZADO EM HIPERTROFIA
Baseado em: Schoenfeld, Israetel, Zourdos, Helms, Renaissance Periodization

═══════════════════════════════════════════════════════════════
PERFIL COMPLETO DO USUÁRIO
═══════════════════════════════════════════════════════════════

DADOS BIOMÉTRICOS:
  • Nome: {anamnese.get('name', 'N/A')}
  • Idade: {anamnese.get('age', '?')} anos
  • Peso: {anamnese.get('weight', '?')}kg
  • Altura: {anamnese.get('height', '?')}cm
  • Gordura Corporal: {anamnese.get('body_fat', 'desconhecida')}%

EXPERIÊNCIA:
  • Tempo treino: {anamnese.get('experience_level', '?')}
  • Melhor fase: {anamnese.get('strongest_phase', '?')}
  • Histórico: {anamnese.get('training_history', '?')}

OBJETIVOS:
  • Objetivo principal: {anamnese.get('main_goal', '?')}
  • Meta ganho: {anamnese.get('muscle_gain_goal', '?')}kg/12 meses
  • Meta perda: {anamnese.get('fat_loss_goal', 'nenhuma')}kg

DISPONIBILIDADE:
  • Dias/semana: {anamnese.get('available_days', '?')} treinos
  • Duração: {anamnese.get('session_duration', '?')} min/sessão
  • Melhor horário: {anamnese.get('best_training_time', '?')}
  • Split preferido: {anamnese.get('split_preference', 'N/A')}

EQUIPAMENTOS:
  • Local: {anamnese.get('equipment', '?')}

SAÚDE:
  • Lesões atuais: {anamnese.get('injuries', 'Nenhuma')}
  • Histórico: {anamnese.get('injury_history', 'nenhum')}
  • Medicações: {anamnese.get('medications', 'nenhuma')}

RECUPERAÇÃO:
  • Sono: {anamnese.get('sleep_hours', '?')}h/noite
  • Qualidade: {anamnese.get('sleep_quality', '?')}

NUTRIÇÃO:
  • Dieta: {anamnese.get('diet', '?')}
  • Suplementos: {anamnese.get('supplements', '?')}

ESTILO DE VIDA:
  • Estresse: {anamnese.get('stress_level', '?')}
  • Cardio: {anamnese.get('cardio_frequency', 'não especificado')}

OBSERVAÇÕES:
{anamnese.get('observations', 'Nenhuma')}

═══════════════════════════════════════════════════════════════
TAREFA
═══════════════════════════════════════════════════════════════

Gere um programa de {anamnese.get('available_days', 4)} treinos ({split.upper()}) 
com foco em {focus}.

REQUISITOS:
1. SEGURANÇA: Respeite TODAS as lesões, sem exercícios que causem dor
2. PERIODIZAÇÃO: 3 semanas força → 3 hipertrofia → 3 volume → 1 deload
3. VOLUME: Iniciante 10-12 | Intermediário 12-16 | Avançado 15-20 séries/grupo
4. PUSH/PULL: Ratio 1:1.2 MÍNIMO com face pulls obrigatórios
5. ESTRUTURA: Composto pesado → Hipertrofia → Isolado
6. COMPATIBILIDADE: Horário, sono, histórico personalizado

RESPONDA APENAS COM JSON VÁLIDO (sem markdown):

{{
  "split": "{split.upper()}",
  "focus": "{focus}",
  "total_weekly_sets": <número>,
  "periodization": "Linear",
  "periodization_details": "Semana 1-3: força... Semana 4-6: hipertrofia...",
  "notes": "Notas personalizadas",
  "warnings": "Avisos sobre lesões",
  "workouts": [
    {{
      "day": 1,
      "name": "UPPER A",
      "type": "push",
      "estimated_duration_minutes": 60,
      "estimated_total_sets": 18,
      "exercises": [
        {{
          "order": 1,
          "name": "Nome Exercício",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8-9",
          "rest_seconds": 120,
          "weight_suggestion": "80kg",
          "muscle_group": "Peito",
          "technique_notes": "Descrição técnica",
          "progression": "Como progredir"
        }},
        ...mais exercícios...
      ]
    }},
    ...Upper B, Lower A, Lower B...
  ]
}}

Gere agora. Responda APENAS com JSON válido.
"""
    return prompt

def get_prompt_validar_treino(treino: dict, anamnese: dict) -> str:
    """Gera prompt para validar treino contra critérios científicos"""
    
    prompt = f"""
VOCÊ É UM REVISOR CIENTÍFICO DE PROGRAMAS DE TREINO
Valide contra: Schoenfeld, Israetel, Zourdos, Helms

USUÁRIO:
  • Experiência: {anamnese.get('experience_level', '?')}
  • Objetivo: {anamnese.get('main_goal', '?')}
  • Dias/semana: {anamnese.get('available_days', '?')}
  • Lesões: {anamnese.get('injuries', 'Nenhuma')}

TREINO PARA VALIDAR:
{json.dumps(treino, indent=2)[:2000]}...

═══════════════════════════════════════════════════════════════
VALIDAÇÃO: Responda cada um com ✅ ou ❌
═══════════════════════════════════════════════════════════════

VOLUME & FREQUÊNCIA:
1. Total séries/semana está na range MEV-MRV?
2. Cada grupo muscular 2-3x/semana?
3. Volume não sobrecarrega recuperação?

PUSH/PULL:
4. Ratio push:pull >= 1:1.2?
5. Pulls incluem vertical E horizontal?
6. Face pulls inclusos?

PERIODIZAÇÃO:
7. Tem 3 fases (força, hipertrofia, volume)?
8. Semana 1-3 usa reps 4-6 (força)?
9. Semana 4-6 usa reps 6-10 (hipertrofia)?
10. Semana 10 é deload?

SEGURANÇA:
11. Respeita TODAS as lesões?
12. Sem exercícios perigosos para iniciante?
13. Modificações para limitações?

EXERCÍCIOS:
14. Cada treino tem 1 composto pesado?
15. Exercícios complementam (não redundam)?
16. Ordem: composto → hipertrofia → isolado?

RECUPERAÇÃO:
17. Volume ajustado pro sono?
18. Sem mesma musculatura 2 dias seguidos?

OBJETIVO:
19. Se hipertrofia: reps 6-12, RPE 7-8?
20. Se força: reps 1-6, RPE 8-9?

═══════════════════════════════════════════════════════════════
RESPONDA COM JSON (exatamente assim):

Se APROVADO (✅ >= 17/20):
{{
  "status": "APROVADO",
  "score": <80-100>,
  "motivo": "Treino bem balanceado..."
}}

Se FALHOU (<17/20):
{{
  "status": "FALHOU",
  "score": <0-79>,
  "erros": ["Erro 1: descrição", "Erro 2: descrição"],
  "correcoes": ["Correção 1: o que fazer", "Correção 2: o que fazer"]
}}

Valide AGORA. Responda APENAS com JSON válido.
"""
    return prompt

# ============================================================
# GERADOR DE TREINOS COM QA (MAIN ENDPOINT)
# ============================================================

@app.route('/api/treinos/gerar', methods=['POST', 'OPTIONS'])
@cross_origin()
def gerar_treino():
    """
    Gera treino com validação automática (QA Loop)
    Tenta até 3x até obter ✅ APROVADO
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        anamnese = data.get('anamnese')
        split = data.get('split', 'upper_lower')
        focus = data.get('focus', 'hipertrofia')
        
        if not user_id or not anamnese:
            return jsonify({"error": "user_id e anamnese obrigatórios"}), 400
        
        print(f"\n{'='*60}")
        print(f"🎯 GERANDO TREINO COM QA")
        print(f"User: {user_id} | Split: {split} | Focus: {focus}")
        print(f"{'='*60}")
        
        # ============================================================
        # LOOP: Tenta até 3x
        # ============================================================
        
        for tentativa in range(1, 4):
            print(f"\n📝 TENTATIVA {tentativa}/3")
            print(f"{'─'*60}")
            
            # STAGE 1: Gerar treino
            print("Gerando treino com Claude...")
            
            prompt_gen = get_prompt_gerar_treino(anamnese, split, focus, tentativa)
            
            response_gen = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt_gen}]
            )
            
            response_text = response_gen.content[0].text
            
            # Limpar markdown
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            try:
                treino = json.loads(response_text)
                print(f"✓ Treino gerado com {len(treino.get('workouts', []))} dias")
            except json.JSONDecodeError as e:
                print(f"❌ Erro JSON: {e}")
                if tentativa == 3:
                    return jsonify({"error": "Erro ao gerar JSON válido"}), 500
                continue
            
            # STAGE 2: Validar treino
            print("Validando treino...")
            
            prompt_val = get_prompt_validar_treino(treino, anamnese)
            
            response_val = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt_val}]
            )
            
            response_val_text = response_val.content[0].text.strip()
            
            # Limpar markdown
            if response_val_text.startswith("```json"):
                response_val_text = response_val_text[7:]
            if response_val_text.startswith("```"):
                response_val_text = response_val_text[3:]
            if response_val_text.endswith("```"):
                response_val_text = response_val_text[:-3]
            
            response_val_text = response_val_text.strip()
            
            try:
                validacao = json.loads(response_val_text)
            except json.JSONDecodeError as e:
                print(f"❌ Erro validação JSON: {e}")
                if tentativa == 3:
                    return jsonify({"error": "Erro ao validar treino"}), 500
                continue
            
            # Verificar resultado
            status = validacao.get('status', 'FALHOU')
            score = validacao.get('score', 0)
            
            print(f"Score: {score}/100 | Status: {status}")
            
            if status == 'APROVADO' and score >= 80:
                print(f"\n✅ APROVADO NA TENTATIVA {tentativa}!")
                print(f"{'='*60}\n")
                
                return jsonify({
                    "status": "success",
                    "treino": treino,
                    "validacao": validacao,
                    "tentativas": tentativa,
                    "message": f"Treino gerado e aprovado com score {score}/100"
                }), 201
            
            else:
                print(f"❌ Falhou")
                erros = validacao.get('erros', [])
                correcoes = validacao.get('correcoes', [])
                
                if len(erros) > 0:
                    print(f"Erros: {erros[0]}")
                
                if tentativa < 3:
                    print(f"Tentando novamente...")
                    anamnese['ultima_correcao'] = json.dumps(correcoes)
                else:
                    print(f"\n❌ FALHA FINAL: 3 tentativas concluídas")
                    return jsonify({
                        "status": "error",
                        "message": "Não consegui gerar treino balanceado após 3 tentativas",
                        "ultima_validacao": validacao,
                        "tentativas": 3
                    }), 500
        
    except Exception as e:
        print(f"\n❌ Erro geral: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"\n{'='*60}")
    print(f"🚀 TREINO PRO - BACKEND PREMIUM")
    print(f"{'='*60}")
    print(f"✅ Anthropic API: {bool(ANTHROPIC_API_KEY)}")
    print(f"✅ Supabase: {bool(supabase)}")
    print(f"✅ CORS: HABILITADO")
    print(f"Porta: {port}")
    print(f"{'='*60}\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)
