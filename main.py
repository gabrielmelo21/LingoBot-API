import json
import os
import random
from io import BytesIO
import edge_tts
import asyncio
import io


import openai
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from translate import Translator
from gtts import gTTS

from flask_cors import CORS



from database import db
from routes import routes



# Carrega as variáveis de ambiente do .env
load_dotenv()

# Inicializa o cliente OpenAI corretamente na versão 1.0+
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



# Inicializa o Flask
app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas





basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'database', 'database.db')}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Inicializa o banco de dados
db.init_app(app)

# Registra as rotas no app Flask
app.register_blueprint(routes)

# Cria o banco de dados antes de rodar
with app.app_context():
    db.create_all()



@app.route('/', methods=['GET'])
def hello():
    return "Hello World!"





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



# temas.json é para temas de redação
# textos.json são textos para gerar audio para listening
# textos_longos são para leitura reading







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
