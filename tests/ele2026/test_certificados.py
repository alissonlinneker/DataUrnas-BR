"""Testes da análise de certificados de urna (scripts/ele2026/analisar_certificados.py).

Sem rede: catálogos sintéticos e os .vsc reais de tests/ele2026/fixtures.
"""

import datetime as dt
import importlib.util
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("cryptography")

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
VSC_AC = FIX / "vsc_ac_m01066_z0004_s0077.bin"  # UE2022, Ed521, AC UE2022
VSC_AM = FIX / "vsc_am_m02550_z0001_s0645.bin"  # UE2015, ECDSA P-521, AC URNA

EM_URNA = "L=Brasilia,OU=STI,O=TSE,C=BR,ST=DF,CN=AC URNA"
EM_2022 = "L=Brasilia,OU=STI,O=TSE,C=BR,ST=DF,CN=AC UE2022"


@pytest.fixture(scope="module")
def A():
    p = ROOT / "scripts" / "ele2026" / "analisar_certificados.py"
    spec = importlib.util.spec_from_file_location("analisar_certificados", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def linha(secao, num, modelo="UE2022", emissor=EM_2022, alg="Ed521", sha=None,
          serial=None, cn=None, motivo=None):
    return {
        "uf": "ac", "cd_mun": "01007", "zona": "0009", "secao": secao,
        "status_secao": "ok", "assinatura_valida": True, "assinatura_algoritmo": alg,
        "cert_subject": f"O=TSE,C=BR,CN={cn or f'UEAO{num:08d}'}",
        "cert_issuer": emissor, "cert_serial": serial or f"{num:x}",
        "cert_sha256": sha or f"{num:064x}", "modelo_urna": modelo, "motivo": motivo,
        "_lote": "l1",
    }


def bu_de(cat, **troca):
    rows = []
    for r in cat.to_dict("records"):
        sub = r["cert_subject"].upper()
        num = int(sub.split("UEAO")[-1]) if "UEAO" in sub else None
        rows.append({"uf": r["uf"], "cd_mun": r["cd_mun"], "zona": r["zona"],
                     "secao": r["secao"], "numero_interno_urna": float(num) if num else None,
                     "modelo_bu": r["modelo_urna"], "tipo_urna_bu": "secao"})
    bu = pd.DataFrame(rows)
    for secao, num in troca.items():
        bu.loc[bu["secao"] == secao, "numero_interno_urna"] = float(num)
    return bu


def cat_ok():
    return pd.DataFrame([
        linha("0001", 2468149),
        linha("0002", 2468150),
        linha("0003", 1789754, modelo="UE2015", emissor=EM_URNA,
              alg="ECDSA-secp521r1-SHA512", cn="ueao01789754"),
    ])


# --- funções auxiliares -----------------------------------------------------

def test_cn_e_numero(A):
    assert A.cn_de_subject("O=TSE,C=BR,CN=UEAO02468149") == "UEAO02468149"
    assert A.cn_de_subject(EM_URNA) == "AC URNA"
    assert A.cn_de_subject(None) is None
    assert A.numero_de_cn("UEAO02468149") == 2468149
    assert A.numero_de_cn("ueao01789754") == 1789754
    assert A.numero_de_cn("UEAO123") is None
    assert A.familia_alg("Ed521") == "Ed521"
    assert A.familia_alg("ECDSA-secp521r1-SHA512") == "ECDSA"
    assert A.familia_alg("1.3.6.1.4.1.44588.2.1") == "Ed521"
    assert A.familia_alg("1.2.840.10045.2.1") == "ECDSA"


# --- checagens no catálogo --------------------------------------------------

def test_catalogo_consistente_sem_anomalias(A):
    cat = cat_ok()
    res = A.analisar(cat, bu_de(cat))
    c = res["catalogo"]
    assert res["n_anomalias"] == 0
    assert c["identidade"]["cn_igual_numero_interno_bu"] == 3
    assert c["unicidade"]["certificados_distintos"] == 3
    assert {x["emissor"] for x in c["emissores_por_modelo"]["UE2015"]} == {"AC URNA"}


def test_certificado_reutilizado_em_urnas_diferentes(A):
    cat = cat_ok()
    cat.loc[1, "cert_sha256"] = cat.loc[0, "cert_sha256"]
    res = A.analisar(cat, bu_de(cat))
    a = res["anomalias"]["certificado_em_urnas_diferentes"]
    assert a["n"] == 2
    assert {e["secao_id"] for e in a["exemplos"]} == {"ac-01007-0009-0001", "ac-01007-0009-0002"}
    assert res["catalogo"]["unicidade"]["certificados_em_urnas_diferentes"] == 1


def test_mesma_urna_em_duas_secoes_nao_e_anomalia(A):
    # urna de contingência: mesmo certificado e mesmo número em duas seções
    cat = cat_ok()
    cat.loc[1, ["cert_subject", "cert_sha256", "cert_serial"]] = cat.loc[
        0, ["cert_subject", "cert_sha256", "cert_serial"]].values
    res = A.analisar(cat, bu_de(cat))
    assert "certificado_em_urnas_diferentes" not in res["anomalias"]
    assert res["catalogo"]["unicidade"]["certificados_em_mais_de_uma_secao"] == 1


def test_serial_repetido_e_urna_com_dois_certificados(A):
    cat = cat_ok()
    cat.loc[1, "cert_serial"] = cat.loc[0, "cert_serial"]
    cat = pd.concat([cat, pd.DataFrame([linha("0004", 2468149, sha="ff" * 32)])],
                    ignore_index=True)
    res = A.analisar(cat, bu_de(cat))
    assert res["anomalias"]["serial_repetido_na_emissora"]["n"] >= 2
    assert res["anomalias"]["urna_com_mais_de_um_certificado"]["n"] == 2


def test_cn_difere_bu_e_usuario(A):
    cat = cat_ok()
    cat.loc[2, "motivo"] = "CN do certificado (X) difere do usuário (Y)"
    cat = pd.concat([cat, pd.DataFrame([linha("0005", 1, cn="URNA-X")])], ignore_index=True)
    res = A.analisar(cat, bu_de(cat, **{"0001": 9999999}))
    an = res["anomalias"]
    assert [e["secao_id"] for e in an["cn_difere_numero_interno_bu"]["exemplos"]] == [
        "ac-01007-0009-0001"]
    assert an["cn_difere_usuario_assinatura"]["n"] == 1
    assert an["cn_fora_do_padrao"]["n"] == 1


def test_modelo_emissor_algoritmo_incoerentes(A):
    cat = pd.concat([cat_ok(), pd.DataFrame([
        linha("0006", 2468160), linha("0007", 2468161),
        linha("0008", 2468162, emissor=EM_URNA, alg="ECDSA-secp521r1-SHA512")])],
        ignore_index=True)
    bu = bu_de(cat)
    bu.loc[bu["secao"] == "0002", "modelo_bu"] = "UE2020"
    res = A.analisar(cat, bu)
    an = res["anomalias"]
    assert [e["secao_id"] for e in an["emissor_atipico_para_modelo"]["exemplos"]] == [
        "ac-01007-0009-0008"]
    assert an["algoritmo_incoerente_com_modelo"]["n"] == 1
    assert an["modelo_vsc_difere_bu"]["n"] == 1


def test_catalogo_parcial_e_sem_bu(A, tmp_path):
    parts = tmp_path / "parts"
    parts.mkdir()
    cat = cat_ok()
    cat.iloc[:2].to_parquet(parts / "secoes-a-00001.parquet")
    v2 = cat.iloc[1:].copy()
    v2["_lote"] = "l2"
    v2.to_parquet(parts / "secoes-a-00002.parquet")
    (parts / "secoes-a-00003.parquet").write_bytes(b"parte em gravacao")
    lido, fonte = A.carregar_catalogo(tmp_path)
    assert len(lido) == 3 and fonte == {"partes": 3, "partes_ilegiveis": 1}
    res = A.analisar(lido, None)
    assert res["catalogo"]["identidade"]["sem_numero_interno_no_bu"] == 3
    assert res["n_anomalias"] == 0


# --- checagens nos .vsc reais ------------------------------------------------

def test_info_vsc_fixtures(A):
    ac = A.info_vsc(VSC_AC.read_bytes())
    assert ac["cn"] == ac["usuario"] == "UEAO02293919"
    assert A.cn_de_subject(ac["issuer"]) == "AC UE2022"
    assert A.familia_alg(ac["oid_chave"]) == "Ed521"
    am = A.info_vsc(VSC_AM.read_bytes())
    assert am["cn"] == am["usuario"] == "ueao01789754"
    assert A.familia_alg(am["oid_chave"]) == "ECDSA"
    assert ac["chave_sha256"] != am["chave_sha256"]
    assert am["aki"] == "cdaaf4b29701b3f0deb2b54258594a6d34ada48a"


def test_analisar_vscs_validade_e_chave(A, tmp_path):
    shutil.copy(VSC_AC, tmp_path / VSC_AC.name)
    shutil.copy(VSC_AM, tmp_path / VSC_AM.name)
    (tmp_path / "vsc_rr_m00000_z0001_s0001.bin").write_bytes(b"\x30\x00")
    infos = A.ler_vsc_dir(tmp_path)
    assert set(infos) == {"ac-01066-0004-0077", "am-02550-0001-0645",
                          "rr-00000-0001-0001"}
    an = A.Anomalias()
    out = A.analisar_vscs(infos, pd.DataFrame(), an)
    assert out["com_certificado"] == 2
    assert out["validade"] == {"cobre_dia_eleicao": 2}
    assert out["chaves_em_urnas_diferentes"] == 0 and an.total() == 0
    # fora da validade numa data posterior ao vencimento
    an2 = A.Anomalias()
    out2 = A.analisar_vscs(infos, pd.DataFrame(), an2,
                           dia=dt.datetime(2040, 1, 1, tzinfo=dt.timezone.utc))
    assert out2["validade"] == {"fora_da_validade": 2}
    # mesma chave pública em urnas diferentes
    infos["ac-01066-0004-0077"]["chave_sha256"] = infos["am-02550-0001-0645"]["chave_sha256"]
    an3 = A.Anomalias()
    A.analisar_vscs(infos, pd.DataFrame(), an3)
    assert an3.resumo()["chave_publica_em_urnas_diferentes"]["n"] == 2


def test_vsc_difere_do_catalogo(A):
    info = A.info_vsc(VSC_AC.read_bytes())
    cat = pd.DataFrame([{"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077",
                         "cert_sha256": "00" * 32}])
    an = A.Anomalias()
    A.analisar_vscs({"ac-01066-0004-0077": info}, cat, an)
    assert an.resumo()["certificado_difere_catalogo"]["n"] == 1


# --- cadeia ------------------------------------------------------------------

def _cert(sujeito, emissor, chave_pub, chave_ass, ca):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import NameOID

    agora = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    return (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, sujeito)]))
            .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, emissor)]))
            .public_key(chave_pub).serial_number(x509.random_serial_number())
            .not_valid_before(agora).not_valid_after(agora + dt.timedelta(days=5000))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
            .sign(chave_ass, hashes.SHA512()))


