import os
import tempfile
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
import assemblyai as aai


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

# Cria o banco de dados antes de rodar
with app.app_context():
    db.create_all()





@app.route("/",  methods=['GET'])
def teste_db():
    try:

        result = db.session.execute(text("SELECT 'Conexão bem-sucedida!'")).fetchall()
        print("hello world")
        return str(result)
    except Exception as e:
        return str(e)







@app.route("/criar-tabela-usuarios", methods=["GET"])
def criar_tabela_usuarios():
    inspector = inspect(engine)
    tabelas = inspector.get_table_names()

    if "usuarios" in tabelas:
        return "Tabela 'usuarios' já existe."

    with app.app_context():
        db.create_all()

    return "Tabela 'usuarios' criada com sucesso."





@app.route('/translate', methods=['POST'])
def translate_text():
    """Recebe um texto e retorna a tradução para português"""
    data = request.get_json()
    text = data.get('text', '')

    if not text:
        return jsonify({"error": "Texto é obrigatório"}), 400

    try:
        translator = Translator(to_lang="pt")
        translation = translator.translate(text)
        print(translation)  # Apenas para depuração no console
        return jsonify({"text": translation})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files['file']

    # Salvar arquivo temporariamente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        file.save(tmp.name)
        audio_path = tmp.name

    try:
        config = aai.TranscriptionConfig(speech_model=aai.SpeechModel.best)
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_path)

        if transcript.status == "error":
            return jsonify({"error": transcript.error}), 500

        return jsonify({ "text": transcript.text })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        os.remove(audio_path)


GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY1")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


@app.route('/api/gemini', methods=['POST'])
def call_gemini():
    try:
        # Verifica se a chave API está configurada
        if not GEMINI_API_KEY:
            return jsonify({"error": "API key not configured"}), 500

        # Obtém os dados da requisição
        data = request.get_json()

        # Verifica se o texto foi fornecido
        if not data or 'text' not in data:
            return jsonify({"error": "Text input is required"}), 400

        # Prepara o payload para a API do Gemini
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": data['text']
                        }
                    ]
                }
            ]
        }

        # Faz a chamada para a API do Gemini
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers={'Content-Type': 'application/json'},
            json=payload
        )

        # Verifica se a resposta foi bem-sucedida
        response.raise_for_status()

        # Extrai apenas o texto da resposta
        gemini_response = response.json()
        if (gemini_response.get('candidates') and
                gemini_response['candidates'][0].get('content') and
                gemini_response['candidates'][0]['content'].get('parts') and
                gemini_response['candidates'][0]['content']['parts'][0].get('text')):
            text_response = gemini_response['candidates'][0]['content']['parts'][0]['text']
            return text_response.strip()  # Retorna apenas o texto limpo

        return jsonify({"error": "No text found in Gemini response"}), 500

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred"}), 500














ELEVENLABS_KEY1 = os.getenv("ELEVENLABS_KEY1")
ELEVENLABS_KEY2 = os.getenv("ELEVENLABS_KEY2")


# Mapeamento indexado das vozes disponíveis
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
        print(f"❌ Falha com API key ({api_key[:10]}...): {e}")
        return None


@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text", "").strip()
    voice_index = data.get("voice", len(VOICE_IDS) - 1)  # Padrão: Bella (última da lista)

    if not text:
        return jsonify({"error": "Texto é obrigatório"}), 400

    if not isinstance(voice_index, int) or voice_index < 0 or voice_index >= len(VOICE_IDS):
        return jsonify({"error": "Índice de voz inválido"}), 400

    voice_id = VOICE_IDS[voice_index]
    print(f"🔊 Gerando TTS para: {text[:60]}... (voz {voice_index})")

    # Tenta com as duas API keys do ElevenLabs
    for key in [ELEVENLABS_KEY1, ELEVENLABS_KEY2]:
        if key:
            audio = generate_tts_with_elevenlabs(key, text, voice_id)
            if audio:
                print("✅ Áudio gerado com ElevenLabs")
                return send_file(audio, mimetype="audio/mp3")

    # Fallback: Edge TTS
    print("⚠️ Falha com ElevenLabs, tentando Google TTS (edge-tts)...")
    try:
        audio = asyncio.run(generate_tts_google(text))
        return send_file(audio, mimetype="audio/mp3")
    except Exception as e:
        print(f"❌ Falha total: {e}")
        return jsonify({"error": "Erro ao gerar áudio com todos os serviços"}), 500


if __name__ == '__main__':
    app.run(debug=True)
