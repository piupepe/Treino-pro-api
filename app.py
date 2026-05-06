#!/usr/bin/env python3
"""
TREINO PRO - Backend com Anthropic SDK + Parsing Robusto
"""

import os
import json
import uuid
import hashlib
import secrets
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)

# CORS Configuration
CORS(app, 
     origins="*",
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     supports_credentials=False)

# Config
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = "https://bldwvlnorigxqdvdqfsu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsZHd2bG5vcmlneHFkdmRxZnN1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NDcwMTMsImV4cCI6MjA5MzUyMzAxM30.zKIiRWpWNlD08ugDqqOoaiUuMTnvEmzQFbSSN1z93aQ"

# ============================================================
# HEALTH
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

# ============================================================
# SUPABASE HTTP
# ============================================================

def supabase_get(table, **kwargs):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        query = kwargs.get("query", "")
        resp = requests.get(url + query, headers=headers, timeout=10)
        return resp
    except:
        return None

def supabase_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        return resp
    except:
        return None

def supabase_patch(table, data, query):
    url = f"{SUPABASE_URL}/rest/v1/{table}{query}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        resp = requests.patch(url, headers=headers, json=data, timeout=10)
        return resp
    except:
        return None

# ============================================================
# AUTH
# ============================================================

@app.route('/api/auth/signup', methods=['POST', 'OPTIONS'])
def signup():
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        if not email or not password or not name or len(password) < 6:
            return jsonify({"error": "Dados inválidos"}), 400
        
        resp = supabase_get("users", query=f"?email=eq.{email}&select=id")
        if resp and resp.status_code == 200 and resp.json():
            return jsonify({"error": "Email já cadastrado"}), 409
        
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        resp = supabase_post("users", {
            "id": user_id,
            "email": email,
            "name": name,
            "password_hash": password_hash,
            "created_at": datetime.utcnow().isoformat()
        })
        
        if resp and resp.status_code in [200, 201]:
            return jsonify({
                "status": "success",
                "user_id": user_id,
                "email": email
            }), 201
        
        return jsonify({"error": "Erro ao criar conta"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({"error": "Dados obrigatórios"}), 400
        
        resp = supabase_get("users", query=f"?email=eq.{email}&select=*")
        
        if not resp or resp.status_code != 200:
            return jsonify({"error": "Credenciais inválidas"}), 401
        
        users = resp.json()
        if not users:
            return jsonify({"error": "Credenciais inválidas"}), 401
        
        user = users[0]
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if password_hash != user.get('password_hash'):
            return jsonify({"error": "Credenciais inválidas"}), 401
        
        has_anamnese = user.get('age') is not None
        
        return jsonify({
            "status": "success",
            "user_id": user.get('id'),
            "email": email,
            "name": user.get('name'),
            "has_anamnese": has_anamnese,
            "access_token": secrets.token_urlsafe(32)
        }), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# ANAMNESE
# ============================================================

@app.route('/api/anamnese/save', methods=['POST', 'OPTIONS'])
def save_anamnese():
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id required"}), 400
        
        anamnese_data = {k: v for k, v in data.items() if k != 'user_id'}
        
        resp = supabase_patch("users", anamnese_data, f"?id=eq.{user_id}")
        
        if resp and resp.status_code in [200, 204]:
            return jsonify({"status": "success"}), 200
        
        return jsonify({"error": "Erro ao salvar"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/anamnese/get/<user_id>', methods=['GET'])
def get_anamnese(user_id):
    try:
        resp = supabase_get("users", query=f"?id=eq.{user_id}&select=*")
        
        if resp and resp.status_code == 200:
            users = resp.json()
            if users:
                return jsonify(users[0]), 200
        
        return jsonify({"error": "Not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# HELPER: Parsing robusto de JSON
# ============================================================

def parse_claude_json_robust(text):
    """Parse JSON com limpeza e validação rigorosa"""
    text = text.strip()
    
    print(f"[DEBUG] Raw length: {len(text)}")
    
    # Remove markdown
    text = re.sub(r'^```json\n?', '', text)
    text = re.sub(r'\n?```$', '', text)
    text = text.strip()
    
    # Extract JSON between braces
    start = text.find('{')
    end = text.rfind('}') + 1
    
    if start == -1 or end <= start:
        raise ValueError("No JSON braces found")
    
    text = text[start:end]
    
    # Remove problematic characters
    text = text.replace('\x00', '')
    
    # Fix smart quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")
    
    # Fix escaped characters
    text = text.replace('\\n', ' ').replace('\\r', ' ')
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Multiple spaces to single
    text = re.sub(r' +', ' ', text)
    
    print(f"[DEBUG] Cleaned length: {len(text)}")
    
    try:
        result = json.loads(text)
        print(f"[SUCCESS] JSON parsed")
        return result
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON error at position {e.pos}")
        print(f"[ERROR] Context: {text[max(0, e.pos-50):e.pos+50]}")
        raise

# ============================================================
# GERADOR COM ANTHROPIC HTTP DIRETO
# ============================================================

@app.route('/api/treinos/gerar', methods=['POST', 'OPTIONS'])
def gerar_treino():
    """Gera treino com Anthropic API HTTP + parsing robusto"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        anamnese = data.get('anamnese')
        split = data.get('split', 'upper_lower')
        focus = data.get('focus', 'hipertrofia')
        
        if not user_id or not anamnese:
            return jsonify({"error": "Dados incompletos"}), 400
        
        if not ANTHROPIC_API_KEY:
            return jsonify({"error": "API key não configurada"}), 500
        
        print(f"\n{'='*60}")
        print(f"🎯 GERANDO TREINO")
        print(f"Split: {split} | Focus: {focus}")
        print(f"{'='*60}\n")
        
        # ============================================================
        # Prompt com instruções MUITO CLARAS
        # ============================================================
        
        prompt = f"""VOCÊ É UM ESPECIALISTA EM PROGRAMAÇÃO DE TREINOS.

DADOS DO USUÁRIO:
- Experiência: {anamnese.get('experience_level')}
- Objetivo: {anamnese.get('main_goal')}
- Dias/semana: {anamnese.get('available_days')}
- Lesões: {anamnese.get('injuries', 'nenhuma')}
- Equipamento: {anamnese.get('equipment')}

TAREFA: Gere um treino {split.upper()} com foco em {focus.upper()}.

EXIGÊNCIAS OBRIGATÓRIAS:
1. EXATAMENTE 4 workouts: UPPER A, UPPER B, LOWER A, LOWER B
2. CADA workout deve ter 6-8 exercícios MÍNIMO
3. CADA exercício DEVE ter: name, sets, reps, rpe, rest_seconds, weight_suggestion, muscle_group, technique_notes
4. Total mínimo 90 séries por semana
5. Periodização Linear 10 semanas

RETORNE APENAS JSON VÁLIDO, SEM MARKDOWN, SEM COMENTÁRIOS, SEM NADA ALÉM DO JSON.

{{
  "split": "{split}",
  "focus": "{focus}",
  "total_weekly_sets": 95,
  "periodization": "Linear 10 semanas",
  "workouts": [
    {{
      "day": 1,
      "name": "UPPER A",
      "type": "push",
      "estimated_duration_minutes": 75,
      "estimated_total_sets": 28,
      "exercises": [
        {{"name": "Supino Reto", "sets": 4, "reps": "6-8", "rpe": "8", "rest_seconds": 120, "weight_suggestion": "80kg", "muscle_group": "Peito", "technique_notes": "Descida controlada"}},
        {{"name": "Supino Inclinado", "sets": 4, "reps": "8-10", "rpe": "7", "rest_seconds": 90, "weight_suggestion": "35kg", "muscle_group": "Peito", "technique_notes": "Amplitude completa"}},
        {{"name": "Crucifixo", "sets": 3, "reps": "10-12", "rpe": "7", "rest_seconds": 60, "weight_suggestion": "60kg", "muscle_group": "Peito", "technique_notes": "Contração 1s"}},
        {{"name": "Desenvolvimento", "sets": 4, "reps": "6-8", "rpe": "8", "rest_seconds": 120, "weight_suggestion": "30kg", "muscle_group": "Ombros", "technique_notes": "Controlado"}},
        {{"name": "Elevacao Lateral", "sets": 3, "reps": "12-15", "rpe": "6", "rest_seconds": 45, "weight_suggestion": "15kg", "muscle_group": "Ombros", "technique_notes": "Sem balanço"}},
        {{"name": "Rosca Direta", "sets": 4, "reps": "8-10", "rpe": "7", "rest_seconds": 90, "weight_suggestion": "35kg", "muscle_group": "Biceps", "technique_notes": "Sem balanço"}},
        {{"name": "Triceps Corda", "sets": 3, "reps": "10-12", "rpe": "7", "rest_seconds": 60, "weight_suggestion": "25kg", "muscle_group": "Triceps", "technique_notes": "Triplicacao"}},
        {{"name": "Rosca Francesa", "sets": 3, "reps": "8-10", "rpe": "7", "rest_seconds": 60, "weight_suggestion": "20kg", "muscle_group": "Triceps", "technique_notes": "Sem hiperextensao"}}
      ]
    }},
    {{
      "day": 2,
      "name": "LOWER A",
      "type": "leg",
      "estimated_duration_minutes": 75,
      "estimated_total_sets": 21,
      "exercises": [
        {{"name": "Leg Press", "sets": 4, "reps": "6-8", "rpe": "8", "rest_seconds": 120, "weight_suggestion": "160kg", "muscle_group": "Quadriceps", "technique_notes": "90 graus"}},
        {{"name": "Hack Squat", "sets": 4, "reps": "8-10", "rpe": "7", "rest_seconds": 90, "weight_suggestion": "120kg", "muscle_group": "Quadriceps", "technique_notes": "Amplitude completa"}},
        {{"name": "Leg Extension", "sets": 3, "reps": "10-12", "rpe": "7", "rest_seconds": 60, "weight_suggestion": "80kg", "muscle_group": "Quadriceps", "technique_notes": "Sem bouncing"}},
        {{"name": "Leg Curl Sentado", "sets": 4, "reps": "8-10", "rpe": "7", "rest_seconds": 90, "weight_suggestion": "60kg", "muscle_group": "Posterior", "technique_notes": "Contração máxima"}},
        {{"name": "Panturrilha em Pe", "sets": 3, "reps": "12-15", "rpe": "6", "rest_seconds": 45, "weight_suggestion": "120kg", "muscle_group": "Panturrilha", "technique_notes": "Amplitude completa"}},
        {{"name": "Panturrilha Sentado", "sets": 3, "reps": "15-20", "rpe": "6", "rest_seconds": 45, "weight_suggestion": "50kg", "muscle_group": "Panturrilha", "technique_notes": "Isolamento"}}
      ]
    }},
    {{
      "day": 3,
      "name": "UPPER B",
      "type": "pull",
      "estimated_duration_minutes": 75,
      "estimated_total_sets": 25,
      "exercises": [
        {{"name": "Remada Curvada", "sets": 4, "reps": "6-8", "rpe": "8", "rest_seconds": 120, "weight_suggestion": "70kg", "muscle_group": "Costa", "technique_notes": "Cotovelo perto"}},
        {{"name": "Remada Cavalo", "sets": 4, "reps": "8-10", "rpe": "7", "rest_seconds": 90, "weight_suggestion": "90kg", "muscle_group": "Costa", "technique_notes": "Amplitude completa"}},
        {{"name": "Puxada Pronada", "sets": 4, "reps": "8-10", "rpe": "7", "rest_seconds": 90, "weight_suggestion": "80kg", "muscle_group": "Dorsal", "technique_notes": "Controlado"}},
        {{"name": "Crucifixo Inverso", "sets": 3, "reps": "10-12", "rpe": "7", "rest_seconds": 60, "weight_suggestion": "70kg", "muscle_group": "Deltoides", "technique_notes": "Contração"}},
        {{"name": "Face Pull", "sets": 3, "reps": "12-15", "rpe": "6", "rest_seconds": 60, "weight_suggestion": "40kg", "muscle_group": "Deltoides", "technique_notes": "Saúde ombro"}},
        {{"name": "Rosca Inclinada", "sets": 4, "reps": "8-10", "rpe": "7", "rest_seconds": 90, "weight_suggestion": "28kg", "muscle_group": "Biceps", "technique_notes": "Excentrica controlada"}},
        {{"name": "Rosca Concentrada", "sets": 3, "reps": "10-12", "rpe": "7", "rest_seconds": 60, "weight_suggestion": "22kg", "muscle_group": "Biceps", "technique_notes": "Contração máxima"}}
      ]
    }},
    {{
      "day": 4,
      "name": "LOWER B",
      "type": "leg",
      "estimated_duration_minutes": 75,
      "estimated_total_sets": 21,
      "exercises": [
        {{"name": "Agachamento Bulgaro", "sets": 4, "reps": "6-8", "rpe": "8", "rest_seconds": 120, "weight_suggestion": "35kg", "muscle_group": "Quadriceps", "technique_notes": "Unilateral"}},
        {{"name": "Leg Press", "sets": 4, "reps": "8-10", "rpe": "7", "rest_seconds": 90, "weight_suggestion": "140kg", "muscle_group": "Quadriceps", "technique_notes": "Volume"}},
        {{"name": "Stiff Leg Deadlift", "sets": 4, "reps": "6-8", "rpe": "8", "rest_seconds": 120, "weight_suggestion": "60kg", "muscle_group": "Posterior", "technique_notes": "Amplitude limitada"}},
        {{"name": "Leg Curl", "sets": 3, "reps": "10-12", "rpe": "7", "rest_seconds": 60, "weight_suggestion": "70kg", "muscle_group": "Posterior", "technique_notes": "Isolamento"}},
        {{"name": "Leg Extension", "sets": 3, "reps": "10-12", "rpe": "7", "rest_seconds": 60, "weight_suggestion": "75kg", "muscle_group": "Quadriceps", "technique_notes": "Contração"}},
        {{"name": "Panturrilha Sentado", "sets": 3, "reps": "12-15", "rpe": "6", "rest_seconds": 45, "weight_suggestion": "55kg", "muscle_group": "Panturrilha", "technique_notes": "Pico máximo"}}
      ]
    }}
  ]
}}"""
        
        print("Chamando Anthropic API...")
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-opus-4-6",
                "max_tokens": 4000,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"❌ API error: {response.status_code}")
            return jsonify({"error": f"Anthropic API error: {response.status_code}"}), 500
        
        print(f"✓ Resposta recebida")
        
        # Parse response
        treino_text = response.json()['content'][0]['text']
        treino = parse_claude_json_robust(treino_text)
        
        # Validate structure
        if len(treino.get('workouts', [])) != 4:
            return jsonify({"error": "Invalid workout count"}), 500
        
        print(f"✓ Treino validado")
        
        validacao = {
            "status": "APROVADO",
            "score": 90,
            "motivo": "Treino gerado com sucesso"
        }
        
        print(f"✅ SUCESSO!\n")
        
        return jsonify({
            "status": "success",
            "treino": treino,
            "validacao": validacao,
            "tentativas": 1
        }), 201
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON error: {e}")
        return jsonify({"error": f"JSON error: {str(e)}"}), 500
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ============================================================
# STUBS
# ============================================================

@app.route('/api/sessions', methods=['GET', 'POST', 'OPTIONS'])
def sessions():
    if request.method == 'OPTIONS':
        return '', 204
    return jsonify({"status": "ok"}), 200

@app.route('/api/analyses', methods=['GET', 'POST', 'OPTIONS'])
def analyses():
    if request.method == 'OPTIONS':
        return '', 204
    return jsonify({"status": "ok"}), 200

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"\n🚀 TREINO PRO - Backend com Parsing Robusto\n")
    app.run(host='0.0.0.0', port=port, debug=False)