def test_cadeia_ecdsa_sintetica(A, tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    k_ac = ec.generate_private_key(ec.SECP521R1())
    k_outra = ec.generate_private_key(ec.SECP521R1())
    k_urna = ec.generate_private_key(ec.SECP521R1())
    ac = _cert("AC TESTE", "AC TESTE", k_ac.public_key(), k_ac, True)
    urna = _cert("UEAO00000001", "AC TESTE", k_urna.public_key(), k_ac, False)
    falsa = _cert("UEAO00000002", "AC TESTE", k_urna.public_key(), k_outra, False)
    (tmp_path / "ac.pem").write_bytes(ac.public_bytes(serialization.Encoding.PEM))
    (tmp_path / "lixo.txt").write_text("não é certificado")
    acs = A.carregar_acs(tmp_path)
    assert len(acs) == 1
    assert A.validar_cadeia({"_cert": urna, "aki": None}, acs)[0] is True
    assert A.validar_cadeia({"_cert": falsa, "aki": None}, acs)[0] is False
    assert A.validar_cadeia({"_cert": urna, "aki": None}, [])[0] is None


def test_cadeia_fixtures_sem_ac(A):
    """Sem os certificados das AC, a cadeia fica indeterminada (None)."""
    an = A.Anomalias()
    infos = {"ac-01066-0004-0077": A.info_vsc(VSC_AC.read_bytes()),
             "am-02550-0001-0645": A.info_vsc(VSC_AM.read_bytes())}
    out = A.analisar_vscs(infos, pd.DataFrame(), an, acs=[])
    assert out["cadeia"] == {"acs_carregadas": 0, "sem_ac": 2}
    # certificado Ed521 nunca é aceito por chave de AC de outro tipo
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP521R1())
    falsa_ac = _cert("AC UE2022", "AC UE2022", k.public_key(), k, True)
    assert A.assinado_por(infos["ac-01066-0004-0077"]["_cert"], falsa_ac) is False
    assert A.assinado_por(infos["am-02550-0001-0645"]["_cert"], falsa_ac) is False


