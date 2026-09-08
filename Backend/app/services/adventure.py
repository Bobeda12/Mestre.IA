"""Aberturas e intenções de campanha estáveis, inclusive sem provedor de IA.

A semente seleciona pessoas e tensões uma vez. O catálogo é premissa, não
destino: os atos descrevem perguntas que podem ser resolvidas de várias formas.
"""

import random
import secrets
from typing import Any

INICIOS: dict[str, dict[str, Any]] = {
    "caravana_partida": {
        "nome": "A ponte que cai",
        "resumo": "Uma caravana, uma ponte desabando e um pedido de socorro dos dois lados.",
        "tom": "Resgate e lealdade",
        "icone": "bridge",
        "local": "Ponte dos Sinos",
        "hora": 17,
        "clima": "Chuva oblíqua",
        "descricao": "Uma ponte de madeira liga duas falésias. Carroças presas rangem sobre um rio de água vermelha.",
        "cena": "A primeira corda arrebenta antes do grito. Uma carroça desliza para fora da Ponte dos Sinos; "
        "{aliado} segura uma criança pela gola, enquanto a mala de um mensageiro fica presa do outro lado.",
        "dilema": "Ajudar o resgate exige abandonar a mala por alguns instantes. Recuperá-la primeiro "
        "preserva a única pista sobre o destino da caravana, mas a ponte pode não esperar.",
        "fala": "{rival}, a chefe dos pedágios, mantém uma corda firme: ‘Eu seguro este lado. Escolha onde precisa de mim.’",
        "opcoes": [
            "Prender a corda e resgatar a criança",
            "Alcançar a mala pelo corrimão",
            "Coordenar todos no resgate",
        ],
        "objetivo": "Resolver o resgate na ponte e descobrir por que a caravana foi sabotada.",
        "agenda": "A chefe dos pedágios quer salvar a rota comercial, mesmo que precise esconder dívidas do conselho.",
        "atos": [
            (
                "O peso de uma escolha",
                "Resolver o desastre e assumir o efeito sobre quem foi ajudado ou deixado para trás.",
            ),
            ("Duas versões da estrada", "Ouvir viajantes e cobradores; escolher em quem confiar sobre a sabotagem."),
            ("O preço da passagem", "Negociar, expor ou romper o pacto que explora as famílias da rota."),
            (
                "Quem atravessa amanhã",
                "Decidir com os sobreviventes quem controla a ponte e conectar o acordo ao seu objetivo.",
            ),
        ],
    },
    "baile_mascaras": {
        "nome": "A última dança",
        "resumo": "Um baile clandestino; a pessoa que veio procurar aponta para uma taça envenenada.",
        "tom": "Intriga e infiltração",
        "icone": "mask",
        "local": "Palácio das Máscaras",
        "hora": 22,
        "clima": "Noite abafada",
        "descricao": "Salões dourados cercam um jardim murado. Músicos tocam atrás de cortinas e guardas vigiam as saídas.",
        "cena": "A orquestra erra uma nota. Na sacada do Palácio das Máscaras, {aliado} encosta uma taça nos "
        "seus dedos: ‘Não beba. Alguém precisa morrer antes da última dança, e estão usando o seu nome.’",
        "dilema": "Denunciar o veneno pode fechar as portas e expor seu contato. Seguir discretamente a bandeja "
        "mantém seu disfarce, mas outras taças já circulam entre os convidados.",
        "fala": "{rival}, a regente do baile, se aproxima sem escolta: ‘Você também recebeu um convite que não pediu?’",
        "opcoes": [
            "Impedir discretamente o próximo brinde",
            "Seguir quem trouxe a bandeja",
            "Confrontar a regente sobre o convite",
        ],
        "objetivo": "Impedir o envenenamento e descobrir quem usou seu nome no convite.",
        "agenda": "A regente quer impedir uma guerra de sucessão; protege um herdeiro culpado de outro crime.",
        "atos": [
            ("O brinde interrompido", "Resolver o risco do veneno preservando as pessoas ou o disfarce que escolher."),
            ("Favores sob a máscara", "Investigar três interesses conflitantes e decidir quais segredos divulgar."),
            ("Uma coroa de testemunhas", "Construir uma aliança ou desmontar a disputa sem exigir uma execução."),
            (
                "Depois da última dança",
                "Assumir as consequências públicas do acordo e buscar seu objetivo com os vínculos restantes.",
            ),
        ],
    },
    "julgamento_cinzas": {
        "nome": "O julgamento das cinzas",
        "resumo": "Uma testemunha muda o depoimento; agora você é parte do julgamento.",
        "tom": "Mistério e justiça",
        "icone": "scales",
        "local": "Tribunal de Cinza",
        "hora": 10,
        "clima": "Céu cor de chumbo",
        "descricao": "O tribunal funciona nas ruínas de uma biblioteca incendiada. Uma multidão aguarda entre bancos de pedra.",
        "cena": "‘Essa pessoa conhece a verdade.’ A voz de {aliado} atravessa o Tribunal de Cinza e centenas "
        "de olhos procuram os seus. A sentença já estava escrita; uma página chamuscada acaba de cair do processo.",
        "dilema": "A testemunha corre risco ao pedir sua ajuda. Exigir acesso à página pode adiar a sentença; "
        "criar uma distração abre uma fuga, mas pode fazer a multidão acreditar na acusação.",
        "fala": "{rival}, quem preside o tribunal, baixa o selo: ‘Traga um fato verificável e eu interrompo isto.’",
        "opcoes": [
            "Examinar a página diante do tribunal",
            "Pedir que a testemunha seja ouvida",
            "Abrir uma rota de fuga pelos arquivos",
        ],
        "objetivo": "Interromper uma sentença precipitada e investigar a página retirada do processo.",
        "agenda": "Quem preside teme uma revolta; quer uma prova pública, mas seu antigo mentor falsificou o processo.",
        "atos": [
            ("Antes do selo", "Responder ao julgamento por prova, influência ou fuga e lidar com a reação pública."),
            ("O arquivo que sobreviveu", "Confrontar depoimentos sem tratar suspeita como culpa estabelecida."),
            ("Justiça para quem", "Escolher entre reforma, reparação e exposição dos responsáveis pelo incêndio."),
            ("O nome nas cinzas", "Decidir o legado do julgamento e como ele muda a busca do seu próprio objetivo."),
        ],
    },
    "farol_afogado": {
        "nome": "O farol sob a maré",
        "resumo": "Um naufrágio transmite sinais do fundo do mar; a vila apaga suas luzes.",
        "tom": "Exploração e horror brando",
        "icone": "lighthouse",
        "local": "Farol da Maré Oca",
        "hora": 3,
        "clima": "Névoa salgada",
        "descricao": "Escadas inundadas cercam um farol rachado. Luzes de um navio submerso piscam entre as ondas.",
        "cena": "Três batidas chegam do mar, respondidas por três batidas dentro da parede. {aliado} empurra "
        "a porta do Farol da Maré Oca: uma pessoa viva acena do navio que afundou há muitos anos.",
        "dilema": "Acender o farol pode guiar um resgate, mas o guardião insiste que a luz também desperta "
        "algo sob o cais. Descer agora deixa a vila sem aviso caso ele esteja certo.",
        "fala": "{rival}, o guardião, entrega a chave com as mãos trêmulas: ‘Eu apaguei a luz naquela noite. "
        "Não vou decidir por você outra vez.’",
        "opcoes": [
            "Investigar o sinal antes de acender",
            "Preparar um resgate pela escada",
            "Ouvir a confissão do guardião",
        ],
        "objetivo": "Descobrir quem pede ajuda no naufrágio e responder ao sinal antes da maré alta.",
        "agenda": "O guardião protege a vila de um pacto marítimo, mas deseja reparar o abandono de sua antiga tripulação.",
        "atos": [
            ("Três batidas", "Responder ao pedido de socorro e descobrir a primeira regra do fenômeno."),
            ("A dívida da costa", "Ouvir sobreviventes, habitantes e o mar; descobrir quem paga pelo pacto."),
            ("O que a maré devolve", "Romper, renegociar ou revelar a dívida com um custo escolhido conscientemente."),
            (
                "Um porto para voltar",
                "Determinar quem pode regressar e o que essa reparação significa para seu objetivo.",
            ),
        ],
    },
    "floresta_memorias": {
        "nome": "A floresta que lembra",
        "resumo": "Árvores repetem uma lembrança sua; um povoado está perdendo os próprios nomes.",
        "tom": "Fantasia e identidade",
        "icone": "tree",
        "local": "Bosque dos Nomes",
        "hora": 6,
        "clima": "Orvalho luminoso",
        "descricao": "Nomes brilham nas cascas das árvores. Trilhas mudam ao som de um sino enterrado entre as raízes.",
        "cena": "Uma árvore pronuncia seu nome. {aliado} corre na sua direção, tentando lembrar o próprio; "
        "atrás, casas inteiras desaparecem sob raízes sem produzir um único ruído.",
        "dilema": "O sino parece conduzir ao centro do bosque, mas cada toque faz alguém esquecer. "
        "Silenciá-lo preserva os nomes por enquanto e pode apagar a trilha até os desaparecidos.",
        "fala": "{rival}, a jardineira do bosque, mostra uma árvore vazia: ‘Não arranque nada antes de saber "
        "quem está guardado aqui.’",
        "opcoes": [
            "Ajudar a pessoa a reconstruir seu nome",
            "Seguir o toque até o sino",
            "Perguntar à jardineira pelas árvores",
        ],
        "objetivo": "Conter o esquecimento e descobrir a ligação entre as árvores e as pessoas desaparecidas.",
        "agenda": "A jardineira abriga memórias de refugiados; teme que devolvê-las entregue suas identidades aos perseguidores.",
        "atos": [
            ("O primeiro nome", "Preservar uma identidade e compreender como o bosque armazena memórias."),
            ("Lembranças emprestadas", "Investigar quem pediu para esquecer e quem foi silenciado contra a vontade."),
            (
                "O direito de lembrar",
                "Encontrar uma solução com consentimento para pessoas que querem destinos diferentes.",
            ),
            (
                "Raízes e caminhos",
                "Escolher o futuro do bosque sem reescrever o passado do herói e retomar seu objetivo.",
            ),
        ],
    },
    "ultimo_trem": {
        "nome": "O último trem de éter",
        "resumo": "Uma máquina arcana sem freios corre para uma estação que não existe no mapa.",
        "tom": "Ação e engenhos arcanos",
        "icone": "train",
        "local": "Expresso de Éter",
        "hora": 23,
        "clima": "Tempestade elétrica",
        "descricao": "Vagões de cobre correm sobre trilhos luminosos. A locomotiva queima cristais e o horizonte se dobra.",
        "cena": "O bilhete perfura sozinho uma segunda data: amanhã. {aliado} cai no corredor do Expresso "
        "de Éter quando as luzes apagam; pela janela, a última ponte da linha cresce rápido demais.",
        "dilema": "Desacoplar o vagão traseiro reduz o peso e deixa passageiros isolados. "
        "Entrar na locomotiva pode salvar todos, mas o mecanismo está lacrado por dentro.",
        "fala": "{rival}, a maquinista, fala pelo tubo de cobre: ‘A carga me impede de frear. "
        "Posso explicar, se você conseguir chegar aqui.’",
        "opcoes": [
            "Alcançar a locomotiva pelo teto",
            "Organizar os passageiros no corredor",
            "Examinar o lacre e falar com a maquinista",
        ],
        "objetivo": "Evitar o desastre do expresso e descobrir o que sua carga mantém em movimento.",
        "agenda": "A maquinista transporta um refúgio em miniatura; frear sem estabilizar o cristal colocaria seus moradores em risco.",
        "atos": [
            ("Antes da curva", "Estabilizar a viagem escolhendo quem ajudar e que risco assumir."),
            ("Passageiros invisíveis", "Descobrir os interesses na carga sem transformar todos a bordo em inimigos."),
            (
                "A estação que falta",
                "Definir um destino que responda à disputa entre passageiros, carga e donos da linha.",
            ),
            ("O próximo bilhete", "Assumir o custo da chegada e decidir como a nova rota serve ao seu objetivo."),
        ],
    },
    "cerco_aurora": {
        "nome": "Até a aurora",
        "resumo": "Um portão sitiado, refugiados do lado de fora e um inimigo disposto a conversar.",
        "tom": "Tática e liderança",
        "icone": "castle",
        "local": "Portão da Aurora",
        "hora": 4,
        "clima": "Vento frio",
        "descricao": "Barricadas cercam uma cidade cansada. Fogueiras de sitiantes recortam a planície e refugiados batem no portão.",
        "cena": "‘São pessoas, não escudos!’ {aliado} segura a manivela do Portão da Aurora. "
        "Do lado de fora, uma família ergue um pano branco; atrás dela, uma patrulha se aproxima.",
        "dilema": "Abrir o portão dá passagem aos refugiados e expõe a muralha. Manter a defesa "
        "ganha tempo, mas será preciso encontrar outra maneira de tirar aquelas pessoas da linha de tiro.",
        "fala": "{rival}, a emissária dos sitiantes, deixa a arma no chão: ‘Eu trouxe os refugiados. "
        "Você consegue manter seus arqueiros quietos por um minuto?’",
        "opcoes": [
            "Coordenar uma abertura protegida",
            "Negociar uma trégua com a emissária",
            "Procurar passagem pelo aqueduto",
        ],
        "objetivo": "Resolver a travessia dos refugiados e descobrir o que mantém o cerco.",
        "agenda": "A emissária quer recuperar suprimentos confiscados; o conselho sitiado teme perder legitimidade se admitir o confisco.",
        "atos": [
            ("Um minuto de trégua", "Resolver o impasse do portão e estabelecer quem aceita conversar."),
            ("A fome dos dois lados", "Descobrir os custos do cerco para a cidade e os sitiantes."),
            ("A mesa ou a muralha", "Escolher defesa, evacuação, acordo ou sabotagem com consequências para os civis."),
            (
                "Quando amanhecer",
                "Construir o pós-cerco com os sobreviventes e ligar sua responsabilidade ao objetivo pessoal.",
            ),
        ],
    },
    "heranca_maldita": {
        "nome": "A casa que o escolheu",
        "resumo": "Uma casa impossível reconhece você como herdeiro; seus moradores discordam.",
        "tom": "Enigmas e vínculos",
        "icone": "key",
        "local": "Solar das Portas Vivas",
        "hora": 19,
        "clima": "Garoa morna",
        "descricao": "Um solar estreito tem mais portas por dentro do que janelas por fora. Retratos acompanham visitantes com os olhos.",
        "cena": "A porta se fecha e todas as velas dizem: ‘Finalmente.’ {aliado}, que trouxe o convite, "
        "puxa a maçaneta em vão. No Solar das Portas Vivas, o inventário da herança acaba de incluir seu nome.",
        "dilema": "Assinar como herdeiro pode abrir a saída, mas o contrato também lista os moradores "
        "como propriedade. Rasgar o documento ameaça desfazer o lugar que os mantém vivos.",
        "fala": "{rival}, a zeladora, põe uma pena sobre a mesa: ‘A casa pode escolher um dono. "
        "Nós ainda podemos recusar.’",
        "opcoes": [
            "Ler o contrato à procura de uma brecha",
            "Ouvir os moradores antes de assinar",
            "Investigar as portas e a origem da casa",
        ],
        "objetivo": "Descobrir por que a casa escolheu você e encontrar uma saída que respeite seus moradores.",
        "agenda": "A zeladora quer libertar os moradores sem perder o abrigo; esconde que assinou o contrato original sob coerção.",
        "atos": [
            ("A cláusula viva", "Entender o contrato e escolher como responder à suposta herança."),
            ("Quartos de outras vidas", "Investigar histórias dos moradores e distinguir proteção de posse."),
            ("Uma casa sem dono", "Renegociar, desfazer ou transferir o pacto incluindo a vontade dos moradores."),
            ("A porta de saída", "Determinar o destino do solar e o que levar dessa experiência para seu objetivo."),
        ],
    },
}

