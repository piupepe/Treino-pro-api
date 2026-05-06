#!/usr/bin/env python3
import os, json, uuid, hashlib, secrets, re
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], supports_credentials=False)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = "https://bldwvlnorigxqdvdqfsu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsZHd2bG5vcmlneHFkdmRxZnN1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NDcwMTMsImV4cCI6MjA5MzUyMzAxM30.zKIiRWpWNlD08ugDqqOoaiUuMTnvEmzQFbSSN1z93aQ"

# ====== HELPERS ======
def supabase_get(table, **kwargs):
    try:
        query = kwargs.get("query", "")
        resp = requests.get(f"{SUPABASE_URL}/rest/v1/{table}{query}", headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}, timeout=10)
        return resp
    except:
        return None

def supabase_post(table, data):
    try:
        resp = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}, json=data, timeout=10)
        return resp
    except:
        return None

def supabase_patch(table, data, query):
    try:
        resp = requests.patch(f"{SUPABASE_URL}/rest/v1/{table}{query}", headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}, json=data, timeout=10)
        return resp
    except:
        return None

def parse_json_clean(text):
    text = text.strip()
    text = re.sub(r'^```json\n?', '', text)
    text = re.sub(r'\n?```$', '', text)
    text = text.strip()
    start = text.find('{')
    end = text.rfind('}') + 1
    if start == -1 or end <= start:
        raise ValueError("No JSON")
    text = text[start:end]
    text = text.replace('\x00', '')
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r' +', ' ', text)
    return json.loads(text)

# ====== ROUTES ======
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

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
            return jsonify({"error": "Invalid"}), 400
        resp = supabase_get("users", query=f"?email=eq.{email}&select=id")
        if resp and resp.status_code == 200 and resp.json():
            return jsonify({"error": "Email exists"}), 409
        user_id = str(uuid.uuid4())
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        resp = supabase_post("users", {"id": user_id, "email": email, "name": name, "password_hash": password_hash, "created_at": datetime.utcnow().isoformat()})
        if resp and resp.status_code in [200, 201]:
            return jsonify({"status": "success", "user_id": user_id, "email": email}), 201
        return jsonify({"error": "Error"}), 500
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
            return jsonify({"error": "Required"}), 400
        resp = supabase_get("users", query=f"?email=eq.{email}&select=*")
        if not resp or resp.status_code != 200:
            return jsonify({"error": "Invalid"}), 401
        users = resp.json()
        if not users:
            return jsonify({"error": "Invalid"}), 401
        user = users[0]
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != user.get('password_hash'):
            return jsonify({"error": "Invalid"}), 401
        has_anamnese = user.get('age') is not None
        return jsonify({"status": "success", "user_id": user.get('id'), "email": email, "name": user.get('name'), "has_anamnese": has_anamnese, "access_token": secrets.token_urlsafe(32)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/anamnese/save', methods=['POST', 'OPTIONS'])
def save_anamnese():
    if request.method == 'OPTIONS':
        return '', 204
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"error": "No ID"}), 400
        anamnese_data = {k: v for k, v in data.items() if k != 'user_id'}
        resp = supabase_patch("users", anamnese_data, f"?id=eq.{user_id}")
        if resp and resp.status_code in [200, 204]:
            return jsonify({"status": "success"}), 200
        return jsonify({"error": "Error"}), 500
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

