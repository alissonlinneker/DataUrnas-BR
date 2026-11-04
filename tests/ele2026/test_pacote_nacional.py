"""National package audit: BU image x BU comparison and per-voter log metrics."""

from __future__ import annotations

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _carregar():
    p = RAIZ / "scripts" / "ele2026" / "pacote_nacional.py"
    spec = importlib.util.spec_from_file_location("pacote_nacional", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _carregar()
DIA = "25/10/2026"


def _linha(hora: str, msg: str, nivel: str = "INFO", urna: str = "11111111",
           data: str = DIA) -> str:
    return f"{data} {hora}\t{nivel}\t{urna}\tVOTA\t{msg}\tABCDEF"


def _eleitor(h: str, h_voto: str, tipo: str, urna: str = "11111111") -> list[str]:
    """Log lines of one voter: biometric, manual after fingerprint or no fingerprint."""
    out = [_linha(h, M.EVENTO_ID, urna=urna)]
    if tipo == "bio":
        out += [_linha(h, "Solicita digital. Tentativa [1] de [4]", urna=urna),
                _linha(h, "Tipo de habilitação do eleitor [biométrica]", urna=urna)]
    elif tipo == "biog":
        out += [_linha(h, "Solicita digital. Tentativa [1] de [4]", urna=urna),
                _linha(h, "Solicitação de dado pessoal do eleitor para habilitação manual",
                       urna=urna)]
    out += [_linha(h, "Eleitor foi habilitado", urna=urna), _linha(h_voto, M.EVENTO_VOTO,
                                                                    urna=urna)]
    return out


def test_classes_and_rapid_runs():
    linhas = [_linha("07:00:00", "Votos do turno anterior", data="04/10/2026")]
    # five fast voters without fingerprint (gaps of 20 s), then two slow biometric ones
    for i in range(5):
        s = 10 + 20 * i
        linhas += _eleitor(f"08:00:{s - 5:02d}", f"08:00:{s:02d}", "sem")
    linhas += _eleitor("08:10:00", "08:10:30", "bio")
    linhas += _eleitor("08:20:00", "08:20:30", "biog")
    m, ev = M.metricas_log("\n".join(linhas), DIA, 0)
    assert m["votos_log"] == 7
    assert (m["votos_sem_digital"], m["votos_bio"], m["votos_biog"]) == (5, 1, 1)
    assert m["votos_sem_bio"] == 6
    assert m["rajadas"] == 1 and m["rajadas_votos"] == 5 and m["rajadas_so_sem_bio"] == 1
    assert m["rajadas_sb"] == 1 and m["rajadas_sb_votos"] == 5
    assert m["maior_seq_sem_bio"] == 5   # the biometric vote breaks the streak
    assert not ev


def test_windows_use_brasilia_time_and_machine_swap_breaks_runs():
    # Acre (offset -2): 15:30 local is 17:30 in Brasilia
    linhas = _eleitor("14:10:00", "14:10:10", "sem")            # 16:10 BSB: last hour
    linhas += _eleitor("15:30:00", "15:30:10", "sem")           # after 17h BSB
    for i in range(4):
        linhas += _eleitor(f"15:31:{i * 10:02d}", f"15:31:{i * 10 + 5:02d}", "bio",
                           urna="22222222")                     # other machine
    linhas.append(_linha("15:40:00", "Falha na captura 123", nivel="ERRO"))
    m, ev = M.metricas_log("\n".join(linhas), DIA, -2)
    assert m["votos_ultima_hora"] == 1 and m["sem_bio_ultima_hora"] == 1
    assert m["votos_apos_17h"] == 5 and m["sem_bio_apos_17h"] == 1
    assert m.get("rajadas", 0) == 0          # 1 + 4 votes split by the machine swap
    assert ev[("ERRO", "VOTA", "Falha na captura N")] == 1 and m["linhas_erro"] == 1


def test_comparar_a_flags_each_field():
    img = {"img_candidatos": {13: 10, 22: 20}, "img_brancos": 1, "img_nulos": 2,
           "img_total_apurado": 33, "img_cab_comparecimento": 33}
    bu = {"bu_candidatos": {13: 10, 22: 21}, "bu_brancos": 1, "bu_nulos": 2,
          "bu_comparecimento": 33}
    assert M.comparar_a(img, bu) == ["candidatos"]
    bu["bu_candidatos"] = {13: 10, 22: 20}
    assert M.comparar_a(img, bu) == []
