import os
import tempfile
import edge_tts
import asyncio
import io

import requests
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




ELEVENLABS_KEY1 = os.getenv("ELEVENLABS_KEY1")
ELEVENLABS_KEY2 = os.getenv("ELEVENLABS_KEY2")



@app.route("/",  methods=['GET'])
def teste_db():
    try:
        # Debug - remova depois de testar
        print("ELEVENLABS_KEY1 carregada:", ELEVENLABS_KEY1 is not None)
        print("ELEVENLABS_KEY2 carregada:", ELEVENLABS_KEY2 is not None)

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


def get_default_voice_id():
    """
    Voice IDs públicos conhecidos da ElevenLabs
    EXAVITQu4vr4xnSDxMaL = Bella (feminina, inglês)
    """
    return "EXAVITQu4vr4xnSDxMaL"


def get_available_voices(api_key):
    """Busca vozes disponíveis para validar se a chave funciona"""
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            voices = response.json()
            return voices.get("voices", [])
        else:
            print(f"Erro ao buscar vozes: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Erro ao conectar para buscar vozes: {e}")
        return []


async def generate_tts_google(text):
    voice = "en-US-ChristopherNeural"
    tts = edge_tts.Communicate(text, voice)
    audio_file = io.BytesIO()
    temp_filename = "output.mp3"

    await tts.save(temp_filename)

    with open(temp_filename, "rb") as f:
        audio_file.write(f.read())

    audio_file.seek(0)
    return audio_file


def generate_tts_elevenlabs(text, api_key):
    """
    Gera TTS usando ElevenLabs com parâmetros corretos da documentação oficial
    """
    if not api_key:
        print("API key não fornecida")
        return None

    voice_id = get_default_voice_id()

    # URL correta conforme documentação oficial
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    # Dados conforme documentação oficial da ElevenLabs
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",  # Modelo padrão recomendado
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)

        # Debug detalhado dos erros
        print(f"ElevenLabs Status: {response.status_code}")
        print(f"Voice ID: {voice_id}")
        print(f"API Key (primeiros 10): {api_key[:10]}...")

        if response.status_code == 401:
            print("❌ Erro 401: Chave API inválida, expirada ou sem permissão")
            print("Response:", response.text)
            return None
        elif response.status_code == 422:
            print("❌ Erro 422: Parâmetros inválidos na requisição")
            print("Response:", response.text)
            return None
        elif response.status_code == 429:
            print("❌ Erro 429: Rate limit atingido ou cota excedida")
            print("Response:", response.text)
            return None
        elif response.status_code == 400:
            print("❌ Erro 400: Requisição malformada")
            print("Response:", response.text)
            return None

        # Levanta exceção para outros códigos de erro
        response.raise_for_status()

        # Verifica se realmente recebeu áudio
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('audio/'):
            print(f"❌ Resposta não é áudio. Content-Type: {content_type}")
            print("Response preview:", response.text[:200] if response.text else "No text")
            return None

        print("✅ ElevenLabs TTS gerado com sucesso!")
        audio_file = io.BytesIO(response.content)
        audio_file.seek(0)
        return audio_file

    except requests.exceptions.Timeout:
        print(f"❌ Timeout na requisição para ElevenLabs")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão com ElevenLabs (key {api_key[:10]}...): {e}")
        return None
    except Exception as e:
        print(f"❌ Erro inesperado com ElevenLabs (key {api_key[:10]}...): {e}")
        return None


@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "Texto é obrigatório"}), 400

    print(f"\n=== Iniciando TTS para: '{text[:50]}...' ===")

    # Tenta primeira chave ElevenLabs
    if ELEVENLABS_KEY1:
        print("🔄 Tentando ElevenLabs KEY1...")
        audio = generate_tts_elevenlabs(text, ELEVENLABS_KEY1)
        if audio:
            print("✅ Sucesso com KEY1!")
            return send_file(audio, mimetype='audio/mp3')

    # Tenta segunda chave ElevenLabs
    if ELEVENLABS_KEY2:
        print("🔄 Tentando ElevenLabs KEY2...")
        audio = generate_tts_elevenlabs(text, ELEVENLABS_KEY2)
        if audio:
            print("✅ Sucesso com KEY2!")
            return send_file(audio, mimetype='audio/mp3')

    # Fallback para Edge TTS
    print("🔄 Fallback para Edge TTS...")
    try:
        audio = asyncio.run(generate_tts_google(text))
        print("✅ Sucesso com Edge TTS!")
        return send_file(audio, mimetype='audio/mp3')
    except Exception as e:
        print(f"❌ Erro no Edge TTS: {e}")
        return jsonify({"error": "Todos os serviços de TTS falharam"}), 500


# Função para testar as chaves (execute separadamente para debug)
def test_keys():
    """Função para testar as chaves ElevenLabs"""
    print("=== TESTE DAS CHAVES ELEVENLABS ===")

    if ELEVENLABS_KEY1:
        print(f"\n--- Testando KEY1 ({ELEVENLABS_KEY1[:15]}...) ---")
        voices = get_available_voices(ELEVENLABS_KEY1)
        if voices:
            print(f"✅ KEY1 OK - {len(voices)} vozes disponíveis")
            print(f"Primeira voz: {voices[0]['name']} (ID: {voices[0]['voice_id']})")
        else:
            print("❌ KEY1 FALHOU - Não conseguiu buscar vozes")

    if ELEVENLABS_KEY2:
        print(f"\n--- Testando KEY2 ({ELEVENLABS_KEY2[:15]}...) ---")
        voices = get_available_voices(ELEVENLABS_KEY2)
        if voices:
            print(f"✅ KEY2 OK - {len(voices)} vozes disponíveis")
            print(f"Primeira voz: {voices[0]['name']} (ID: {voices[0]['voice_id']})")
        else:
            print("❌ KEY2 FALHOU - Não conseguiu buscar vozes")


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

if __name__ == '__main__':
    app.run(debug=True)
