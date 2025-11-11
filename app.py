import os
import json
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, render_template, request, send_file, jsonify, flash, redirect, url_for
from pathlib import Path
import glob
from typing import Dict, List, Any, Optional
import openpyxl
import sys
sys.path.append('.')

from dotenv import load_dotenv
load_dotenv()

from app.services.database import DatabaseService
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pendencias_secret_key_2025')

def formatar_moeda(valor):
    if valor is None or valor == 0:
        return "R$ 0,00"
    try:
        return f"R$ {float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return "R$ 0,00"

def formatar_numero(valor):
    if valor is None or valor == 0:
        return "0"
    try:
        return f"{int(valor):,}".replace(',', '.')
    except (ValueError, TypeError):
        return "0"

@app.template_filter('moeda')
def filtro_moeda(valor):
    return formatar_moeda(valor)

@app.template_filter('numero')
def filtro_numero(valor):
    return formatar_numero(valor)

def calcular_evolucao_pendencia(dados_historicos: List[Dict]) -> List[Dict]:
    """Calcula a evolução de uma pendência entre as datas do histórico"""
    if len(dados_historicos) < 2:
        return []
    
    # Ordenar por data
    dados_ordenados = sorted(dados_historicos, key=lambda x: x['data'])
    evolucoes = []
    
    for i in range(len(dados_ordenados) - 1):
        atual = dados_ordenados[i]
        proximo = dados_ordenados[i + 1]
        
        qtd_anterior = atual['quantidade'] or 0
        qtd_atual = proximo['quantidade'] or 0
        diferenca = qtd_atual - qtd_anterior
        
        # Calcular percentual
        if qtd_anterior != 0:
            percentual = round((diferenca / qtd_anterior) * 100, 2)
        else:
            percentual = 0 if diferenca == 0 else 100
        
        # Determinar tendência
        if diferenca < 0:
            tendencia = 'redução'
        elif diferenca > 0:
            tendencia = 'aumento'
        else:
            tendencia = 'estável'
        
        eh_monetario = atual.get('eh_monetario', False)
        
        evolucoes.append({
            'data_de': atual['data'],
            'data_para': proximo['data'],
            'qtd_anterior': qtd_anterior,
            'qtd_anterior_formatada': formatar_moeda(qtd_anterior) if eh_monetario else formatar_numero(qtd_anterior),
            'qtd_atual': qtd_atual,
            'qtd_atual_formatada': formatar_moeda(qtd_atual) if eh_monetario else formatar_numero(qtd_atual),
            'diferenca': abs(diferenca),
            'diferenca_formatada': formatar_moeda(abs(diferenca)) if eh_monetario else formatar_numero(abs(diferenca)),
            'percentual': percentual,
            'tendencia': tendencia,
            'eh_monetario': eh_monetario
        })
    
    # Retornar em ordem reversa (mais recente primeiro)
    return list(reversed(evolucoes))

