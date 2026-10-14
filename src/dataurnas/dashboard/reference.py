"""Fonte única de dados de referência usados pelo dashboard.

Resultados oficiais de 2022 (Presidente) divulgados pelo TSE e o catálogo de
códigos de inconsistência. Antes havia duas cópias divergentes (app.py e
analysis.py); ambos os módulos agora leem daqui.

Fonte dos resultados: TSE, resultados.tse.jus.br, totalização oficial de
02/10/2022 (1º turno) e 30/10/2022 (2º turno).
"""

from __future__ import annotations

try:  # limiar real usado pelo analisador; o fallback mantém o valor documentado
    from dataurnas.analyzer.statistical import LIMIAR_ABSTENCAO_PCT
except ImportError:  # pragma: no cover
    LIMIAR_ABSTENCAO_PCT = 40.0

FONTE_TSE_2022 = "TSE, totalização oficial (resultados.tse.jus.br), Eleições Gerais 2022"

TSE_2022: dict[int, dict] = {
    1: {
        "turno": 1,
        "label": "1º Turno",
        "data": "02/10/2022",
        "eleitores_aptos": 156_454_011,
        "comparecimento": 123_682_372,
        "abstencao": 32_770_982,
        "votos_validos": 118_229_719,
        "brancos": 1_964_779,
        "nulos": 3_487_874,
        "pct_abstencao": 20.95,
        "candidatos": {
            13: {"nome": "Luiz Inácio Lula da Silva", "curto": "Lula", "partido": "PT",
                 "votos": 57_259_504, "pct": 48.43},
            22: {"nome": "Jair Messias Bolsonaro", "curto": "Bolsonaro", "partido": "PL",
                 "votos": 51_072_345, "pct": 43.20},
            15: {"nome": "Simone Tebet", "curto": "Tebet", "partido": "MDB",
                 "votos": 4_915_423, "pct": 4.16},
            12: {"nome": "Ciro Gomes", "curto": "Ciro", "partido": "PDT",
                 "votos": 3_599_287, "pct": 3.04},
        },
        "diferenca_1_2": 6_187_159,
        "vencedor": 13,
    },
    2: {
        "turno": 2,
        "label": "2º Turno",
        "data": "30/10/2022",
        "eleitores_aptos": 156_454_011,
        "comparecimento": 124_252_796,
        "abstencao": 32_201_215,
        "votos_validos": 118_556_778,
        "brancos": 1_958_988,
        "nulos": 3_736_630,
        "pct_abstencao": 20.59,
        "candidatos": {
            13: {"nome": "Luiz Inácio Lula da Silva", "curto": "Lula", "partido": "PT",
                 "votos": 60_345_999, "pct": 50.90},
            22: {"nome": "Jair Messias Bolsonaro", "curto": "Bolsonaro", "partido": "PL",
                 "votos": 58_206_354, "pct": 49.10},
        },
        "diferenca_1_2": 2_139_645,
        "vencedor": 13,
    },
}


def oficial_resumo(turno: int) -> dict:
    """Formato compacto (chaves lula_pct/bolso_pct) usado pelo módulo de análise."""
    ref = TSE_2022[turno]
    return {
        "turno": turno,
        "eleitores_aptos": ref["eleitores_aptos"],
        "comparecimento": ref["comparecimento"],
        "votos_validos": ref["votos_validos"],
        "lula_pct": ref["candidatos"][13]["pct"],
        "bolso_pct": ref["candidatos"][22]["pct"],
        "diferenca": ref["diferenca_1_2"],
    }


