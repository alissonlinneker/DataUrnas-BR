# Certificados das autoridades certificadoras das urnas

Esta pasta guarda os certificados **públicos** das autoridades certificadoras (AC) do TSE que emitem os certificados das urnas eletrônicas. Nenhuma chave privada, nenhum dado pessoal. Eles são usados por `scripts/ele2026/analisar_certificados.py` (arquivos `-vota.vsc` de 2026) e por `scripts/ele2022/analisar_certificados.py` (arquivos `.vscmr` de 2022, amostra de 5%) para conferir se o certificado que acompanha cada arquivo de assinatura foi de fato emitido pela AC indicada nele.

## Arquivos

| Arquivo | Titular (CN) | Emissor | Serial | Validade (UTC) | Algoritmo |
|---|---|---|---|---|---|
| `ac/acurna.pem` | AC URNA | AC RAIZ UE | 3 | 22/07/2011 21:59:57 a 18/07/2026 21:59:57 | ECDSA P-521 com SHA-512 |
| `ac/acue2020.pem` | AC UE2020 | AC URNA v2 | 5 | 05/07/2021 21:31:56 a 01/07/2037 21:31:56 | Ed521 |
| `ac/acue2022.pem` | AC UE2022 | AC URNA v2 | 8 | 28/02/2023 13:46:49 a 24/02/2039 13:46:49 | Ed521 |

| Arquivo | SHA-256 do certificado (DER) | SKI | AKI (chave do emissor) |
|---|---|---|---|
| `ac/acurna.pem` | `dc20a4c3b8aef01794b80efe8e143e1fbf719707e00bb0d4ba8865191dc2731d` | `cdaaf4b29701b3f0deb2b54258594a6d34ada48a` | `8668837bbbe348cd19b61030a489d5dfde6742c0` (AC RAIZ UE) |
| `ac/acue2020.pem` | `77f31bef3d8eb35f0cc969a2b9bba3ff2a498cc339d29a375d3181e0547c0376` | `bcb3545deeea432e1e832e81283cb8ae948e400b` | `d02566c491034b3a9313b3074921eca9b500e21f` (AC URNA v2) |
| `ac/acue2022.pem` | `6ae65790dae7cc5d97394e461204744c8e2f7a810d0303af828d4d3dbecfa293` | `bb7c517f294a5b96f9bf6a964c4f255a755f698a` | `d02566c491034b3a9313b3074921eca9b500e21f` (AC URNA v2) |

Para conferir localmente:

```bash
openssl x509 -in data/certificados/ac/acurna.pem -noout -fingerprint -sha256 -dates -ext subjectKeyIdentifier,authorityKeyIdentifier
```

O OpenSSL não reconhece a curva Ed521 dos certificados AC UE2020 e AC UE2022; para esses, o próprio script imprime a ficha completa (`descrever_acs`) e a grava no bloco `acs` de `certificados_resumo.json`.

## Origem

