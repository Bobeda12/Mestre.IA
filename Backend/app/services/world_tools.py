"""As mesmas operações atendem o narrador e os controles visuais."""

from collections.abc import Callable

from app.domain.emergencia import Aprendizado, Consequencia, Intencao, Particularidade
from app.domain.imersao import MarcaJornada, MomentoPessoal, Oportunidade
from app.domain.instalacoes import Instalacao
from app.domain.living_world import ConflitoMundo, EntidadeCena, PessoaMundo
from app.domain.organizacoes import Organizacao
from app.domain.projetos import CondicaoProjeto, PropostaProjeto
from app.services import economia, emergencia, imersao, instalacoes, organizacoes, projetos
from app.services import living_world as mundo

# Chaves que só o Pydantic usa — o servidor revalida tudo com o modelo de
# verdade em `registrar_*`, então mandá-las ao LLM é só custo de token
# (Fase 0 do plano "jogo completo": o teto de tokens por minuto do provedor
# gratuito fez cada byte de schema contar).
_SO_PYDANTIC = {"$defs", "title", "default", "maxLength", "minLength", "maximum", "minimum", "pattern", "maxItems"}
# Campos que o SERVIDOR preenche ou zera no registro (`registrar_pessoa`
# reseta memória e clampa confiança; relógios e descobertas são estado de
# jogo) — o narrador não decide nenhum deles, então não os enxerga.
_CAMPOS_DO_SERVIDOR = {
    "segredo_revelado", "confianca", "lembrancas", "promessas",  # PessoaMundo
    "progresso", "proximo_avanco", "estado_relogio", "intervencoes", "desfecho",  # ConflitoMundo
    "descoberto", "bloqueado_por", "recolhido",  # EntidadeCena
    "turno",  # Conhecimento
    "pistas_descobertas", "expira_turno", "nome_organizacao", "nome_npc", "estoque", "estoque_inicializado",
    # Fase 1 (Mundo Vivo) — "evidencia"/"ativa" só existem em modelos onde o
    # servidor sempre os sobrescreve (CondicaoProjeto, PropostaProjeto,
    # Instalacao); ao contrário de "local"/"origem"/"organizacao"/"estado",
    # nenhum desses dois nomes é reaproveitado em outro modelo como entrada
    # legítima da IA, então é seguro tirá-los do schema em todo lugar.
    "evidencia", "ativa",
}


def _expandir(schema: dict, raiz: dict | None = None) -> dict:
    raiz = raiz or schema
    if "$ref" in schema:
        return _expandir(raiz["$defs"][schema["$ref"].split("/")[-1]], raiz)
    saida = {
        k: (
            _expandir(v, raiz)
            if isinstance(v, dict)
            else [_expandir(item, raiz) if isinstance(item, dict) else item for item in v]
            if isinstance(v, list)
            else v
        )
        for k, v in schema.items()
        if k not in _SO_PYDANTIC
    }
    propriedades = saida.get("properties")
    if isinstance(propriedades, dict):
        propriedades = {k: v for k, v in propriedades.items() if k not in _CAMPOS_DO_SERVIDOR}
        saida["properties"] = propriedades
        obrigatorios = saida.get("required")
        if isinstance(obrigatorios, list):
            saida["required"] = [k for k in obrigatorios if k in propriedades]
    # `anyOf: [{type: X}, {type: null}]` (Optional) vira só `type: X`
    if isinstance(saida.get("anyOf"), list):
        tipos = [o for o in saida["anyOf"] if o.get("type") != "null"]
        if len(tipos) == 1:
            saida = {**{k: v for k, v in saida.items() if k != "anyOf"}, **tipos[0]}
    return saida


def _tool(nome, descricao, propriedades, obrigatorios):
    return {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "parameters": {"type": "object", "properties": propriedades, "required": obrigatorios},
        },
    }


