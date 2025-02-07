import schedule
import time
from datetime import datetime
from routes import db, Usuario, app  # Certifique-se de importar corretamente seu app Flask


def reset_checkins():
    with app.app_context():  # Garante que o contexto do Flask esteja ativo
        usuarios = Usuario.query.all()
        for usuario in usuarios:
            usuario.checkIn = False
        db.session.commit()
        print(f"[{datetime.utcnow()}] Check-ins resetados com sucesso!")

# Agendar para rodar todo dia às 00:01
schedule.every().day.at("00:01").do(reset_checkins)

print("🚀 Reset de check-ins agendado para rodar diariamente às 00:01.")

while True:
    schedule.run_pending()
    time.sleep(60)  # Checa a cada minuto
