# -*- coding: utf-8 -*-
# source code owned by Twitch Plays Pokemon AUTHORIZED USE ONLY see LICENSE.MD

import os
import json

from pokecat.utils import normalize_name

_local_dir = os.path.dirname(os.path.realpath(__file__))
_pokedex_path = os.path.join(_local_dir, "pokedex.json")
with open(_pokedex_path, "r", encoding="utf-8") as f:
    POKEDEX = json.load(f)

POKEDEX_ID_DICT = {}

POKEDEX_NAME_DICT = {}

for entry in POKEDEX:
    POKEDEX_ID_DICT[entry["id"].lower()] = entry
    POKEDEX_NAME_DICT[normalize_name(entry["name"])] = entry

GEN1_MAX_ID = 151  # Mew
GEN2_MAX_ID = 251  # Celebi
GEN3_MAX_ID = 386  # Deoxys
GEN4_MAX_ID = 493  # Arceus
GEN5_MAX_ID = 649  # Genesect
GEN6_MAX_ID = 721  # Volcanion
GEN7_MAX_ID = 807  # Zeraora
GEN8_MAX_ID = 898  # Calyrex
GEN9_MAX_ID = 1017  # Ogerpon
HIGHEST_MAIN_BADGE = GEN9_MAX_ID
GENS = {
    0: 0,
    1: GEN1_MAX_ID,
    2: GEN2_MAX_ID,
    3: GEN3_MAX_ID,
    4: GEN4_MAX_ID,
    5: GEN5_MAX_ID,
    6: GEN6_MAX_ID,
    7: GEN7_MAX_ID,
    8: GEN8_MAX_ID,
    9: GEN9_MAX_ID
}


def get_entry(nat_id):
    """Returns a pokemon dict by national id.
    Raises IndexError if not found."""
    nat_id = str(nat_id)
    split = nat_id.split("-", maxsplit=1)
    try:
        int_id = int(split[0])
    except ValueError:
        raise IndexError("Pokemon ID not recognized")
    if len(split) > 1:
        nat_id = str(int_id) + "-" + split[1]
    else:
        nat_id = str(int_id)
    entry = POKEDEX_ID_DICT.get(nat_id.lower())
    if not entry:
        raise IndexError("Pokemon ID not recognized")
    return entry


def get_by_name(name):
    """Returns a pokemon dict by name.
    Returns None if no Pokemon matched."""
    name = normalize_name(name)
    return POKEDEX_NAME_DICT.get(name)


def get_by_name_or_entry(name_or_entry):
    """Returns a pokemon dict by name or entry.
    Returns None if no Pokemon matched."""
    pokemon = None
    if name_or_entry[0] == "#":
        name_or_entry = name_or_entry[1:]
    # Try entry first
    try:
        pokemon = get_entry(name_or_entry)
    except LookupError:
        pass
    if pokemon is None:
        # Try name
        pokemon = get_by_name(name_or_entry)
    return pokemon