TEMPERAMENTOS = ["Justo", "Épico", "Implacável"]
DIFICULDADES = ["História", "Normal", "Difícil"]


def catalogo_aventura() -> dict:
    return {
        "inicios": [
            {
                "id": "surpresa",
                "nome": "Surpreenda-me",
                "resumo": "Uma abertura escolhida para esta campanha.",
                "tom": "Destino aberto",
                "icone": "dice",
            }
        ]
        + [
            {"id": chave, **{campo: inicio[campo] for campo in ("nome", "resumo", "tom", "icone")}}
            for chave, inicio in INICIOS.items()
        ],
        "temperamentos": TEMPERAMENTOS.copy(),
        "dificuldades": DIFICULDADES.copy(),
    }


def preparar_abertura(char: Any, semente: int | None = None) -> dict:
    """Mesma entrada + semente => mesmo roteiro; sem semente cria campanha nova."""
    semente = secrets.randbelow(2**31 - 1) + 1 if semente is None else semente
    rng = random.Random(semente)
    surpresa = rng.choice(list(INICIOS))
    escolhido = getattr(char, "inicio_aventura", "surpresa")
    if escolhido not in INICIOS:
        escolhido = surpresa
    inicio = INICIOS[escolhido]
    aliado, rival = rng.sample(["Íria", "Nilo", "Sena", "Miro", "Tália", "Cael", "Olma", "Ravi", "Lume", "Dara"], 2)
    nomes = {"aliado": aliado, "rival": rival}
    vinculo = rng.choice(
        [
            f"{aliado} foi quem lhe ofereceu abrigo ontem, sem pedir sua história em troca.",
            f"{aliado} ajudou você a chegar até aqui e pediu apenas que ouvisse seu lado da história.",
            f"{aliado} reconheceu seu nome no registro de viajantes e se ofereceu para apresentar o lugar.",
        ]
    )
    pressao = rng.choice(
        [
            "Há uma testemunha disposta a falar, desde que sua família não seja exposta.",
            "Um acordo antigo beneficia pessoas vulneráveis e também protege quem causou o problema.",
            "Uma facção oferece ajuda real, mas exigirá crédito público pelo resultado.",
            "A prova decisiva pode absolver uma pessoa e comprometer alguém que prestou ajuda ao herói.",
        ]
    )
    passado = (getattr(char, "background", "") or "viajante").strip()
    objetivo = (getattr(char, "objetivo", "") or "encontrar seu próprio caminho").strip().rstrip(".")
    # Rodada de conserto - antes isto embutia um trecho cru de `historia_texto`
    # entre aspas ("Voce traz consigo esta lembranca: '...'"), e o LLM do
    # prologo (narrator.gerar_prologo_missao) recebe este dict inteiro como
    # "abertura canonica" a preservar - o resultado era o modelo copiando a
    # citacao ao pe da letra em vez de narrar a cena com as proprias palavras.
    # `historia_texto` completo ja chega ao LLM separadamente, sem aspas, via
    # `historia_extra` em narrator.py - nao precisa duplicar aqui.
    identidade = (
        f"Você é {char.nome}, {char.raca} {char.classe}. Seu passado como {passado} trouxe você até aqui, "
        f"em busca de {objetivo}. {vinculo}"
    )
    chaves = [
        f"Início da campanha: {inicio['nome']} em {inicio['local']}.",
        vinculo,
        f"Objetivo pessoal declarado: {objetivo}.",
        f"Impasse inicial: {inicio['dilema']}",
        f"Pessoa presente: {inicio['fala'].format(**nomes)}",
    ]
    return {
        "inicio_aventura": escolhido,
        "semente_aventura": semente,
        "local_inicial": inicio["local"],
        "local_inicial_descricao": inicio["descricao"],
        "clima_inicial": inicio["clima"],
        "hora_do_dia": inicio["hora"],
        "nome_missao": inicio["nome"],
        "objetivo_missao": inicio["objetivo"],
        "intro_narrativa": "\n\n".join(
            [
                inicio["cena"].format(**nomes),
                identidade,
                f"{inicio['dilema']} {inicio['fala'].format(**nomes)} O que você faz?",
            ]
        ),
        "atos": [{"titulo": titulo, "objetivo": objetivo_ato} for titulo, objetivo_ato in inicio["atos"]],
        "opcoes": inicio["opcoes"].copy(),
        "chaves": chaves,
        "direcao": f"{rival}: {inicio['agenda']} Pressão secundária: {pressao}",
    }


