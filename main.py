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

# Chaves de API do .env
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY1")
MISTRAL_KEY = os.getenv("MISTRAL_KEY")

# URLs das APIs
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


def call_gemini(text):
    """Função para chamar a API do Gemini"""
    if not GEMINI_API_KEY:
        raise Exception("Gemini API key not configured")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": text}
                ]
            }
        ]
    }

    response = requests.post(
        f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
        headers={'Content-Type': 'application/json'},
        json=payload
    )

    response.raise_for_status()

    gemini_response = response.json()
    if (gemini_response.get('candidates') and
            gemini_response['candidates'][0].get('content') and
            gemini_response['candidates'][0]['content'].get('parts') and
            gemini_response['candidates'][0]['content']['parts'][0].get('text')):
        return gemini_response['candidates'][0]['content']['parts'][0]['text'].strip()

    raise Exception("No text found in Gemini response")


def call_mistral(text, max_retries=3):
    """Função para chamar a API da Mistral com retry"""
    if not MISTRAL_KEY:
        raise Exception("Mistral API key not configured")

    headers = {
        "Authorization": f"Bearer {MISTRAL_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mistral-tiny",  # Você pode usar 'mistral-small' ou 'mistral-medium'
        "messages": [
            {"role": "user", "content": text}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(MISTRAL_API_URL, headers=headers, json=payload, timeout=30)

            if response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Mistral rate limited. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
                continue

            response.raise_for_status()

            mistral_response = response.json()
            if (mistral_response.get('choices') and
                    mistral_response['choices'][0].get('message') and
                    mistral_response['choices'][0]['message'].get('content')):
                return mistral_response['choices'][0]['message']['content'].strip()

            raise Exception("No text found in Mistral response")

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"Mistral timeout. Retrying {attempt + 1}/{max_retries}")
                time.sleep(1)
                continue
            else:
                raise Exception("Mistral timeout after multiple attempts")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Mistral API request failed: {str(e)}")

    raise Exception("Mistral retries exceeded")


@app.route('/api/gemini', methods=['POST'])
def call_ai():
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({"error": "Text input is required"}), 400

        text = data['text']
        use_mistral = data.get('mistral', False)

        # Forçar uso do Mistral
        if use_mistral:
            try:
                response_text = call_mistral(text)
                return response_text
            except Exception as e:
                return jsonify({"error": f"Mistral API error: {str(e)}"}), 500

        # Usa Gemini por padrão
        try:
            response_text = call_gemini(text)
            return response_text
        except Exception as gemini_error:
            print(f"Gemini failed: {str(gemini_error)}. Trying Mistral as failover...")

            # Failover: tenta Mistral se Gemini falhar
            try:
                response_text = call_mistral(text)
                return response_text
            except Exception as mistral_error:
                return jsonify({
                    "error": "Both AI services failed",
                    "gemini_error": str(gemini_error),
                    "mistral_error": str(mistral_error)
                }), 500

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500






COHERE_KEY = os.getenv("COHERE_KEY")
COHERE_API_URL = "https://api.cohere.ai/v1/chat"



def call_cohere(text):
    """Função para chamar a API da Cohere"""
    if not COHERE_KEY:
        raise Exception("Cohere API key not configured")

    headers = {
        "Authorization": f"Bearer {COHERE_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "message": text,
        "model": "command-r",  # Você pode mudar para outro como 'command-r-plus' se preferir
        "temperature": 0.7,
        "max_tokens": 1000
    }

    response = requests.post(COHERE_API_URL, headers=headers, json=payload)

    response.raise_for_status()

    data = response.json()
    if 'text' in data:
        return data['text'].strip()

    raise Exception("No text found in Cohere response")




@app.route('/cohere', methods=['POST'])
def call_cohere_endpoint():
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({"error": "Text input is required"}), 400

        text = data['text']
        response_text = call_cohere(text)
        return response_text

    except Exception as e:
        return jsonify({"error": f"Cohere API error: {str(e)}"}), 500





















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
        return send_file(audio, mimetype="audio/mp3")
    except Exception as e:
        print(f"❌ Falha total: {e}")
        return jsonify({"error": "Erro ao gerar áudio com todos os serviços"}), 500































if __name__ == '__main__':
    app.run(debug=True)
