#!/usr/bin/env python3
"""
TREINO PRO - Backend com QA Loop Rigoroso
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
# HELPER: Parse JSON from Claude
# ============================================================

def parse_claude_json(text):
    """Parse JSON from Claude response"""
    text = text.strip()
    
    # Remove markdown
    while text.startswith('```'):
        text = text[3:]
    while text.endswith('```'):
        text = text[:-3]
    
    if text.startswith('json'):
        text = text[4:]
    
    text = text.strip()
    
    # Extract JSON
    start = text.find('{')
    end = text.rfind('}') + 1
    
    if start != -1 and end > start:
        text = text[start:end]
    
    # Fix quotes
    text = text.replace('"', '"').replace('"', '"')
    
    # Fix newlines
    def fix_multiline(t):
        pattern = r'"([^"]*)"'
        def replacer(m):
            s = m.group(1).replace('\n', ' ').replace('\r', ' ')
            s = ' '.join(s.split())
            return f'"{s}"'
        return re.sub(pattern, replacer, t)
    
    text = fix_multiline(text)
    
    return json.loads(text.strip())

# ============================================================
# GERADOR COM QA LOOP RIGOROSO - 3 TENTATIVAS
# ============================================================

@app.route('/api/treinos/gerar', methods=['POST', 'OPTIONS'])
def gerar_treino():
    """Gera treino com QA rigoroso - máx 3 tentativas"""
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
        print(f"🎯 GERANDO TREINO COM QA RIGOROSO")
        print(f"Split: {split} | Focus: {focus}")
        print(f"{'='*60}\n")
        
        treino = None
        validacao = None
        
        for tentativa in range(1, 4):
            print(f"\n📝 TENTATIVA {tentativa}/3")
            print(f"{'─'*60}")
            
            # ============================================================
            # STAGE 1: Gerar
            # ============================================================
            
            prompt_gerar = f"""Gere um treino {split} com foco em {focus}.
Perfil: {anamnese.get('experience_level')}, {anamnese.get('main_goal')}, {anamnese.get('available_days')} dias/semana
Lesões: {anamnese.get('injuries', 'nenhuma')}

Responda APENAS JSON: {{"split": "{split}", "focus": "{focus}", "total_weekly_sets": 76, "workouts": [{{"day": 1, "name": "UPPER A", "exercises": [{{"name": "Supino", "sets": 4, "reps": "6-8", "muscle_group": "Peito"}}]}}]}}"""
            
            print("Gerando...")
            
            response_gen = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-opus-4-6",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt_gerar}]
                },
                timeout=40
            )
            
            if response_gen.status_code != 200:
                print(f"❌ Claude error")
                if tentativa == 3:
                    return jsonify({"error": "Claude API error"}), 500
                continue
            
            try:
                treino_text = response_gen.json()['content'][0]['text']
                treino = parse_claude_json(treino_text)
                print(f"✓ Gerado")
            except Exception as e:
                print(f"❌ Parse error: {e}")
                if tentativa == 3:
                    return jsonify({"error": "JSON error"}), 500
                continue
            
            # ============================================================
            # STAGE 2: Validação RIGOROSA
            # ============================================================
            
            prompt_validar = f"""Valide RIGOROSAMENTE:
- 4 workouts (UPPER A/B, LOWER A/B)?
- Cada um com 4+ exercícios?
- Total séries >= 70?
- Push:Pull >= 1:1.2?
- Todos campos (sets, reps, rest, rpe)?

Treino: {json.dumps(treino)[:800]}

Responda JSON: {{"status": "APROVADO", "score": 85, "motivo": "OK"}} ou {{"status": "FALHOU", "score": 40, "erros": ["erro"]}}"""
            
            print("Validando...")
            
            response_val = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-opus-4-6",
                    "max_tokens": 600,
                    "messages": [{"role": "user", "content": prompt_validar}]
                },
                timeout=30
            )
            
            if response_val.status_code != 200:
                print(f"❌ Validation error")
                if tentativa == 3:
                    return jsonify({"error": "Validation error"}), 500
                continue
            
            try:
                validacao_text = response_val.json()['content'][0]['text']
                validacao = parse_claude_json(validacao_text)
            except Exception as e:
                print(f"❌ Parse validation error")
                if tentativa == 3:
                    return jsonify({"error": "Validation parse error"}), 500
                continue
            
            status = validacao.get('status', 'FALHOU')
            score = validacao.get('score', 0)
            
            print(f"Score: {score}/100 | {status}")
            
            if status == 'APROVADO' and score >= 80:
                print(f"\n✅ APROVADO NA TENTATIVA {tentativa}!\n")
                
                return jsonify({
                    "status": "success",
                    "treino": treino,
                    "validacao": validacao,
                    "tentativas": tentativa
                }), 201
            
            print(f"Erros: {validacao.get('erros', [])[:1]}")
        
        return jsonify({
            "status": "error",
            "message": "3 tentativas falharam",
            "ultima_validacao": validacao
        }), 500
        
    except requests.Timeout:
        return jsonify({"error": "Timeout"}), 504
    except Exception as e:
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
    print(f"\n🚀 TREINO PRO - QA Rigoroso\n")
    app.run(host='0.0.0.0', port=port, debug=False)
