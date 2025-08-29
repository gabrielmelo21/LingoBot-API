import os
import tempfile
import time

import edge_tts
import asyncio
import io

import requests
from elevenlabs import ElevenLabs, VoiceSettings
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from sqlalchemy import create_engine, text, inspect
from translate import Translator
from flask_cors import CORS
from database import db
from flask_migrate import Migrate
from routes import routes
from ai_routes import ai
import assemblyai as aai
import json
from datetime import datetime
from ping_manager import PingManager



# Carrega as variáveis de ambiente do .env
load_dotenv()
api_key = os.getenv("ASSEMBLYAI_API_KEY")




# Configurar AssemblyAI
aai.settings.api_key = api_key


# Inicializa o Flask
app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_TOKEN_LOCATION"] = ["headers"]  # Garante que o token é buscado apenas nos headers
app.config["JWT_HEADER_NAME"] = "Authorization"  # Nome do header (padrão)
app.config["JWT_HEADER_TYPE"] = "Bearer"  # Tipo do token (padrão)

jwt = JWTManager(app)


@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({"erro": "Token inválido ou expirado"}), 401


@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({"erro": "Token ausente no header Authorization"}), 401



# Ajusta a string do banco de dados para garantir compatibilidade
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")


# Adiciona SSL se necessário
if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Evita conexões quebradas
    pool_recycle=300,  # Fecha conexões inativas após 5 minutos
    pool_timeout=30  # Tempo limite para obter uma nova conexão
)


app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# Inicializa o banco de dados
db.init_app(app)
migrate = Migrate(app, db)
# Registra as rotas no app Flask
app.register_blueprint(routes)
app.register_blueprint(ai)

# Cria o banco de dados antes de rodar
with app.app_context():
    db.create_all()





@app.route("/",  methods=['GET'])
def teste_db():
    PingManager.update_last_activity()

    try:
        inspector = inspect(engine)
        tabelas = inspector.get_table_names()

        if not tabelas:
            with app.app_context():
                db.create_all()
            return "Banco de dados e tabelas criados com sucesso na rota /!"
        elif "usuario" not in tabelas:
            with app.app_context():
                db.create_all()
            return "Tabela 'usuario' e outras tabelas ausentes criadas com sucesso na rota /."
        else:
            result = db.session.execute(text("SELECT 'Conexão bem-sucedida!'")).fetchall()
            print("hello world")
            return str(result)
    except Exception as e:
        return str(e)


@app.route("/ping",  methods=['GET'])
def ping_system():
    PingManager.update_last_activity()
    return 'ok'



@app.route("/criar-tabela-usuarios", methods=["GET"])
def criar_tabela_usuarios():
    PingManager.update_last_activity()


    inspector = inspect(engine)
    tabelas = inspector.get_table_names()

    if not tabelas:  # If no tables exist at all
        with app.app_context():
            db.create_all()
        return "Banco de dados e tabelas criados com sucesso!"
    elif "usuario" not in tabelas: # Check for 'usuario' table specifically
        with app.app_context():
            db.create_all()
        return "Tabela 'usuario' e outras tabelas ausentes criadas com sucesso."
    else:
        return "Tabelas do banco de dados já existem."














ELEVENLABS_KEY = os.getenv("ELEVENLABS_KEY1")

VOICE_IDS = [
    "TxGEqnHWrfWFTfGW9XjX",  # 0 - Josh
    "pNInz6obpgDQGcFmaJgB",  # 1 - Adam
    "onwK4e9ZLuTAKqWW03F9",  # 2 - James
    "yoZ06aMxZJJ28mfd3POQ",  # 3 - Sam
    "VR6AewLTigWG4xSOukaG",  # 4 - Arnold
    "EXAVITQu4vr4xnSDxMaL",  # 5 - Bella (feminina padrão)
]

async def generate_tts_google(text):
    tts = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    temp_filename = "output.mp3"
    await tts.save(temp_filename)
    with open(temp_filename, "rb") as f:
        buffer = io.BytesIO(f.read())
    buffer.seek(0)
    return buffer

def generate_tts_with_elevenlabs(api_key, text, voice_id):
    try:
        client = ElevenLabs(api_key=api_key)
        stream = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format="mp3_22050_32",
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True
            )
        )

        buffer = io.BytesIO()
        for chunk in stream:
            buffer.write(chunk)
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"❌ Falha com ElevenLabs: {e}")
        return None

@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text", "").strip()
    voice_index = data.get("voice", len(VOICE_IDS) - 1)  # Padrão: última voz
    premium = data.get("premium", False)

    if not text:
        return jsonify({"error": "Texto é obrigatório"}), 400

    if not isinstance(voice_index, int) or voice_index < 0 or voice_index >= len(VOICE_IDS):
        return jsonify({"error": "Índice de voz inválido"}), 400

    voice_id = VOICE_IDS[voice_index]
    print(f"🔊 Gerando TTS para: {text[:60]}... (voz {voice_index}) | Premium: {premium}")

    if premium:
        audio = generate_tts_with_elevenlabs(ELEVENLABS_KEY, text, voice_id)
        if audio:
            print("✅ Áudio gerado com ElevenLabs")
            return send_file(audio, mimetype="audio/mp3")

        print("⚠️ Falha com ElevenLabs, usando Google TTS como fallback...")

    try:
        audio = asyncio.run(generate_tts_google(text))
        PingManager.update_last_activity()
        return send_file(audio, mimetype="audio/mp3")
    except Exception as e:
        print(f"❌ Falha total: {e}")
        return jsonify({"error": "Erro ao gerar áudio com todos os serviços"}), 500



if __name__ == '__main__':
    app.run(debug=True)
