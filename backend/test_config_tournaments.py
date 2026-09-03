import json
from pathlib import Path
from app.services.tournaments import _load_tournament_configs, CONFIG_FILE

def test_config_file():
    assert CONFIG_FILE.exists()
    data=json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    assert isinstance(data["torneios"], list) and data["torneios"]
    ids=[x["id_config"] for x in data["torneios"]]
    assert len(ids)==len(set(ids))
    for c in data["torneios"]:
        p=c["premiacao"]
        assert p["primeiro"]+p["segundo"]+p["organizador"]+p["sistema"]==100
        assert c["tempo"]["inscricao_minutos"]>0
        assert c["tempo"]["inicio_apos_lotacao_minutos"]>=0
        assert c["tempo"]["duelo_minutos"]>0
        assert c["participantes"]["minimo"] >= 2
        assert c["participantes"]["maximo"] >= c["participantes"]["minimo"]
        assert c["card"]["quantidade_opcoes"] >= 1
        assert c["duelo"]["quantidade_respostas"] >= 1

def test_loader():
    configs=_load_tournament_configs()
    assert len(configs)>=3
