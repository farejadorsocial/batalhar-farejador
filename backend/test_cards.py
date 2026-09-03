import json
from app.services.tournaments import _load_tournament_configs, _load_themes

def test_theme_catalogs_exist():
    themes = _load_themes()
    assert {"perfil", "habitos", "habitos_diarios"}.issubset(themes)
    for category, rows in themes.items():
        assert rows
        for theme in rows:
            assert theme["id"] and theme["nome"]
            assert len(theme["opcoes"]) >= 2

def test_tournament_card_rules_are_valid():
    themes = _load_themes()
    configs = _load_tournament_configs()
    assert configs
    for c in configs:
        category = c["categoria"]
        theme_id = c["tema_id"]
        theme = next(x for x in themes[category] if x["id"] == theme_id)
        card = c["card"]
        duel = c["duelo"]
        assert 1 <= card["quantidade_opcoes"] <= len(theme["opcoes"])
        assert 1 <= duel["quantidade_respostas"]
        assert sum(c["premiacao"][k] for k in ("primeiro", "segundo", "organizador", "sistema")) == 100
