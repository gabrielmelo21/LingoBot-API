"""
Módulo centralizado para gerenciar o estado de ping da API
USO: from ping_manager import PingManager
"""
import time
import threading
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime

@dataclass
class PingState:
    is_warming_up: bool = False
    warming_started_at: Optional[float] = None
    warming_client_id: Optional[str] = None
    last_activity: Optional[float] = None
    waiting_clients: Dict[str, float] = None

    def __post_init__(self):
        if self.waiting_clients is None:
            self.waiting_clients = {}

# Instância global do estado de ping
_ping_state = PingState()
_ping_lock = threading.Lock()

# Configurações globais
COLD_START_THRESHOLD = 10 * 60  # 10 minutos sem atividade = API fria
WARMING_TIMEOUT = 30  # 30 segundos para considerar warming completo

class PingManager:
    """Classe para gerenciar o estado de ping de forma thread-safe"""

    @staticmethod
    def update_last_activity():
        """
        ⭐ MÉTODO PRINCIPAL - Atualiza o timestamp da última atividade da API
        Use este método em todos os seus endpoints importantes!
        """
        with _ping_lock:
            _ping_state.last_activity = time.time()

    @staticmethod
    def is_api_cold() -> bool:
        """Verifica se a API está fria (sem atividade recente)"""
        with _ping_lock:
            if _ping_state.last_activity is None:
                return True
            return time.time() - _ping_state.last_activity > COLD_START_THRESHOLD

    @staticmethod
    def get_ping_state_info() -> dict:
        """Retorna informações sobre o estado atual (para debug/status)"""
        with _ping_lock:
            current_time = time.time()
            return {
                'is_api_cold': PingManager.is_api_cold(),
                'is_warming_up': _ping_state.is_warming_up,
                'warming_client_id': _ping_state.warming_client_id,
                'waiting_clients_count': len(_ping_state.waiting_clients),
                'last_activity': (
                    datetime.fromtimestamp(_ping_state.last_activity).isoformat()
                    if _ping_state.last_activity else None
                ),
                'last_activity_seconds_ago': (
                    round(current_time - _ping_state.last_activity, 2)
                    if _ping_state.last_activity else None
                )
            }

    @staticmethod
    def force_reset():
        """Força reset do estado (para admin/debug)"""
        with _ping_lock:
            _ping_state.is_warming_up = False
            _ping_state.warming_started_at = None
            _ping_state.warming_client_id = None
            _ping_state.waiting_clients.clear()
            _ping_state.last_activity = None

    # Métodos internos para o sistema de ping (não use diretamente)
    @staticmethod
    def _set_warming_state(client_id: str, is_warming: bool):
        with _ping_lock:
            _ping_state.is_warming_up = is_warming
            if is_warming:
                _ping_state.warming_client_id = client_id
                _ping_state.warming_started_at = time.time()
            else:
                _ping_state.warming_client_id = None
                _ping_state.warming_started_at = None

    @staticmethod
    def _add_waiting_client(client_id: str):
        with _ping_lock:
            _ping_state.waiting_clients[client_id] = time.time()

    @staticmethod
    def _clear_waiting_clients():
        with _ping_lock:
            _ping_state.waiting_clients.clear()

    @staticmethod
    def _cleanup_old_waiting_clients():
        with _ping_lock:
            current_time = time.time()
            to_remove = []

            for client_id, timestamp in _ping_state.waiting_clients.items():
                if current_time - timestamp > WARMING_TIMEOUT * 2:
                    to_remove.append(client_id)

            for client_id in to_remove:
                del _ping_state.waiting_clients[client_id]

    @staticmethod
    def _get_warming_info():
        with _ping_lock:
            if not _ping_state.is_warming_up:
                return None

            current_time = time.time()

            # Verifica timeout
            if (_ping_state.warming_started_at and
                current_time - _ping_state.warming_started_at > WARMING_TIMEOUT):
                return 'timeout'

            return {
                'warming_client_id': _ping_state.warming_client_id,
                'waiting_clients_count': len(_ping_state.waiting_clients),
                'warming_duration': round(current_time - _ping_state.warming_started_at, 2)
            }

# Inicializar com API "quente" no desenvolvimento
if __name__ != '__main__':
    PingManager.update_last_activity()