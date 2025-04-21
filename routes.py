import json
import random
import re
import string
from datetime import timedelta, datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required
from sqlalchemy import desc

from database import db, Usuario, DEFAULT_METAS_DIARIAS
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
    ip_usuario = request.remote_addr  # Obtendo o IP do usuário

    # Verificar se já existe outra conta no mesmo IP (limite de 3 contas por IP)
    max_contas_por_ip = 5
    if Usuario.query.filter_by(ip_address=ip_usuario).count() >= max_contas_por_ip:
        return jsonify({"erro": "Limite de contas por IP atingido!"}), 403

    # Verificar se o usuário está tentando usar o próprio código de referência
    if "referal_code" in dados and dados["referal_code"]:
        usuario_referenciador = Usuario.query.filter_by(referal_code=dados["referal_code"]).first()
        if usuario_referenciador and usuario_referenciador.email == dados["email"]:
            return jsonify({"erro": "Você não pode usar seu próprio código de referência!"}), 403

    # Validar nome e sobrenome
    if not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ\s]+$", dados["nome"]) or not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ\s]+$", dados["sobrenome"]):
        return jsonify({"erro": "Nome e sobrenome devem conter apenas letras."}), 400

    # Validar e-mail
    try:
        validate_email(dados["email"])
    except EmailNotValidError:
        return jsonify({"erro": "E-mail inválido!"}), 400

    senha_hash = hash_senha(dados["password"])

    # Gerar um código único
    referal_code = generate_referal_code()
    while Usuario.query.filter_by(referal_code=referal_code).first():
        referal_code = generate_referal_code()

    # Criar novo usuário com dados de fingerprinting, mas sem proteção por eles
    novo_usuario = Usuario(
        nome=dados["nome"],
        sobrenome=dados.get("sobrenome"),
        email=dados["email"],
        password=senha_hash,
        gender=dados.get("gender"),
        data_nascimento=dados.get("data_nascimento"),
        referal_code=referal_code,
        invited_by=dados.get("referal_code"),
        ip_address=ip_usuario,
        device_type=dados.get("device_type"),  # Salvando o tipo de dispositivo
        screen_resolution=dados.get("screen_resolution"),  # Salvando a resolução da tela
        language=dados.get("language"),  # Salvando o idioma
        timezone=dados.get("timezone"),  # Salvando o fuso horário
    )

    db.session.add(novo_usuario)
    db.session.commit()

    # Verificar se o novo usuário foi convidado por outro usuário e adicionar tokens
    if novo_usuario.invited_by:
        usuario_referenciador = Usuario.query.filter_by(referal_code=novo_usuario.invited_by).first()
        if usuario_referenciador:
            usuario_referenciador.tokens += 100  # Adiciona 5000 tokens ao referenciador
            usuario_referenciador.tokens_by_referral += 100  # Soma os tokens no campo tokens_by_referral
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


@routes.route('/reset_metas', methods=['POST'])
def reset_metas():
    """Reseta as metas diárias de todos os usuários"""
    try:
        usuarios = Usuario.query.all()
        for usuario in usuarios:
            usuario.metasDiarias = DEFAULT_METAS_DIARIAS.copy()
        db.session.commit()
        return jsonify({"message": "Metas diárias resetadas para todos os usuários!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes.route("/checkin/<int:id>", methods=["POST"])
def fazer_checkin(id):
    # Obtém o usuário pelo ID fornecido na URL
    usuario = Usuario.query.get(id)

    if not usuario:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    # Obtém os dados do corpo da requisição
    dados = request.get_json()

    # Atualiza os dados do check-in
    usuario.checkIn = dados.get("checkIn", True)  # Se não for passado, assume que o check-in foi realizado
    usuario.nextCheckin = dados.get("nextCheckin", datetime.utcnow() + timedelta(
        hours=24))  # Atualiza para 24h a partir de agora, se não for passado

    # Commit na sessão do banco para salvar as alterações
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()  # Caso ocorra erro, faz rollback
        return jsonify({"erro": "Erro ao atualizar o check-in", "detalhes": str(e)}), 500

    # Retorna resposta de sucesso com os dados atualizados
    return jsonify({
        "mensagem": "Check-in realizado com sucesso!",
        "checkIn": usuario.checkIn,
        "nextCheckin": usuario.nextCheckin.isoformat()  # Retorna o nextCheckin no formato ISO 8601
    }), 200









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
    Retorna a lista dos usuários ordenados pelo LXP em ordem decrescente.
    Apenas os campos: nome, avatar, email e LingoEXP são retornados.
    """
    usuarios = Usuario.query.order_by(desc(Usuario.LingoEXP)).all()

    ranking = [
        {
            "nome": usuario.nome,
            "avatar": usuario.avatar,
            "email": usuario.email,
            "LingoEXP": usuario.LingoEXP
        }
        for usuario in usuarios
    ]

    return jsonify(ranking)



