
import logging
from typing import Optional

from app.services.database import DatabaseService
from app.services.pendencias import PendenciasService
from app.utils.logger import get_logger

# Import com fallback
try:
    from config.settings import APP_CONFIG
except ImportError:
    APP_CONFIG = {'version': '2.0.0'}


class PendenciasApp:
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.db_service = DatabaseService()
        self.pendencias_service = PendenciasService()
    
    def exibir_cabecalho(self) -> None:
        print("🚀 SISTEMA DE CONSULTAS SQL - amm_consulta_pendencias")
        print(f"🕐 Iniciado em: {self._get_timestamp()}")
        print("🗃️  Foco: Banco de dados SQL Server Azure")
        print(f"📋 Versão: {APP_CONFIG['version']}")
        print("✅ Sistema otimizado e modular!")
    
    def exibir_menu(self) -> None:
        print("\n" + "=" * 80)
        print("🗃️  SISTEMA DE CONSULTAS - amm_consulta_pendencias")
        print("=" * 80)
        print("1. ✅ Testar conexão com banco SQL Server")
        print("11. 🚀 EXECUTAR TODAS AS CONSULTAS DE PENDÊNCIAS")
        print("0. 🚪 Sair")
        print("=" * 80)
    
    def testar_conexao(self) -> None:
        print("\n Testando conexão com o banco de dados...")
        
        if self.db_service.test_connection():
            print(" Conexão com o banco estabelecida com sucesso!")
        else:
            print("❌ Falha na conexão com o banco de dados!")
            print("🔧 Verifique as configurações de rede e credenciais")
    
    def executar_todas_consultas(self) -> None:
        """Executa todas as consultas de pendências"""
        print("\n🚀 INICIANDO EXECUÇÃO DE TODAS AS CONSULTAS DE PENDÊNCIAS")
        print("⚠️  Este processo pode demorar alguns minutos...")
        
        # Confirmação do usuário
        resposta = input("\n🤔 Deseja continuar? (s/n): ").lower().strip()
        if resposta not in ['s', 'sim', 'y', 'yes']:
            print("❌ Operação cancelada pelo usuário")
            return
        
        # Executar
        resumo = self.pendencias_service.executar_todas_consultas()
        
        if resumo:
            self.pendencias_service.imprimir_resumo_final(resumo)
            print("\n✅ Execução completa!")
            print("📁 Verifique a pasta 'output' para os arquivos gerados")
        else:
            print("❌ Erro na execução das consultas")
    
    def executar(self) -> None:
        """Loop principal da aplicação"""
        self.exibir_cabecalho()
        
        while True:
            try:
                self.exibir_menu()
                opcao = input("\n👉 Escolha uma opção: ").strip()
                
                if opcao == '0':
                    print("\n👋 Encerrando o sistema...")
                    print("🙏 Obrigado por usar o Sistema de Consultas!")
                    break
                
                elif opcao == '1':
                    self.testar_conexao()
                
                elif opcao == '11':
                    self.executar_todas_consultas()
                
                else:
                    print("❌ Opção inválida! Escolha 1, 11 ou 0.")
                
                if opcao != '0':
                    input("\n⏸️  Pressione Enter para continuar...")
                
            except KeyboardInterrupt:
                print("\n\n👋 Programa interrompido pelo usuário")
                break
            except Exception as e:
                self.logger.error(f"Erro inesperado: {e}")
                print(f"❌ Erro inesperado: {e}")
                input("\n⏸️  Pressione Enter para continuar...")
    
    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")