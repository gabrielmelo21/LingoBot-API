from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    sobrenome = db.Column(db.String(100), nullable=True)  # Adicionado sobrenome
    email = db.Column(db.String(100), unique=True, nullable=False)
    avatar = db.Column(db.String(255))
    password = db.Column(db.String(255), nullable=False)
    OTP_code = db.Column(db.String(10), nullable=True)
    LingoEXP = db.Column(db.Integer, default=0)
    Level = db.Column(db.Integer, default=1)
    gender = db.Column(db.String(50))
    data_nascimento = db.Column(db.String(50))
    tokens_usage = db.Column(db.Integer, default=0)
    plano = db.Column(db.String(50))
    trial7dias = db.Column(db.String(10), default="false")
    trialBeginDate = db.Column(db.String(50), nullable=True)
    trialEndDate = db.Column(db.String(50), nullable=True)
    checkIn = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.String(50))
    created_at = db.Column(db.String(50))

    def __init__(self, nome, sobrenome, email, password, avatar=None, gender=None, data_nascimento=None):
        self.nome = nome
        self.sobrenome = sobrenome  # Adicionado sobrenome ao construtor
        self.email = email
        self.avatar = avatar
        self.password = generate_password_hash(password)  # Hash da senha
        self.gender = gender
        self.data_nascimento = data_nascimento
        self.created_at = datetime.utcnow().isoformat()

    def update_user(self, **kwargs):
        """Atualiza os dados do usuário"""
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        db.session.commit()

    def delete_user(self):
        """Deleta o usuário do banco"""
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def get_user_by_id(user_id):
        """Retorna um usuário pelo ID"""
        return Usuario.query.get(user_id)

    @staticmethod
    def get_user_by_email(email):
        """Retorna um usuário pelo email"""
        return Usuario.query.filter_by(email=email).first()

    @staticmethod
    def insert_user(nome, sobrenome, email, password, avatar=None, gender=None, data_nascimento=None):
        """Cria um novo usuário no banco"""
        novo_usuario = Usuario(nome, sobrenome, email, password, avatar, gender, data_nascimento)
        db.session.add(novo_usuario)
        db.session.commit()
        return novo_usuario

    @staticmethod
    def get_all_users():
        """Retorna todos os usuários"""
        return Usuario.query.all()

    def set_password(self, password):
        """Criptografa a senha antes de salvar no banco."""
        self.password = generate_password_hash(password)  # Corrigido para armazenar corretamente

    def check_password(self, password):
        """Verifica se a senha fornecida é válida."""
        return check_password_hash(self.password, password)

    def reset_checkin(self):
        """Reseta o check-in diário (para ser rodado a cada 24h no sistema)."""
        self.checkIn = False