def test_main_grava_resumo(A, tmp_path):
    base = tmp_path / "integ"
    (base / "parts").mkdir(parents=True)
    cat = cat_ok()
    cat.to_parquet(base / "parts" / "secoes-x-00001.parquet")
    bu = bu_de(cat).rename(columns={"modelo_bu": "modelo_urna", "tipo_urna_bu": "tipo_urna"})
    bu.to_parquet(tmp_path / "bu.parquet")
    saida = tmp_path / "out" / "certificados_resumo.json"
    assert A.main(["--integridade", str(base), "--bu", str(tmp_path / "bu.parquet"),
                   "--saida", str(saida)]) == 0
    res = json.loads(saida.read_text(encoding="utf-8"))
    assert res["n_anomalias"] == 0 and res["catalogo"]["secoes_com_certificado"] == 3
    assert res["cadeia_validada"] is False


def test_ac_vencida_no_dia_e_emissao_fora_da_validade(A, tmp_path):
    """AC com validade encerrada antes da eleição vira anomalia, mesmo com assinatura boa."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    def nome(cn):
        return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])

    k_ac = ec.generate_private_key(ec.SECP521R1())
    k_urna = ec.generate_private_key(ec.SECP521R1())
    utc = dt.timezone.utc
    ac = (x509.CertificateBuilder().subject_name(nome("AC TESTE")).issuer_name(nome("AC TESTE"))
          .public_key(k_ac.public_key()).serial_number(1)
          .not_valid_before(dt.datetime(2011, 7, 22, tzinfo=utc))
          .not_valid_after(dt.datetime(2026, 7, 18, tzinfo=utc))
          .sign(k_ac, hashes.SHA512()))
    urna = (x509.CertificateBuilder().subject_name(nome("UEAO00000001"))
            .issuer_name(nome("AC TESTE")).public_key(k_urna.public_key()).serial_number(2)
            .not_valid_before(dt.datetime(2026, 8, 3, tzinfo=utc))
            .not_valid_after(dt.datetime(2037, 12, 31, tzinfo=utc))
            .sign(k_ac, hashes.SHA512()))
    der = urna.public_bytes(serialization.Encoding.DER)
    info = {"cn": "UEAO00000001", "usuario": "UEAO00000001", "issuer": "CN=AC TESTE",
            "serial": "2", "sha256": "ab" * 32, "nao_antes": "2026-08-03T00:00:00+00:00",
            "nao_depois": "2037-12-31T00:00:00+00:00", "oid_chave": "1.2.840.10045.2.1",
            "alg_hw": "ecdsa", "chave_sha256": A.hashlib.sha256(A._spki_der(der)).hexdigest(),
            "aki": None, "_cert": urna, "_der": der}
    an = A.Anomalias()
    out = A.analisar_vscs({"sp-00001-0001-0001": info}, pd.DataFrame(), an, acs=[ac])
    r = an.resumo()
    assert out["cadeia"]["valida"] == 1
    assert r["ac_emissora_fora_da_validade_no_dia"]["n"] == 1
    assert r["certificado_emitido_fora_da_validade_da_ac"]["n"] == 1


# --- modo completo (--todas), sem rede ----------------------------------------

AC_REPO = ROOT / "data" / "certificados" / "ac"


def test_ac_do_repositorio_conferem_resumo_oficial(A):
    """Os PEM das AC UE2020 e UE2022 são byte a byte os arquivos do resumo digital do TSE."""
    assert A.conferir_resumo_oficial((AC_REPO / "acue2020.pem").read_bytes()) == "acue2020.cer"
    assert A.conferir_resumo_oficial((AC_REPO / "acue2022.pem").read_bytes()) == "acue2022.cer"
    assert A.conferir_resumo_oficial(b"outro") is None
    fichas = {f["cn"]: f for f in A.descrever_acs(AC_REPO)}
    assert set(fichas) == {"AC URNA", "AC UE2020", "AC UE2022"}
    assert fichas["AC URNA"]["valida_no_dia_da_eleicao"] is False
    assert fichas["AC UE2022"]["aki"] == fichas["AC UE2020"]["aki"]  # mesma AC URNA v2
    assert all(f["nivel"] == "intermediaria" for f in fichas.values())


def test_avaliar_vsc_fixtures(A):
    A._init_worker(None)
    sem = A.avaliar_vsc(VSC_AC.read_bytes())
    assert sem["cadeia_ok"] is None and "AC emissora ausente" in sem["motivo"]
    A._init_worker(str(AC_REPO))
    ac = A.avaliar_vsc(VSC_AC.read_bytes())
    assert ac["cadeia_ok"] is True and ac["nivel_cadeia"] == "intermediaria"
    assert ac["emissor"] == "AC UE2022" and ac["modelo"] == "UE2022"
    assert ac["valido_na_eleicao"] and ac["ac_valida_na_eleicao"] and ac["motivo"] is None
    assert ac["cadeia_caminho"] == "UEAO02293919 > AC UE2022"
    am = A.avaliar_vsc(VSC_AM.read_bytes())
    assert am["cadeia_ok"] is True and am["emissor"] == "AC URNA"
    assert am["ac_valida_na_eleicao"] is False
    assert am["motivo"].startswith("observação: certificado publicado da AC URNA")
    assert A.avaliar_vsc(b"\x30\x00")["motivo"]
    A._init_worker(None)


def test_subir_cadeia_ate_a_raiz(A):
    from cryptography.hazmat.primitives.asymmetric import ec

    k_raiz, k_int, k_urna = (ec.generate_private_key(ec.SECP521R1()) for _ in range(3))
    raiz = _cert("RAIZ", "RAIZ", k_raiz.public_key(), k_raiz, True)
    inter = _cert("AC INTER", "RAIZ", k_int.public_key(), k_raiz, True)
    urna = _cert("UEAO00000001", "AC INTER", k_urna.public_key(), k_int, False)
    assert A.subir_cadeia(inter, [raiz, inter]) == ("raiz", ["AC INTER", "RAIZ"])
    assert A.subir_cadeia(inter, [inter]) == ("intermediaria", ["AC INTER"])
    ok, _, ac = A.validar_cadeia({"_cert": urna, "aki": None}, [raiz, inter])
    assert ok is True and A._cn_cert(ac) == "AC INTER"
    # raiz com o mesmo nome e outra chave não fecha a cadeia
    k_falsa = ec.generate_private_key(ec.SECP521R1())
    falsa = _cert("RAIZ", "RAIZ", k_falsa.public_key(), k_falsa, True)
    assert A.subir_cadeia(inter, [falsa, inter])[0] == "intermediaria"


def test_nome_vsc(A):
    assert A.nome_vsc("AC", "01007", "0009", "0001") == "o03220ac0100700090001-vota.vsc"


class FakeFetcher:
    """Responde por URL; levanta erro nas URLs marcadas como falha de rede."""

    def __init__(self, respostas, falhas=()):
        self.respostas, self.falhas, self.urls = respostas, set(falhas), []
        self.stats = {}

    async def get(self, url):
        self.urls.append(url)
        if url in self.falhas:
            raise RuntimeError("falha simulada")
        return self.respostas.get(url)

    async def get_json(self, url):
        b = await self.get(url)
        return None if b is None else json.loads(b)


def test_coletar_todas_retomavel_sem_rede(A, tmp_path):
    import asyncio

    from dataurnas.downloader import ele2026 as E

    sec = pd.DataFrame([
        {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077", "status": "ok",
         "hash": "aa11", "fase": "oficial"},          # caminho direto
        {"uf": "am", "cd_mun": "02550", "zona": "0001", "secao": "0645", "status": "ok",
         "hash": None, "fase": "oficial"},            # via -aux.json
        {"uf": "rr", "cd_mun": "03018", "zona": "0001", "secao": "0001", "status": "ok",
         "hash": "bb22", "fase": "oficial"},          # .vsc inexistente
        {"uf": "rr", "cd_mun": "03018", "zona": "0001", "secao": "0002", "status": "ok",
         "hash": "cc33", "fase": "oficial"},          # falha de rede: fica pendente
    ])
    aux_am = {"hashes": [{"hash": "dd44", "st": "Totalizado", "arq": [
        {"nm": "o03220am0255000010645-vota.vsc", "tp": "vota"}]}]}
    url_s4 = E.url_arquivo("rr", "03018", "0001", "0002", "cc33",
                           A.nome_vsc("rr", "03018", "0001", "0002"))
    resp = {
        E.url_arquivo("ac", "01066", "0004", "0077", "aa11",
                      A.nome_vsc("ac", "01066", "0004", "0077")): VSC_AC.read_bytes(),
        E.url_aux("am", "02550", "0001", "0645"): json.dumps(aux_am).encode(),
        E.url_arquivo("am", "02550", "0001", "0645", "dd44",
                      "o03220am0255000010645-vota.vsc"): VSC_AM.read_bytes(),
    }
    f = FakeFetcher(resp, falhas=[url_s4])
    tabela = tmp_path / "certificados.parquet"
    logs = []
    st = asyncio.run(A.coletar_todas(sec, f, tabela, AC_REPO, processos=0, lote=2,
                                     tarefas=2, log=logs.append))
    assert st["processadas"] == 3 and st["falhas_rede"] == 1
    assert st["origem"] == {"direto": 1, "aux": 1, "aux sem hash": 1}
    assert len(list(A.partes_de(tabela).glob("parte-*.parquet"))) == 2
    df = A.consolidar(tabela)
    assert list(df.columns) == A.COLS_TABELA and len(df) == 3
    por = df.set_index("secao")
    assert por.loc["0077", "cadeia_ok"] and por.loc["0077", "origem"] == "direto"
    assert por.loc["0645", "emissor"] == "AC URNA" and por.loc["0645", "origem"] == "aux"
    assert pd.isna(por.loc["0001", "cert_sha256"]) and por.loc["0001", "motivo"] == "aux sem hash"
    # retomada: só a seção que falhou é tentada de novo
    f2 = FakeFetcher(dict(resp, **{url_s4: VSC_AC.read_bytes()}))
    st2 = asyncio.run(A.coletar_todas(sec, f2, tabela, AC_REPO, processos=0,
                                      tarefas=2, log=logs.append))
    assert st2["ja_feitas"] == 3 and st2["processadas"] == 1 and f2.urls == [url_s4]
    df = A.consolidar(tabela)
    assert len(df) == 4 and A.chaves_feitas(A.partes_de(tabela)) == {
        tuple(r) for r in sec[A.CHAVE].itertuples(index=False, name=None)}

    res = A.resumir_tabela(df, total_ok=10)
    assert res["situacao"] == "em andamento" and res["cobertura_pct"] == 40.0
    assert res["com_certificado"] == 3 and res["cadeia_ok"] == {"True": 3}
    assert res["nivel_cadeia"] == {"intermediaria": 3}
    assert res["sem_certificado_por_motivo"] == {"aux sem hash": 1}
    # mesmo .vsc reaproveitado em 0002: certificado repetido, mas da mesma urna
    assert res["certificados_em_mais_de_uma_secao"] == 1
    assert res["chaves_em_urnas_diferentes"] == 0
    assert res["por_emissor_e_modelo"]["AC URNA"]["UE2015"]["ac_valida_na_eleicao"] == {
        "False": 1}
    assert A.resumir_tabela(df, total_ok=4)["situacao"] == "concluído"


def test_carregar_secoes_ok(A, tmp_path):
    p = tmp_path / "s.parquet"
    pd.DataFrame([
        {"uf": "rr", "cd_mun": "1", "zona": "1", "secao": "2", "status": "ok", "hash": "x"},
        {"uf": "rr", "cd_mun": "1", "zona": "1", "secao": "1", "status": "ok", "hash": "y"},
        {"uf": "ac", "cd_mun": "1", "zona": "1", "secao": "1", "status": "ok", "hash": "z"},
        {"uf": "rr", "cd_mun": "1", "zona": "1", "secao": "3", "status": "agregada",
         "hash": None},
    ]).to_parquet(p)
    df, total = A.carregar_secoes_ok(p, ["RR"], limite=1)
    assert total == 3 and df["secao"].tolist() == ["1"]


def test_resumo_preserva_bloco_todas(A, tmp_path):
    saida = tmp_path / "r.json"
    A.atualizar_resumo(saida, {"situacao": "em andamento"})
    base = tmp_path / "integ"
    (base / "parts").mkdir(parents=True)
    cat_ok().to_parquet(base / "parts" / "secoes-x-00001.parquet")
    assert A.main(["--integridade", str(base), "--bu", str(tmp_path / "nao-existe.parquet"),
                   "--saida", str(saida)]) == 0
    res = json.loads(saida.read_text(encoding="utf-8"))
    assert res["todas"] == {"situacao": "em andamento"} and "catalogo" in res
    args = A.parse_args(["--todas", "--integridade", str(base)])
    assert args.concorrencia == 8 and args.tabela == str(base / "certificados.parquet")


def test_relatorio_secao_certificados(tmp_path):
    p = ROOT / "scripts" / "docs" / "gerar_relatorio_integridade.py"
    spec = importlib.util.spec_from_file_location("gerar_relatorio_integridade", p)
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    assert "ainda não foi executada" in R.secao_certificados(tmp_path)
    res = {
        "catalogo": {"ufs": ["rr"], "secoes_com_certificado": 2,
                     "unicidade": {"certificados_distintos": 2},
                     "identidade": {"cn_igual_numero_interno_bu": 2, "comparados_com_bu": 2},
                     "emissores_por_modelo": {"UE2022": [
                         {"emissor": "AC UE2022", "algoritmo": "Ed521", "secoes": 2}]}},
        "vsc": {"vsc_analisados": 2, "validade": {"cobre_dia_eleicao": 2},
                "cadeia": {"acs_carregadas": 3, "valida": 2}},
        "todas": {"situacao": "em andamento", "cobertura_pct": 0.01, "secoes_processadas": 50,
                  "secoes_ok_no_pais": 499207, "cadeia_ok": {"True": 50},
                  "nivel_cadeia": {"intermediaria": 50}, "valido_na_eleicao": {"True": 50},
                  "por_emissor_e_modelo": {"AC UE2022": {"UE2022": {
                      "secoes": 50, "nao_antes_min": "2023-08-13T16:16:10+00:00",
                      "nao_antes_max": "2024-06-21T00:10:45+00:00",
                      "cadeia_ok": {"True": 50}, "ac_valida_na_eleicao": {"True": 50}}}},
                  "acs": [{"cn": "AC UE2022", "emissor": "AC URNA v2",
                           "nao_antes": "2023-02-28T13:46:49+00:00",
                           "nao_depois": "2039-02-24T13:46:49+00:00",
                           "valida_no_dia_da_eleicao": True,
                           "confere_resumo_oficial_tse": "acue2022.cer"}]},
    }
    (tmp_path / "certificados_resumo.json").write_text(json.dumps(res), encoding="utf-8")
    md = R.secao_certificados(tmp_path)
    assert md.startswith("## Certificados das urnas")
    assert "**Em andamento.** Modo completo" in md and "ausente nesta cópia" in md
    assert "validade no dia da eleição: válidos: 2" in md and "cadeia: conferida: 2" in md
    assert "| AC UE2022 | UE2022 | 50 | 13/08/2023 a 21/06/2024 | sim: 50 | sim: 50 |" in md
    assert "acue2022.cer" in md and "não indício de adulteração" in md
    assert chr(0x2014) not in md and chr(0x2013) not in md
