"""Seleção local com orçamento e consulta paginada; não chama outro LLM."""

import json
import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.tools import ToolExecutor


def serializar(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))


def termos(texto: str) -> set[str]:
    normal = unicodedata.normalize("NFKD", texto.casefold())
    normal = "".join(c for c in normal if not unicodedata.combining(c))
    return {p for p in re.findall(r"\w+", normal) if len(p) > 2} - {
        "para", "com", "uma", "que", "por", "dos", "das", "como", "quero", "vou", "meu", "minha",
    }


def selecionar(textos: list[str], consulta: str, limite: int) -> list[str]:
    """Frases inteiras, sem duplicatas; relevância lexical e recência como desempate."""
    palavras = termos(consulta)
    unicos = list(dict.fromkeys(t for t in textos if t))
    ordenados = sorted(enumerate(unicos), key=lambda x: (len(termos(x[1]) & palavras), x[0]), reverse=True)
    escolhidos = []
    usados = 0
    for _, texto in ordenados:
        if usados + len(texto) + 1 <= limite:
            escolhidos.append(texto)
            usados += len(texto) + 1
    return escolhidos


def registros_mundo(w_state) -> list[dict]:
    """Referências estáveis aos registros completos do save, inclusive fora da cena."""
    m = w_state.mundo
    registros = []
    for categoria in ("pessoas", "conflitos", "particularidades", "consequencias", "aprendizados",
                      "momentos", "marcas_jornada", "oportunidades", "projetos", "organizacoes", "instalacoes",
                      "remessas"):
        for chave, obj in getattr(m, categoria).items():
            if categoria == "oportunidades" and w_state.turno >= obj.expira_turno:
                continue
            dados = obj.model_dump(exclude={"propostas"}) if categoria == "projetos" else obj.model_dump()
            if categoria == "remessas":
                dados["local"] = obj.destino
            registros.append({"ref": f"{categoria}/{chave}", "dados": dados})
            if categoria == "projetos":
                for acordo in obj.propostas:
                    registros.append({"ref": f"acordos/{chave}/{acordo.id}", "dados": {
                        **acordo.model_dump(), "projeto": chave,
                        "local": m.pessoas[acordo.npc].local if acordo.npc in m.pessoas else obj.local,
                    }})
    for local, cena in m.cenas.items():
        registros.append({"ref": f"cenas/{local}", "dados": {"local": local, "descricao": cena.descricao}})
        for chave, entidade in cena.entidades.items():
            registros.append({"ref": f"entidades/{local}/{chave}", "dados": {"local": local, **entidade.model_dump()}})
    registros.extend({"ref": f"acontecimentos/{a.id}", "dados": a.model_dump()} for a in m.acontecimentos)
    if m.preparacao and m.preparacao.expira_em > m.minutos:
        registros.append({"ref": "preparacao/atual", "dados": {**m.preparacao.model_dump(), "local": w_state.local}})
    registros.extend({"ref": f"conhecimento/{i}", "dados": c.model_dump()} for i, c in enumerate(m.conhecimento))
    registros.extend({"ref": f"condicoes/{alvo}", "dados": {"alvo": alvo, "condicoes": condicoes}}
                     for alvo, condicoes in m.condicoes.items() if condicoes)
    return registros


def contexto_mundo(w_state, consulta: str, limite: int = 6500) -> dict:
    """Protege regras/limites ao selecionar registros completos em vez de cortar frases."""
    palavras = termos(consulta)
    registros = registros_mundo(w_state)
    pessoas_locais = {p.id for p in w_state.mundo.pessoas.values() if p.local == w_state.local}

    def prioridade(registro):
        dados = registro["dados"]
        local = dados.get("local") == w_state.local
        ref = registro["ref"]
        peso = 0
        if ref.startswith("acordos/") and dados.get("estado") in {"aceita", "cumprida"}:
            peso += 20
        if ref.startswith("projetos/") and dados.get("estado") == "ativo":
            peso += 30
        if ref.startswith("condicoes/") and (
            w_state.local in ref or dados.get("alvo") == "heroi" or dados.get("alvo") in pessoas_locais
        ):
            peso += 25
        if local:
            peso += 12
        if local and ref.startswith(("particularidades/", "pessoas/")):
            peso += 8
        if local and dados.get("estado") in {"disponivel", "ativo"}:
            peso += 8
        if local and ref.startswith("oportunidades/"):
            peso += 10
        peso += min(15, len(termos(serializar(dados)) & palavras) * 3)
        return peso

    relevantes = sorted(registros, key=prioridade, reverse=True)
    saida: dict = {"local": w_state.local, "objetivos": w_state.mundo.objetivos[-2:], "registros": []}
    for registro in relevantes:
        if prioridade(registro) <= 0:
            continue
        proposta = {**saida, "registros": [*saida["registros"], registro]}
        if len(serializar(proposta)) <= limite - 250:
            saida["registros"].append(registro)
    saida["omitidos"] = len(registros) - len(saida["registros"])
    if saida["omitidos"]:
        saida["consulta"] = "consultar_contexto: mundo, registro (ref exata), memoria ou regras; dados privados."
    return saida


