import os
import time

import openai
import requests
from flask import Blueprint, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

# Criação do Blueprint
ai = Blueprint("ai", __name__)

# API Keys
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY1")
MISTRAL_KEY = os.getenv("MISTRAL_KEY")
COHERE_KEY = os.getenv("COHERE_KEY")
openai.api_key = os.getenv("GROQ_KEY")
OPENROUTER_KEY = os.getenv('OPENROUTER_KEY')


# URLs das APIs
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
COHERE_API_URL = "https://api.cohere.ai/v1/chat"
openai.base_url = "https://api.groq.com/openai/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ===================== FUNÇÕES DE CADA IA =====================

def call_gemini(text):
    if not GEMINI_API_KEY:
        raise Exception("Gemini API key not configured")

    payload = {
        "contents": [
            {
                "parts": [{"text": text}]
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
    if not MISTRAL_KEY:
        raise Exception("Mistral API key not configured")

    headers = {
        "Authorization": f"Bearer {MISTRAL_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mistral-tiny",
        "messages": [{"role": "user", "content": text}],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(MISTRAL_API_URL, headers=headers, json=payload, timeout=30)
            if response.status_code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue

            response.raise_for_status()
            mistral_response = response.json()

            if (mistral_response.get('choices') and
                    mistral_response['choices'][0].get('message') and
                    mistral_response['choices'][0]['message'].get('content')):
                return mistral_response['choices'][0]['message']['content'].strip()

            raise Exception("No text found in Mistral response")

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                continue
            raise Exception(f"Mistral request failed: {str(e)}")


def call_cohere(text):
    if not COHERE_KEY:
        raise Exception("Cohere API key not configured")

    headers = {
        "Authorization": f"Bearer {COHERE_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "message": text,
        "model": "command-r",
        "temperature": 0.7,
        "max_tokens": 1000
    }

    response = requests.post(COHERE_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()

    if 'text' in data:
        return data['text'].strip()

    raise Exception("No text found in Cohere response")



client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_KEY"],
)

def call_groq(text):
    chat_completion = client.chat.completions.create(
        model= "meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "user", "content": text}
        ],
        temperature=0.7,
    )
    return chat_completion.choices[0].message.content


def call_openrouter(text):
    """
    Encapsula a lógica de chamada para a API do OpenRouter

    Args:
        text (str): Texto da pergunta/prompt do usuário

    Returns:
        str: Resposta da IA ou mensagem de erro
    """
    # Lista de modelos para tentar (em ordem de preferência)
    models_to_try = [
        "qwen/qwen3-235b-a22b-07-25:free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "microsoft/phi-3-mini-128k-instruct:free",
        "google/gemma-2-9b-it:free"
    ]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://lingobot-api.onrender.com",
        "X-Title": "Flask OpenRouter App"
    }

    for model in models_to_try:
        try:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.7
            }

            response = requests.post(
                OPENROUTER_URL,
                json=payload,
                headers=headers,
                timeout=30  # Timeout de 30 segundos
            )

            # Se a requisição foi bem sucedida
            if response.status_code == 200:
                data = response.json()

                # Extrai apenas o texto da resposta
                if 'choices' in data and len(data['choices']) > 0:
                    return data['choices'][0]['message']['content'].strip()
                else:
                    continue  # Tenta próximo modelo

            # Se deu 503, tenta próximo modelo
            elif response.status_code == 503:
                continue

            # Para outros erros, tenta próximo modelo mas registra o erro
            else:
                print(f"Modelo {model} retornou status {response.status_code}")
                continue

        except requests.exceptions.Timeout:
            print(f"Timeout ao tentar modelo {model}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"Erro de requisição com modelo {model}: {str(e)}")
            continue
        except Exception as e:
            print(f"Erro inesperado com modelo {model}: {str(e)}")
            continue

    # Se nenhum modelo funcionou
    return "Erro: Todos os modelos estão indisponíveis no momento. Tente novamente em alguns minutos."






# ===================== ROTAS =====================

@ai.route('/ai/gemini', methods=['POST'])
def call_ai():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Text input is required"}), 400

        text = data['text']
        use_mistral = data.get('mistral', False)
        use_cohere = data.get('cohere', False)
        use_groq = data.get('groq', False)

        # Forçar uso apenas do Mistral
        if use_mistral:
            try:
                return call_mistral(text)
            except Exception as e:
                return jsonify({"error": f"Mistral API error: {str(e)}"}), 500

        # Forçar uso apenas do Cohere
        if use_cohere:
            try:
                return call_cohere(text)
            except Exception as e:
                return jsonify({"error": f"Cohere API error: {str(e)}"}), 500

        # Forçar uso apenas do Groq
        if use_groq:
            try:
                return call_groq(text)
            except Exception as e:
                return jsonify({"error": f"Groq API error: {str(e)}"}), 500

        # Tentativa 1: Gemini
        try:
            return call_gemini(text)
        except Exception as gemini_error:
            print(f"Gemini failed: {str(gemini_error)}. Trying Mistral...")

            # Tentativa 2: Mistral
            try:
                return call_mistral(text)
            except Exception as mistral_error:
                print(f"Mistral failed: {str(mistral_error)}. Trying Cohere...")

                # Tentativa 3: Cohere
                try:
                    return call_cohere(text)
                except Exception as cohere_error:
                    print(f"Cohere failed: {str(cohere_error)}. Trying Groq...")

                    # Tentativa 4: Groq
                    try:
                        return call_groq(text)
                    except Exception as groq_error:
                        print(f"Groq failed: {str(groq_error)}. Trying OpenRouter...")

                        # Tentativa 5: OpenRouter
                        try:
                            return call_openrouter(text)
                        except Exception as openrouter_error:
                            return jsonify({
                                "error": "All AI services failed",
                                "gemini_error": str(gemini_error),
                                "mistral_error": str(mistral_error),
                                "cohere_error": str(cohere_error),
                                "groq_error": str(groq_error),
                                "openrouter_error": str(openrouter_error)
                            }), 500

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500



# ===================== COHERE =====================
@ai.route('/ai/cohere', methods=['POST'])
def cohere_route():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Text input is required"}), 400

        text = data['text']
        return call_cohere(text)

    except Exception as e:
        return jsonify({"error": f"Cohere error: {str(e)}"}), 500



# ===================== MISTRAL =====================
@ai.route('/ai/mistral', methods=['POST'])
def ask_mistral():
    data = request.get_json()

    if not data or "text" not in data:
        return jsonify({"error": "Campo 'text' obrigatório."}), 400

    text = data["text"]

    try:
        response = call_mistral(text)
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500







# ===================== GROQ =====================
@ai.route('/ai/groq', methods=['POST'])
def call_groq_endpoint():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Text input is required"}), 400

        text = data['text']
        return call_groq(text)

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

# ===================== OPENROUTER =====================
@ai.route('/ai/openrouter', methods=['POST'])
def ai_openrouter():
    """
    Endpoint para processar requisições de IA via OpenRouter

    Espera JSON: {"text": "sua pergunta aqui"}
    Retorna: texto puro da resposta da IA
    """
    try:
        # Verifica se a chave da API está configurada
        if not OPENROUTER_KEY:
            return "Erro: OPENROUTER_KEY não configurada", 500

        # Obtém o JSON da requisição
        data = request.get_json()

        if not data or 'text' not in data:
            return "Erro: JSON deve conter o campo 'text'", 400

        user_text = data['text']

        if not user_text or not user_text.strip():
            return "Erro: O campo 'text' não pode estar vazio", 400

        # Chama a função que encapsula a lógica do OpenRouter
        response_text = call_openrouter(user_text)

        # Retorna apenas o texto puro
        return response_text, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    except Exception as e:
        return f"Erro interno: {str(e)}", 500













# ===================== benchmark =====================
@ai.route('/ai/benchmark', methods=['POST'])
def ai_benchmark():
    data = request.get_json()
    text = data.get("text")

    results = {}

    def benchmark_model(name, func):
        start = time.time()
        try:
            output = func(text)
        except Exception as e:
            output = f"Erro: {str(e)}"
        end = time.time()
        duration = round(end - start, 2)
        print(f"{name} - Tempo: {duration}s\nResposta: {output}\n")
        results[name] = {
            "response": output,
            "time_seconds": duration
        }

    # Benchmark de cada modelo
    benchmark_model("Gemini", call_gemini)
    benchmark_model("Mistral", call_mistral)
    benchmark_model("Cohere", call_cohere)
    benchmark_model("Groq", call_groq)
    benchmark_model("OpenRouter", call_openrouter)

    return jsonify(results)
