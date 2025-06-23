import json
import random
import re
import string
from datetime import timedelta
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token
from sqlalchemy import desc

from database import db, Usuario
from email_validator import validate_email, EmailNotValidError
import bcrypt

routes = Blueprint("routes", __name__)


# Função para gerar hash da senha
def hash_senha(senha):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha.encode('utf-8'), salt).decode('utf-8')


# Função para verificar senha
def verificar_senha(senha, senha_hash):
    return bcrypt.checkpw(senha.encode('utf-8'), senha_hash.encode('utf-8'))


def generate_referal_code():
    return ''.join(random.choices(string.digits, k=6))  # Gera um código de 6 números aleatórios




@routes.route("/usuarios", methods=["POST"])
def criar_usuario():
    dados = request.get_json()

    # Verifica nome e sobrenome com regex
    if not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ\s]+$", dados["nome"]) or not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ\s]+$", dados["sobrenome"]):
        return jsonify({"erro": "Nome e sobrenome devem conter apenas letras."}), 400

    # Validação de email
    try:
        validate_email(dados["email"])
    except EmailNotValidError:
        return jsonify({"erro": "E-mail inválido!"}), 400

    # Impede o uso do próprio código de referência
    if "referal_code" in dados and dados["referal_code"]:
        usuario_referenciador = Usuario.query.filter_by(referal_code=dados["referal_code"]).first()
        if usuario_referenciador and usuario_referenciador.email == dados["email"]:
            return jsonify({"erro": "Você não pode usar seu próprio código de referência!"}), 403

    # Hash da senha
    senha_hash = hash_senha(dados["password"])

    # Geração de código de referência único
    referal_code = generate_referal_code()
    while Usuario.query.filter_by(referal_code=referal_code).first():
        referal_code = generate_referal_code()

    # Itens iniciais
    itens_iniciais = [
        {
            "itemName": "OG Ticket",
            "dropRate": 0.01,
            "gemsValue": 50,
            "rarity": "legendary",
            "itemSrc": "assets/lingobot/itens/og_ticket.png",
            "describe": "OG ticket é para os pioneiros.",
            "quant": 1
        },
        {
            "itemName": "Beta Tester Ticket",
            "dropRate": 0.01,
            "gemsValue": 50,
            "rarity": "legendary",
            "itemSrc": "assets/lingobot/itens/beta_tester_ticket.png",
            "describe": "Ticket dos escolhidos.",
            "quant": 1
        }
    ]

    # Criar novo usuário
    novo_usuario = Usuario(
        nome=dados["nome"],
        sobrenome=dados.get("sobrenome"),
        email=dados["email"],
        password=senha_hash,
        gender=dados.get("gender"),
        data_nascimento=dados.get("data_nascimento"),
        referal_code=referal_code,
        invited_by=dados.get("referal_code"),
        items=json.dumps(itens_iniciais)
    )

    db.session.add(novo_usuario)
    db.session.commit()

    # Bônus por indicação (removido tokens_by_referral)
    if novo_usuario.invited_by:
        usuario_referenciador = Usuario.query.filter_by(referal_code=novo_usuario.invited_by).first()
        if usuario_referenciador:
            usuario_referenciador.tokens += 100
            db.session.commit()

    return jsonify({"mensagem": "Usuário criado com sucesso!"}), 201






@routes.route("/login", methods=["POST"])
def login():
    dados = request.get_json()
    email = dados.get("email")
    password = dados.get("password")

    usuario = Usuario.get_user_by_email(email)
    if not usuario or not usuario.check_password(password):
        return jsonify({"erro": "Credenciais inválidas!"}), 401

    usuario_data = {campo: getattr(usuario, campo) for campo in Usuario.__table__.columns.keys()}
    access_token = create_access_token(identity=usuario.id, additional_claims=usuario_data,
                                       expires_delta=timedelta(days=7))
    refresh_token = create_refresh_token(identity=usuario.id, expires_delta=timedelta(days=30))

    return jsonify(
        {"mensagem": "Login realizado com sucesso!", "access_token": access_token, "refresh_token": refresh_token}), 200


@routes.route("/usuarios/<int:id>", methods=["PUT"])
def atualizar_usuario(id):
    usuario = Usuario.query.get(id)
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    dados = request.get_json()
    for campo, valor in dados.items():
        if hasattr(usuario, campo) and valor is not None:
            setattr(usuario, campo, valor)

    db.session.commit()
    return jsonify({"mensagem": "Usuário atualizado com sucesso!"})


@routes.route("/usuarios/<int:id>", methods=["DELETE"])
def deletar_usuario(id):
    usuario = Usuario.query.get(id)
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    db.session.delete(usuario)
    db.session.commit()
    return jsonify({"mensagem": "Usuário deletado com sucesso!"})


@routes.route("/usuarios", methods=["GET"])
def listar_usuarios():
    usuarios = Usuario.query.all()
    lista_usuarios = [{campo: getattr(u, campo) for campo in Usuario.__table__.columns.keys()} for u in usuarios]
    return jsonify(lista_usuarios)


@routes.route("/usuarios/<int:id>", methods=["GET"])
def obter_usuario(id):
    usuario = Usuario.query.get(id)
    if not usuario:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    return jsonify({campo: getattr(usuario, campo) for campo in Usuario.__table__.columns.keys()})



# Novo endpoint que atualiza o usuário e gera um novo JWT
@routes.route("/generate-new-jwt", methods=["POST"])
def generate_new_jwt():
    dados = request.get_json()

    if not dados:
        return jsonify({"erro": "Dados do usuário não fornecidos!"}), 400

    user_id = dados.get("id") or dados.get("sub")  # Pegamos o ID do usuário

    if not user_id:
        return jsonify({"erro": "ID do usuário não fornecido!"}), 400

    # Verificamos se o usuário existe no banco de dados
    usuario = Usuario.query.get(user_id)

    if not usuario:
        return jsonify({"erro": "Usuário não encontrado!"}), 404

    # Apenas os campos válidos para atualização
    campos_validos = {k: v for k, v in dados.items() if k in Usuario.__table__.columns.keys() and v is not None}

    # Atualizar usuário no banco de dados
    for campo, valor in campos_validos.items():
        setattr(usuario, campo, valor)

    db.session.commit()

    # Criamos um novo JWT
    access_token = create_access_token(
        identity=str(user_id),
        additional_claims=campos_validos,  # Apenas valores válidos
        expires_delta=timedelta(days=7)
    )

    return jsonify({
        "mensagem": "Novo JWT gerado e usuário atualizado com sucesso!",
        "access_token": access_token
    }), 200






@routes.route("/ranking", methods=["GET"])
def listar_ranking():
    """
    Retorna a lista dos usuários ordenados pelo ranking em ordem decrescente.
    Apenas os campos: nome, avatar, email e ranking são retornados.
    """
    usuarios = Usuario.query.order_by(desc(Usuario.ranking)).all()

    ranking = [
        {
            "nome": usuario.nome,
            "email": usuario.email,
            "ranking": usuario.ranking
        }
        for usuario in usuarios
    ]

    return jsonify(ranking)





 