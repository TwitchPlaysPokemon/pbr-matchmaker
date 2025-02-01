from .exceptions import InvalidMatch
from .utils import pokedex

import pokecat
import re, logging
from typing import List

log = logging.getLogger(__name__)


match_bid_pat = re.compile(r"""^
    (
        (?P<modes> [^,-/]+)  \s+
    )?
    (?P<teams>
        (?P<team1>[^/]+)
        /
        (?P<team2>[^/]+)
    )?
    (?P<unrecognized>
        .*
    )?
    $""", re.IGNORECASE | re.VERBOSE)


modes_only_bid_pat = re.compile(r"""^
    (
        (?P<modes> [^,]+)  \s+
    )?
    (?P<teams>)     # Empty group.
    (?P<unrecognized>
        .*
    )?
    $""", re.IGNORECASE | re.VERBOSE)


team_size_bid_pat = re.compile(r"""
    (?P<team1size> [1-6]) 
    (v|vs)
    (?P<team2size> [1-6])
    """, re.IGNORECASE | re.VERBOSE)


ally_hit_pat = re.compile(r"""
    (?P<percentage> \d+) %? ally(hit|target)
    """, re.IGNORECASE | re.VERBOSE)

battle_timer_pat = re.compile(r"""
    (?P<minutes> \d+)(min|minute|minutes)
    """, re.IGNORECASE | re.VERBOSE)


def parse_match_bid_command(match_bid_command):
    match_bid_command += ' ' # Trailing space needed for regex matching.
    pat = match_bid_pat if '/' in match_bid_command else modes_only_bid_pat
    m = pat.match(match_bid_command)
    if not m:
        return None, None, None, match_bid_command

    # Extract modes and teams.
    modes_str = m.group('modes')
    teams_str = m.group('teams')
    unrecognized = m.group('unrecognized').strip()

    if modes_str:
        modes = modes_str.split()
    else:
        modes = None

    if teams_str:
        team1 = m.group('team1').split(",")
        team2 = m.group('team2').split(",")
        teams = [team1, team2]
    else:
        teams = None

    team_sizes = None
    ally_hit = None
    battle_timer = None
    if modes:
        for mode in list(modes):
            m = team_size_bid_pat.match(mode)
            if m:
                modes.remove(mode)
                team_sizes = (int(m.group('team1size')), int(m.group('team2size')))
                break

        for mode in list(modes):
            m = ally_hit_pat.match(mode)
            if m:
                modes.remove(mode)
                ally_hit = int(m.group('percentage'))
                if ally_hit < 0 or 100 < ally_hit:
                    raise InvalidMatch(f"Ally target percentage must be between 0 and 100 (got {ally_hit}%)")
                break

        for mode in list(modes):
            if mode.lower() in ('randommin', 'randomtimer', 'randomtimed', 'randombattletimer', 'randombattletime'):
                modes.remove(mode)
                battle_timer = 'random'
                break
            m = battle_timer_pat.match(mode)
            if m:
                modes.remove(mode)
                battle_timer = int(m.group('minutes'))
                if battle_timer < 1 or 15 < battle_timer:
                    raise InvalidMatch(f"Battle timer must be \"random\" or between 1 and 15 minutes (got {battle_timer})")
                break

    if battle_timer is not None:
        if not any(m.lower() in ('timed', 'timer') for m in modes):
            modes.append('timed')

    if team_sizes and teams:
        for i, team_size in enumerate(team_sizes):
            if team_size != len(teams[i]):
                raise InvalidMatch('The team sizes specified in your bid do not match.')

    return modes, teams, team_sizes, ally_hit, battle_timer, unrecognized


def parse_pokeset(name_or_id):
    """Return a species id and setname from a user-requested pokeset.

    Raises InvalidMatch if no species could be matched.
    """
    name_or_id = name_or_id.lower().strip()
    pkmn_name_regex = r"(?:mr. )?[^ -]+?(?:(?: jr.)|(?:-o|-oh|-z))?"
    match = re.match(r"^({0})((?:\s|-).*?)?$".format(pkmn_name_regex), name_or_id)
    if not match:
        raise InvalidMatch('Did not recognize Pokémon: {}'.format(name_or_id))
    name_or_id = match.group(1)
    species_id = parse_species_name_or_id(name_or_id)
    if not species_id:
        raise InvalidMatch('Did not recognize Pokémon species: {}'.format(name_or_id))
    elif species_id <= 0 or 493 < species_id:
        raise InvalidMatch('Pokémon species {} is not in Generation 4.'
                           .format(name_or_id))
    setname = (match.group(2) or '')[1:].strip()
    return species_id, setname


def parse_species_name_or_id(name_or_id):
    """Return a species id from a species name or id."""
    try:
        species_id = int(name_or_id)
    except ValueError:
        species_name = name_or_id
        pokemon = pokedex.get_by_name(species_name)
        if not pokemon:
            return None
        try:
            species_id = int(pokemon['id'])
        except ValueError:
            return None
    return species_id


def normalized_name_from_id(nat_id):
    return pokecat.normalize_name(name_from_id(nat_id))


def name_from_id(nat_id):
    return pokedex.get_entry(nat_id)['name']


# The code above was adapted from the code below,
# which is kept here for reference:

# def _parse_pokemon_name_or_id_old(pokemon_sets, name_or_id, tags = ['biddable']) -> List[dict]:
#     """Returns a list of pokemon data dicts matching the given national ID
#     or pokemon name.
#     Returns an empty list if no Pokemon matched.
#     """
#     name_or_id = name_or_id.lower().strip()
#     pkmn_name_regex = r"(?:mr. )?[^ -]+?(?:(?: jr.)|(?:-o|-oh|-z))?"
#     match = re.match(r"^({0})((?:\s|-).*?)?$".format(pkmn_name_regex), name_or_id)
#     if not match:
#         return []
#     name_or_id = match.group(1)
#     setname = (match.group(2) or '')[1:].strip()
#     try:
#         nat_id = int(name_or_id)
#         # it apparently is an ID at this point
#         # this might return [] for invalid ids, as desired
#         pokemon = _get_pokemon_by_species_id(pokemon_sets, nat_id, tags, setname)
#     except ValueError:
#         pass
#         # seems to be a string
#         # this might return None if not found, as desired
#         pokemon = _get_pokemon_by_name(pokemon_sets, name_or_id, tags, setname)
#     # hide hidden pokemon
#     pokemon = [p for p in pokemon if not p['hidden']]
#     return pokemon

#
# def _get_pokemon_by_species_id(pokemon_sets, species_id, tags, setname=None) -> List[dict]:
#     candidates = pokemon_sets.get_by_species_id_and_tags(species_id, tags)
#     if setname:
#         candidates = [c for c in candidates if c['setname'].lower() == setname.lower()]
#     return candidates
#
#
# def _get_pokemon_by_name(pokemon_sets, name, tags, setname=None) -> List[dict]:
#     pokemon = get_by_name(name)
#     if not pokemon:
#         return []
#     candidates = pokemon_sets.get_by_species_id_and_tags(pokemon['id'],tags)
#     if setname:
#         candidates = [c for c in candidates if c['setname'].lower() == setname]
#     return candidates