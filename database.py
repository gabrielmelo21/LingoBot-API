from email.policy import default

import bcrypt
import json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from sqlalchemy import CheckConstraint

db = SQLAlchemy()


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    sobrenome = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    OTP_code = db.Column(db.String(10), nullable=True)
    LingoEXP = db.Column(db.Integer, default=0)
    Level = db.Column(db.Integer, default=1)
    gender = db.Column(db.String(50))
    data_nascimento = db.Column(db.String(50))
    tokens = db.Column(db.Integer, default=0)
    plano = db.Column(db.String(50), default="free")
    created_at = db.Column(db.String(50))
    referal_code = db.Column(db.String(50), unique=True, nullable=True)
    invited_by = db.Column(db.String(50), nullable=True)
    ranking = db.Column(db.Integer, default=4)

    # Níveis de habilidade
    listening = db.Column(db.Integer, default=1)
    writing = db.Column(db.Integer, default=1)
    reading = db.Column(db.Integer, default=1)
    speaking = db.Column(db.Integer, default=1)

    gemas = db.Column(db.Integer, default=10)
    items = db.Column(db.Text, nullable=False)
    dailyMissions = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(50), default="easy")
    battery = db.Column(db.Integer, default=10, nullable=False)

    learning = db.Column(db.String(50), default="english")



    __table_args__ = (
        CheckConstraint('battery >= 0 AND battery <= 10', name='check_battery_range'),
    )

    def __init__(self, nome, sobrenome, email, password, gender=None, data_nascimento=None,
                 referal_code=None, invited_by=None, items=None, plano=None, learning=None, dailyMissions=None):
        self.nome = nome
        self.sobrenome = sobrenome
        self.email = email
        self.gender = gender
        self.data_nascimento = data_nascimento
        self.created_at = datetime.utcnow().isoformat()
        self.password = password
        self.referal_code = referal_code
        self.invited_by = invited_by
        self.items = items if items else json.dumps([])
        self.plano = plano if plano else "free"
        self.learning = "english"
        default_daily_missions = {
            "writing": False,
            "reading": False,
            "listening": False,
            "speaking": False,
            "chestWasOpen1": False,
            "chestWasOpen2": False,
            "chestWasOpen3": False,
            "chestWasOpen4": False,
            "strikes": 0,
            "rewardPerChest": 5,
            "chestsOpenedAt": 0,
            "refreshTimeAt": 0
        }
        self.dailyMissions = dailyMissions if dailyMissions else json.dumps(default_daily_missions)

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
    def insert_user(nome, sobrenome, email, password, gender=None, data_nascimento=None, referal_code=None,
                    invited_by=None):
        """Cria um novo usuário no banco"""
        novo_usuario = Usuario(nome, sobrenome, email, password, gender=gender, data_nascimento=data_nascimento,
                               referal_code=referal_code, invited_by=invited_by)
        db.session.add(novo_usuario)
        db.session.commit()
        return novo_usuario

    @staticmethod
    def get_all_users():
        """Retorna todos os usuários"""
        return Usuario.query.all()

    def set_password(self, password):
        """Criptografa a senha com bcrypt antes de salvar no banco."""
        salt = bcrypt.gensalt()
        self.password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password):
        """Verifica se a senha fornecida é válida."""
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))