S = {"type": "string"}
WORLD_DISPATCH: dict[str, Callable] = {
    "despachar_remessa": economia.despachar_remessa,
    "propor_instalacao": instalacoes.propor_instalacao,
    "usar_instalacao": instalacoes.usar_instalacao,
    "registrar_organizacao": organizacoes.registrar_organizacao,
    "mobilizar_organizacao": organizacoes.mobilizar_organizacao,
    "propor_acordo_projeto": projetos.propor_acordo_projeto,
    "decidir_acordo_projeto": projetos.decidir_acordo_projeto,
    "cumprir_acordo_projeto": projetos.cumprir_acordo_projeto,
    "gerir_projeto": projetos.gerir_projeto,
    "planejar_projeto": projetos.planejar_projeto,
    "registrar_avanco_projeto": projetos.registrar_avanco_projeto,
    "registrar_momento": imersao.registrar_momento,
    "registrar_marca": imersao.registrar_marca,
    "apresentar_oportunidades": imersao.apresentar_oportunidades,
    "registrar_particularidade": emergencia.registrar_particularidade,
    "resolver_intencao": emergencia.resolver_intencao,
    "desenvolver_consequencia": emergencia.desenvolver_consequencia,
    "propor_aprendizado": emergencia.propor_aprendizado,
    "escolher_aprendizado": emergencia.escolher_aprendizado,
    "registrar_cena": mundo.registrar_cena,
    "registrar_pessoa": mundo.registrar_pessoa,
    "registrar_conflito": mundo.registrar_conflito,
    "agir_no_mundo": mundo.agir_no_mundo,
    "intervir_conflito": mundo.intervir_conflito,
    "definir_objetivo": mundo.definir_objetivo,
    "escolher_especializacao": mundo.escolher_especializacao,
    "registrar_vinculo": mundo.registrar_vinculo,
    "abrir_arco": mundo.abrir_arco,
    "encerrar_arco": mundo.encerrar_arco,
}
WORLD_TOOLS = [
    _tool("despachar_remessa", "Transfere estoque real entre comerciantes por saída direta existente. "
          "Requer remetente presente e acontecimento que justifique a decisão comercial, respeitando seus interesses. "
          "Não use simples pedido como prova de acordo. Reserva 1–3 unidades; chega em 2h se a rota estiver acessível. "
          "Bloqueios retêm carga; não gera itens nem altera o ouro do herói. Uma remessa ativa por remetente.",
          {"id": S, "remetente": S, "destinatario": S, "passagem": S, "item": S,
           "quantidade": {"type": "integer"}, "acontecimento": S},
          ["id", "remetente", "destinatario", "passagem", "item", "quantidade", "acontecimento"]),
    _tool("propor_instalacao", "Melhoria física derivada de projeto concluído aqui e condição com evidência. "
          "A evidência precisa justificar o uso e permanecer no alvo. Um projeto sustenta uma instalação. "
          "abrigo permite descanso longo; oficina prepara +1 no próximo resolver_intencao do atributo definido, "
          "sem acumular, por 24h; preparar custa 1h. Nome e descrição próprios da história, números do motor. "
          "O jogador inaugura. Não transforme qualquer feito em abrigo ou oficina sem fundamento.",
          {"instalacao": _expandir(Instalacao.model_json_schema())}, ["instalacao"]),
    _tool("registrar_organizacao", "Apresente grupo gerado com propósito e princípio públicos próprios. "
          "Membros são IDs de NPCs presentes; não filie o herói. Não copie segredos. Identidade é persistente.",
          {"organizacao": _expandir(Organizacao.model_json_schema())}, ["organizacao"]),
    _tool("mobilizar_organizacao", "Organização reage a acontecimento real conhecido por membro presente. "
          "A iniciativa usa relógio: efeito bloquear muda alvo registrado; partir afasta o agente; disputa registra "
          "desfecho social sem conceder recursos. Sinal deve anunciar risco e permitir intervenção. "
          "Respeite recursos, princípios, regras e conquistas; não imponha obrigações ao herói. "
          "Um representante por iniciativa; máximo duas ativas por grupo. Não executa imediatamente.",
          {"organizacao": S, "origem": S, "iniciativa": _expandir(ConflitoMundo.model_json_schema())},
          ["organizacao", "origem", "iniciativa"]),
    _tool("propor_acordo_projeto", "Proposta de NPC presente sobre condição aberta de projeto. "
          "Oferta, contrapartida e motivo declarado devem respeitar seus recursos, desejos e limites. "
          "exclusiva=true impede outros acordos na mesma condição enquanto o vínculo persistir. "
          "Somente o jogador aceita. Não entregue recursos, não revele motivos secretos, não invente influência.",
          {"projeto": S, "proposta": _expandir(PropostaProjeto.model_json_schema())}, ["projeto", "proposta"]),
    _tool("cumprir_acordo_projeto", "Registre contrapartida cumprida apenas quando a mudança executada "
          "realmente atende ao compromisso. origem=acontecimento_id bem-sucedido; evidencia=texto exato "
          "de condição persistente do alvo da condição do projeto, presente nesse acontecimento. "
          "Não confunda cumprir promessa com receber a oferta; não entrega recursos.",
          {"projeto": S, "acordo": S, "origem": S, "evidencia": S},
          ["projeto", "acordo", "origem", "evidencia"]),
    _tool("planejar_projeto", "Proponha condições de resultado para a ambição escolhida pelo jogador. "
          "Use alvos presentes, interesses particulares e meios livres; não imponha missões ou sequência. "
          "Condições registradas são preservadas. Não invente obrigações já aceitas.",
          {"projeto": S, "condicoes": {"type": "array", "items": _expandir(CondicaoProjeto.model_json_schema())}},
          ["projeto", "condicoes"]),
    _tool("registrar_avanco_projeto", "Associe mudança já realizada à condição do projeto. origem=acontecimento_id "
          "bem-sucedido; evidencia=texto exato de condição persistente produzida nesse acontecimento no alvo. "
          "Use superada=true quando uma solução alternativa tornou a exigência desnecessária. "
          "Só registre quando a evidência realmente satisfaz ou supera o resultado desejado; promessas não bastam.",
          {"projeto": S, "condicao": S, "origem": S, "evidencia": S, "superada": {"type": "boolean"}},
          ["projeto", "condicao", "origem", "evidencia"]),
    _tool("registrar_momento", "Gesto ou convite de NPC presente, ligado a acontecimento real. "
          "Convivência sem missão obrigatória: use hábito/voz, não imponha aceitação, afeto ou promessa do jogador.",
          {"momento": _expandir(MomentoPessoal.model_json_schema())}, ["momento"]),
    _tool("registrar_marca", "Registre identidade conquistada: apelido atribuído por NPC, vínculo observado, "
          "significado de objeto possuído ou feito. Exige origem real; não dá bônus nem define sentimentos do herói.",
          {"marca": _expandir(MarcaJornada.model_json_schema())}, ["marca"]),
    _tool("apresentar_oportunidades", "Registre percepções e riscos atuais em alvos existentes, sem indicar solução "
          "obrigatória ou criar recurso conveniente. Expiram; podem ser ignoradas. Não revela segredos.",
          {"oportunidades": {"type": "array", "items": _expandir(Oportunidade.model_json_schema())}},
          ["oportunidades"]),
    _tool("resolver_intencao", "Resolve ação criativa sem verbo predefinido. Declare fundamento na ficção, "
          "efeitos de sucesso E falha antes do dado. Condições são fatos ficcionais, não dano/HP/itens. "
          "Respeite limites pessoais e regras estabelecidas; não converta alegação do jogador em verdade. "
          "Efeitos não podem impor escolhas ao herói. Custa uma ação; motor decide teste e reação.",
          {"proposta": _expandir(Intencao.model_json_schema())}, ["proposta"]),
    _tool("registrar_particularidade", "Registre regra singular de alvo real antes de apresentá-la. "
          "Não invente imunidades retroativas; id existente preserva regra. publica=false oculta regra, mostra pista. "
          "pistas são evidências alternativas predefinidas. resolver_intencao efeito pista usa alvo=id da regra "
          "e texto=id da pista; revelar mostra a regra. Não exija ordem nem todas as pistas para uma boa dedução.",
          {"particularidade": _expandir(Particularidade.model_json_schema())}, ["particularidade"]),
    _tool("desenvolver_consequencia", "Gere uma iniciativa de NPC motivada por acontecimento_id real. "
          "Use o que o NPC sabe, quer e teme; sinal perceptível, sem desfecho obrigatório. "
          "Prazo torna iniciativa disponível, não vitória automática. substitui=id permite replanejar "
          "iniciativa do mesmo agente à luz de um novo acontecimento.",
          {"consequencia": _expandir(Consequencia.model_json_schema())}, ["consequencia"]),
    _tool("propor_aprendizado", "Ofereça aprendizado singular apoiado em duas ações livres registradas. "
          "Nome e descrição vêm das experiências; bônus situacional +1 em atributo/alvo, só após escolha na interface.",
          {"aprendizado": _expandir(Aprendizado.model_json_schema())}, ["aprendizado"]),
    _tool(
        "registrar_cena",
        "Registre objetos e saídas que existem na cena ANTES de narrar sua presença. "
        "Aditivo: nunca restaura o estado anterior. Não crie recursos só para garantir sucesso do jogador.",
        {"descricao": S, "entidades": {"type": "array", "items": _expandir(EntidadeCena.model_json_schema())}},
        ["descricao", "entidades"],
    ),
    _tool(
        "registrar_pessoa",
        "Registre uma pessoa apresentada na cena: desejos, medo, limite, necessidade concreta "
        "e conhecimento separado em fato/boato/suspeita. Segredos nunca são expostos ao jogador automaticamente.",
        {"pessoa": _expandir(PessoaMundo.model_json_schema())},
        ["pessoa"],
    ),
    _tool(
        "registrar_conflito",
        "Registre uma iniciativa do NPC presente, com sinal perceptível, prazo em minutos "
        "e consequência causal. No máximo 2 conflitos novos por cena. Sem roteiro obrigatório ou morte automática.",
        {"conflito": _expandir(ConflitoMundo.model_json_schema())},
        ["conflito"],
    ),
    _tool(
        "agir_no_mundo",
        (
            "Resolve uma intenção livre pelas propriedades reais do alvo (ex: bloquear alvo=porta" 
            "meio=estante; destrancar; negociar com proposta). Use IDs do estado; meio = objeto da cena ou" 
            "item possuído. Examinar/investigar dão informação, não loot; falha mantém alternativas; limites" 
            "do NPC valem."
        ),
        {"acao": {"type": "string", "enum": list(mundo.ACOES)}, "alvo": S, "meio": S, "proposta": S},
        ["acao", "alvo"],
    ),
    _tool(
        "intervir_conflito",
        "Apoie, atrase ou resolva um conflito atual por proposta concreta do jogador. "
        "Resolver exige agente cooperativo e duas intervenções bem-sucedidas; recompensa única.",
        {"conflito": S, "abordagem": {"type": "string", "enum": ["apoiar", "atrasar", "resolver"]}, "proposta": S},
        ["conflito", "abordagem", "proposta"],
    ),
    _tool(
        "definir_objetivo",
        "Define o objetivo atual do jogador (única ferramenta pra isso — não existe mais 'atualizar_missao'). "
        "origem='jogador': ele mesmo decidiu perseguir algo, inclusive abandonar a missão anterior; "
        "nome é opcional (vira 'Meu caminho'). origem='npc': alguém deu uma tarefa nova; informe "
        "nome (título curto, ex: 'Resgatar o Ferreiro'). Nunca use origem='npc' pra substituir um "
        "objetivo que o próprio jogador acabou de declarar sem que a ficção justifique a mudança.",
        {"objetivo": S, "nome": S, "origem": {"type": "string", "enum": ["jogador", "npc"]}},
        ["objetivo", "origem"],
    ),
    _tool(
        "registrar_vinculo",
        "Registre uma promessa explícita do jogador ou um boato/suspeita comunicado "
        "na conversa atual. Não transforma alegações em fatos; a pessoa deve estar presente.",
        {"npc": S, "natureza": {"type": "string", "enum": ["promessa", "boato", "suspeita"]}, "texto": S},
        ["npc", "natureza", "texto"],
    ),
    _tool(
        "abrir_arco",
        "Quando um conflito registrado ganha peso de história e não há arco ativo, abra um arco com "
        "título e premissa. É o capítulo atual da campanha; o servidor decide quando ele pode encerrar.",
        {"titulo": S, "premissa": S, "conflito": {"type": "string", "description": "id do conflito central"}},
        ["titulo", "premissa", "conflito"],
    ),
    _tool(
        "encerrar_arco",
        "Peça o fechamento do arco atual. Só passa se o servidor confirmar (turnos mínimos, fatos "
        "registrados, conflito central resolvido/concretizado ou chefe enfrentado). Nunca narre um fim de "
        "arco sem esta ferramenta devolver encerrado=true.",
        {"resumo_proposto": S},
        [],
    ),
    _tool(
        "escolher_especializacao",
        "Aplique a escolha explícita de especialização do jogador. "
        "Disponível nos níveis 3 e 7, trocável fora de combate; nunca escolhe por ele.",
        {
            "marco": {"type": "string", "enum": ["3", "7"]},
            "escolha": {"type": "string", "enum": ["explorador", "diplomata", "combatente"]},
        },
        ["marco", "escolha"],
    ),
]
