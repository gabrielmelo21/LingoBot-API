import bcrypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# JSON padrão para metas diárias
DEFAULT_METAS_DIARIAS = {
    "meta1": False,
    "meta2": False,
    "meta3": False,
    "meta4": False,
    "meta5": False,
    "meta6": False,
    "meta7": False,
    "meta8": False,
    "meta9": False,
    "meta10": False
}

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    sobrenome = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    avatar = db.Column(db.String(255), default='assets/lingobot/lingobot-icon.png')
    password = db.Column(db.String(255), nullable=False)
    OTP_code = db.Column(db.String(10), nullable=True)
    LingoEXP = db.Column(db.Integer, default=0)
    Level = db.Column(db.Integer, default=1)
    gender = db.Column(db.String(50))
    data_nascimento = db.Column(db.String(50))
    tokens = db.Column(db.Integer, default=0)
    plano = db.Column(db.String(50))
    checkIn = db.Column(db.Boolean, default=False)
    nextCheckinTime = db.Column(db.String(50), nullable=True)
    last_login = db.Column(db.String(50))
    created_at = db.Column(db.String(50))
    referal_code = db.Column(db.String(50), unique=True, nullable=True)
    invited_by = db.Column(db.String(50), nullable=True)
    ranking = db.Column(db.Integer, default=0)
    ip_address = db.Column(db.String(45), nullable=True)

    # Niveis de Listening, Wrting, Speaking, Reading
    listening = db.Column(db.Integer, default=1)
    writing = db.Column(db.Integer, default=1)
    reading = db.Column(db.Integer, default=1)
    speaking = db.Column(db.Integer, default=1)


    difficulty = db.Column(db.String(50), default="medium")

    # Novo campo para metas diárias
    metasDiarias = db.Column(db.JSON, default=lambda: DEFAULT_METAS_DIARIAS.copy())

    # Campo para tokens ganhos por referral
    tokens_by_referral = db.Column(db.Integer, default=0)

    # Campos separados para fingerprint
    device_type = db.Column(db.String(50), nullable=True)
    screen_resolution = db.Column(db.String(50), nullable=True)
    language = db.Column(db.String(50), nullable=True)
    timezone = db.Column(db.String(50), nullable=True)

    def __init__(self, nome, sobrenome, email, password, avatar=None, gender=None, data_nascimento=None, referal_code=None, invited_by=None, ip_address=None, device_type=None, screen_resolution=None, language=None, timezone=None):
        self.nome = nome
        self.sobrenome = sobrenome
        self.email = email
        self.avatar = avatar
        self.gender = gender
        self.data_nascimento = data_nascimento
        self.created_at = datetime.utcnow().isoformat()
        self.password = password
        self.referal_code = referal_code
        self.invited_by = invited_by
        self.metasDiarias = DEFAULT_METAS_DIARIAS.copy()
        self.ip_address = ip_address
        self.device_type = device_type
        self.screen_resolution = screen_resolution
        self.language = language
        self.timezone = timezone



    def reset_metas_diarias(self):
        """Reseta as metas diárias do usuário"""
        self.metasDiarias = DEFAULT_METAS_DIARIAS.copy()
        db.session.commit()

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
    def insert_user(nome, sobrenome, email, password, avatar=None, gender=None, data_nascimento=None, referal_code=None, invited_by=None):
        """Cria um novo usuário no banco"""
        novo_usuario = Usuario(nome, sobrenome, email, password, avatar, gender, data_nascimento, referal_code, invited_by)
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

    def reset_checkin(self):
        """Reseta o check-in diário (para ser rodado a cada 24h no sistema)."""
        self.checkIn = False
        self.nextCheckinTime = None  # Remove o próximo check-in, pois ainda não foi feito
        db.session.commit()



