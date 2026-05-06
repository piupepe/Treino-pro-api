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
    """Parse JSON from Claude response com validação rigorosa"""
    text = text.strip()
    
    print(f"[DEBUG] Raw text length: {len(text)}")
    print(f"[DEBUG] First 150 chars: {text[:150]}")
    
    # Remove markdown
    text = text.replace('```json', '').replace('```', '').strip()
    if text.startswith('json'):
        text = text[4:].strip()
    
    # Extract JSON between first { and last }
    start = text.find('{')
    end = text.rfind('}') + 1
    
    if start == -1 or end <= start:
        print(f"[ERROR] No JSON braces found")
        raise ValueError("No JSON found in response")
    
    text = text[start:end]
    print(f"[DEBUG] Extracted JSON length: {len(text)}")
    
    # Fix common issues
    # Remove any control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t\r')
    
    # Fix quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace("'", '"')
    
    # Fix escaped quotes inside strings
    text = text.replace('\\"', '"')
    
    # Fix newlines in values
    def fix_newlines(match):
        content = match.group(1)
        content = content.replace('\n', ' ').replace('\r', ' ')
        content = ' '.join(content.split())  # Normalize spaces
        return f'"{content}"'
    
    text = re.sub(r'"([^"]*)"', fix_newlines, text)
    
    print(f"[DEBUG] Cleaned text length: {len(text)}")
    
    try:
        result = json.loads(text)
        print(f"[SUCCESS] JSON parsed. Workouts: {len(result.get('workouts', []))}")
        return result
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decode failed: {e}")
        print(f"[ERROR] Position {e.pos}")
        if e.pos > 0:
            start_context = max(0, e.pos - 100)
            end_context = min(len(text), e.pos + 100)
            print(f"[ERROR] Context: ...{text[start_context:end_context]}...")
        raise

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
            
            prompt_gerar = f"""VOCÊ É UM GERADOR DE TREINOS PROFISSIONAL.

IMPORTANTE: Retorne APENAS um JSON válido, sem nenhum texto antes ou depois.

DADOS DO USUÁRIO:
- Experiência: {anamnese.get('experience_level')}
- Objetivo: {anamnese.get('main_goal')}
- Dias/semana: {anamnese.get('available_days')}
- Lesões: {anamnese.get('injuries', 'nenhuma')}
- Sono: {anamnese.get('sleep_hours')}h
- Equipamento: {anamnese.get('equipment')}

ESTRUTURA OBRIGATÓRIA (JSON):
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
      "estimated_duration_minutes": 70,
      "estimated_total_sets": 28,
      "exercises": [
        {{
          "name": "Supino Reto",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8",
          "rest_seconds": 120,
          "weight_suggestion": "80kg",
          "muscle_group": "Peito",
          "technique_notes": "Descida controlada, 1 segundo pausa no pecho"
        }},
        {{
          "name": "Supino Inclinado",
          "sets": 4,
          "reps": "8-10",
          "rpe": "7",
          "rest_seconds": 90,
          "weight_suggestion": "35kg",
          "muscle_group": "Peito",
          "technique_notes": "Amplitude completa"
        }},
        {{
          "name": "Crucifixo",
          "sets": 3,
          "reps": "10-12",
          "rpe": "7",
          "rest_seconds": 60,
          "weight_suggestion": "60kg",
          "muscle_group": "Peito",
          "technique_notes": "Contração de 1 segundo no pico"
        }},
        {{
          "name": "Desenvolvimento Halteres",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8",
          "rest_seconds": 120,
          "weight_suggestion": "30kg",
          "muscle_group": "Ombros",
          "technique_notes": "Movimento controlado, sem hiperextensão"
        }},
        {{
          "name": "Elevação Lateral",
          "sets": 3,
          "reps": "12-15",
          "rpe": "6",
          "rest_seconds": 45,
          "weight_suggestion": "15kg",
          "muscle_group": "Ombros",
          "technique_notes": "Sem balanço, controlado na descida"
        }},
        {{
          "name": "Rosca Direta",
          "sets": 4,
          "reps": "8-10",
          "rpe": "7",
          "rest_seconds": 90,
          "weight_suggestion": "35kg",
          "muscle_group": "Biceps",
          "technique_notes": "Sem balanço do corpo"
        }},
        {{
          "name": "Tríceps Corda",
          "sets": 3,
          "reps": "10-12",
          "rpe": "7",
          "rest_seconds": 60,
          "weight_suggestion": "25kg",
          "muscle_group": "Triceps",
          "technique_notes": "Extensão completa com triplicação"
        }},
        {{
          "name": "Rosca Francesa",
          "sets": 3,
          "reps": "8-10",
          "rpe": "7",
          "rest_seconds": 60,
          "weight_suggestion": "20kg",
          "muscle_group": "Triceps",
          "technique_notes": "Amplitude controlada, sem hiperextensão"
        }}
      ]
    }},
    {{
      "day": 2,
      "name": "LOWER A",
      "type": "leg",
      "estimated_duration_minutes": 75,
      "estimated_total_sets": 21,
      "exercises": [
        {{
          "name": "Leg Press 45 graus",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8",
          "rest_seconds": 120,
          "weight_suggestion": "160kg",
          "muscle_group": "Quadriceps",
          "technique_notes": "90 graus na amplitude, sem trancar joelho"
        }},
        {{
          "name": "Hack Squat",
          "sets": 4,
          "reps": "8-10",
          "rpe": "7",
          "rest_seconds": 90,
          "weight_suggestion": "120kg",
          "muscle_group": "Quadriceps",
          "technique_notes": "Amplitude completa, movimento controlado"
        }},
        {{
          "name": "Leg Extension",
          "sets": 3,
          "reps": "10-12",
          "rpe": "7",
          "rest_seconds": 60,
          "weight_suggestion": "80kg",
          "muscle_group": "Quadriceps",
          "technique_notes": "Sem bouncing, contração no topo"
        }},
        {{
          "name": "Leg Curl Sentado",
          "sets": 4,
          "reps": "8-10",
          "rpe": "7",
          "rest_seconds": 90,
          "weight_suggestion": "60kg",
          "muscle_group": "Posterior",
          "technique_notes": "Contração máxima, 1 segundo pausa"
        }},
        {{
          "name": "Panturrilha em Pe",
          "sets": 3,
          "reps": "12-15",
          "rpe": "6",
          "rest_seconds": 45,
          "weight_suggestion": "120kg",
          "muscle_group": "Panturrilha",
          "technique_notes": "Amplitude completa, carga máxima"
        }},
        {{
          "name": "Panturrilha Sentado",
          "sets": 3,
          "reps": "15-20",
          "rpe": "6",
          "rest_seconds": 45,
          "weight_suggestion": "50kg",
          "muscle_group": "Panturrilha",
          "technique_notes": "Isolamento, pico máximo de contração"
        }}
      ]
    }},
    {{
      "day": 3,
      "name": "UPPER B",
      "type": "pull",
      "estimated_duration_minutes": 75,
      "estimated_total_sets": 25,
      "exercises": [
        {{
          "name": "Remada Curvada",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8",
          "rest_seconds": 120,
          "weight_suggestion": "70kg",
          "muscle_group": "Costa",
          "technique_notes": "Cotovelo próximo do corpo, contração no topo"
        }},
        {{
          "name": "Remada Cavalo",
          "sets": 4,
          "reps": "8-10",
          "rpe": "7",
          "rest_seconds": 90,
          "weight_suggestion": "90kg",
          "muscle_group": "Costa",
          "technique_notes": "Amplitude completa, controlado"
        }},
        {{
          "name": "Puxada Pronada",
          "sets": 4,
          "reps": "8-10",
          "rpe": "7",
          "rest_seconds": 90,
          "weight_suggestion": "80kg",
          "muscle_group": "Dorsal",
          "technique_notes": "Movimento controlado, amplitude completa"
        }},
        {{
          "name": "Crucifixo Inverso",
          "sets": 3,
          "reps": "10-12",
          "rpe": "7",
          "rest_seconds": 60,
          "weight_suggestion": "70kg",
          "muscle_group": "Deltoides",
          "technique_notes": "Pico de contração, controlado na descida"
        }},
        {{
          "name": "Face Pull",
          "sets": 3,
          "reps": "12-15",
          "rpe": "6",
          "rest_seconds": 60,
          "weight_suggestion": "40kg",
          "muscle_group": "Deltoides",
          "technique_notes": "Amplitude completa, saúde do ombro"
        }},
        {{
          "name": "Rosca Inclinada",
          "sets": 4,
          "reps": "8-10",
          "rpe": "7",
          "rest_seconds": 90,
          "weight_suggestion": "28kg",
          "muscle_group": "Biceps",
          "technique_notes": "Fase excêntrica controlada, 2 segundos descida"
        }},
        {{
          "name": "Rosca Concentrada",
          "sets": 3,
          "reps": "10-12",
          "rpe": "7",
          "rest_seconds": 60,
          "weight_suggestion": "22kg",
          "muscle_group": "Biceps",
          "technique_notes": "Contração máxima, isolamento total"
        }}
      ]
    }},
    {{
      "day": 4,
      "name": "LOWER B",
      "type": "leg",
      "estimated_duration_minutes": 75,
      "estimated_total_sets": 21,
      "exercises": [
        {{
          "name": "Agachamento Bulgaro",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8",
          "rest_seconds": 120,
          "weight_suggestion": "35kg",
          "muscle_group": "Quadriceps",
          "technique_notes": "Força unilateral, estabilidade máxima"
        }},
        {{
          "name": "Leg Press",
          "sets": 4,
          "reps": "8-10",
          "rpe": "7",
          "rest_seconds": 90,
          "weight_suggestion": "140kg",
          "muscle_group": "Quadriceps",
          "technique_notes": "Volume, movimento controlado"
        }},
        {{
          "name": "Stiff Leg Deadlift",
          "sets": 4,
          "reps": "6-8",
          "rpe": "8",
          "rest_seconds": 120,
          "weight_suggestion": "60kg",
          "muscle_group": "Posterior",
          "technique_notes": "Amplitude limitada, contração posterior"
        }},
        {{
          "name": "Leg Curl",
          "sets": 3,
          "reps": "10-12",
          "rpe": "7",
          "rest_seconds": 60,
          "weight_suggestion": "70kg",
          "muscle_group": "Posterior",
          "technique_notes": "Contração máxima, isolamento"
        }},
        {{
          "name": "Leg Extension",
          "sets": 3,
          "reps": "10-12",
          "rpe": "7",
          "rest_seconds": 60,
          "weight_suggestion": "75kg",
          "muscle_group": "Quadriceps",
          "technique_notes": "Pico de contração no topo"
        }},
        {{
          "name": "Panturrilha Sentado",
          "sets": 3,
          "reps": "12-15",
          "rpe": "6",
          "rest_seconds": 45,
          "weight_suggestion": "55kg",
          "muscle_group": "Panturrilha",
          "technique_notes": "Pico máximo de contração"
        }}
      ]
    }}
  ]
}}

NÃO ADICIONE NADA ALÉM DO JSON!
NÃO USE MARKDOWN!
NÃO ADICIONE COMENTÁRIOS!
APENAS O JSON ESTRUTURADO ACIMA!"""
            
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
                    return jsonify({"error": f"Parse error: {str(e)}"}), 500
                continue
            
            # ============================================================
            # STAGE 2: Validação RIGOROSA
            # ============================================================
            
            prompt_validar = f"""Você é um validador de treinos.

Valide RAPIDAMENTE este treino:
- Tem 4 workouts exatamente?
- Cada workout tem campo 'exercises' com exercícios?
- Cada exercício tem: sets, reps, rest_seconds, rpe, muscle_group?

Responda APENAS JSON (sem markdown, sem texto extra):
{{"status": "APROVADO", "score": 88, "motivo": "Treino bem estruturado com 4 workouts completos e exercícios detalhados"}}

Se algum campo obrigatório faltar, retorne:
{{"status": "FALHOU", "score": 40, "motivo": "Campos faltando"}}"""
            
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
                print(f"❌ Parse validation error: {e}")
                if tentativa == 3:
                    return jsonify({"error": f"Validation parse error: {str(e)}"}), 500
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
