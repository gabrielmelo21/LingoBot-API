import json
import os
import random

import edge_tts
import asyncio
import io

import openai

from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

from sqlalchemy import create_engine, text
from translate import Translator


from flask_cors import CORS

from database import db
from routes import routes

# temas.json é para temas de redação
# textos.json são textos para gerar audio para listening
# textos_longos são para leitura reading


# Carrega as variáveis de ambiente do .env
load_dotenv()

# Inicializa o cliente OpenAI corretamente na versão 1.0+
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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


#basedir = os.path.abspath(os.path.dirname(__file__))
#app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'database', 'database.db')}"
#app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False




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

# Registra as rotas no app Flask
app.register_blueprint(routes)

# Cria o banco de dados antes de rodar
with app.app_context():
    db.create_all()




@app.route("/",  methods=['GET'])
def teste_db():
    try:
        result = db.session.execute(text("SELECT 'Conexão bem-sucedida!'")).fetchall()
        return str(result)
    except Exception as e:
        return str(e)



@app.route("/gerar-jwt", methods=["GET"])
def gerar_jwt():
    token = create_access_token(identity={"id": 1, "nome": "Gabriel", "email": "gabriel@gmail.com"})
    return jsonify({"token": token})


@app.route("/teste-jwt", methods=["GET"])
@jwt_required()  # Requer um token JWT válido
def teste_jwt():
    usuario = get_jwt_identity()  # Obtém a identidade do usuário do token
    return jsonify({"mensagem": f"JWT válido! Usuário: {usuario}"}), 200






@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "Arquivo sem nome"}), 400

    try:
        # Converte o arquivo para um formato compatível
        audio_file = io.BytesIO(file.read())
        audio_file.name = file.filename  # Atribuir nome ao arquivo

        # Enviar para a OpenAI Whisper API
        response = client.audio.transcriptions.create(
            model="whisper-1",  # Modelo Whisper
            file=audio_file,
            response_format="json"
        )

        return jsonify({"text": response.text}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500












def sendPrompt(prompt):
    """Envia um prompt para a OpenAI e retorna a resposta"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Ou outro modelo disponível
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return str(e)


@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint que recebe um prompt e retorna a resposta da OpenAI"""
    data = request.json
    prompt = data.get("prompt", "")

    if not prompt:
        return jsonify({"error": "Prompt é obrigatório"}), 400

    response = sendPrompt(prompt)
    print(response)
    return jsonify({"response": response})


# Carregar o arquivo JSON com os textos
with open('textos.json', 'r', encoding='utf-8') as file:
    textos = json.load(file)


@app.route('/get-text', methods=['POST'])
def get_text():
    # Pega a dificuldade enviada pelo usuário
    data = request.get_json()

    # Verifica se a dificuldade foi fornecida e está correta
    difficulty = data.get('difficulty')

    if difficulty not in textos:
        return jsonify({'error': 'Dificuldade inválida. Escolha entre easy, medium ou hard.'}), 400

    # Escolhe um texto aleatório da dificuldade solicitada
    selected_text = random.choice(textos[difficulty])

    return jsonify({'text': selected_text})


# Carregar o arquivo JSON com os textos
with open('temas.json', 'r', encoding='utf-8') as file:
    temas = json.load(file)


@app.route('/get-temas', methods=['POST'])
def get_temas():
    # Pega a dificuldade enviada pelo usuário
    data = request.get_json()

    # Verifica se a dificuldade foi fornecida e está correta
    difficulty = data.get('difficulty')

    if difficulty not in temas:
        return jsonify({'error': 'Dificuldade inválida. Escolha entre easy, medium ou hard.'}), 400

    # Escolhe um texto aleatório da dificuldade solicitada
    selected_tema = random.choice(temas[difficulty])

    return jsonify({'text': selected_tema})


# Carregar o arquivo JSON com os textos
with open('textos_longos.json', 'r', encoding='utf-8') as file:
    long_text = json.load(file)


@app.route('/get-long-texts', methods=['POST'])
def get_long_texts():
    # Pega a dificuldade enviada pelo usuário
    data = request.get_json()

    # Verifica se a dificuldade foi fornecida e está correta
    difficulty = data.get('difficulty')

    if difficulty not in long_text:
        return jsonify({'error': 'Dificuldade inválida. Escolha entre easy, medium ou hard.'}), 400

    # Escolhe um texto aleatório da dificuldade solicitada
    selected_long_text = random.choice(long_text[difficulty])

    return jsonify({'text': selected_long_text})


async def generate_tts(text):
    voice = "en-US-ChristopherNeural"  # Outra voz masculina robótica
    tts = edge_tts.Communicate(text, voice)

    audio_file = io.BytesIO()
    temp_filename = "output.mp3"  # Nome temporário do arquivo

    await tts.save(temp_filename)  # Salvar em um arquivo

    with open(temp_filename, "rb") as f:
        audio_file.write(f.read())  # Copiar para BytesIO

    audio_file.seek(0)
    return audio_file


@app.route('/tts', methods=['POST'])
def tts():
    data = request.get_json()
    text = data.get('text', '')

    if not text:
        return jsonify({"error": "Texto é obrigatório"}), 400

    audio_file = asyncio.run(generate_tts(text))
    return send_file(audio_file, mimetype='audio/mp3')


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


if __name__ == '__main__':
    app.run(debug=True)
