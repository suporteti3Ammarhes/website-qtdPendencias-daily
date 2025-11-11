
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass
from decimal import Decimal
import sys

# Adicionar o diretório raiz ao path
root_path = Path(__file__).parent.parent.parent
sys.path.append(str(root_path))

try:
    from app.services.database import DatabaseService
    from app.utils.logger import setup_logging
except ImportError:
    # Fallback para execução direta
    sys.path.append(str(Path(__file__).parent))
    sys.path.append(str(Path(__file__).parent.parent))
    try:
        from database import DatabaseService
        from app.utils.logger import setup_logging
    except ImportError:
        # Último fallback - só logging básico
        DatabaseService = None
        def setup_logging():
            logging.basicConfig(level=logging.INFO)


@dataclass
class ResultadoComparacao:
    consulta_id: int
    nome_pendencia: str
    contagem_anterior: int
    contagem_atual: int
    diferenca: int
    percentual_reducao: float
    valor_monetario_anterior: Optional[Decimal] = None
    valor_monetario_atual: Optional[Decimal] = None
    diferenca_monetaria: Optional[Decimal] = None
    eh_monetario: bool = False


class AnalisadorTendencias:
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.database_service = DatabaseService()
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
    
    def buscar_resultados_por_data(self, data: datetime) -> Optional[Dict]:
        try:
            # Buscar arquivos JSON da data
            data_str = data.strftime("%Y%m%d")
            pattern = f"resultados_execucao_pendencias_{data_str}_*.json"
            
            arquivos = list(self.output_dir.glob(pattern))
            
            if not arquivos:
                self.logger.warning(f"⚠️ Nenhum arquivo encontrado para a data {data_str}")
                return None
            
            # Pegar o arquivo mais recente da data
            arquivo_mais_recente = max(arquivos, key=lambda x: x.stat().st_mtime)
            
            with open(arquivo_mais_recente, 'r', encoding='utf-8') as f:
                dados = json.load(f)
            
            self.logger.info(f"📁 Carregado arquivo: {arquivo_mais_recente.name}")
            return dados
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar resultados da data {data_str}: {e}")
            return None
    
    def comparar_entre_datas(self, data_anterior: datetime, data_atual: datetime) -> List[ResultadoComparacao]:
        try:
            self.logger.info(f"🔍 Comparando dados entre {data_anterior.strftime('%d/%m/%Y')} e {data_atual.strftime('%d/%m/%Y')}")
            
            # Buscar dados das duas datas
            dados_anterior = self.buscar_resultados_por_data(data_anterior)
            dados_atual = self.buscar_resultados_por_data(data_atual)
            
            if not dados_anterior or not dados_atual:
                self.logger.error("❌ Dados insuficientes para comparação")
                return []
            
            comparacoes = []
            
            # Converter resultados se necessário
            resultados_atual = dados_atual.get('resultados', {})
            resultados_anterior = dados_anterior.get('resultados', {})
            
            # Se resultados é uma lista, converter para dict
            if isinstance(resultados_atual, list):
                resultados_atual = {str(r['id']): r for r in resultados_atual}
            if isinstance(resultados_anterior, list):
                resultados_anterior = {str(r['id']): r for r in resultados_anterior}
            
            # Comparar cada consulta
            for consulta_id, info_atual in resultados_atual.items():
                if consulta_id in resultados_anterior:
                    info_anterior = resultados_anterior[consulta_id]
                    
                    # Extrair contagens (compatibilidade com formatos antigos e novos)
                    contagem_atual = info_atual.get('total_registros', info_atual.get('quantidade', 0))
                    contagem_anterior = info_anterior.get('total_registros', info_anterior.get('quantidade', 0))
                    
                    # Calcular diferença
                    diferenca = contagem_anterior - contagem_atual
                    
                    # Calcular percentual de redução
                    if contagem_anterior > 0:
                        percentual_reducao = (diferenca / contagem_anterior) * 100
                    else:
                        percentual_reducao = 0
                    
                    # Verificar se é monetário (exibe_contagem = 2)
                    eh_monetario = info_atual.get('exibe_contagem') == 2
                    
                    resultado = ResultadoComparacao(
                        consulta_id=int(consulta_id),
                        nome_pendencia=info_atual.get('nome_pendencia', 'N/A'),
                        contagem_anterior=contagem_anterior,
                        contagem_atual=contagem_atual,
                        diferenca=diferenca,
                        percentual_reducao=percentual_reducao,
                        eh_monetario=eh_monetario
                    )
                    
                    # Se for monetário, tratar como valores em reais
                    if eh_monetario:
                        resultado.valor_monetario_anterior = Decimal(str(contagem_anterior))
                        resultado.valor_monetario_atual = Decimal(str(contagem_atual))
                        resultado.diferenca_monetaria = Decimal(str(diferenca))
                    
                    comparacoes.append(resultado)
            
            self.logger.info(f"✅ Comparação concluída: {len(comparacoes)} consultas analisadas")
            return comparacoes
            
        except Exception as e:
            self.logger.error(f"❌ Erro na comparação entre datas: {e}")
            return []
    
    def identificar_maiores_reducoes(self, comparacoes: List[ResultadoComparacao], limite: int = 10) -> List[ResultadoComparacao]:
        # Filtrar apenas reduções (diferença positiva)
        reducoes = [c for c in comparacoes if c.diferenca > 0]
        
        # Ordenar por diferença absoluta (maiores reduções primeiro)
        reducoes_ordenadas = sorted(reducoes, key=lambda x: x.diferenca, reverse=True)
        
        return reducoes_ordenadas[:limite]
    
    def identificar_maiores_reducoes_percentuais(self, comparacoes: List[ResultadoComparacao], limite: int = 10) -> List[ResultadoComparacao]:
        # Filtrar apenas reduções (diferença positiva) e com contagem anterior > 0
        reducoes = [c for c in comparacoes if c.diferenca > 0 and c.contagem_anterior > 0]
        
        # Ordenar por percentual de redução
        reducoes_ordenadas = sorted(reducoes, key=lambda x: x.percentual_reducao, reverse=True)
        
        return reducoes_ordenadas[:limite]
    
    def gerar_relatorio_comparativo(self, data_anterior: datetime, data_atual: datetime) -> str:
        try:
            comparacoes = self.comparar_entre_datas(data_anterior, data_atual)
            
            if not comparacoes:
                return "❌ Não foi possível gerar o relatório comparativo"
            
            # Separar monetárias e não monetárias
            monetarias = [c for c in comparacoes if c.eh_monetario]
            nao_monetarias = [c for c in comparacoes if not c.eh_monetario]
            
            # Identificar maiores reduções
            top_reducoes_abs = self.identificar_maiores_reducoes(comparacoes, 10)
            top_reducoes_perc = self.identificar_maiores_reducoes_percentuais(comparacoes, 10)
            
            # Estatísticas gerais
            total_reducoes = sum(1 for c in comparacoes if c.diferenca > 0)
            total_aumentos = sum(1 for c in comparacoes if c.diferenca < 0)
            total_inalteradas = sum(1 for c in comparacoes if c.diferenca == 0)
            
            # Economias monetárias
            economia_total = sum(c.diferenca_monetaria for c in monetarias if c.diferenca > 0 and c.diferenca_monetaria)
            
            # Construir relatório
            relatorio = []
            relatorio.append("="*80)
            relatorio.append("📊 RELATÓRIO COMPARATIVO DE PENDÊNCIAS")
            relatorio.append("="*80)
            relatorio.append(f"📅 Período: {data_anterior.strftime('%d/%m/%Y')} → {data_atual.strftime('%d/%m/%Y')}")
            relatorio.append(f"🔍 Total de consultas analisadas: {len(comparacoes)}")
            relatorio.append("")
            
            # Resumo geral
            relatorio.append("📈 RESUMO GERAL:")
            relatorio.append(f"  ✅ Reduções: {total_reducoes}")
            relatorio.append(f"  ⬆️ Aumentos: {total_aumentos}")
            relatorio.append(f"  ➡️ Inalteradas: {total_inalteradas}")
            
            if economia_total and economia_total > 0:
                relatorio.append(f"  💰 Economia monetária total: R$ {economia_total:,.2f}")
            
            relatorio.append("")
            
            # Top 10 maiores reduções absolutas
            if top_reducoes_abs:
                relatorio.append("🏆 TOP 10 - MAIORES REDUÇÕES (Valores Absolutos):")
                relatorio.append("-" * 80)
                for i, resultado in enumerate(top_reducoes_abs, 1):
                    if resultado.eh_monetario:
                        relatorio.append(f"{i:2d}. {resultado.nome_pendencia[:50]:<50}")
                        relatorio.append(f"     💰 De: R$ {resultado.valor_monetario_anterior:>12,.2f} → Para: R$ {resultado.valor_monetario_atual:>12,.2f}")
                        relatorio.append(f"     📉 Economia: R$ {resultado.diferenca_monetaria:>12,.2f} ({resultado.percentual_reducao:>6.1f}%)")
                    else:
                        relatorio.append(f"{i:2d}. {resultado.nome_pendencia[:50]:<50}")
                        relatorio.append(f"     📊 De: {resultado.contagem_anterior:>8,} → Para: {resultado.contagem_atual:>8,}")
                        relatorio.append(f"     📉 Redução: {resultado.diferenca:>8,} ({resultado.percentual_reducao:>6.1f}%)")
                    relatorio.append("")
            
            # Top 10 maiores reduções percentuais
            if top_reducoes_perc:
                relatorio.append("🎯 TOP 10 - MAIORES REDUÇÕES (Percentuais):")
                relatorio.append("-" * 80)
                for i, resultado in enumerate(top_reducoes_perc, 1):
                    if resultado.eh_monetario:
                        relatorio.append(f"{i:2d}. {resultado.nome_pendencia[:50]:<50}")
                        relatorio.append(f"     💰 De: R$ {resultado.valor_monetario_anterior:>12,.2f} → Para: R$ {resultado.valor_monetario_atual:>12,.2f}")
                        relatorio.append(f"     📉 Redução: {resultado.percentual_reducao:>6.1f}% (R$ {resultado.diferenca_monetaria:>10,.2f})")
                    else:
                        relatorio.append(f"{i:2d}. {resultado.nome_pendencia[:50]:<50}")
                        relatorio.append(f"     📊 De: {resultado.contagem_anterior:>8,} → Para: {resultado.contagem_atual:>8,}")
                        relatorio.append(f"     📉 Redução: {resultado.percentual_reducao:>6.1f}% ({resultado.diferenca:>6,} unidades)")
                    relatorio.append("")
            
            relatorio.append("="*80)
            
            # Salvar relatório
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"relatorio_comparativo_{timestamp}.txt"
            caminho_arquivo = self.output_dir / nome_arquivo
            
            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                f.write('\n'.join(relatorio))
            
            self.logger.info(f"📄 Relatório salvo em: {caminho_arquivo}")
            
            return '\n'.join(relatorio)
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao gerar relatório comparativo: {e}")
            return f"❌ Erro ao gerar relatório: {e}"
    
    def executar_analise_ontem_hoje(self) -> str:
        hoje = datetime.now()
        ontem = hoje - timedelta(days=1)
        
        return self.gerar_relatorio_comparativo(ontem, hoje)
    
    def executar_analise_datas_customizadas(self, data_inicial: str, data_final: str) -> str:
        try:
            data_inicial_dt = datetime.strptime(data_inicial, "%Y-%m-%d")
            data_final_dt = datetime.strptime(data_final, "%Y-%m-%d")
            
            return self.gerar_relatorio_comparativo(data_inicial_dt, data_final_dt)
            
        except ValueError as e:
            return f"❌ Formato de data inválido. Use YYYY-MM-DD: {e}"


