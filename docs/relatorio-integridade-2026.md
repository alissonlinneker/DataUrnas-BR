# Relatório de integridade dos arquivos de urna: 1º turno de 2026

> **Em andamento.** Cobertura: 0,76% das seções instaladas verificadas (3.789 de 499.207). Relatório gerado em 14/10/2026 00:56 por `scripts/docs/gerar_relatorio_integridade.py`; os números mudam a cada nova execução enquanto a verificação não termina.

Registro da coleta: gerado em: 2026-10-13T23:29:30.

<p align="center">
  <img src="assets/2026-integridade.svg" alt="Cobertura da verificação de integridade por UF: 3.789 seções verificadas, 0 com divergência" width="100%">
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
- que o certificado pertence à urna física daquela seção além do que os campos dele declaram e do que a conferência com a AC emissora mostra (ver [Certificados das urnas](#certificados-das-urnas));
- que os votos registrados correspondem à intenção dos eleitores;
- nada sobre arquivos que a assinatura não cobre (imagem do BU, o próprio `.vsc` e outros).

Uma divergência indica que o arquivo publicado não corresponde ao que a urna assinou e merece investigação; não é, por si só, prova de adulteração (pode haver falha de publicação, de download ou de leitura). Ausência de divergência também não prova a lisura da eleição.

## Totais

| Métrica | Valor |
|---|---:|
| Seções instaladas (oficial) | 499.207 |
| Seções verificadas | 3.789 (0,76%) |
| Seções agregadas a outra | 249 |
| Seções não instaladas | 0 |
| Seções sem arquivos publicados | 0 |
| Arquivos catalogados | 15.156 |
| SHA-512 comparados | 11.367 |
| SHA-512 iguais ao assinado | 11.367 (100,00%) |
| SHA-512 diferentes do assinado | 0 |
| Arquivos fora da assinatura | 3.789 |
| Assinaturas válidas | 3.789 |
| Assinaturas inválidas | 0 |
| Assinaturas não verificadas | 0 |
| Seções com alguma divergência | 0 |

## Por UF

| UF | Nome | Instaladas | Verificadas | Cobertura | SHA-512 conferem | SHA-512 divergem | Assinaturas válidas | Seções divergentes |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| AC | Acre | 2.270 | 2.270 | 100,0% | 6.810 | 0 | 2.270 | 0 |
| AL | Alagoas | 7.101 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| AM | Amazonas | 8.157 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| AP | Amapá | 1.914 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| BA | Bahia | 35.476 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| CE | Ceará | 23.765 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| DF | Distrito Federal | 6.969 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| ES | Espírito Santo | 9.844 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| GO | Goiás | 15.686 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| MA | Maranhão | 18.093 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| MG | Minas Gerais | 52.062 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| MS | Mato Grosso do Sul | 7.106 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| MT | Mato Grosso | 8.287 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| PA | Pará | 20.827 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| PB | Paraíba | 10.712 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| PE | Pernambuco | 21.418 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| PI | Piauí | 10.225 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| PR | Paraná | 27.142 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| RJ | Rio de Janeiro | 37.675 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| RN | Rio Grande do Norte | 8.115 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| RO | Rondônia | 4.698 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| RR | Roraima | 1.519 | 1.519 | 100,0% | 4.557 | 0 | 1.519 | 0 |
| RS | Rio Grande do Sul | 27.547 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| SC | Santa Catarina | 17.326 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| SE | Sergipe | 5.923 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| SP | São Paulo | 103.656 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| TO | Tocantins | 4.384 | 0 | 0,0% | 0 | 0 | 0 | 0 |
| ZZ | Exterior | 1.310 | 0 | 0,0% | 0 | 0 | 0 | 0 |

## Divergências

Nenhuma divergência encontrada nas 3.789 seções verificadas, de um total de 499.207 instaladas; a verificação continua.

## Certificados das urnas

> **Em andamento.** Números do catálogo parcial e de uma amostra de arquivos `.vsc`; o modo completo (`--todas`) ainda não gerou `certificados.parquet`.

Cada `.vsc` traz o certificado de hardware da urna que o assinou. O script `scripts/ele2026/analisar_certificados.py` confere a coerência desses certificados entre si e com o BU e verifica, com a chave pública da autoridade certificadora (AC) emissora, que cada certificado foi de fato emitido por ela. Os certificados públicos das AC usados estão em [`data/certificados/`](../data/certificados/README.md).

**Catálogo** (AC, MG, RJ, RR, SP):

| Métrica | Valor |
|---|---:|
| Seções com certificado | 50.699 |
| Certificados distintos | 50.699 |
| Certificados em urnas diferentes | 0 |
| Urnas com mais de um certificado | 0 |
| Números de série repetidos na mesma AC | 0 |
| CN igual ao número interno da urna no BU | 50.699 de 50.699 |

| Modelo | AC emissora | Algoritmo | Seções |
|---|---|---|---:|
| UE2013 | AC URNA | ECDSA | 419 |
| UE2015 | AC URNA | ECDSA | 12.303 |
| UE2020 | AC UE2020 | Ed521 | 20.942 |
| UE2022 | AC UE2022 | Ed521 | 17.035 |

**Amostra de arquivos `.vsc`** (400 arquivos): validade no dia da eleição: válidos: 400; chaves públicas em urnas diferentes: 0; cadeia: conferida: 400.

| AC | Emitida por | Validade | Válida em 04/10/2026 | Confere com o resumo digital do TSE |
|---|---|---|---|---|
| AC UE2020 | AC URNA v2 | 05/07/2021 a 01/07/2037 | sim | acue2020.cer |
| AC UE2022 | AC URNA v2 | 28/02/2023 a 24/02/2039 | sim | acue2022.cer |
| AC URNA | AC RAIZ UE | 22/07/2011 a 18/07/2026 | não | não consta |

**Até onde vai a cadeia.** A conferência chega à AC intermediária (AC URNA, AC UE2020 e AC UE2022). Os certificados das raízes (AC RAIZ UE e AC RAIZ UE v2) e da AC URNA v2 não estão disponíveis publicamente para download; o SHA-512 deles, publicado pelo TSE, já está no script, que sobe até a raiz assim que os arquivos forem colocados em `data/certificados/ac/`.

**Observação sobre a AC URNA.** O certificado publicado da AC URNA tem validade até 18/07/2026, antes da eleição, e há certificado de urna emitido depois dessa data cuja assinatura confere com a chave dessa AC. A explicação mais provável é um certificado renovado da AC URNA, com a mesma chave, que não foi publicado. É um ponto a esclarecer com o TSE, não indício de adulteração.

**Assinatura de software (CEPESC).** O `.vsc` traz também uma assinatura de software feita com algoritmo de governo não publicado; ela não pode ser verificada com informação pública. A conferência acima usa a assinatura de hardware de cada urna.

## Como conferir uma seção por conta própria

Exemplo com a seção 0001 da zona 0009, município 01007 (AC). Troque os códigos para conferir qualquer outra.

1. Baixe o `aux.json` da seção e anote o diretório (`hash`) e os nomes dos arquivos (`arq`):

```bash
curl -sO https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ac/01007/0009/0001/p003220-ac-m01007-z0009-s0001-aux.json
```

2. Baixe o BU e o arquivo de assinatura (`-vota.vsc`) do diretório indicado:

```bash
curl -sO https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ac/01007/0009/0001/YiFQglN2UiWNjLTL9Rzo+SkImXJLgkNPEqguS7Oq-Pk=/o03220ac0100700090001-bu.dat
curl -sO https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/ac/01007/0009/0001/YiFQglN2UiWNjLTL9Rzo+SkImXJLgkNPEqguS7Oq-Pk=/<nome do arquivo -vota.vsc>
```

3. Calcule o SHA-512 do arquivo (sem dependências além do Python):

```bash
python3 -c "import hashlib,sys; print(hashlib.sha512(open(sys.argv[1],'rb').read()).hexdigest())" o03220ac0100700090001-bu.dat
# alternativa: shasum -a 512 o03220ac0100700090001-bu.dat
```

4. Leia o SHA-512 que a urna assinou, com o leitor do projeto, e compare:

```bash
python3 -c "from dataurnas.parsers.signature import SignatureParser as P; [print(k, v.hex()) for k, v in P().extract_file_hashes('<arquivo>-vota.vsc').items()]"
```

Para esta seção, o valor assinado do BU registrado no catálogo é:

```
ed99d17488e9ad3c20f4d28e41c2421aff89e91e5c554fbc644f67a88d2fd40bd6fa756193cfc525d6f10e324fc13c8785494fe32eec01c5da09df24df46ad8f
```

O resultado do passo 3 deve ser idêntico ao do passo 4 (e ao valor do catálogo em `data/parquet/2026/integridade/arquivos_<uf>.parquet`, coluna `sha512_assinado`). O painel, na página **Integridade dos arquivos (2026)**, mostra os mesmos valores para qualquer seção.

## Reproduzir este relatório

```bash
python scripts/docs/gerar_relatorio_integridade.py
```

Os dados de entrada ficam em `data/parquet/2026/integridade` (`arquivos_<uf>.parquet`, `secoes.parquet` e `resumo.json`); o número de seções instaladas vem de `data/parquet/2026/resultado_uf.parquet`. Veja também a [metodologia](metodologia.md#integridade-em-2026) e as [perguntas frequentes](faq.md).
