
import os
from pathlib import Path

class ProductionConfig:
    
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
    DEBUG = False
    TESTING = False
    
    DB_SERVER = os.environ.get('DB_SERVER')
    DB_NAME = os.environ.get('DB_NAME')
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    
    OUTPUT_DIR = Path(os.environ.get('OUTPUT_DIR', 'output'))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  
    
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    @staticmethod
    def init_app(app):
        """Initialize application with production settings"""
        pass

class DevelopmentConfig:
    
    SECRET_KEY = 'dev-secret-key'
    DEBUG = True
    TESTING = False
    
    OUTPUT_DIR = Path('output')
    
    LOG_LEVEL = 'DEBUG'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}