def main():
    try:
        # Configurar logging
        setup_logging()
        
        analisador = AnalisadorTendencias()
        
        print("\n" + "="*70)
        print("📊 ANALISADOR DE TENDÊNCIAS DE PENDÊNCIAS")
        print("="*70)
        print("1. 📈 Comparar ontem vs hoje")
        print("2. 📅 Comparar datas customizadas")
        print("3. 🔍 Listar arquivos disponíveis")
        print("0. ❌ Sair")
        print("="*70)
        
        while True:
            try:
                opcao = input("\n👉 Escolha uma opção: ").strip()
                
                if opcao == "1":
                    print("🔄 Analisando tendências (ontem vs hoje)...")
                    resultado = analisador.executar_analise_ontem_hoje()
                    print(resultado)
                    
                elif opcao == "2":
                    data_inicial = input("📅 Data inicial (YYYY-MM-DD): ").strip()
                    data_final = input("📅 Data final (YYYY-MM-DD): ").strip()
                    
                    print(f"🔄 Analisando tendências ({data_inicial} vs {data_final})...")
                    resultado = analisador.executar_analise_datas_customizadas(data_inicial, data_final)
                    print(resultado)
                    
                elif opcao == "3":
                    print("📁 Arquivos de resultados disponíveis:")
                    arquivos = list(analisador.output_dir.glob("resultados_execucao_pendencias_*.json"))
                    if arquivos:
                        for arquivo in sorted(arquivos):
                            data_mod = datetime.fromtimestamp(arquivo.stat().st_mtime)
                            print(f"   📄 {arquivo.name} (modificado: {data_mod.strftime('%d/%m/%Y %H:%M')})")
                    else:
                        print("   ❌ Nenhum arquivo de resultado encontrado")
                    
                elif opcao == "0":
                    print("👋 Saindo do analisador...")
                    break
                    
                else:
                    print("❌ Opção inválida!")
                    
            except KeyboardInterrupt:
                print("\n🛑 Interrompido pelo usuário")
                break
                
    except Exception as e:
        print(f"❌ Erro crítico no analisador: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()