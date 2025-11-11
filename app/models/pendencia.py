
from dataclasses import dataclass
from typing import Optional, Any, Dict, List
from datetime import datetime


@dataclass
class Pendencia:
    id: int
    id_pendencia: int
    consulta_pendencia: str
    id_grupo: Optional[int] = None
    nome_pendencia: Optional[str] = None
    dt_criacao: Optional[datetime] = None
    dt_modificacao: Optional[datetime] = None
    exibe_contagem: Optional[int] = None


@dataclass
class ResultadoExecucao:
    id: int
    id_pendencia: int
    nome_pendencia: Optional[str]
    id_grupo: Optional[int]
    quantidade: Optional[int]
    status: str
    exibe_contagem: Optional[int] = None
    erro: Optional[str] = None
    consulta_preview: Optional[str] = None


@dataclass
class ResumoExecucao:
    timestamp: str
    total_consultas: int
    consultas_executadas: int
    consultas_com_erro: int
    total_pendencias_encontradas: int
    resultados: List[ResultadoExecucao]
    top_pendencias: List[Dict[str, Any]]
    
    @property
    def taxa_sucesso(self) -> float:
        if self.total_consultas == 0:
            return 0.0
        return (self.consultas_executadas / self.total_consultas) * 100