- **Fonte primária:** pacote oficial do TSE `formato-arquivos-bu-rdv-ass-digital-v2.zip` (documentação dos formatos do BU, RDV e arquivos de assinatura, arquivos datados de 25/09/2024; SHA-256 do zip `1e423054f32b8ba056960c58ada167d702c2618cc4d1dfd5de88f5090c84a235`), arquivo `python/lib/mr_util.py`, constante `_AC_RAIZ_UE_PEMS`, comentada pelo TSE como "obtidos em dpc.acue2020.tse.jus.br". O conteúdo dos três PEM é idêntico ao dessa constante.
- **Espelhos idênticos:** <https://github.com/doccaz/urnas-br/tree/main/docv2> (`python/lib/mr_util.py`), e as cópias do mesmo arquivo em `larc-logs-transparentes/logs-transparentes` e `fernandysson/resultados-eleicoes-2026`.
- **Data da obtenção:** 14/10/2026.
- **Conferência independente:** o resumo digital (hashes SHA-512) do sistema HOLOCRON publicado pelo TSE para as Eleições Gerais 2026 (cabeçalho "HOLOCRON - 02/09/2026", pasta `D:\Aplic\SEVIN\Holocron\certificados`, cópia em <https://github.com/havaianasdestruido/resumos-eleicao-2026>, arquivo `extracted/pc1holo/pc1holo.html`) lista os arquivos `acue2020.cer` e `acue2022.cer`. O SHA-512 dos nossos `acue2020.pem` e `acue2022.pem`, byte a byte, é **igual** ao publicado nesse resumo. O certificado da AC URNA não aparece nesse resumo, então ele só tem a fonte primária acima.

## O que falta e por quê

Os certificados das raízes (**AC RAIZ UE** e **AC RAIZ UE v2**), da **AC URNA v2** e de uma eventual AC URNA renovada não estão disponíveis publicamente em forma que o projeto consiga baixar:

- `dpc.acue2020.tse.jus.br` responde 403 a acesso automatizado (testado com `curl` e com navegador automatizado em 14/10/2026);
- o Internet Archive só tem a página de índice desse endereço (captura de 23/12/2022, <http://web.archive.org/web/20221223060044id_/http://dpc.acue2020.tse.jus.br/>), com links para `acraizue.crt`, `acraizuev2.crt`, `acue2020.crt`, `acurna.crt` e `acurnav2.crt`, mas nenhum dos `.crt` foi arquivado (consulta ao índice CDX sem resultados; os endereços `id_` respondem 404);
- os endereços de DPC e LCR citados dentro dos certificados (`dpc.acraizue`, `lcr.acraizue`, `dpc.acurnav2`, `lcr.acurnav2` etc.) não têm nenhuma captura;
- nenhum repositório público consultado (pacote do TSE, `doccaz/urnas-br`, `epicleet/var-ue` e cópias) traz esses certificados.

O resumo digital do HOLOCRON publica o SHA-512 deles, o que permite conferir byte a byte quando forem obtidos:

| Arquivo no resumo do TSE | SHA-512 (base64) |
|---|---|
| `acraiz-ue.pem` | `O/LBooMqsk+Zx//zxVwXr0lboFIPwvgVj/nILBlZQaC+HZtQ1PuAFEdaWga458oPijiuUl5umAjVO+2bIcgt0g==` |
| `acraizuev2.cer` | `2a/T+2kuy0njwNLrSgqlAkala9p7FF6PL8x3327/M+xY9RHeQTytbeSSBEqib40aFS0q0Ir9HuL0LVwhRi6ozw==` |
| `acurnav2.cer` | `OTL7MHgqDbasQvSjBMWk5SkqBf5UTV7V3YjQ/kWqe8ZYZfayRLLJRJAtnS9USj4MIVg5ejiWM5ZGKiAJ1usOgw==` |

Esses valores estão também em `RESUMO_OFICIAL_SHA512` no script. Basta colocar os arquivos em `ac/`: o script os carrega, confere o hash contra o resumo oficial e passa a subir a cadeia até a raiz (`nivel_cadeia = "raiz"`) sem nenhuma outra mudança.

## Como são usados

1. Para cada seção, o certificado da urna é tirado do `-vota.vsc`; a AC candidata é a que tem o mesmo nome do emissor ou cujo SKI é igual ao AKI do certificado.
2. A assinatura do certificado da urna é verificada com a chave pública da AC (ECDSA P-521 pela biblioteca `cryptography`; Ed521 pela implementação própria em `src/dataurnas/parsers/ed521.py`). Resultado em `cadeia_ok`.
3. A partir dessa AC, o script sobe a cadeia enquanto encontrar o emissor nesta pasta e a assinatura conferir. Com os arquivos atuais a conferência para na AC intermediária (`nivel_cadeia = "intermediaria"`); com as raízes, chegaria a `"raiz"`.
4. A validade da AC no dia da eleição (04/10/2026) é registrada à parte (`ac_valida_na_eleicao`), como observação.

## Eleições de 2022

Em 2022 as urnas usaram duas AC emissoras, as duas com certificado nesta pasta: **AC URNA** (UE2009 a UE2015, ECDSA P-521, emitida pela AC RAIZ UE) e **AC UE2020** (UE2020, Ed521, emitida pela AC URNA v2). A AC URNA (validade até 18/07/2026) e a AC UE2020 (até 01/07/2037) estavam válidas nos dois turnos (02/10 e 30/10/2022). O `.vscmr` de 2022 traz só o certificado da urna, sem a cadeia; nova tentativa de baixar as raízes em 15/10/2026 (`dpc.acue2020.tse.jus.br/acraizue.crt`, `acurnav2.crt`, `dpc.acraizue`, `lcr.acraizue`) recebeu HTTP 403, então a conferência de 2022 também para na AC intermediária.

## Observação sobre a AC URNA

O certificado publicado da AC URNA venceu em 18/07/2026, antes da eleição, e há certificado de urna UE2013 emitido em 03/08/2026 cuja assinatura confere com a chave dessa AC. A explicação mais provável é um certificado renovado da AC URNA, com a mesma chave, que não foi publicado. É um ponto a esclarecer com o TSE, não indício de adulteração: a assinatura de cada urna continua conferindo com a chave da AC.
