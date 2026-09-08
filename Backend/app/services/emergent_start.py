"""Composição de condições iniciais, sem sequência de cenas ou atos obrigatórios."""

import random
import secrets

from app.domain.living_world import SAIDA_LIVRE, CenaPersistente, ConflitoMundo, EntidadeCena, MundoVivo, PessoaMundo


def validar_mundo_inicial(dados: dict, local: str) -> dict:
    mundo = MundoVivo.model_validate(dados)
    if local not in mundo.cenas or len(mundo.cenas) > 8 or len(mundo.pessoas) > 8 or len(mundo.conflitos) > 4:
        raise ValueError("Origem sem cena coerente ou maior que o limite inicial.")
    for cena in mundo.cenas.values():
        if len(cena.entidades) > 20 or any(chave != entidade.id for chave, entidade in cena.entidades.items()):
            raise ValueError("Entidades iniciais inválidas.")
    for chave, pessoa in mundo.pessoas.items():
        if chave != pessoa.id or pessoa.local not in mundo.cenas:
            raise ValueError("Pessoa sem local existente.")
        pessoa.confianca = max(-20, min(20, pessoa.confianca))
        pessoa.segredo_revelado = False
        pessoa.lembrancas = []
        pessoa.promessas = []
    for chave, conflito in mundo.conflitos.items():
        if chave != conflito.id or conflito.agente not in mundo.pessoas or conflito.local not in mundo.cenas:
            raise ValueError("Conflito sem agente ou local.")
        if conflito.efeito == "bloquear" and conflito.alvo not in mundo.cenas[conflito.local].entidades:
            raise ValueError("Conflito sem alvo existente.")
        conflito.progresso = conflito.intervencoes = 0
        conflito.estado = "ativo"
        conflito.proximo_avanco = conflito.intervalo
    mundo.minutos = 0
    mundo.especializacoes = {}
    mundo.conhecimento = []
    mundo.tentativas = {}
    return mundo.model_dump()