class PendenciasWebsite:
    def __init__(self):
        self.output_dir = Path(os.environ.get('OUTPUT_DIR', 'output'))
        self.db_service = DatabaseService()
        self.grupos_info = self._carregar_grupos_do_banco()
        
    def _carregar_grupos_do_banco(self) -> Dict[int, str]:
        try:
            query = """
            SELECT DISTINCT id_grupo, grupo_param 
            FROM amm_consulta_pendencias p
            WHERE id_grupo IS NOT NULL AND grupo_param IS NOT NULL AND p.ativo = 1
            ORDER BY id_grupo
            """
            
            resultados = self.db_service.execute_query(query)
            
            if resultados:
                grupos = {}
                for row in resultados:
                    grupos[row['id_grupo']] = row['grupo_param']
                return grupos
            else:
                return self._grupos_padrao()
                
        except Exception as e:
            print(f"Error loading groups from database: {e}")
            return self._grupos_padrao()
    
    def _grupos_padrao(self) -> Dict[int, str]:
        return {
            1: "ERRO",
            2: "ERRO", 
            3: "ERRO",
            4: "ERRO",
            5: "ERRO",
            6: "ERRO",
            7: "ERRO",
            8: "ERRO",
            9: "ERRO",
            10: "ERRO"
        }
        
    def carregar_dados_historicos(self, limite_dias: int = 3) -> List[Dict]:
        try:
            query = f"""
            SELECT 
                h.idPendencia,
                h.data,
                h.hora,
                h.idUsuario,
                h.qtd,
                p.id_grupo,
                p.nome_pendencia,
                p.grupo_param,
                p.exibe_contagem,
                p.ordem,
                u.nome as nome_usuario
            FROM amm_histPendencias h
            INNER JOIN amm_consulta_pendencias p ON h.idPendencia = p.id_pendencia
            LEFT JOIN amm_usuarios u ON h.idUsuario = u.id
            WHERE h.data >= DATEADD(DAY, -{limite_dias}, GETDATE()) AND p.ativo = 1
            ORDER BY h.data DESC, h.hora DESC
            """
            
            resultados = self.db_service.execute_query(query)
            
            if not resultados:
                print("Nenhum dado histórico encontrado")
                return []
            
            # Agrupar dados por data para simular estrutura anterior
            dados_por_data = {}
            
            for row in resultados:
                data_str = row['data'].strftime('%d/%m/%Y') if hasattr(row['data'], 'strftime') else str(row['data'])
                hora_str = row['hora'].strftime('%H:%M:%S') if hasattr(row['hora'], 'strftime') else str(row['hora'])
                timestamp = f"{data_str} {hora_str}"
                
                data_chave = row['data'].strftime('%Y-%m-%d') if hasattr(row['data'], 'strftime') else str(row['data'])
                
                if data_chave not in dados_por_data:
                    dados_por_data[data_chave] = {
                        'timestamp': timestamp,
                        'data_execucao': data_chave,
                        'resultados': {}
                    }
                
                resultado_key = f"{row['idPendencia']}_{data_chave}_{hora_str}"
                
                dados_por_data[data_chave]['resultados'][resultado_key] = {
                    'id_pendencia': row['idPendencia'],
                    'nome_pendencia': row['nome_pendencia'],
                    'id_grupo': row['id_grupo'],
                    'grupo_param': row['grupo_param'],
                    'total_registros': row['qtd'],
                    'exibe_contagem': row['exibe_contagem'],
                    'status': 'sucesso',
                    'id_usuario': row['idUsuario'],
                    'nome_usuario': row['nome_usuario'],
                    'ordem_prioridade': row.get('ordem', 3)
                }
            
            # Converter para lista ordenada
            dados_historicos = []
            for data_chave in sorted(dados_por_data.keys(), reverse=True):
                dados_historicos.append(dados_por_data[data_chave])
            
            print(f"📊 Carregados {len(dados_historicos)} dias de dados históricos do banco")
            return dados_historicos
            
        except Exception as e:
            print(f"Erro ao carregar dados históricos: {e}")
            return []
    
    def organizar_dados_por_grupo(self, dados_historicos: List[Dict], grupos_selecionados: List[str] = None) -> Dict[int, Dict]:

        dados_por_grupo = {}
        
        for dados in dados_historicos:
            data_execucao = dados.get('data_execucao', '')
            
            for resultado_id, resultado in dados.get('resultados', {}).items():
                id_grupo = resultado.get('id_grupo')
                grupo_param = resultado.get('grupo_param', '')
                
                # Filtrar por grupos selecionados se especificado
                if grupos_selecionados and grupo_param not in grupos_selecionados:
                    continue
                
                if id_grupo is None:
                    id_grupo = 999
                    grupo_param = "Outros"
                
                if id_grupo not in dados_por_grupo:
                    dados_por_grupo[id_grupo] = {
                        'nome_grupo': grupo_param or self.grupos_info.get(id_grupo, f"Grupo {id_grupo}"),
                        'id_grupo': id_grupo,
                        'grupo_param': grupo_param,
                        'historico': [],
                        'pendencias': {}
                    }
                
                id_pendencia = resultado['id_pendencia']
                if id_pendencia not in dados_por_grupo[id_grupo]['pendencias']:
                    dados_por_grupo[id_grupo]['pendencias'][id_pendencia] = {
                        'nome_pendencia': resultado.get('nome_pendencia', f'Pendência {id_pendencia}'),
                        'ordem_prioridade': resultado.get('ordem_prioridade', 3),
                        'dados_historicos': []
                    }
                
                exibe_contagem = resultado.get('exibe_contagem', 1)
                quantidade = resultado.get('total_registros', 0) or 0
                
                # Debug: verificar dados
                if id_pendencia == 1:  # Debug apenas para primeira pendência
                    print(f"Debug - Data: {data_execucao}, Quantidade: {quantidade}, Status: {resultado.get('status')}")
                
                dados_por_grupo[id_grupo]['pendencias'][id_pendencia]['dados_historicos'].append({
                    'data': data_execucao,
                    'quantidade': quantidade,
                    'status': resultado.get('status', 'sucesso'),
                    'exibe_contagem': exibe_contagem,
                    'valor_formatado': formatar_moeda(quantidade) if exibe_contagem == 2 else formatar_numero(quantidade),
                    'eh_monetario': exibe_contagem == 2,
                    'id_usuario': resultado.get('id_usuario'),
                    'nome_usuario': resultado.get('nome_usuario')
                })
        
        # Organizar histórico por data
        for grupo_id, grupo_info in dados_por_grupo.items():
            historico_por_data = {}
            
            for pend_id, pend_info in grupo_info['pendencias'].items():
                for item in pend_info['dados_historicos']:
                    data = item['data']
                    if data not in historico_por_data:
                        historico_por_data[data] = []
                    
                    historico_por_data[data].append({
                        'id_pendencia': pend_id,
                        'nome_pendencia': pend_info['nome_pendencia'],
                        'quantidade': item['quantidade'],
                        'valor_formatado': item['valor_formatado'],
                        'eh_monetario': item['eh_monetario'],
                        'status': item['status'],
                        'nome_usuario': item.get('nome_usuario', 'N/A')
                    })
            
            grupo_info['historico'] = [
                {'data': data, 'itens': itens}
                for data, itens in sorted(historico_por_data.items(), reverse=True)
            ]
        
        return dados_por_grupo
    
    def obter_grupos_disponiveis(self) -> List[Dict]:
        try:
            query = """
            SELECT DISTINCT grupo_param, id_grupo, COUNT(*) as total_pendencias
            FROM amm_consulta_pendencias 
            WHERE grupo_param IS NOT NULL AND ativo = 1
            GROUP BY grupo_param, id_grupo
            ORDER BY grupo_param
            """
            
            resultados = self.db_service.execute_query(query)
            
            grupos = []
            for row in resultados:
                grupos.append({
                    'grupo_param': row['grupo_param'],
                    'id_grupo': row['id_grupo'],
                    'total_pendencias': row['total_pendencias']
                })
            
            return grupos
            
        except Exception as e:
            print(f"Erro ao obter grupos disponíveis: {e}")
            return []

