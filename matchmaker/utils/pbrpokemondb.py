
import logging
import json
from functools import lru_cache
from os import path

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_pbr_pokemon_db(dir_path):
    file = path.join(dir_path, "pbrpokemondb.json")
    with open(file, "rt", encoding="utf-8") as f:
        result = list(json.load(f))
    # check uniqueness of species and setname
    existing = set()
    for i, pokeset in enumerate(result[:]):
        id_ = (pokeset["species"]["id"], pokeset["setname"])
        if id_ in existing:
            log.error("pokeset species+setname is not unique and therefore removed: %s %s", pokeset["species"]["name"],
                      pokeset["setname"])
            result.remove(pokeset)
        existing.add(id_)
    del existing
    return result