def consultar_contexto(executor: "ToolExecutor", assunto: str, consulta: str = "", pagina: int = 0) -> dict:
    """Leitura da campanha atual. Paginação limita bytes, sem destruir o texto original."""
    if not isinstance(consulta, str) or len(consulta) > 200 or type(pagina) is not int or not 0 <= pagina <= 10000:
        return {"erro": "Consulta até 200 caracteres; página inteira entre 0 e 10000."}
    if assunto == "ferramentas":
        from app.services.tools import GRUPOS_FERRAMENTAS, tools_para

        grupo = GRUPOS_FERRAMENTAS.get(consulta)
        if grupo is None:
            return {"grupos": list(GRUPOS_FERRAMENTAS), "erro": "Escolha um grupo do catálogo."}
        permitidas = {t["function"]["name"] for t in tools_para(executor.c_state)}
        return {"habilitar_ferramentas": sorted(grupo & permitidas)}
    registros = registros_mundo(executor.w_state)
    campos_heroi = ("nome", "raca", "classe", "nivel", "atributos", "background", "historia_texto",
                    "objetivo", "inventario", "equipamento", "aliados", "hp_atual", "hp_max", "ouro")
    registros += [
        {"ref": "estado/heroi", "dados": {k: getattr(executor.heroi, k, None) for k in campos_heroi}},
        {"ref": "estado/combate", "dados": executor.c_state.model_dump()},
        {"ref": "estado/missoes", "dados": executor.q_state.model_dump()},
        {"ref": "estado/viagem_progressao", "dados": executor.w_state.model_dump(exclude={"mundo"})},
    ]
    memorias = [
        {"ref": f"historico/{i}", "dados": m.get("content", "")}
        for i, m in enumerate(executor.heroi.historico_chat or []) if m.get("content")
    ] + [{"ref": f"resumo/{campo}/{i}", "dados": texto}
         for campo, textos in (executor.heroi.resumo_rolante or {}).items()
         for i, texto in enumerate(textos) if isinstance(texto, str)]
    if assunto == "registro":
        from app.services.rag_regras import _secoes

        registros += memorias + [{"ref": f"regras/{i}", "dados": s} for i, s in enumerate(_secoes())]
        registro = next((r for r in registros if r["ref"] == consulta), None)
        if registro is None:
            return {"erro": "Referência não encontrada; busque por mundo antes."}
        texto = serializar(registro)
        inicio = pagina * 3000
        return {"ref": consulta, "fragmento_json": texto[inicio:inicio + 3000],
                "proxima_pagina": pagina + 1 if inicio + 3000 < len(texto) else None}
    if assunto == "memoria":
        registros = memorias
    elif assunto == "regras":
        from app.services.rag_regras import _secoes

        registros = [{"ref": f"regras/{i}", "dados": secao} for i, secao in enumerate(_secoes())]
    elif assunto != "mundo":
        return {"erro": "Assuntos: mundo, registro, memoria, regras, ferramentas."}
    palavras = termos(consulta)
    encontrados = [(len(termos(serializar(r)) & palavras), i, r) for i, r in enumerate(registros)]
    encontrados = sorted((r for r in encontrados if r[0] or not palavras), key=lambda r: (r[0], r[1]), reverse=True)
    # Resultados completos viram fragmentos endereçáveis, com metadados de continuação.
    paginas = []
    for _, _, registro in encontrados:
        texto = serializar(registro["dados"])
        for inicio in range(0, len(texto), 2400):
            paginas.append({"ref": registro["ref"], "trecho": texto[inicio:inicio + 2400],
                            "parte": inicio // 2400 + 1, "partes": (len(texto) + 2399) // 2400})
    return {"resultados": paginas[pagina:pagina + 1], "total_paginas": len(paginas),
            "proxima_pagina": pagina + 1 if pagina + 1 < len(paginas) else None,
            "aviso": "Arquivo privado do Mestre; rumores não são fatos e NPCs não sabem tudo que o arquivo contém."}
