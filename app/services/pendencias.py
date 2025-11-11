import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.models.pendencia import Pendencia, ResultadoExecucao, ResumoExecucao
from app.services.database import DatabaseService

try:
    from config.settings import MAIN_QUERY, APP_CONFIG
except ImportError:
    MAIN_QUERY = "SELECT id, id_pendencia, consulta_pendencia, id_grupo, nome_pendencia, dt_criacao, dt_modificacao FROM amm_consulta_pendencias AND ativo = 1 ORDER BY id"
    APP_CONFIG = {'output_dir': 'output'}


class PendenciasService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db_service = DatabaseService()
        self.output_dir = Path(APP_CONFIG['output_dir'])
        self.output_dir.mkdir(exist_ok=True)
    
    def _inserir_historico_pendencia(self, conn, id_pendencia: int, quantidade: int, id_usuario: int = 1) -> bool:
        try:
            agora = datetime.now()
            data_atual = agora.strftime('%Y-%m-%d')
            hora_atual = agora.strftime('%H:%M:%S')
            
            cursor = conn.cursor()
            
            query_verificar = """
            SELECT COUNT(*) as total 
            FROM amm_histPendencias 
            WHERE idPendencia = ? AND data = ? 
            """
            
            cursor.execute(query_verificar, (id_pendencia, data_atual))
            resultado = cursor.fetchone()
            existe_registro = resultado[0] > 0
            
            if existe_registro:
                query_update = """
                UPDATE amm_histPendencias 
                SET hora = ?, idUsuario = ?, qtd = ?, idGestora = 919, usoSistema = 1, responsabilidade = ''
                WHERE idPendencia = ? AND data = ?
                """
                cursor.execute(query_update, (hora_atual, id_usuario, quantidade, id_pendencia, data_atual))
            else:
                query_insert = """
                INSERT INTO amm_histPendencias 
                (idPendencia, data, hora, idUsuario, qtd, idGestora, usoSistema, responsabilidade)
                VALUES (?, ?, ?, ?, ?, 919, 1, '')
                """
                cursor.execute(query_insert, (id_pendencia, data_atual, hora_atual, id_usuario, quantidade))
            
            conn.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to insert/update history for pendência {id_pendencia}: {e}")
            return False
    
    def extrair_pendencias(self) -> Optional[List[Pendencia]]:
        results = self.db_service.execute_query(MAIN_QUERY)
        if not results:
            self.logger.error("Failed to extract pendências from database")
            return None
        
        pendencias = []
        for row in results:
            pendencia = Pendencia(
                id=row['id'],
                id_pendencia=row['id_pendencia'],
                consulta_pendencia=row['consulta_pendencia'],
                id_grupo=row.get('id_grupo'),
                nome_pendencia=row.get('nome_pendencia'),
                dt_criacao=row.get('dt_criacao'),
                dt_modificacao=row.get('dt_modificacao'),
                exibe_contagem=row.get('exibe_contagem')
            )
            pendencias.append(pendencia)
        
        return pendencias
    
    def executar_todas_consultas(self) -> Optional[ResumoExecucao]:
        self.logger.info("Starting execution of all pendência queries")
        self.logger.info("=" * 60)
        
        # Extrair pendências
        pendencias = self.extrair_pendencias()
        if not pendencias:
            return None
        
        self.logger.info(f" Total de consultas para executar: {len(pendencias)}")
        self.logger.info("-" * 60)
        
        resultados = []
        consultas_executadas = 0
        consultas_com_erro = 0
        
        # Executar com conexão única
        try:
            with self.db_service.get_connection() as conn:
                for i, pendencia in enumerate(pendencias, 1):
                    resultado = self._executar_consulta_individual(
                        conn, pendencia, i, len(pendencias)
                    )
                    resultados.append(resultado)
                    
                    if resultado.status == 'sucesso':
                        consultas_executadas += 1
                    else:
                        consultas_com_erro += 1
        
        except Exception as e:
            self.logger.error(f"Critical execution error: {e}")
            return None
        
        # Criar resumo
        resumo = self._criar_resumo_execucao(
            resultados, len(pendencias), consultas_executadas, consultas_com_erro
        )
        
        # Salvar resultados
        self._salvar_resultados(resumo)
        
        return resumo
    
    def _executar_consulta_individual(
        self, 
        conn, 
        pendencia: Pendencia, 
        index: int, 
        total: int
    ) -> ResultadoExecucao:
        nome_display = pendencia.nome_pendencia or f"Pendência {pendencia.id_pendencia}"
        
        try:
            cursor = conn.cursor()
            cursor.execute(pendencia.consulta_pendencia)
            
            row = cursor.fetchone()
            if row and len(row) > 0:
                quantidade = int(row[0]) if row[0] is not None else 0
                
                self._inserir_historico_pendencia(conn, pendencia.id_pendencia, quantidade)
                
                return ResultadoExecucao(
                    id=pendencia.id,
                    id_pendencia=pendencia.id_pendencia,
                    nome_pendencia=pendencia.nome_pendencia,
                    id_grupo=pendencia.id_grupo,
                    quantidade=quantidade,
                    status='sucesso',
                    exibe_contagem=pendencia.exibe_contagem,
                    consulta_preview=pendencia.consulta_pendencia[:100] + "..." if len(pendencia.consulta_pendencia) > 100 else pendencia.consulta_pendencia
                )
            else:
                self.logger.warning(f"No results for query: {nome_display}")
                
                self._inserir_historico_pendencia(conn, pendencia.id_pendencia, 0)
                
                return ResultadoExecucao(
                    id=pendencia.id,
                    id_pendencia=pendencia.id_pendencia,
                    nome_pendencia=pendencia.nome_pendencia,
                    id_grupo=pendencia.id_grupo,
                    quantidade=0,
                    status='sucesso',
                    exibe_contagem=pendencia.exibe_contagem
                )
                
        except Exception as e:
            self.logger.error(f"Error executing query for {nome_display}: {str(e)}")
            return ResultadoExecucao(
                id=pendencia.id,
                id_pendencia=pendencia.id_pendencia,
                nome_pendencia=pendencia.nome_pendencia,
                id_grupo=pendencia.id_grupo,
                quantidade=None,
                status='erro',
                exibe_contagem=pendencia.exibe_contagem,
                erro=str(e),
                consulta_preview=pendencia.consulta_pendencia[:100] + "..." if len(pendencia.consulta_pendencia) > 100 else pendencia.consulta_pendencia
            )
    
    def _criar_resumo_execucao(
        self, 
        resultados: List[ResultadoExecucao], 
        total: int, 
        executadas: int, 
        erros: int
    ) -> ResumoExecucao:
        # Calcular estatísticas
        resultados_com_dados = [r for r in resultados if r.status == 'sucesso' and r.quantidade and r.quantidade > 0]
        total_pendencias = sum(r.quantidade for r in resultados_com_dados)
        
        # Top 5 pendências
        top_pendencias = sorted(resultados_com_dados, key=lambda x: x.quantidade, reverse=True)[:5]
        top_list = []
        for i, pend in enumerate(top_pendencias, 1):
            nome_display = pend.nome_pendencia or f"Pendência {pend.id_pendencia}"
            top_list.append({
                'posicao': i,
                'id': pend.id,
                'nome': nome_display,
                'quantidade': pend.quantidade
            })
        
        return ResumoExecucao(
            timestamp=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            total_consultas=total,
            consultas_executadas=executadas,
            consultas_com_erro=erros,
            total_pendencias_encontradas=total_pendencias,
            resultados=resultados,
            top_pendencias=top_list
        )
    
    def _salvar_resultados(self, resumo: ResumoExecucao) -> None:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"resultados_execucao_pendencias_{timestamp}.json"
            filepath = self.output_dir / filename
            
            # Converter resultados para dict
            data = {
                'timestamp': resumo.timestamp,
                'total_consultas': resumo.total_consultas,
                'consultas_executadas': resumo.consultas_executadas,
                'consultas_com_erro': resumo.consultas_com_erro,
                'total_pendencias_encontradas': resumo.total_pendencias_encontradas,
                'taxa_sucesso': resumo.taxa_sucesso,
                'top_pendencias': resumo.top_pendencias,
                'resultados': {
                    str(r.id): {
                        'id': r.id,
                        'id_pendencia': r.id_pendencia,
                        'nome_pendencia': r.nome_pendencia,
                        'id_grupo': r.id_grupo,
                        'total_registros': r.quantidade,
                        'exibe_contagem': r.exibe_contagem,
                        'status': r.status,
                        'erro': r.erro,
                        'consulta_preview': r.consulta_preview
                    }
                    for r in resumo.resultados
                }
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            
            
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")
    
    def imprimir_resumo_final(self, resumo: ResumoExecucao) -> None:
        print("\n" + "=" * 60)
        print("EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Successful queries: {resumo.consultas_executadas}")
        print(f"Failed queries: {resumo.consultas_com_erro}")
        print(f"Success rate: {resumo.taxa_sucesso:.1f}%")
        print(f"Total pendências found: {resumo.total_pendencias_encontradas}")
        
        if resumo.top_pendencias:
            print(f"\nTOP 5 PENDÊNCIAS WITH MOST RESULTS:")
            for top in resumo.top_pendencias:
                print(f"   {top['posicao']}. ID {top['id']} - {top['nome']}: {top['quantidade']} items")
        
        print("Reports saved successfully!")