def contexto_campanha(heroi: Any, mundo: Any) -> str:
    """Reconstitui intenções iniciais; fatos posteriores sempre têm precedência."""
    semente = getattr(mundo, "semente_aventura", 0)
    inicio = getattr(mundo, "inicio_aventura", "surpresa")
    if not semente or inicio not in INICIOS:
        return ""
    # Personagem guarda a escolha no WorldState, não numa nova coluna SQL.
    from types import SimpleNamespace

    char = SimpleNamespace(
        inicio_aventura=inicio,
        nome=heroi.nome,
        raca=heroi.raca,
        classe=heroi.classe,
        background=heroi.background,
        objetivo=heroi.objetivo,
        historia_texto=heroi.historia_texto,
    )
    abertura = preparar_abertura(char, semente)
    marcos = "\n".join(f"- {marco}" for marco in getattr(mundo, "marcos", [])[-16:])
    return (
        f"[ORIGEM DA CAMPANHA] {INICIOS[inicio]['nome']}\n"
        f"[INTENÇÕES INICIAIS DOS NPCS — NÃO REVELAR COMO SPOILER] {abertura['direcao']}\n"
        "Intenções podem mudar por fatos, promessas e escolhas registradas. Nunca ressuscite um NPC "
        "nem force uma traição para cumprir a premissa. Não trate hipóteses como fatos já descobertos.\n"
        f"[MARCOS DA JORNADA]\n{marcos}"
    )
