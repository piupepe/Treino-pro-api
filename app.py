#!/usr/bin/env python3
"""
TREINO PRO - API Server (Production Ready)
Render.com Deployment
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from datetime import datetime
import uuid
from dotenv import load_dotenv

# ============================================================
# IMPORTS & CONFIG
# ============================================================

load_dotenv()

# Importar Anthropic corretamente
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("❌ Anthropic não importado")

# ============================================================
# INICIALIZAR APP
# ============================================================

app = Flask(__name__)
CORS(app)

# ============================================================
# CLIENTE ANTHROPIC
# ============================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    print("❌ ANTHROPIC_API_KEY não configurada")
    client = None
elif not ANTHROPIC_AVAILABLE:
    print("❌ Anthropic SDK não disponível")
    client = None
else:
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        print("✅ Anthropic Client inicializado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao inicializar Anthropic: {e}")
        client = None

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
        "version": "4.0",
        "anthropic_available": client is not None,
        "endpoints": {
            "health": "GET /health",
            "webhook": "POST /webhook/session",
            "sessions": "GET /api/sessions",
            "analysis": "GET /api/analysis",
            "stats": "GET /api/stats"
        }
    }), 200


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "sessions": len(DATA["sessions"]),
        "analyses": len(DATA["analysis"]),
        "claude_available": client is not None,
        "api_key_set": bool(ANTHROPIC_API_KEY)
    }), 200


@app.route("/webhook/session", methods=["POST"])
def webhook_session():
    """Receber dados de treino e analisar com Claude"""
    try:
        data = request.get_json()

        # Validar dados
        if not data:
            return jsonify({"error": "no data received"}), 400

        if "session_id" not in data:
            return jsonify({"error": "session_id required"}), 400

        # Armazenar sessão
        data["received_at"] = datetime.now().isoformat()
        DATA["sessions"].append(data)

        # Analisar com Claude
        if client:
            analysis = analyze_with_claude(data)
        else:
            analysis = "⚠️ Claude não disponível - configure ANTHROPIC_API_KEY"

        # Armazenar análise
        DATA["analysis"].append({
            "session_id": data.get("session_id"),
            "date": data.get("date"),
            "workout": data.get("workout"),
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis
        })

        return jsonify({
            "status": "received",
            "session_id": data.get("session_id"),
            "analysis": analysis,
            "claude_available": client is not None
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Exception: {str(e)}",
            "type": type(e).__name__
        }), 500


def analyze_with_claude(session):
    """Analisar sessão com Claude"""
    
    if not client:
        return "❌ Cliente Claude não inicializado"

    try:
        # Construir prompt
        exercises_text = "\n".join([
            f"  • {ex.get('name')}: {ex.get('weight')}kg - Séries: {ex.get('sets', [])}"
            for ex in session.get("exercises", [])
        ])

        prompt = f"""Analise concisamente esta sessão de treino:

📋 SESSÃO
• Treino: {session.get('workout')}
• Data: {session.get('date')}
• Energia: {session.get('energy')}/10
• Sono: {session.get('sleep')}h
• Notas: {session.get('notes', 'N/A')}

💪 EXERCÍCIOS:
{exercises_text}

🎯 ANÁLISE:
Forneça em formato estruturado:
1. Status geral (✅ OK / ⚠️ ATENÇÃO / 🚨 CRÍTICO)
2. Pontos positivos (máx 3)
3. Recomendações (máx 3)
4. Próximos passos
"""

        # Chamar Claude
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=800,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extrair resposta
        analysis_text = ""
        if response.content:
            for block in response.content:
                if hasattr(block, "text"):
                    analysis_text += block.text

        return analysis_text if analysis_text else "Análise gerada (sem conteúdo)"

    except Exception as e:
        error_msg = f"❌ Erro na análise: {str(e)}"
        print(error_msg)
        return error_msg


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
            "total_sessions": 0,
            "avg_energy": 0,
            "avg_sleep": 0,
            "total_analyses": len(DATA["analysis"])
        }), 200

    recent = sessions[-7:]
    avg_energy = sum(s.get("energy", 5) for s in recent) / len(recent) if recent else 0
    avg_sleep = sum(s.get("sleep", 7) for s in recent) / len(recent) if recent else 0

    return jsonify({
        "total_sessions": len(sessions),
        "avg_energy_7d": round(avg_energy, 1),
        "avg_sleep_7d": round(avg_sleep, 1),
        "total_analyses": len(DATA["analysis"]),
        "claude_available": client is not None
    }), 200


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "server error", "message": str(e)}), 500


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":
    # Não usar app.run() aqui - Gunicorn vai rodar
    print("\n" + "="*60)
    print("🎯 TREINO PRO - API SERVER")
    print("="*60)
    print(f"✅ API Key: {'Configurada' if ANTHROPIC_API_KEY else 'NÃO CONFIGURADA'}")
    print(f"✅ Claude: {'Disponível' if client else 'NÃO DISPONÍVEL'}")
    print("="*60 + "\n")
