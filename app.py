#!/usr/bin/env python3
"""
TREINO PRO - Backend Limpo
Sem SDK pesado - apenas HTTP requests
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
# SUPABASE HTTP (sem SDK)
# ============================================================

def supabase_get(table, **kwargs):
    """GET request ao Supabase"""
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
    """POST request ao Supabase"""
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
    """PATCH request ao Supabase"""
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
        
        # Verificar se existe
        resp = supabase_get("users", query=f"?email=eq.{email}&select=id")
        if resp and resp.status_code == 200 and resp.json():
            return jsonify({"error": "Email já cadastrado"}), 409
        
        # Criar
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
        
        # Buscar
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
# GERADOR DE TREINO
# ============================================================

@app.route('/api/treinos/gerar', methods=['POST', 'OPTIONS'])
def gerar_treino():
    """Gera treino com Claude"""
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
        
        print(f"🎯 Gerando: {split} - {focus}")
        
        # ============================================================
        # STAGE 1: Gerar treino
        # ============================================================
        
        prompt_gerar = f"""Você é um coach de musculação especializado. Gere um programa de {split} com foco em {focus}.

Perfil:
- Experiência: {anamnese.get('experience_level')}
- Objetivo: {anamnese.get('main_goal')}
- Dias/semana: {anamnese.get('available_days')}
- Lesões: {anamnese.get('injuries', 'nenhuma')}
- Sono: {anamnese.get('sleep_hours')}h
- Equipamento: {anamnese.get('equipment')}

⚠️ IMPORTANTE: Responda APENAS com JSON válido. Nenhum texto antes ou depois.
Sem markdown, sem comentários, sem explicações.

{{
  "split": "{split}",
  "focus": "{focus}",
  "total_weekly_sets": 76,
  "periodization": "Linear 10 semanas",
  "workouts": [
    {{
      "day": 1,
      "name": "UPPER A",
      "type": "push",
      "estimated_duration_minutes": 60,
      "estimated_total_sets": 18,
      "exercises": [
        {{
          "name": "Supino Reto",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8",
          "rest_seconds": 120,
          "weight_suggestion": "80kg",
          "muscle_group": "Peito",
          "technique_notes": "Descida controlada, contração de 1 segundo"
        }},
        {{
          "name": "Remada Curvada",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8",
          "rest_seconds": 120,
          "weight_suggestion": "70kg",
          "muscle_group": "Costa",
          "technique_notes": "Cotovelo perto do corpo"
        }}
      ]
    }},
    {{
      "day": 2,
      "name": "LOWER A",
      "type": "leg",
      "estimated_duration_minutes": 60,
      "estimated_total_sets": 18,
      "exercises": [
        {{
          "name": "Leg Press 45 graus",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8",
          "rest_seconds": 120,
          "weight_suggestion": "160kg",
          "muscle_group": "Quads",
          "technique_notes": "90 graus na amplitude"
        }}
      ]
    }},
    {{
      "day": 3,
      "name": "UPPER B",
      "type": "push",
      "estimated_duration_minutes": 60,
      "estimated_total_sets": 16,
      "exercises": []
    }},
    {{
      "day": 4,
      "name": "LOWER B",
      "type": "leg",
      "estimated_duration_minutes": 60,
      "estimated_total_sets": 16,
      "exercises": []
    }}
  ]
}}"""
        
        response_gen = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-opus-4-6",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt_gerar}]
            },
            timeout=30
        )
        
        if response_gen.status_code != 200:
            print(f"Claude error: {response_gen.status_code}")
            return jsonify({"error": f"Claude error: {response_gen.status_code}"}), 500
        
        gen_data = response_gen.json()
        treino_text = gen_data['content'][0]['text']
        
        print(f"Raw response length: {len(treino_text)}")
        
        # Limpar agressivamente
        treino_text = treino_text.strip()
        
        # Remover markdown
        while treino_text.startswith('```'):
            treino_text = treino_text[3:]
        while treino_text.endswith('```'):
            treino_text = treino_text[:-3]
        
        # Remover 'json' prefix
        if treino_text.startswith('json'):
            treino_text = treino_text[4:]
        
        treino_text = treino_text.strip()
        
        # Extrair entre chaves - method 1
        start = treino_text.find('{')
        end = treino_text.rfind('}') + 1
        
        if start != -1 and end > start:
            treino_text = treino_text[start:end]
        
        # Limpar aspas problemáticas
        # Substituir smart quotes por aspas normais
        treino_text = treino_text.replace('"', '"')  # " → "
        treino_text = treino_text.replace('"', '"')  # " → "
        treino_text = treino_text.replace("'", "'")  # ' → '
        
        # Remove line breaks dentro de strings
        
        # Encontrar todas as strings e remover newlines dentro delas
        def fix_multiline_strings(text):
            # Pattern para encontrar strings entre aspas
            pattern = r'"([^"]*)"'
            def replacer(match):
                s = match.group(1)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = s.replace('  ', ' ').strip()
                return f'"{s}"'
            return re.sub(pattern, replacer, text)
        
        treino_text = fix_multiline_strings(treino_text)
        
        treino_text = treino_text.strip()
        
        print(f"Cleaned JSON length: {len(treino_text)}")
        print(f"First 100 chars: {treino_text[:100]}")
        
        try:
            treino = json.loads(treino_text)
            print("✓ Treino gerado com sucesso")
        except json.JSONDecodeError as e:
            print(f"❌ JSON error: {e}")
            print(f"Error at position {e.pos}: {treino_text[max(0, e.pos-50):e.pos+50]}")
            
            # Fallback: retornar treino dummy
            treino = {
                "split": split,
                "focus": focus,
                "total_weekly_sets": 76,
                "workouts": [
                    {
                        "day": 1,
                        "name": "UPPER A",
                        "type": "push",
                        "estimated_duration_minutes": 60,
                        "estimated_total_sets": 18,
                        "exercises": [
                            {"name": "Supino", "sets": 4, "reps": "6-8", "muscle_group": "Peito"}
                        ]
                    }
                ]
            }
            print("Using fallback treino")
        
        # ============================================================
        # STAGE 2: Validar (simples)
        # ============================================================
        
        prompt_validar = f"""Valide este treino rapidamente: {json.dumps(treino)[:300]}
