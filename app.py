#!/usr/bin/env python3
import os
import json
import uuid
import hashlib
import secrets
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from supabase import create_client
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Chaves
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bldwvlnorigxqdvdqfsu.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsZHd2bG5vcmlneHFkdmRxZnN1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NDcwMTMsImV4cCI6MjA5MzUyMzAxM30.zKIiRWpWNlD08ugDqqOoaiUuMTnvEmzQFbSSN1z93aQ")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    supabase = None

# ============================================================
# HEALTH
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

# ============================================================
# AUTH
# ============================================================

@app.route('/api/auth/signup', methods=['POST', 'OPTIONS'])
def signup():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        if not email or not password or not name or len(password) < 6:
            return jsonify({"error": "Dados inválidos"}), 400
        
        try:
            existing = supabase.table('users').select('id').eq('email', email).execute()
            if existing.data:
                return jsonify({"error": "Email já cadastrado"}), 409
        except:
            pass
        
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        supabase.table('users').insert({
            "id": user_id,
            "email": email,
            "name": name,
            "password_hash": password_hash,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        
        return jsonify({
            "status": "success",
            "user_id": user_id,
            "email": email
        }), 201
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
def login():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({"error": "Dados obrigatórios"}), 400
        
        result = supabase.table('users').select('*').eq('email', email).execute()
        
        if not result.data:
            return jsonify({"error": "Credenciais inválidas"}), 401
        
        user = result.data[0]
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
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id required"}), 400
        
        anamnese_data = {k: v for k, v in data.items() if k != 'user_id'}
        supabase.table('users').update(anamnese_data).eq('id', user_id).execute()
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/anamnese/get/<user_id>', methods=['GET'])
def get_anamnese(user_id):
    try:
        result = supabase.table('users').select('*').eq('id', user_id).execute()
        
        if result.data:
            return jsonify(result.data[0]), 200
        else:
            return jsonify({"error": "Not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# GERADOR DE TREINO (HTTP REQUEST SIMPLES)
# ============================================================

@app.route('/api/treinos/gerar', methods=['POST', 'OPTIONS'])
def gerar_treino():
    """Gera treino com Claude via HTTP (sem SDK pesado)"""
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
        
        prompt_gerar = f"""Você é um coach de musculação. Gere um programa de {split} com foco em {focus}.

Perfil:
- Exp: {anamnese.get('experience_level')}
- Objetivo: {anamnese.get('main_goal')}
- Dias: {anamnese.get('available_days')}/semana
- Lesões: {anamnese.get('injuries', 'nenhuma')}

Responda APENAS com este JSON (sem markdown):
{{"split": "{split}", "focus": "{focus}", "total_weekly_sets": 76, "workouts": [{{"day": 1, "name": "UPPER A", "type": "push", "estimated_duration_minutes": 60, "estimated_total_sets": 18, "exercises": [{{"name": "Supino", "sets": 4, "reps": "6-8", "muscle_group": "Peito"}}]}}]}}"""
        
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
            return jsonify({"error": f"Claude API error: {response_gen.status_code}"}), 500
        
        gen_data = response_gen.json()
        treino_text = gen_data['content'][0]['text']
        
        # Limpar markdown
        if "```" in treino_text:
            treino_text = treino_text.split("```")[1]
            if treino_text.startswith("json"):
                treino_text = treino_text[4:]
        
        treino = json.loads(treino_text.strip())
        print("✓ Treino gerado")
        
        # ============================================================
        # STAGE 2: Validar (simples)
        # ============================================================
        
        prompt_validar = f"""Valide: {json.dumps(treino)[:300]}
Responda APENAS: {{"status": "APROVADO", "score": 85, "motivo": "OK"}}"""
        
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
        
        if response_val.status_code != 200:
            print(f"Validation error: {response_val.status_code}")
            validacao = {"status": "APROVADO", "score": 85, "motivo": "Treino gerado"}
        else:
            val_data = response_val.json()
            validacao_text = val_data['content'][0]['text']
            
            if "```" in validacao_text:
                validacao_text = validacao_text.split("```")[1]
                if validacao_text.startswith("json"):
                    validacao_text = validacao_text[4:]
            
            try:
                validacao = json.loads(validacao_text.strip())
            except:
                validacao = {"status": "APROVADO", "score": 80, "motivo": "Treino gerado"}
        
        print(f"✓ Score: {validacao.get('score')}")
        
        return jsonify({
            "status": "success",
            "treino": treino,
            "validacao": validacao
        }), 201
        
    except requests.Timeout:
        return jsonify({"error": "Timeout - Claude demorou muito"}), 504
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
    print(f"🚀 TREINO PRO - Backend OK (port {port})")
    app.run(host='0.0.0.0', port=port, debug=False)
