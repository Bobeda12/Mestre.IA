"""Modelo tipado do sumário rolante — a memória de médio prazo (Etapa 5). É
a forma do JSON gravado em `personagens.resumo_rolante`: quatro listas
estruturadas em vez de um resumo em texto solto, para o narrador conseguir
citar um fato específico sem precisar reinterpretar um parágrafo."""

from pydantic import BaseModel


class ResumoRolante(BaseModel):
    fatos_estabelecidos: list[str] = []
    npcs_conhecidos: list[str] = []
    promessas_feitas: list[str] = []
    mudancas_no_mundo: list[str] = []