def _limiar(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")




# ----------------------------------------------------------------------
# Grupos de leitura: o que cada código pode dizer sobre manipulação
# ----------------------------------------------------------------------
# A severidade diz a prioridade de investigar; o grupo diz que tipo de
# conclusão o achado admite. Um código só entra no grupo 1 se não houver
# explicação operacional conhecida para ele num sistema íntegro.
GRUPO_ADULTERACAO = "adulteracao"
GRUPO_INVESTIGAR = "investigar"
GRUPO_OPERACIONAL = "operacional"

GRUPOS: dict[str, dict] = {
    GRUPO_ADULTERACAO: {
        "ordem": 1,
        "nome": "Indício direto de adulteração",
        "resumo": "Não deveria ocorrer num sistema íntegro: uma única ocorrência exige explicação.",
        "tom": "red",
    },
    GRUPO_INVESTIGAR: {
        "ordem": 2,
        "nome": "Inconsistência a investigar",
        "resumo": "Tem explicações legítimas conhecidas e só ganha sentido com o contexto da seção.",
        "tom": "amber",
    },
    GRUPO_OPERACIONAL: {
        "ordem": 3,
        "nome": "Operacional ou estatístico",
        "resumo": "Descreve como o dia de votação transcorreu; sozinho, não é evidência de manipulação.",
        "tom": "grey",
    },
}
GRUPOS_ORDEM: tuple[str, ...] = tuple(sorted(GRUPOS, key=lambda g: GRUPOS[g]["ordem"]))
GRUPO_SEM_CLASSIFICACAO = "Não classificado"

# Catálogo único de códigos de inconsistência: (descrição curta, grupo, motivo do grupo)
ISSUE_CATALOGO: dict[str, tuple[str, str, str]] = {
    "C01": ("Hash SHA-512 inválido", GRUPO_ADULTERACAO,
            "O arquivo publicado não é o que a urna resumiu e assinou: mudou depois da assinatura."),
    "C05": ("Total de votos > eleitores aptos", GRUPO_ADULTERACAO,
            "A urna só libera eleitores do caderno da seção; votos acima dos aptos não têm causa operacional."),
    "A02": ("Votos > comparecimento", GRUPO_ADULTERACAO,
            "Cada eleitor liberado vota uma vez por vaga; mais votos que comparecimento é impossível num BU íntegro."),
    "A06": ("Comparecimento divergente entre cargos", GRUPO_ADULTERACAO,
            "Na mesma eleição o eleitor vota em todos os cargos na mesma sessão; o comparecimento é o mesmo."),
    "A01": ("Divergência de eleitores aptos entre eleições", GRUPO_INVESTIGAR,
            "Já desconta o voto em trânsito, que explicava os casos de 2022; o restante pede conferir o caderno."),
    "A03": ("Divergência de votos no log vs BU", GRUPO_INVESTIGAR,
            "A troca de urna divide o log entre equipamentos; a contagem do log sozinha fica incompleta."),
    "E02": ("BU não decodificado (ex.: tipo de voto desconhecido); seção excluída dos totais", GRUPO_INVESTIGAR,
            "Pode ser arquivo corrompido, versão de formato nova ou limitação do decodificador."),
    "E03": ("Duração negativa de votação no log", GRUPO_INVESTIGAR,
            "Linha do tempo incoerente costuma vir de ajuste de relógio ou de log de outra urna na seção."),
    "M03": ("Abertura não encontrada no log", GRUPO_INVESTIGAR,
            "Log incompleto ou de urna substituída; sem a abertura não é possível conferir o horário."),
    "C06": ("Reinício durante votação", GRUPO_OPERACIONAL,
            "Falha de energia, travamento ou contingência; o BU continua conferível com o comparecimento."),
    "A04": ("Abertura muito tardia", GRUPO_OPERACIONAL,
            "Atraso na instalação da seção; afeta o acesso ao voto, não a contagem."),
    "A05": ("Encerramento antes do horário", GRUPO_OPERACIONAL,
            "Em geral reflete relógio ou fuso; afeta o acesso ao voto, não a contagem registrada."),
    "M01": ("Abertura antes do horário ajustado", GRUPO_OPERACIONAL,
            "Registro de horário fora da janela, em geral por relógio ou fuso; não altera votos."),
    "M02": ("Encerramento muito tarde", GRUPO_OPERACIONAL,
            "Fila no fim do dia ou relógio desajustado."),
    "M04": ("Número elevado de erros no log", GRUPO_OPERACIONAL,
            "Erros de periféricos (leitor biométrico, impressora) são registrados no log."),
    "M05": ("Ajustes de hora detectados", GRUPO_OPERACIONAL,
            "O ajuste de relógio é um procedimento previsto e fica registrado no log."),
    "M06": ("Alta taxa de liberação sem biometria", GRUPO_OPERACIONAL,
            "Falha de leitura de digital libera o eleitor por código, como previsto."),
    "I01": ("Eventos de substituição/contingência", GRUPO_OPERACIONAL,
            "Troca de urna é procedimento de contingência documentado."),
    "I02": ("Alertas de mesário elevados", GRUPO_OPERACIONAL,
            "Alertas operacionais do terminal do mesário."),
    "I03": ("Proporção elevada de nulos", GRUPO_OPERACIONAL,
            "Voto nulo é direito do eleitor; proporção alta é dado estatístico."),
    "I04": ("Proporção elevada de brancos", GRUPO_OPERACIONAL,
            "Voto em branco é direito do eleitor; proporção alta é dado estatístico."),
    "I05": (f"Abstenção acima de {_limiar(LIMIAR_ABSTENCAO_PCT)}%", GRUPO_OPERACIONAL,
            "Abstenção depende do eleitorado (exterior, presídios, cadastros antigos)."),
    "I06": ("Urna não padrão (reservaSeção)", GRUPO_OPERACIONAL,
            "Urna de reserva entra quando a original é substituída."),
    "E01": ("Assinatura não verificável (falha de leitura ou arquivo ausente; não é hash inválido)",
            GRUPO_OPERACIONAL,
            "Indica que a verificação não foi possível, não que falhou; não é evidência de adulteração."),
}

ISSUE_DESCRICOES: dict[str, str] = {c: v[0] for c, v in ISSUE_CATALOGO.items()}
ISSUE_GRUPOS: dict[str, str] = {c: v[1] for c, v in ISSUE_CATALOGO.items()}
ISSUE_MOTIVOS: dict[str, str] = {c: v[2] for c, v in ISSUE_CATALOGO.items()}

# Categorias da auditoria de integridade de 2026 (arquivos publicados x .vsc)
INTEGRIDADE_CATEGORIAS: dict[str, tuple[str, str, str]] = {
    "hash_diverge": ("SHA-512 do arquivo publicado difere do assinado no .vsc", GRUPO_ADULTERACAO,
                     "Equivale ao C01: o arquivo mudou depois de assinado pela urna."),
    "assinatura_invalida": ("Assinatura da urna inválida no .vsc", GRUPO_ADULTERACAO,
                            "A lista de hashes não foi assinada pela chave do certificado que a acompanha."),
    "hash_assinado_ausente": ("Arquivo publicado sem hash assinado no .vsc", GRUPO_ADULTERACAO,
                              "Um BU, RDV ou log publicado deveria estar coberto pela assinatura da urna."),
    "arquivo_ausente_tse": ("Arquivo listado no .vsc, mas não publicado pelo TSE", GRUPO_ADULTERACAO,
                            "A urna assinou um arquivo que não aparece na publicação oficial."),
    "votos_divergem": ("Votos do BU assinado diferem do BU da coleta de resultados", GRUPO_INVESTIGAR,
                       "Compara duas leituras do BU; a diferença pode vir de versão republicada ou de contingência."),
}

# Recontagem do RDV x BU e linha do tempo do log (2026), mesmos nomes de
# analyzer/rdv_recontagem.CATEGORIAS
RDV_CATEGORIAS: dict[str, tuple[str, str, str]] = {
    "rdv_bu_diverge": ("Recontagem do RDV difere do BU num cargo", GRUPO_ADULTERACAO,
                       "O BU é a soma dos votos do RDV da mesma urna; não há causa operacional "
                       "para a soma diferir."),
    "rdv_registros_diverge": ("Registros do RDV diferem do comparecimento x escolhas",
                              GRUPO_ADULTERACAO,
                              "Cada eleitor gera um registro por escolha em cada cargo."),
    "rdv_estrutura": ("RDV com registro inválido, cargo repetido ou seção trocada",
                      GRUPO_ADULTERACAO,
                      "O formato do RDV é fixo; registro fora do spec não sai de urna íntegra."),
    "rdv_hash_diverge": ("SHA-512 baixado difere do catálogo assinado", GRUPO_ADULTERACAO,
                         "Equivale ao C01: o arquivo mudou depois de assinado pela urna."),
    "rdv_nao_decodificado": ("RDV publicado que o decodificador não lê", GRUPO_INVESTIGAR,
                             "Pode ser arquivo corrompido ou limitação do decodificador."),
    "rdv_bu_diverge_sa": ("RDV difere do BU do Sistema de Apuração", GRUPO_INVESTIGAR,
                          "O BU do SA soma cédulas de papel que não estão no RDV da urna."),
    "log_votos_diverge": ("Votos computados no log diferem do comparecimento do BU",
                          GRUPO_INVESTIGAR,
                          "A troca de urna divide o log entre equipamentos; equivale ao A03."),
    "log_voto_fora_sequencia": ("Voto antes da abertura ou depois do encerramento no log",
                                GRUPO_INVESTIGAR,
                                "Pode vir de log de outra urna na seção ou de reinício; "
                                "pede conferir a sequência de eventos."),
    "log_voto_outra_data": ("Voto computado com data diferente do dia da eleição",
                            GRUPO_INVESTIGAR,
                            "Em geral relógio da urna desajustado; pede conferir o log."),
    "log_voto_antes_8h": ("Voto antes das 8h de Brasília", GRUPO_OPERACIONAL,
                          "Hora local da urna, relógio ou fuso; não altera a contagem."),
    "log_intervalo_curto": ("Votos consecutivos a menos de 10 s", GRUPO_OPERACIONAL,
                            "Eleitor rápido ou voto em poucos cargos; informativo."),
    "log_lacuna_60min": ("Mais de 60 min sem voto durante a votação", GRUPO_OPERACIONAL,
                         "Seção pequena ou movimento baixo; informativo."),
    "log_relogio_inverso": ("Hora de voto menor que a do voto anterior", GRUPO_OPERACIONAL,
                            "Ajuste de relógio durante a votação."),
}

# Análises agregadas: não geram ocorrência por seção, mas também precisam de leitura
ANALISES_ESTATISTICAS: dict[str, tuple[str, str, str]] = {
    "benford": ("Lei de Benford", GRUPO_OPERACIONAL,
                "Votos por seção não seguem Benford por natureza (seções têm tamanho limitado); "
                "o teste tem alta taxa de falso positivo em dados eleitorais."),
    "outliers": ("Outliers estatísticos", GRUPO_OPERACIONAL,
                 "Seções atípicas existem em qualquer eleição (presídios, aldeias, exterior); "
                 "desvio estatístico não aponta causa."),
}


def issue_label(codigo: str) -> str:
    """Rótulo 'C01: Hash SHA-512 inválido' para listas e legendas."""
    desc = ISSUE_DESCRICOES.get(codigo)
    return f"{codigo}: {desc}" if desc else codigo


def grupo_nome(grupo: str | None) -> str:
    """Nome do grupo com o número na frente ('1. Indício direto de adulteração').

    O número e o texto identificam o grupo sem depender da cor.
    """
    info = GRUPOS.get(grupo or "")
    return f"{info['ordem']}. {info['nome']}" if info else GRUPO_SEM_CLASSIFICACAO


def grupo_do_codigo(codigo: str) -> str | None:
    return ISSUE_GRUPOS.get(str(codigo))


def grupo_label(codigo: str) -> str:
    """Nome numerado do grupo de um código de inconsistência."""
    return grupo_nome(grupo_do_codigo(codigo))


def codigos_do_grupo(grupos) -> tuple[str, ...]:
    """Códigos (ordenados) que pertencem a qualquer um dos grupos."""
    alvo = set(grupos)
    return tuple(sorted(c for c, g in ISSUE_GRUPOS.items() if g in alvo))


def contar_por_grupo(contagens) -> dict[str, int]:
    """Soma contagens por código (ou categoria de integridade) em cada grupo.

    Aceita um mapeamento {código: total}. Chaves fora do catálogo são ignoradas.
    Devolve os três grupos, mesmo os sem ocorrência.
    """
    grupos_por_chave = {**ISSUE_GRUPOS, **{k: v[1] for k, v in INTEGRIDADE_CATEGORIAS.items()},
                        **{k: v[1] for k, v in RDV_CATEGORIAS.items()}}
    out = {g: 0 for g in GRUPOS_ORDEM}
    for chave, total in dict(contagens).items():
        grupo = grupos_por_chave.get(str(chave))
        if grupo is not None:
            out[grupo] += int(total or 0)
    return out