@app.route('/api/treinos/gerar', methods=['POST', 'OPTIONS'])
def gerar_treino():
    if request.method == 'OPTIONS':
        return '', 204
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        anamnese = data.get('anamnese')
        split = data.get('split', 'upper_lower')
        focus = data.get('focus', 'hipertrofia')
        
        if not user_id or not anamnese or not ANTHROPIC_API_KEY:
            return jsonify({"error": "Missing data"}), 400
        
        print(f"\n{'='*60}")
        print(f"🎯 GERANDO {split.upper()} - {focus.upper()}")
        print(f"{'='*60}\n")
        
        # JSON template base
        json_template = '''{"split":"upper_lower","focus":"hipertrofia","total_weekly_sets":95,"periodization":"Linear 10 semanas","workouts":[{"day":1,"name":"UPPER A","type":"push","estimated_duration_minutes":75,"estimated_total_sets":28,"exercises":[{"name":"Supino Reto","sets":4,"reps":"6-8","rpe":"8","rest_seconds":120,"weight_suggestion":"80kg","muscle_group":"Peito","technique_notes":"Descida controlada"},{"name":"Supino Inclinado","sets":4,"reps":"8-10","rpe":"7","rest_seconds":90,"weight_suggestion":"35kg","muscle_group":"Peito","technique_notes":"Amplitude"},{"name":"Crucifixo","sets":3,"reps":"10-12","rpe":"7","rest_seconds":60,"weight_suggestion":"60kg","muscle_group":"Peito","technique_notes":"Contração"},{"name":"Desenvolvimento","sets":4,"reps":"6-8","rpe":"8","rest_seconds":120,"weight_suggestion":"30kg","muscle_group":"Ombros","technique_notes":"Controlado"},{"name":"Elevacao Lateral","sets":3,"reps":"12-15","rpe":"6","rest_seconds":45,"weight_suggestion":"15kg","muscle_group":"Ombros","technique_notes":"Sem balanço"},{"name":"Rosca Direta","sets":4,"reps":"8-10","rpe":"7","rest_seconds":90,"weight_suggestion":"35kg","muscle_group":"Biceps","technique_notes":"Sem balanço"},{"name":"Triceps Corda","sets":3,"reps":"10-12","rpe":"7","rest_seconds":60,"weight_suggestion":"25kg","muscle_group":"Triceps","technique_notes":"Triplicacao"},{"name":"Rosca Francesa","sets":3,"reps":"8-10","rpe":"7","rest_seconds":60,"weight_suggestion":"20kg","muscle_group":"Triceps","technique_notes":"Sem hiperext"}]},{"day":2,"name":"LOWER A","type":"leg","estimated_duration_minutes":75,"estimated_total_sets":21,"exercises":[{"name":"Leg Press 45","sets":4,"reps":"6-8","rpe":"8","rest_seconds":120,"weight_suggestion":"160kg","muscle_group":"Quadriceps","technique_notes":"90 graus"},{"name":"Hack Squat","sets":4,"reps":"8-10","rpe":"7","rest_seconds":90,"weight_suggestion":"120kg","muscle_group":"Quadriceps","technique_notes":"Amplitude"},{"name":"Leg Extension","sets":3,"reps":"10-12","rpe":"7","rest_seconds":60,"weight_suggestion":"80kg","muscle_group":"Quadriceps","technique_notes":"Sem bouncing"},{"name":"Leg Curl Sentado","sets":4,"reps":"8-10","rpe":"7","rest_seconds":90,"weight_suggestion":"60kg","muscle_group":"Posterior","technique_notes":"Contração"},{"name":"Panturrilha Pe","sets":3,"reps":"12-15","rpe":"6","rest_seconds":45,"weight_suggestion":"120kg","muscle_group":"Panturrilha","technique_notes":"Amplitude"},{"name":"Panturrilha Sentado","sets":3,"reps":"15-20","rpe":"6","rest_seconds":45,"weight_suggestion":"50kg","muscle_group":"Panturrilha","technique_notes":"Isolamento"}]},{"day":3,"name":"UPPER B","type":"pull","estimated_duration_minutes":75,"estimated_total_sets":25,"exercises":[{"name":"Remada Curvada","sets":4,"reps":"6-8","rpe":"8","rest_seconds":120,"weight_suggestion":"70kg","muscle_group":"Costa","technique_notes":"Cotovelo"},{"name":"Remada Cavalo","sets":4,"reps":"8-10","rpe":"7","rest_seconds":90,"weight_suggestion":"90kg","muscle_group":"Costa","technique_notes":"Amplitude"},{"name":"Puxada Pronada","sets":4,"reps":"8-10","rpe":"7","rest_seconds":90,"weight_suggestion":"80kg","muscle_group":"Dorsal","technique_notes":"Controlado"},{"name":"Crucifixo Inverso","sets":3,"reps":"10-12","rpe":"7","rest_seconds":60,"weight_suggestion":"70kg","muscle_group":"Deltoides","technique_notes":"Contração"},{"name":"Face Pull","sets":3,"reps":"12-15","rpe":"6","rest_seconds":60,"weight_suggestion":"40kg","muscle_group":"Deltoides","technique_notes":"Saúde"},{"name":"Rosca Inclinada","sets":4,"reps":"8-10","rpe":"7","rest_seconds":90,"weight_suggestion":"28kg","muscle_group":"Biceps","technique_notes":"Excentrica"},{"name":"Rosca Concentrada","sets":3,"reps":"10-12","rpe":"7","rest_seconds":60,"weight_suggestion":"22kg","muscle_group":"Biceps","technique_notes":"Máxima"}]},{"day":4,"name":"LOWER B","type":"leg","estimated_duration_minutes":75,"estimated_total_sets":21,"exercises":[{"name":"Agachamento Bulgaro","sets":4,"reps":"6-8","rpe":"8","rest_seconds":120,"weight_suggestion":"35kg","muscle_group":"Quadriceps","technique_notes":"Unilateral"},{"name":"Leg Press","sets":4,"reps":"8-10","rpe":"7","rest_seconds":90,"weight_suggestion":"140kg","muscle_group":"Quadriceps","technique_notes":"Volume"},{"name":"Stiff Leg Deadlift","sets":4,"reps":"6-8","rpe":"8","rest_seconds":120,"weight_suggestion":"60kg","muscle_group":"Posterior","technique_notes":"Amplitude"},{"name":"Leg Curl","sets":3,"reps":"10-12","rpe":"7","rest_seconds":60,"weight_suggestion":"70kg","muscle_group":"Posterior","technique_notes":"Isolamento"},{"name":"Leg Extension 2","sets":3,"reps":"10-12","rpe":"7","rest_seconds":60,"weight_suggestion":"75kg","muscle_group":"Quadriceps","technique_notes":"Contração"},{"name":"Panturrilha Sentado 2","sets":3,"reps":"12-15","rpe":"6","rest_seconds":45,"weight_suggestion":"55kg","muscle_group":"Panturrilha","technique_notes":"Pico"}]}]}'''
        
        # ============================================================
        # LOOP: Até 3 tentativas
        # ============================================================
        
        treino = None
        validacao = None
        
        for tentativa in range(1, 4):
            print(f"\n📝 TENTATIVA {tentativa}/3")
            print(f"{'─'*60}")
            
            # ============================================================
            # STAGE 1: Gerar ou Refinar
            # ============================================================
            
            if tentativa == 1:
                prompt_gen = f"Retorne este JSON exato:\n{json_template}"
                print("Gerando treino...")
            else:
                # Pedir refinamento baseado em erros anteriores
                erros = validacao.get('erros', [])
                print(f"Refinando (erros: {', '.join(erros[:2])}...)")
                prompt_gen = f"""Corrija este JSON conforme os erros:

Erros encontrados:
{json.dumps(erros, ensure_ascii=False)}

JSON original:
{json.dumps(treino, ensure_ascii=False)[:500]}

Retorne o JSON CORRIGIDO e completo:
{json_template}"""
            
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-opus-4-6", "max_tokens": 4000, "messages": [{"role": "user", "content": prompt_gen}]},
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"❌ API error")
                if tentativa == 3:
                    return jsonify({"error": "API error"}), 500
                continue
            
            try:
                treino_text = response.json()['content'][0]['text']
                treino = parse_json_clean(treino_text)
                print(f"✓ Treino gerado/refinado")
            except Exception as e:
                print(f"❌ Parse error")
                if tentativa == 3:
                    return jsonify({"error": f"Parse error: {str(e)}"}), 500
                continue
            
            # ============================================================
            # STAGE 2: Validação Rigorosa
            # ============================================================
            
            prompt_val = f"""Valide RIGOROSAMENTE este treino:

{json.dumps(treino)[:800]}

Critérios OBRIGATÓRIOS:
1. Exatamente 4 workouts (UPPER A/B, LOWER A/B)?
2. Cada workout tem 6+ exercícios?
3. Total séries >= 90?
4. Cada exercício tem: name, sets, reps, rpe, rest_seconds, weight_suggestion, muscle_group, technique_notes?
5. Push >= 25 séries? Pull >= 25 séries?
6. Periodização definida?

Retorne JSON:
{{"status":"APROVADO","score":90,"motivo":"OK"}}
OU
{{"status":"FALHOU","score":40,"erros":["erro1","erro2"]}}"""
            
            print("Validando...")
            
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-opus-4-6", "max_tokens": 800, "messages": [{"role": "user", "content": prompt_val}]},
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"❌ Validation API error")
                if tentativa == 3:
                    return jsonify({"error": "Validation error"}), 500
                continue
            
            try:
                val_text = response.json()['content'][0]['text']
                validacao = parse_json_clean(val_text)
            except:
                validacao = {"status": "FALHOU", "score": 0, "erros": ["Erro de parsing validação"]}
            
            status = validacao.get('status', 'FALHOU')
            score = validacao.get('score', 0)
            
            print(f"Score: {score}/100 | {status}")
            
            # ============================================================
            # Se APROVADO: Retornar!
            # ============================================================
            
            if status == 'APROVADO' and score >= 80:
                print(f"\n✅ TREINO APROVADO NA TENTATIVA {tentativa}!")
                print(f"{'='*60}\n")
                
                return jsonify({
                    "status": "success",
                    "treino": treino,
                    "validacao": validacao,
                    "tentativas": tentativa
                }), 201
            
            # Se FALHOU: mostrar erros e tentar novamente
            erros = validacao.get('erros', [])
            if len(erros) > 0:
                print(f"Erros: {erros[0]}")
        
        # ============================================================
        # FALHOU após 3 tentativas
        # ============================================================
        
        print(f"\n❌ FALHA FINAL após 3 tentativas")
        print(f"{'='*60}\n")
        
        return jsonify({
            "status": "error",
            "message": "Não consegui gerar treino válido",
            "ultima_validacao": validacao,
            "tentativas": 3
        }), 500
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/sessions', methods=['GET', 'POST', 'OPTIONS'])
def sessions():
    return '', 204 if request.method == 'OPTIONS' else jsonify({"status": "ok"}), 200

@app.route('/api/analyses', methods=['GET', 'POST', 'OPTIONS'])
def analyses():
    return '', 204 if request.method == 'OPTIONS' else jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"\n🚀 TREINO PRO\n")
    app.run(host='0.0.0.0', port=port, debug=False)
