# Relatório de integridade dos arquivos de urna: 1º turno de 2026

> **Em andamento.** Cobertura: 0,00% das seções instaladas verificadas (0 de 499.207). Relatório gerado em 13/10/2026 22:38 por `scripts/docs/gerar_relatorio_integridade.py`; os números mudam a cada nova execução enquanto a verificação não termina.

<p align="center">
  <img src="assets/2026-integridade.svg" alt="Cobertura da verificação de integridade por UF: 0 seções verificadas, 0 com divergência" width="100%">
</p>

## Como funciona o mecanismo

Ao encerrar a votação, cada urna grava o Boletim de Urna (`bu.dat`), o Registro Digital do Voto (`rdv.dat`) e o log (`log.jez`). Ela calcula o resumo **SHA-512** de cada um desses arquivos e grava os resumos num arquivo de assinatura (`.vsc`), assinado com a chave privada da própria urna. O TSE publica todos esses arquivos por seção, junto com um `aux.json` que lista os nomes e o diretório de publicação.

A verificação feita pelo projeto, para cada seção:

1. baixa os arquivos publicados e calcula MD5, SHA-256 e SHA-512 de cada um;
2. lê do `.vsc` o SHA-512 assinado de cada arquivo coberto e compara com o calculado (`hash_confere`);
3. verifica a assinatura do `.vsc` com a chave pública do certificado que o acompanha e registra algoritmo, titular, emissor, número de série e SHA-256 do certificado;
4. registra o token do `aux.json` (32 bytes em base64url) e a data e hora informadas pelo TSE.

MD5 e SHA-256 não fazem parte do mecanismo da urna: ficam no catálogo para facilitar conferências com outras fontes. O token do `aux.json` identifica o conjunto publicado e não é o hash de nenhum arquivo isolado; por isso é registrado e não comparado.

## O que fica comprovado e o que não fica

**Comprovado, para cada seção verificada sem divergência:** os arquivos `bu.dat`, `rdv.dat` e `log.jez` publicados pelo TSE têm exatamente o conteúdo cujo SHA-512 está no arquivo de assinatura, e esse arquivo de assinatura foi assinado pela chave correspondente ao certificado que o acompanha.

**Não comprovado por esta verificação:**

- que o software da urna é o oficial, nem que funcionou corretamente;
- que o certificado pertence à urna física daquela seção além do que os campos dele declaram, salvo onde a cadeia de certificação for validada;
- que os votos registrados correspondem à intenção dos eleitores;
- nada sobre arquivos que a assinatura não cobre (imagem do BU, o próprio `.vsc` e outros).

Uma divergência indica que o arquivo publicado não corresponde ao que a urna assinou e merece investigação; não é, por si só, prova de adulteração (pode haver falha de publicação, de download ou de leitura). Ausência de divergência também não prova a lisura da eleição.

## Totais

A verificação ainda não gravou dados: os totais abaixo estão zerados.

| Métrica | Valor |
|---|---:|
| Seções instaladas (oficial) | 499.207 |
| Seções verificadas | 0 (0,00%) |
| Seções agregadas a outra | 0 |
| Seções não instaladas | 0 |
| Seções sem arquivos publicados | 0 |
| Arquivos catalogados | 0 |
| SHA-512 comparados | 0 |
| SHA-512 iguais ao assinado | 0 (0,00%) |
| SHA-512 diferentes do assinado | 0 |
| Arquivos fora da assinatura | 0 |
| Assinaturas válidas | 0 |
| Assinaturas inválidas | 0 |
| Assinaturas não verificadas | 0 |
| Seções com alguma divergência | 0 |

## Por UF

Nenhuma UF verificada ainda.

## Divergências

Nenhuma seção verificada ainda.

## Como conferir uma seção por conta própria

Exemplo com a seção 0001 da zona 0009, município 01007 (AC). Troque os códigos para conferir qualquer outra.

1. Baixe o `aux.json` da seção e anote o diretório (`hash`) e os nomes dos arquivos (`arq`):

```bash
curl -sO https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ac/01007/0009/0001/p003220-ac-m01007-z0009-s0001-aux.json
```

2. Baixe o BU e o arquivo de assinatura (`-vota.vsc`) do diretório indicado:

```bash
curl -sO https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ac/01007/0009/0001/<token>/<nome do arquivo -bu.dat>
curl -sO https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ac/01007/0009/0001/<token>/<nome do arquivo -vota.vsc>
```

3. Calcule o SHA-512 do arquivo (sem dependências além do Python):

```bash
python3 -c "import hashlib,sys; print(hashlib.sha512(open(sys.argv[1],'rb').read()).hexdigest())" <nome do arquivo -bu.dat>
# alternativa: shasum -a 512 <nome do arquivo -bu.dat>
```

4. Leia o SHA-512 que a urna assinou, com o leitor do projeto, e compare:

```bash
python3 -c "from dataurnas.parsers.signature import SignatureParser as P; [print(k, v.hex()) for k, v in P().extract_file_hashes('<arquivo>-vota.vsc').items()]"
```

O resultado do passo 3 deve ser idêntico ao do passo 4 (e ao valor do catálogo em `data/parquet/2026/integridade/arquivos_<uf>.parquet`, coluna `sha512_assinado`). O painel, na página **Integridade dos arquivos (2026)**, mostra os mesmos valores para qualquer seção.

## Reproduzir este relatório

```bash
python scripts/docs/gerar_relatorio_integridade.py
```

Os dados de entrada ficam em `data/parquet/2026/integridade` (`arquivos_<uf>.parquet`, `secoes.parquet` e `resumo.json`); o número de seções instaladas vem de `data/parquet/2026/resultado_uf.parquet`. Veja também a [metodologia](metodologia.md#integridade-em-2026) e as [perguntas frequentes](faq.md).