# Global instance
website = PendenciasWebsite()

@app.route('/')
def index():
    try:
        dados_historicos = website.carregar_dados_historicos()
        grupos_selecionados = request.args.getlist('grupos') or None
        dados_por_grupo = website.organizar_dados_por_grupo(dados_historicos, grupos_selecionados)
        grupos_disponiveis = website.obter_grupos_disponiveis()
        
        print(f"DEBUG - Dados históricos carregados: {len(dados_historicos)} dias")
        print(f"DEBUG - Grupos encontrados: {len(dados_por_grupo)}")
        
        # Calcular estatísticas detalhadas
        total_pendencias = sum(len(grupo['pendencias']) for grupo in dados_por_grupo.values())
        total_execucoes = 0
        total_reducoes = 0
        total_aumentos = 0
        
        for grupo in dados_por_grupo.values():
            for pendencia in grupo['pendencias'].values():
                dados_hist = pendencia.get('dados_historicos', [])
                total_execucoes += len(dados_hist)
                
                # Calcular evolução para contar reduções e aumentos
                if len(dados_hist) >= 2:
                    try:
                        evolucao = calcular_evolucao_pendencia(dados_hist)
                        if evolucao and len(evolucao) > 0:
                            ultima_evolucao = evolucao[0]
                            if ultima_evolucao['tendencia'] == 'redução':
                                total_reducoes += 1
                            elif ultima_evolucao['tendencia'] == 'aumento':
                                total_aumentos += 1
                    except Exception as e:
                        print(f"Erro ao calcular evolução: {e}")
        
        print(f"DEBUG - Execuções: {total_execucoes}, Reduções: {total_reducoes}, Aumentos: {total_aumentos}")
        
        estatisticas = {
            'total_grupos': len(dados_por_grupo),
            'total_grupos_disponiveis': len(grupos_disponiveis),
            'total_dias': len(dados_historicos),
            'ultimo_update': dados_historicos[0]['timestamp'] if dados_historicos else 'N/A'
        }
        
        return render_template('index.html', 
                             dados_por_grupo=dados_por_grupo,
                             grupos_info=website.grupos_info,
                             estatisticas=estatisticas,
                             grupos_disponiveis=grupos_disponiveis,
                             grupos_selecionados=grupos_selecionados or [],
                             total_pendencias=total_pendencias,
                             total_execucoes=total_execucoes,
                             total_reducoes=total_reducoes,
                             total_aumentos=total_aumentos)
    except Exception as e:
        flash(f'Erro ao carregar dados: {str(e)}', 'error')
        return render_template('index.html', 
                             dados_por_grupo={}, 
                             grupos_info={}, 
                             estatisticas={},
                             grupos_disponiveis=[],
                             grupos_selecionados=[],
                             total_pendencias=0,
                             total_execucoes=0,
                             total_reducoes=0,
                             total_aumentos=0)

