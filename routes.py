from flask import Blueprint, jsonify, request
from database import db, Usuario

routes = Blueprint("routes", __name__)

# Obter um usuário por ID
@routes.route("/usuarios/<int:id>", methods=["GET"])
def obter_usuario(id):
    usuario = Usuario.query.get(id)
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    # Retorna todos os campos do usuário
    return jsonify({
        "id": usuario.id,
        "nome": usuario.nome,
        "sobrenome": usuario.sobrenome,
        "email": usuario.email,
        "avatar": usuario.avatar,
        "password": usuario.password,  # Considerar não retornar a senha em produção!
        "OTP_code": usuario.OTP_code,
        "LingoEXP": usuario.LingoEXP,
        "Level": usuario.Level,
        "gender": usuario.gender,
        "data_nascimento": usuario.data_nascimento,
        "tokens_usage": usuario.tokens_usage,
        "plano": usuario.plano,
        "trial7dias": usuario.trial7dias,
        "trialBeginDate": usuario.trialBeginDate,
        "trialEndDate": usuario.trialEndDate,
        "checkIn": usuario.checkIn,
        "last_login": usuario.last_login,
        "created_at": usuario.created_at
    })

# Criar um novo usuário
@routes.route("/usuarios", methods=["POST"])
def criar_usuario():
    dados = request.get_json()

    # Verifica se todos os campos obrigatórios foram enviados
    if "nome" not in dados or "email" not in dados or "password" not in dados:
        return jsonify({"erro": "Os campos 'nome', 'email' e 'password' são obrigatórios"}), 400

    # Cria um novo usuário com os dados fornecidos
    novo_usuario = Usuario(
        nome=dados["nome"],
        sobrenome=dados.get("sobrenome"),
        email=dados["email"],
        password=dados["password"],
        avatar=dados.get("avatar"),
        gender=dados.get("gender"),
        data_nascimento=dados.get("data_nascimento")
    )
    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify({"mensagem": "Usuário criado com sucesso!"}), 201

# Atualizar um usuário
@routes.route("/usuarios/<int:id>", methods=["PUT"])
def atualizar_usuario(id):
    usuario = Usuario.query.get(id)
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    dados = request.get_json()

    usuario.nome = dados.get("nome", usuario.nome)
    usuario.sobrenome = dados.get("sobrenome", usuario.sobrenome)
    usuario.email = dados.get("email", usuario.email)
    usuario.avatar = dados.get("avatar", usuario.avatar)
    usuario.password = dados.get("password", usuario.password)
    usuario.gender = dados.get("gender", usuario.gender)
    usuario.data_nascimento = dados.get("data_nascimento", usuario.data_nascimento)

    db.session.commit()
    return jsonify({"mensagem": "Usuário atualizado com sucesso!"})

# Excluir um usuário
@routes.route("/usuarios/<int:id>", methods=["DELETE"])
def deletar_usuario(id):
    usuario = Usuario.query.get(id)
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    db.session.delete(usuario)
    db.session.commit()
    return jsonify({"mensagem": "Usuário deletado com sucesso!"})

# Obter todos os usuários
@routes.route("/usuarios", methods=["GET"])
def listar_usuarios():
    usuarios = Usuario.query.all()
    lista_usuarios = [{
        "id": u.id,
        "nome": u.nome,
        "sobrenome": u.sobrenome,
        "email": u.email,
        "avatar": u.avatar,
        "password": u.password,  # Lembre-se de não retornar a senha em produção
        "OTP_code": u.OTP_code,
        "LingoEXP": u.LingoEXP,
        "Level": u.Level,
        "gender": u.gender,
        "data_nascimento": u.data_nascimento,
        "tokens_usage": u.tokens_usage,
        "plano": u.plano,
        "trial7dias": u.trial7dias,
        "trialBeginDate": u.trialBeginDate,
        "trialEndDate": u.trialEndDate,
        "checkIn": u.checkIn,
        "last_login": u.last_login,
        "created_at": u.created_at
    } for u in usuarios]

    return jsonify(lista_usuarios)