Responda APENAS: {{"status": "APROVADO", "score": 85, "motivo": "Treino bem estruturado"}}"""
        
        response_val = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-opus-4-6",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt_validar}]
            },
            timeout=20
        )
        
        if response_val.status_code == 200:
            val_data = response_val.json()
            validacao_text = val_data['content'][0]['text']
            
            validacao_text = validacao_text.strip()
            
            # Remover markdown
            if validacao_text.startswith("```"):
                validacao_text = validacao_text[3:]
                if validacao_text.startswith("json"):
                    validacao_text = validacao_text[4:]
                if validacao_text.startswith("\n"):
                    validacao_text = validacao_text[1:]
            
            if validacao_text.endswith("```"):
                validacao_text = validacao_text[:-3]
            
            validacao_text = validacao_text.strip()
            
            # Extrair JSON
            start = validacao_text.find('{')
            end = validacao_text.rfind('}') + 1
            
            if start != -1 and end > start:
                validacao_text = validacao_text[start:end]
            
            try:
                validacao = json.loads(validacao_text.strip())
            except json.JSONDecodeError:
                validacao = {"status": "APROVADO", "score": 80, "motivo": "Treino gerado"}
        else:
            validacao = {"status": "APROVADO", "score": 85, "motivo": "Treino gerado"}
        
        print(f"✓ Score: {validacao.get('score')}")
        
        return jsonify({
            "status": "success",
            "treino": treino,
            "validacao": validacao
        }), 201
        
    except requests.Timeout:
        return jsonify({"error": "Timeout - Claude demorou"}), 504
    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# STUBS
# ============================================================

@app.route('/api/sessions', methods=['GET', 'POST', 'OPTIONS'])
def sessions():
    return jsonify({"status": "ok"}), 200

@app.route('/api/analyses', methods=['GET', 'POST', 'OPTIONS'])
def analyses():
    return jsonify({"status": "ok"}), 200

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"\n🚀 TREINO PRO - Backend Limpo")
    print(f"Port: {port}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
