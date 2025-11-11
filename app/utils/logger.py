
import logging
import sys
from pathlib import Path
from datetime import datetime
import os

# Configuração básica (fallback se não conseguir importar settings)
try:
    from config.settings import APP_CONFIG
except ImportError:
    APP_CONFIG = {'log_level': 'INFO'}


def setup_logging() -> None:
    """Configura o sistema de logging"""
    
    # Criar diretório de logs se não existir
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Nome do arquivo de log com timestamp
    log_filename = f"pendencias_{datetime.now().strftime('%Y%m%d')}.log"
    log_filepath = log_dir / log_filename
    
    # Configurar formato
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configurar logging
    logging.basicConfig(
        level=getattr(logging, APP_CONFIG['log_level']),
        format=log_format,
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Silenciar logs verbosos do pandas
    logging.getLogger('pandas').setLevel(logging.WARNING)
    
    # Log inicial
    logger = logging.getLogger(__name__)
    logger.info(f"Sistema de logging inicializado - Arquivo: {log_filepath}")


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado"""
    return logging.getLogger(name)