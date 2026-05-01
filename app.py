#!/usr/bin/env python3
"""
TREINO PRO - API SERVER (PRODUCTION READY)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime
import uuid
from dotenv import load_dotenv
import anthropic

# ============================================================
# CONFIGURAÇÃO
# ============================================================

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise RuntimeError("❌ ANTHROPIC_API_KEY não configurada")

# Cliente Anthropic (novo padrão)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

app = Flask(__name__)
CORS(app)

# ============================================================
# STORAGE (TEMPORÁRIO)
# ============================================================

DATA_STORAGE = {
    "sessions": [],
    "analysis_history": []
}

AGENT_CONVERSATION = []

# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "sessions": len(DATA_STORAGE["sessions"]),
        "analysis": len(DATA_STORAGE["analysis_history"])
    })

# ============================================================
# WEBHOOK - RECEBER SESSÃO
# ============================================================

@app.route("/webhook/session", methods=["POST"])
def receive_session():
    try:
        data = request.get_json()

        if not data or "session_id" not in data:
            return jsonify({"error": "session_id obrigatório"}), 400

        data["received_at"] = datetime.now().isoformat()

        DATA_STORAGE["sessions"].append(data)

        analysis = analyze_session(data)

        return jsonify({
            "status": "received",
            "session_id": data["session_id"],
            "analysis": analysis
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
# ANÁLISE
# ============================================================

def analyze_session(session):
    try:
        context = build_context(session)
        response = call_claude(context)

        record = {
            "id": str(uuid.uuid4()),
            "session_id": session["session_id"],
            "timestamp": datetime.now().isoformat(),
            "analysis": response
        }

        DATA_STORAGE["analysis_history"].append(record)

        return response

    except Exception as e:
        return f"Erro na análise: {str(e)}"

# ============================================================
# CONTEXTO
# ============================================================

def build_context(session):
    recent = DATA_STORAGE["sessions"][-7:]

    avg_energy = (
        sum(s.get("energy", 5) for s in recent) / len(recent)
        if recent else 0
    )

    avg_sleep = (
        sum(s.get("sleep", 7) for s in recent) / len(recent)
        if recent else 0
    )

    return f"""
Nova sessão de treino:

Treino: {session.get("workout")}
Data: {session.get("date")}
Energia: {session.get("energy")}/10
Sono: {session.get("sleep")}h

Média últimos dias:
Energia: {avg_energy:.1f}
Sono: {avg_sleep:.1f}

Analise performance, recuperação e recomende ajustes.
"""

# ============================================================
# CLAUDE
# ============================================================

def call_claude(prompt):
    system = """
Você é especialista em treinamento de hipertrofia.
Analise sessões de treino e dê recomendações objetivas.
"""

    response = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )

    output = ""
    for block in response.content:
        if hasattr(block, "text"):
            output += block.text

    return output.strip()

# ============================================================
# CONSULTAS
# ============================================================

@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    return jsonify(DATA_STORAGE["sessions"][-10:])


@app.route("/api/analysis", methods=["GET"])
def get_analysis():
    return jsonify(DATA_STORAGE["analysis_history"][-10:])


@app.route("/api/stats", methods=["GET"])
def get_stats():
    sessions = DATA_STORAGE["sessions"]

    if not sessions:
        return jsonify({"error": "sem dados"}), 404

    recent = sessions[-7:]

    avg_energy = sum(s.get("energy", 5) for s in recent) / len(recent)
    avg_sleep = sum(s.get("sleep", 7) for s in recent) / len(recent)

    return jsonify({
        "total_sessions": len(sessions),
        "avg_energy": round(avg_energy, 1),
        "avg_sleep": round(avg_sleep, 1)
    })

# ============================================================
# ENTRYPOINT (LOCAL)
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