def criar_origem(char, semente: int | None = None) -> dict:
    semente = semente if semente is not None else secrets.randbelow(2**31 - 1) + 1
    rng = random.Random(semente)
    lugar, descricao, clima = rng.choice(
        [
            ("Entreposto das Pontes", "Pontes de madeira ligam oficinas sobre um rio cheio.", "Chuva fina"),
            ("Porto das Lanternas", "Barcos silenciosos cercam um mercado iluminado por lanternas.", "Névoa"),
            ("Jardim das Ruínas", "Casas e hortas ocupam as fundações de uma cidade abandonada.", "Vento seco"),
            ("Oficinas da Serra", "Ferreiros e viajantes dividem abrigo numa passagem montanhosa.", "Frio"),
            ("Pátio dos Viajantes", "Caravanas negociam espaço junto a um poço comunitário.", "Céu limpo"),
            ("Mercado das Raízes", "Bancas se distribuem entre as raízes de árvores antigas.", "Nublado"),
        ]
    )
    aliada, rival = rng.sample(["Íria", "Ravi", "Dara", "Nilo", "Sena", "Cael", "Olma", "Tália"], 2)
    recurso = rng.choice(["água limpa", "remédios", "ferramentas", "sementes", "alimentos", "abrigo"])
    evento = rng.choice(
        [
            "um carregamento chegou com o selo de alguém que desapareceu",
            "os registros de distribuição foram alterados durante a noite",
            "uma testemunha afirma que a escassez foi provocada",
            "uma oferta de ajuda chegou acompanhada de uma exigência inesperada",
            "dois grupos apresentam documentos válidos para a mesma entrega",
            "uma rota antes segura foi fechada sem explicação",
        ]
    )
    necessidade = rng.choice(["Tocha", "Poção de Cura", "Corda"])
    interesse = rng.choice(
        [
            "garantir uma reserva para famílias que vivem longe do mercado",
            "pagar trabalhadores que passaram semanas sem receber",
            "reparar uma dívida sem expor quem confiou em sua palavra",
            "evitar que uma disputa local seja usada como pretexto para ocupação",
        ]
    )
    prazo = rng.choice([60, 90, 120])
    porta = EntidadeCena(
        id="passagem",
        nome="Portão do depósito",
        tipo="saida",
        destino=f"Depósito de {lugar}",
        descricao="Uma passagem para a área de armazenamento.",
        propriedades=["trancado", "mecanismo"],
    )
    cena = CenaPersistente(
        descricao=descricao,
        visitas=1,
        entidades={
            "passagem": porta,
            "estante": EntidadeCena(
                id="estante",
                nome="Estante de madeira",
                descricao="Uma estante perto do portão.",
                propriedades=["movel", "pesado", "inflamavel", "cobertura"],
            ),
            "registro": EntidadeCena(
                id="registro",
                nome="Registro de entregas",
                descricao="Anotações deixadas numa mesa.",
                propriedades=["investigavel", "fragil"],
                pista=f"Há duas assinaturas diferentes para a mesma remessa de {recurso}.",
            ),
            "estrada": EntidadeCena(
                id="estrada",
                nome="Estrada para fora",
                tipo="saida",
                destino=SAIDA_LIVRE,
                descricao="A estrada continua. Você pode partir sem aceitar qualquer compromisso.",
            ),
        },
    )
    npc_a = PessoaMundo(
        id="interlocutora",
        nome=aliada,
        local=lugar,
        descricao=f"{aliada} organiza os pedidos dos moradores.",
        objetivo=f"distribuir {recurso} sem deixar ninguém para trás",
        medo="perder a confiança do grupo",
        limite="Não aceita sacrificar os moradores para ganhar influência.",
        necessidade=necessidade,
        segredo="Guardou uma cópia de um registro para proteger uma testemunha.",
    )
    npc_b = PessoaMundo(
        id="responsavel",
        nome=rival,
        local=lugar,
        descricao=f"{rival} acompanha a movimentação junto ao depósito.",
        objetivo=interesse,
        medo="ser responsabilizado por uma decisão que não tomou sozinho",
        limite="Não entrega nomes de pessoas sob sua proteção.",
        necessidade="Corda",
        segredo="Uma parte da reserva foi prometida a um grupo que não aparece no registro.",
    )
    conflito = ConflitoMundo(
        id="distribuicao",
        nome=f"A disputa por {recurso}",
        agente=npc_b.id,
        local=lugar,
        objetivo=interesse,
        sinal=f"{rival} avisa que vai restringir o acesso ao depósito se não houver um acordo.",
        consequencia=f"{rival} restringiu o acesso ao depósito. Novos acordos ou caminhos ainda são possíveis.",
        efeito="bloquear",
        alvo=porta.id,
        intervalo=prazo,
        proximo_avanco=prazo,
    )
    fala = (f"{aliada} mantém a mão sobre o registro. ‘Se fecharem o depósito, quem fica sem {recurso}?’ "
            f"{rival} responde: ‘Também há gente contando comigo.’")
    tipo = (semente % 31) % 4
    if tipo == 1:
        evento = "uma pessoa reconhece um símbolo em sua bagagem e pede para falar longe dos curiosos"
        npc_a.objetivo = "proteger uma testemunha que pretende deixar a região"
        npc_a.descricao = f"{aliada} acompanha quem chega, como se esperasse por alguém."
        npc_b.objetivo = "partir antes que uma denúncia exponha sua família"
        npc_b.descricao = f"{rival} segura uma mala pronta para viagem."
        npc_b.segredo = "Viu uma troca de identidades, mas não conhece todos os envolvidos."
        porta.nome = "Porta da hospedaria"
        porta.destino = f"Hospedaria de {lugar}"
        cena.entidades["registro"].nome = "Bilhete sem assinatura"
        cena.entidades["registro"].pista = "A mesma descrição de viajante aparece com dois nomes diferentes."
        conflito.nome = "Uma testemunha de partida"
        conflito.objetivo = npc_b.objetivo
        conflito.sinal = f"{rival} pretende partir com a próxima caravana."
        conflito.efeito = "partir"
        conflito.consequencia = f"{rival} partiu. A conversa terá de esperar um reencontro; as pistas permanecem."
        fala = f"{aliada} aponta o bilhete. ‘Você também viu esse símbolo?’ {rival} fecha a mala: ‘Não aqui.’"
    elif tipo == 2:
        evento = "um objeto antigo começa a responder aos sons da rua, embora ninguém o esteja tocando"
        npc_a.objetivo = "entender o fenômeno antes que destruam a única evidência"
        npc_a.descricao = f"{aliada} anota cada vibração num caderno gasto."
        npc_b.objetivo = "isolar o fenômeno sem expulsar os moradores"
        npc_b.descricao = f"{rival} mantém os curiosos afastados de uma passagem."
        npc_b.segredo = "Já ouviu esse som antes e conhece alguém que voltou mudado."
        porta.nome = "Porta da câmara antiga"
        porta.destino = f"Câmara sob {lugar}"
        cena.entidades["registro"].nome = "Inscrição ressonante"
        cena.entidades["registro"].pista = "As marcas vibram na mesma ordem dos sinos, mesmo quando o vento muda."
        conflito.nome = "A decisão de interditar"
        conflito.objetivo = npc_b.objetivo
        conflito.sinal = f"{rival} prepara a interdição da câmara."
        conflito.consequencia = f"{rival} interditou a câmara; o fenômeno continua e outras abordagens são possíveis."
        fala = f"{aliada} interrompe uma anotação. ‘Ele está respondendo.’ {rival} recua: ‘A quê?’"
    elif tipo == 3:
        evento = "uma celebração é interrompida por duas pessoas reivindicando a mesma herança"
        npc_a.objetivo = "preservar o espaço comunitário deixado por um parente"
        npc_a.descricao = f"{aliada} segura um contrato coberto de anotações."
        npc_b.objetivo = "honrar uma dívida que depende da venda da propriedade"
        npc_b.descricao = f"{rival} tenta falar sem interromper quem discorda."
        npc_b.segredo = "A dívida existe, mas seu credor esconde parte do acordo."
        porta.nome = "Portão da propriedade"
        porta.destino = f"Solar de {lugar}"
        cena.entidades["registro"].nome = "Contrato de herança"
        cena.entidades["registro"].pista = "A propriedade e o direito de uso foram deixados a pessoas diferentes."
        conflito.nome = "O destino da propriedade"
        conflito.objetivo = npc_b.objetivo
        conflito.sinal = f"{rival} vai anunciar a venda se não surgir uma alternativa para a dívida."
        conflito.efeito = "disputa"
        conflito.consequencia = f"{rival} anunciou a venda. Interessados começam a chegar e a negociação mudou."
        fala = f"{aliada} estende o contrato. ‘Não é só um prédio.’ {rival} responde: ‘Também não é só dinheiro.’"
    mundo = MundoVivo(
        cenas={lugar: cena},
        pessoas={npc_a.id: npc_a, npc_b.id: npc_b},
        conflitos={conflito.id: conflito},
        objetivos=[char.objetivo],
    )
    return {
        "local_inicial": lugar,
        "local_inicial_descricao": descricao,
        "clima_inicial": clima,
        "nome_missao": "Seu próximo passo",
        "objetivo_missao": char.objetivo,
        "intro_narrativa": (
            f"O movimento em {lugar} para por um instante: {evento}. {descricao}\n\n"
            f"{fala} Nenhum dos dois parece disposto a contar tudo na frente dos curiosos.\n\n"
            f"{char.nome}, sua busca por {char.objetivo.rstrip('.')} trouxe você até este lugar. "
            "O registro está ao alcance, há espaço para uma conversa e a estrada continua aberta. "
            "Você ainda não prometeu nada a ninguém."
        ),
        "opcoes": [
            f"Examinar {cena.entidades['registro'].nome}",
            f"Ouvir {aliada} e {rival}",
            "Seguir meu próprio caminho",
        ],
        "atos": [],
        "chaves": [],
        "inicio_aventura": "emergente",
        "semente_aventura": semente,
        "hora_do_dia": rng.choice([7, 11, 16, 20]),
        "mundo_inicial": mundo.model_dump(),
        "direcao": f"Passado declarado: {char.background}. História: {char.historia_texto or ''}. "
        "Conecte uma oportunidade ao objetivo sem inventar decisões ou lembranças do jogador. "
        "Os conflitos são opcionais e os NPCs continuam agindo se o herói partir. Não existe desfecho predefinido.",
    }
