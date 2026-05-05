#!/usr/bin/env python3
"""
TREINO PRO - API Server com Supabase
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
# IMPORTS
# ============================================================

load_dotenv()

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)
CORS(app)

# ============================================================
# CONFIGURAÇÃO SUPABASE
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://bldwvlnorigxqdvdqfsu.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsZHd2bG5vcmlneHFkdmRxZnN1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NDcwMTMsImV4cCI6MjA5MzUyMzAxM30.zKIiRWpWNlD08ugDqqOoaiUuMTnvEmzQFbSSN1z93aQ"

supabase: Client = None

if SUPABASE_AVAILABLE:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase inicializado!")
    except Exception as e:
        print(f"❌ Erro Supabase: {e}")
        supabase = None
else:
    print("❌ Supabase SDK não disponível")

# ============================================================
# CLIENTE ANTHROPIC
# ============================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

client = None
if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        print("✅ Anthropic inicializado!")
    except Exception as e:
        print(f"❌ Erro Anthropic: {e}")

# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def index():
    """Root endpoint"""
    return jsonify({
        "app": "Treino Pro API",
        "status": "ok",
        "version": "6.0",
        "supabase_connected": supabase is not None,
        "claude_available": client is not None,
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
    """Health check"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "supabase_connected": supabase is not None,
        "claude_available": client is not None,
        "api_key_set": bool(ANTHROPIC_API_KEY)
    }), 200


@app.route("/webhook/session", methods=["POST"])
def webhook_session():
    """Receber treino e armazenar no Supabase"""
    try:
        data = request.get_json()

        if not data or "session_id" not in data:
            return jsonify({"error": "session_id required"}), 400

        # Salvar no Supabase
        if supabase:
            try:
                session_record = {
                    "session_id": data.get("session_id"),
                    "date": data.get("date"),
                    "time": data.get("time", ""),
                    "workout": data.get("workout"),
                    "exercises": json.dumps(data.get("exercises", [])),
                    "energy": data.get("energy"),
                    "sleep": data.get("sleep"),
                    "notes": data.get("notes", "")
                }

                response = supabase.table("sessions").insert(session_record).execute()
                print(f"✅ Sessão salva no Supabase: {data.get('session_id')}")
            except Exception as e:
                print(f"❌ Erro ao salvar no Supabase: {e}")

        # Analisar com Claude
        analysis = ""
        if client:
            analysis = analyze_with_claude(data)

            # Salvar análise no Supabase
            if supabase:
                try:
                    analysis_record = {
                        "session_id": data.get("session_id"),
                        "date": data.get("date"),
                        "workout": data.get("workout"),
                        "analysis": analysis,
                        "model": "claude-sonnet-4-6"
                    }
                    supabase.table("analyses").insert(analysis_record).execute()
                    print(f"✅ Análise salva no Supabase: {data.get('session_id')}")
                except Exception as e:
                    print(f"❌ Erro ao salvar análise: {e}")
        else:
            analysis = "⚠️ Claude não disponível"

        return jsonify({
            "status": "received",
            "session_id": data.get("session_id"),
            "analysis": analysis,
            "supabase_saved": supabase is not None
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e),
            "type": type(e).__name__
        }), 500


def analyze_with_claude(session):
    """Analisar com Claude"""
    if not client:
        return "Claude não disponível"

    try:
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

💪 EXERCÍCIOS:
{exercises_text}

🎯 Forneça:
1. Status (✅ OK / ⚠️ ATENÇÃO / 🚨 CRÍTICO)
2. Pontos positivos (máx 3)
3. Recomendações (máx 3)
4. Próximos passos
"""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )

        analysis = ""
        if response.content:
            for block in response.content:
                if hasattr(block, "text"):
                    analysis += block.text

        return analysis if analysis else "Análise gerada"

    except Exception as e:
        return f"❌ Erro: {str(e)}"


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """Retornar sessões do Supabase"""
    if not supabase:
        return jsonify({"error": "Supabase not connected"}), 500

    try:
        response = supabase.table("sessions").select("*").order("created_at", desc=True).limit(10).execute()
        return jsonify({
            "total": len(response.data),
            "sessions": response.data
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysis", methods=["GET"])
def get_analysis():
    """Retornar análises do Supabase"""
    if not supabase:
        return jsonify({"error": "Supabase not connected"}), 500

    try:
        response = supabase.table("analyses").select("*").order("created_at", desc=True).limit(10).execute()
        return jsonify({
            "total": len(response.data),
            "analyses": response.data
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Retornar estatísticas"""
    if not supabase:
        return jsonify({"error": "Supabase not connected"}), 500

    try:
        sessions_response = supabase.table("sessions").select("*").execute()
        analyses_response = supabase.table("analyses").select("*").execute()

        sessions = sessions_response.data
        if sessions:
            recent = sessions[-7:]
            avg_energy = sum(s.get("energy", 5) for s in recent) / len(recent) if recent else 0
            avg_sleep = sum(s.get("sleep", 7) for s in recent) / len(recent) if recent else 0
        else:
            avg_energy = 0
            avg_sleep = 0

        return jsonify({
            "total_sessions": len(sessions),
            "total_analyses": len(analyses_response.data),
            "avg_energy_7d": round(avg_energy, 1),
            "avg_sleep_7d": round(avg_sleep, 1),
            "supabase_connected": True
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": str(e)}), 500


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🎯 TREINO PRO - API + SUPABASE")
    print("="*60)
    print(f"✅ Supabase: {'Conectado' if supabase else 'ERRO'}")
    print(f"✅ Claude: {'Disponível' if client else 'NÃO'}")
    print(f"✅ API Key: {'Sim' if ANTHROPIC_API_KEY else 'NÃO'}")
    print("="*60 + "\n")
