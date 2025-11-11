
import pyodbc
import pandas as pd
import logging
from typing import Optional, List, Any, Dict
from contextlib import contextmanager
import os
from dotenv import load_dotenv

# Import com fallback
try:
    from config.settings import DATABASE_CONFIG
except ImportError:
    load_dotenv()

    DATABASE_CONFIG = {
        'server': os.getenv('DB_SERVER'),
        'database': os.getenv('DB_DATABASE'),
        'username': os.getenv('DB_USERNAME'),
        'password': os.getenv('DB_PASSWORD'),
        'driver': os.getenv('DB_DRIVER', '{ODBC Driver 18 for SQL Server}'),
        'port': int(os.getenv('DB_PORT', '1433')),
        'timeout': int(os.getenv('DB_TIMEOUT', '30'))
    }


class DatabaseService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._connection = None
    
    def _get_connection_string(self) -> str:
        return (
            f"DRIVER={DATABASE_CONFIG['driver']};"
            f"SERVER={DATABASE_CONFIG['server']},{DATABASE_CONFIG['port']};"
            f"DATABASE={DATABASE_CONFIG['database']};"
            f"UID={DATABASE_CONFIG['username']};"
            f"PWD={DATABASE_CONFIG['password']};"
            f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout={DATABASE_CONFIG['timeout']};"
        )
    
    @contextmanager
    def get_connection(self):
        connection = None
        try:
            self.logger.info("Connecting to database...")
            connection = pyodbc.connect(self._get_connection_string())
            self.logger.info("Database connection established successfully")
            yield connection
        except Exception as e:
            self.logger.error(f"Database connection error: {e}")
            raise
        finally:
            if connection:
                connection.close()
                self.logger.info("Database connection closed")
    
    def test_connection(self) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                return result[0] == 1
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def execute_query(self, query: str) -> Optional[List[Dict[str, Any]]]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                
                # Obter nomes das colunas
                columns = [column[0] for column in cursor.description]
                
                # Buscar todos os resultados
                rows = cursor.fetchall()
                
                # Converter para lista de dicionários
                results = []
                for row in rows:
                    results.append(dict(zip(columns, row)))
                
                self.logger.info(f"Query executed successfully. {len(results)} registros encontrados")
                return results
                
        except Exception as e:
            self.logger.error(f"Error executing query: {e}")
            return None
    
    def execute_query_to_dataframe(self, query: str) -> Optional[pd.DataFrame]:
        try:
            with self.get_connection() as conn:
                df = pd.read_sql(query, conn)
                self.logger.info(f"Query executed successfully. DataFrame criado com {len(df)} registros")
                return df
        except Exception as e:
            self.logger.error(f"Error executing query: {e}")
            return None