@app.route('/grupo/<int:id_grupo>')
def detalhes_grupo(id_grupo):
    try:
        dados_historicos = website.carregar_dados_historicos()
        dados_por_grupo = website.organizar_dados_por_grupo(dados_historicos)
        
        if id_grupo not in dados_por_grupo:
            flash('Grupo não encontrado', 'error')
            return redirect(url_for('index'))
        
        dados_grupo = dados_por_grupo[id_grupo]
        nome_grupo = website.grupos_info.get(id_grupo, f'Grupo {id_grupo}')
        
        # Criar objeto simples para compatibilidade com template
        class GrupoInfo:
            def __init__(self, dados):
                self.nome_grupo = dados.get('nome_grupo', '')
                self.grupo_param = dados.get('grupo_param', '')
                self.id_grupo = dados.get('id_grupo', id_grupo)
                self.historico = dados.get('historico', [])
                
                # Converter pendencias para objetos compatíveis
                self.pendencias = {}
                datas_unicas = set()
                
                for pend_id, pend_data in dados.get('pendencias', {}).items():
                    # Organizar dados_historicos por data para criar o formato esperado pelo template
                    historico_por_data = {}
                    for dado in pend_data.get('dados_historicos', []):
                        data = dado['data']
                        datas_unicas.add(data)
                        
                        historico_por_data[data] = {
                            'quantidade': dado.get('quantidade', 0),
                            'status': dado.get('status', 'sucesso'),
                            'exibe_contagem': dado.get('exibe_contagem', 1),
                            'valor_formatado': dado.get('valor_formatado', ''),
                            'eh_monetario': dado.get('eh_monetario', False),
                            'id_usuario': dado.get('id_usuario'),
                            'nome_usuario': dado.get('nome_usuario')
                        }
                    
                    # Criar objeto pendencia compatível
                    class PendenciaInfo:
                        def __init__(self, nome, historico_dict, dados_historicos, ordem_prioridade):
                            self.nome_pendencia = nome
                            self.historico = historico_dict
                            self.ordem_prioridade = ordem_prioridade
                            # Pegar o nome do usuário do registro mais recente
                            self.nome_usuario = 'N/A'
                            if dados_historicos:
                                ultimo_registro = dados_historicos[-1]  # Pega o mais recente
                                self.nome_usuario = ultimo_registro.get('nome_usuario') or 'N/A'
                            
                            # Calcular evolução
                            self.evolucao = calcular_evolucao_pendencia(dados_historicos)
                    
                    self.pendencias[pend_id] = PendenciaInfo(
                        pend_data.get('nome_pendencia', f'Pendência {pend_id}'),
                        historico_por_data,
                        pend_data.get('dados_historicos', []),
                        pend_data.get('ordem_prioridade', 3)
                    )
                
                self.historico_datas = list(datas_unicas)
        
        grupo_info = GrupoInfo(dados_grupo)
        
        return render_template('detalhes_grupo.html',
                             grupo_info=grupo_info,
                             nome_grupo=nome_grupo,
                             id_grupo=id_grupo)
    except Exception as e:
        flash(f'Erro ao carregar detalhes do grupo: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/evolucao/<int:id_grupo>')
