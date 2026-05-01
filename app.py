#!/usr/bin/env python3
"""
TREINO PRO - API Server (Production Ready for Render)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from datetime import datetime
from anthropic import Anthropic
import uuid
from dotenv import load_dotenv

# ============================================================
# CONFIG
# ============================================================

load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    print("❌ ANTHROPIC_API_KEY não configurada")
    client = None
else:
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        print("✅ Anthropic inicializado")
    except Exception as e:
        print(f"❌ Erro Anthropic: {e}")
        client = None

app = Flask(__name__)
CORS(app)

# ============================================================
# STORAGE
# ============================================================

DATA = {
    "sessions": [],
    "analysis": []
}

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def index():
    """Root endpoint"""
    return jsonify({
        "app": "Treino Pro API",
        "status": "ok",
        "endpoints": {
            "health": "/health",
            "webhook": "POST /webhook/session",
            "sessions": "GET /api/sessions",
            "analysis": "GET /api/analysis",
            "stats": "GET /api/stats"
        }
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "sessions": len(DATA["sessions"]),
        "analysis": len(DATA["analysis"]),
        "api_configured": bool(ANTHROPIC_API_KEY)
    }), 200


@app.route("/webhook/session", methods=["POST"])
def webhook_session():
    """Receber dados de treino"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "no data"}), 400

        if "session_id" not in data:
            return jsonify({"error": "session_id required"}), 400

        # Armazenar sessão
        data["received_at"] = datetime.now().isoformat()
        DATA["sessions"].append(data)

        # Analisar com Claude
        analysis = analyze_with_claude(data)

        # Armazenar análise
        DATA["analysis"].append({
            "session_id": data["session_id"],
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis
        })

        return jsonify({
            "status": "received",
            "session_id": data["session_id"],
            "analysis": analysis
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def analyze_with_claude(session):
    """Analisar sessão com Claude"""
    if not client:
        return "Claude não disponível"

    try:
        prompt = f"""
Analise esta sessão de treino:

Treino: {session.get('workout')}
Data: {session.get('date')}
Energia: {session.get('energy')}/10
Sono: {session.get('sleep')}h

Exercícios:
{json.dumps(session.get('exercises', []), indent=2, ensure_ascii=False)}

Notas: {session.get('notes', 'N/A')}

Forneça análise concisa com:
1. Status geral (OK/ATENÇÃO/CRÍTICO)
2. Pontos positivos
3. Recomendações
4. Próximos passos
"""

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.content[0].text

    except Exception as e:
        return f"Erro na análise: {str(e)}"


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """Retornar sessões"""
    return jsonify({
        "total": len(DATA["sessions"]),
        "sessions": DATA["sessions"][-10:]
    }), 200


@app.route("/api/analysis", methods=["GET"])
def get_analysis():
    """Retornar análises"""
    return jsonify({
        "total": len(DATA["analysis"]),
        "analyses": DATA["analysis"][-10:]
    }), 200


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Retornar estatísticas"""
    sessions = DATA["sessions"]

    if not sessions:
        return jsonify({
            "total": 0,
            "avg_energy": 0,
            "avg_sleep": 0
        }), 200

    recent = sessions[-7:]
    avg_energy = sum(s.get("energy", 5) for s in recent) / len(recent)
    avg_sleep = sum(s.get("sleep", 7) for s in recent) / len(recent)

    return jsonify({
        "total_sessions": len(sessions),
        "avg_energy_7d": round(avg_energy, 1),
        "avg_sleep_7d": round(avg_sleep, 1),
        "total_analysis": len(DATA["analysis"])
    }), 200


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "server error"}), 500


# ============================================================
# EXPORT FOR GUNICORN
# ============================================================

# Gunicorn vai usar isso para rodar
# Não use app.run() aqui!
