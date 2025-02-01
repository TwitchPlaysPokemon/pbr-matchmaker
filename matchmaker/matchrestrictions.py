import pokecat
import logging

log = logging.getLogger(__name__)


def meets_base_stats_bulk_ratio(mon, ratio):
    basestats = mon['basestats']
    return (
        ((basestats['hp'] + basestats['def'] + basestats['spD']) / 3)
        /
        ((basestats['atk'] + basestats['spA']) / 2)
    ) >= ratio


restricted_clone_pokemon_team_size_3 = [
    mon for mon in pokecat.gen4data.POKEDEX
    if mon and meets_base_stats_bulk_ratio(mon, 2)
]
restricted_clone_pokemon_team_size_4 = [
    mon for mon in pokecat.gen4data.POKEDEX
    if mon and meets_base_stats_bulk_ratio(mon, 1.5)
]

restricted_clone_ids_team_size_3 = [mon['id'] for mon in restricted_clone_pokemon_team_size_3]
restricted_clone_ids_team_size_4 = [mon['id'] for mon in restricted_clone_pokemon_team_size_4]

restricted_clone_names_team_size_3 = [mon['name'] for mon in restricted_clone_pokemon_team_size_3]
restricted_clone_names_team_size_4 = [mon['name'] for mon in restricted_clone_pokemon_team_size_4]