def api_evolucao_grupo(id_grupo):
    try:
        dados_historicos = website.carregar_dados_historicos()
        dados_por_grupo = website.organizar_dados_por_grupo(dados_historicos)
        
        if id_grupo not in dados_por_grupo:
            return jsonify({'error': 'Grupo não encontrado'}), 404
        
        dados_grupo = dados_por_grupo[id_grupo]
        
        evolucao = []
        for data_info in dados_grupo['historico']:
            data_formatada = datetime.strptime(data_info['data'], '%Y-%m-%d').strftime('%d/%m')
            total_pendencias = sum(item['quantidade'] for item in data_info['itens'] if item['quantidade'])
            
            evolucao.append({
                'data': data_formatada,
                'total': total_pendencias
            })
        
        return jsonify({
            'labels': [item['data'] for item in evolucao],
            'data': [item['total'] for item in evolucao],
            'grupo': website.grupos_info.get(id_grupo, f'Grupo {id_grupo}')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/excel')
def export_excel():
    try:
        dados_historicos = website.carregar_dados_historicos()
        dados_por_grupo = website.organizar_dados_por_grupo(dados_historicos)
        
        filename = f"pendencias_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = website.output_dir / filename
        
        # Simple Excel export
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for grupo_id, grupo_info in dados_por_grupo.items():
                sheet_name = f"Grupo_{grupo_id}"[:31]  # Excel sheet name limit
                
                data_for_excel = []
                for historico in grupo_info['historico']:
                    for item in historico['itens']:
                        data_for_excel.append({
                            'Data': historico['data'],
                            'ID Pendência': item['id_pendencia'],
                            'Nome': item['nome_pendencia'],
                            'Quantidade': item['quantidade'],
                            'Valor Formatado': item['valor_formatado'],
                            'Status': item['status']
                        })
                
                if data_for_excel:
                    df = pd.DataFrame(data_for_excel)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        return send_file(filepath, as_attachment=True, download_name=filename)
        
    except Exception as e:
        flash(f'Erro ao gerar Excel: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/stats')
def api_stats():
    try:
        dados_historicos = website.carregar_dados_historicos()
        dados_por_grupo = website.organizar_dados_por_grupo(dados_historicos)
        
        total_pendencias = 0
        grupos_com_dados = 0
        
        for grupo_info in dados_por_grupo.values():
            if grupo_info['pendencias']:
                grupos_com_dados += 1
                total_pendencias += len(grupo_info['pendencias'])
        
        return jsonify({
            'total_grupos': len(dados_por_grupo),
            'grupos_com_dados': grupos_com_dados,
            'total_pendencias': total_pendencias,
            'ultimo_update': dados_historicos[-1]['timestamp'] if dados_historicos else None
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/grupos-disponiveis')
def api_grupos_disponiveis():
    """
    API para obter lista de grupos disponíveis para filtro
    """
    try:
        grupos = website.obter_grupos_disponiveis()
        return jsonify({
            'grupos': grupos,
            'success': True
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/estatisticas')
def api_estatisticas():
    """
    API para obter estatísticas gerais do dashboard
    """
    try:
        dados_historicos = website.carregar_dados_historicos()
        grupos_disponiveis = website.obter_grupos_disponiveis()
        dados_por_grupo = website.organizar_dados_por_grupo(dados_historicos)
        
        # Calcular estatísticas
        total_pendencias = sum(len(grupo['pendencias']) for grupo in dados_por_grupo.values())
        total_registros = 0
        
        for grupo in dados_por_grupo.values():
            for pendencia in grupo['pendencias'].values():
                for item in pendencia['dados_historicos']:
                    total_registros += item.get('quantidade', 0)
        
        return jsonify({
            'total_grupos_disponiveis': len(grupos_disponiveis),
            'total_grupos_exibidos': len(dados_por_grupo),
            'total_pendencias': total_pendencias,
            'total_registros': total_registros,
            'total_dias': len(dados_historicos),
            'ultimo_update': dados_historicos[0]['timestamp'] if dados_historicos else 'N/A',
            'success': True
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = True 
    app.run(host='0.0.0.0', port=port, debug=debug)