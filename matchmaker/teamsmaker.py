
from .exceptions import InvalidMatch
from .selections import minimal_reoccurrence_selections, weighted_select
from .parsing import parse_pokeset
from .matchrestrictions import restricted_clone_names_team_size_3, restricted_clone_names_team_size_4, \
    restricted_clone_ids_team_size_4, restricted_clone_ids_team_size_3
from .utils.stringutils import stringify_list
import pokecat

import math
import logging, bisect, random, gevent
from itertools import accumulate, chain
from copy import deepcopy
from collections import namedtuple

log = logging.getLogger(__name__)

SetCollection = namedtuple('Collection', ['shinies', 'nonshinies'])


class TeamsMaker:
    def __init__(self, set_repository, cfg):
        self._cfg = cfg
        self._set_repository = set_repository
        self._shiny_chance = cfg['shiny_chance']

    def make(self, metagame, gimmick, match_settings, reusedData=None, team_sizes=None):
        return self._make(metagame, gimmick, match_settings, reusedData=reusedData, team_sizes=team_sizes)

    def make_from_team_choice(self, metagame, gimmick, match_settings, team_args):
        """Get teams from a match bid that chose species / species+sets.

        Args:
            metagame: Selected MatchMetagame.
            gimmick: Selected MatchGimmick.
            team_args: 2d list of team arguments in the bid.

        Returns: 2D list of teams with instantiated Pokemon sets.
        """
        teams = [[None] * len(team) for team in team_args]

        match_sets = []
        for t_ind, team in enumerate(teams):
            team_sets = []
            for p_ind, _ in enumerate(team):
                pokeset_arg = team_args[t_ind][p_ind].strip()
                species_id, setname = (
                    parse_pokeset(pokeset_arg))
                if not setname and metagame.is_combo:
                    raise InvalidMatch("Species-only requests are not supported"
                                       " for metagame mixes. Please omit teams,"
                                       " or specify setnames for all species.")
                pokeset = self._select_pokeset_from_bid(
                    pokeset_arg, species_id, setname,
                    metagame, match_sets, team_sets)
                teams[t_ind][p_ind] = pokeset
                match_sets.append(pokeset)
                team_sets.append(pokeset)
                gevent.sleep(0.002)
        for m in metagame.base_modes:
            set_tag = m.set_tags[0]
            if not any(set_tag in p['tags'] for p in chain(*teams)):
                raise InvalidMatch('The {} metagame was requested, but '
                                   ' was not present in your teams.'
                                   .format(m.first_bid_alias()))
        return self._make(metagame, gimmick, match_settings, pre_alteration_teams=teams)

    def _make(self, metagame, gimmick, match_settings, reusedData=None, pre_alteration_teams=None, team_sizes=None):
        if not pre_alteration_teams:
            # Bidder didn't choose team pokemon, so generate them.
            if not reusedData.sets:
                reusedData.sets = self._get_reusable_set_data(metagame, gimmick, match_settings, team_sizes)
            pre_alteration_teams = self._make_pre_alteration_teams(
                metagame, gimmick, reusedData.sets)
        gevent.sleep(0.002)
        teams, public_teams = _make_gimmick_alterations(
            pre_alteration_teams, gimmick)
        return teams, public_teams


    def _get_reusable_set_data(self, metagame, gimmick, match_settings, team_sizes):
        """Fill teams with instantiated Pokemon sets.

        Args:
            metagame: MatchMetagame for the match.
            gimmick: MatchGimmick for the match.

        Returns: 2D list of Pokemon teams.
        """
        if not team_sizes:
            team_sizes_dict = match_settings.get_setting_value("team_sizes").copy()
            # Ensure doubles always has at least 2 pokemon per side- PBR crashes otherwise
            if 'doubles' in gimmick.base_ids:
                team_sizes_dict = {sizes: v for (sizes, v) in team_sizes_dict.items() if sizes[0] > 1 and sizes[1] > 1}
            # Don't pick dumb team size for randomorder and secrecy
            if any(m in gimmick.base_ids for m in ['random_order', 'secrecy']):
                team_sizes_dict.pop((1, 1), None)
            # Don't allow obvious traitor for traitor mode
            if 'traitor' in gimmick.base_ids:
                for i in range(1, 7):
                    team_sizes_dict.pop((1, i), None)
                    team_sizes_dict.pop((i, 1), None)
            if any(m in gimmick.base_ids for m in ['fog', 'letdown', 'sketchy']):
                for i in range(1, 7):
                    for j in range(4, 7):
                        team_sizes_dict.pop((i, j), None)
                        team_sizes_dict.pop((j, i), None)
            if any(m in gimmick.base_ids for m in ['rainbow', 'hit_and_run', 'boing']):
                for i in range(1, 7):
                    for j in range(5, 7):
                        team_sizes_dict.pop((i, j), None)
                        team_sizes_dict.pop((j, i), None)
            if 'clone' in gimmick.base_ids and gimmick.cloned_pokemon:
                if gimmick.cloned_pokemon.species_id in restricted_clone_ids_team_size_4:
                    for i in range(1, 7):
                        for j in range(5, 7):
                            team_sizes_dict.pop((i, j), None)
                            team_sizes_dict.pop((j, i), None)
                if gimmick.cloned_pokemon.species_id in restricted_clone_ids_team_size_3:
                    for i in range(1, 7):
                        for j in range(4, 7):
                            team_sizes_dict.pop((i, j), None)
                            team_sizes_dict.pop((j, i), None)
            # Pick the team sizes from the remaining options
            team_sizes = list(weighted_select(
                team_sizes_dict, raritygetter=lambda el, coll: coll[el]['rarity']))
            # Ensure autogenerated manvsmachine generates NvM where N < M
            if 'manvsmachine' in gimmick.base_ids and team_sizes[1] < team_sizes[0]:
                team_sizes[0], team_sizes[1] = team_sizes[1], team_sizes[0]
        set_collections = [[SetCollection([], [])] * team_sizes[0],
                           [SetCollection([], [])] * team_sizes[1]]
        tags_none = []
        tags_any = []
        tags_all = []

        if 'afflicted' in gimmick.base_ids:
            tags_none.append("species+Shedinja")

        if 'pokemon_theme' in gimmick.categories:
            tags_any = gimmick.categories['pokemon_theme'].tags_any
            tags_all = gimmick.categories['pokemon_theme'].tags_all

        num_pokemon = len(list(chain(*set_collections)))
        if not metagame.is_combo:
            set_tags = [metagame.set_tags[0]] * num_pokemon
        elif metagame.is_versus:
            set_tags = ([metagame.set_tags[0]] * len(set_collections[0]) +
                        [metagame.set_tags[1]] * len(set_collections[1]))
            tags_none.append('no-mixing')
        else:
            set_tags = minimal_reoccurrence_selections(metagame.set_tags, num_pokemon)
            tags_none.append('no-mixing')

        gevent.sleep(0.002)
        collections_by_set_tag = {}
        for t_ind, team in enumerate(set_collections):
            for p_ind, _ in enumerate(team):
                set_tag = set_tags.pop() # Get set tag for this pokemon.
                if set_tag not in collections_by_set_tag:
                    # Query db for all matching pokesets and store the result.
                    collection, metagame.versus_tags = self._get_pokeset_selections(
                        tags_none, tags_any, tags_all + [set_tag], metagame.rarify_shinies,
                        max(len(team) for team in set_collections), metagame.versus_tags)

                    set_collections[t_ind][p_ind] = collection
                    collections_by_set_tag[set_tag] = collection
                else:
                    # Reuse any pokeset selections already queried from the db.
                    set_collections[t_ind][p_ind] = collections_by_set_tag[set_tag]
        return set_collections

    def _make_pre_alteration_teams(self, metagame, gimmick, reusedData):
        """Fill teams with instantiated Pokemon sets.

        Args:
            metagame: MatchMetagame for the match.
            gimmick: MatchGimmick for the match.

        Returns: 2D list of Pokemon teams.
        """
        teams = [[None] * len(reusedData[0]), [None] * len(reusedData[1])]

        default_teams = deepcopy(metagame.primary_mode.default_teams)
        if default_teams:
            for t_ind, team in enumerate(default_teams):
                for p_ind, _ in enumerate(team):
                    species_id, setname = (
                        parse_pokeset(default_teams[t_ind][p_ind]))
                    pokeset = self._set_repository.get_by(
                        species_id=species_id, setname=setname)[0]['data']
                    default_teams[t_ind][p_ind] = pokecat.instantiate_pokeset(pokeset)
            return default_teams

        match_sets = []
        if metagame.versus_tags:
            taglist = metagame.versus_tags.copy()
            random.shuffle(taglist)
            versus_tags = [taglist.pop(), taglist.pop()]
        else:
            versus_tags = None
        for t_ind, team in enumerate(teams):
            team_sets = []
            for p_ind, _ in enumerate(team):
                reusedSetCollection = reusedData[t_ind][p_ind]
                shinies = reusedSetCollection.shinies
                nonshinies = reusedSetCollection.nonshinies
                tag = versus_tags[t_ind] if versus_tags else None
                pokeset = self._select_pokeset(
                    shinies, nonshinies, match_sets, team_sets, tag)
                teams[t_ind][p_ind] = pokeset
                if not metagame.allow_duplicate_pokesets:
                    match_sets.append(pokeset)
                if not metagame.allow_duplicate_team_species:
                    team_sets.append(pokeset)
        return teams

    def _select_pokeset_from_bid(
            self, pokeset_arg, species_id, setname,
            metagame, match_sets, team_sets):
        # Filter to Pokemon in the provided species_id / setname.
        pokesets = [p['data'] for p in self._set_repository.get_by(
            species_id=species_id, setname=setname)]
        if not pokesets:
            raise InvalidMatch("Setname does not exist for {}.".format(pokeset_arg))
        # Filter to Pokemon that are biddable.
        pokesets = [p for p in pokesets if p['biddable']]
        if not pokesets:
            if setname:
                raise InvalidMatch("{} is blacklisted from match bidding."
                                   .format(pokeset_arg))
            else:
                raise InvalidMatch("No biddable sets exist for {}".format(pokeset_arg))
        # Filter to Pokemon in the provided metagames.
        pokesets = [p for p in pokesets if any(
            tag in p['tags'] for tag in metagame.set_tags)]
        if not pokesets:
            raise InvalidMatch(
                "No biddable sets for {} exist in the requested metagames ({})."
                .format(pokeset_arg,
                        stringify_list(metagame.base_first_bid_aliases())))
        # Filter to Pokemon that are permitted in metagame mixing.
        if len(metagame.set_tags) > 1:
            pokesets = [p for p in pokesets if 'no-mixing' not in p['tags']]
        if not pokesets:
            raise InvalidMatch("{} is not permitted in metagame mixes."
                               .format(pokeset_arg))
        # Filter out sets already in the match.
        for pokeset in pokesets.copy():
            for match_pokeset in match_sets:
                if (pokeset['species']['id'] == match_pokeset['species']['id'] and
                    pokeset['setname'] == match_pokeset['setname']):
                    pokesets.remove(pokeset)
        if not pokesets:
            if setname:
                raise InvalidMatch("Pokéset {} may only appear once per match."
                                   .format(pokeset_arg))
            else:
                raise InvalidMatch("Pokésets may only appear once per match. There are not enough unique "
                                   "biddable pokésets for species {} to create this match."
                                   .format(pokeset_arg))
        # Filter out species already in the team.
        #team_species_ids = [s['species']['id'] for s in team_sets]
        #pokesets = [p for p in pokesets if p['species']['id'] not in team_species_ids]
        #if not pokesets:
        #    raise InvalidMatch("Pokémon species {} may only appear once per team."
        #                        .format(pokeset_arg))
        # Choose a random pokeset from the list of remaining sets.
        # pokeset = self._select_pokeset_from_list(pokesets, rarity=1)
        # Choose the first pokeset from the list of remaining sets.
        pokeset = pokecat.instantiate_pokeset(pokesets[0])
        return pokeset

    def _get_pokeset_selections(self, tags_none, tags_any, tags_all, rarify_shinies, team_size, versus_tags):
        """Select an instantiated pokeset, using random weights."""
        sets = self._set_repository.get_by(
            tags_none=tags_none, tags_any=tags_any, tags_all=tags_all)
        shinies = []
        nonshinies = []

        # Filter to sets with enough pokesets
        # Ex: filter out PWT-Brock if he has only 3 Pokemon and the team size is 4.
        if versus_tags and versus_tags[0] == 'pwt-custom':
            sets_by_tag = {}
            for set in sets:
                tags = set['data']['tags']
                if 'runmon' in tags:
                    trainer_tag = "setname+" + set['data']['setname']
                    sets_by_tag.setdefault(trainer_tag, []).append(set)
                elif 'in-game' in tags:
                    trainer_tags = list(filter(lambda tag: 'PWT' in tag, tags))
                    if trainer_tags:
                        sets_by_tag.setdefault(trainer_tags[0], []).append(set)
            versus_tags = []
            sets = []
            for tag, tag_sets in sets_by_tag.items():
                if len(tag_sets) >= team_size:
                    versus_tags.append(tag)
                    sets.extend(tag_sets)

        for pokeset in sets:
            if rarify_shinies and pokeset['data']['shiny']:
                shinies.append(pokeset)
            else:
                nonshinies.append(pokeset)
        return SetCollection(shinies, nonshinies), versus_tags

    def _select_pokeset(self, shinies, nonshinies, match_sets, team_sets, tag):
        """Select an instantiated pokeset, using random weights."""
        team_species_ids = [s['species']['id'] for s in team_sets]

        selectable_shinies = self._get_filtered_selection(shinies, match_sets, team_species_ids, tag)
        selectable_nonshinies = self._get_filtered_selection(nonshinies, match_sets, team_species_ids, tag)
        gevent.sleep(0.002)
        pokeset = None
        if random.random() < self._shiny_chance:
           pokeset = self._select_pokeset_from_list(selectable_shinies)
        if not pokeset:
           pokeset = self._select_pokeset_from_list(selectable_nonshinies)

        gevent.sleep(0.002)
        if not pokeset:
            log.warning("Could not find enough pokésets to create the match."
                        "\nshinies: {}\nnonshinies: {}\nMatch sets: {}\nTeam species ids: {}\nTag: {}"
                        .format(shinies, nonshinies, match_sets, team_species_ids, tag))
            raise InvalidMatch("Could not find enough pokésets to create the match. Try specifying a small team size, like 3v3.")
        return pokeset

    def _get_filtered_selection(self, pokesets, not_sets, not_species_ids, tag=None):
        sets = []
        for pokeset in pokesets:
            if any(pokeset['_id']['species'] == not_set['species']['id'] and
                   pokeset['_id']['setname'] == not_set['setname'] for
                   not_set in not_sets):
                continue
            if any(pokeset['_id']['species'] == not_sp for
                   not_sp in not_species_ids):
                continue
            if tag and tag not in pokeset['data']['tags']:
                continue
            sets.append(pokeset)
        return sets

    def _select_pokeset_from_list(self, dbpokesets, rarity=None):
        def raritygetter(el, coll):
            return max(
                rarity if rarity else el.get("effective_rarity", 0),
                0.0000000000001
            )
        pokeset = weighted_select(dbpokesets, raritygetter)
        if pokeset:
            return pokecat.instantiate_pokeset(deepcopy(pokeset['data']))
        return None


def _make_gimmick_alterations(pre_alteration_teams, gimmick):
    """Make teams with gimmick based alterations.

    Args:
        pre_alteration_teams: 2d list of teams.  Not altered.
        gimmick: The selected MatchGimmick.

    Returns: teams, public_teams
    """
    teams = deepcopy(pre_alteration_teams)
    team_sizes = (len(teams[0]), len(teams[1]))

    # Add field to preserved species, in case clone overwrites it.
    for pokeset in chain(*teams):
        pokeset['original_species'] = pokeset['species']

    num_pokemon = len(list(chain(*teams)))
    if 'species_replace' in gimmick.categories:
        category = gimmick.categories['species_replace']
        if gimmick.cloned_pokemon:
            pool = [category.finder(gimmick.cloned_pokemon.species_id)]
            form_id = gimmick.cloned_pokemon.form_id
        else:
            if any(size > 4 for size in team_sizes):
                restrictions = restricted_clone_names_team_size_4
            elif any(size > 3 for size in team_sizes):
                restrictions = restricted_clone_names_team_size_3
            else:
                restrictions = None
            pool = category.select_pool(restrictions)
            form_id = 0
        selections = minimal_reoccurrence_selections(pool, num_pokemon)
        for pokeset in chain(*teams):
            if pokeset['ability']['name'] == 'Wonder Guard':
                # Prevent things like "match clone spiritomb" that fish for Ubers Shedinja.
                pokeset['ability']['id'] = 0
                pokeset['ability']['name'] = None
                pokeset['ability']['description'] = ''
            pokeset['species'] = deepcopy(selections.pop(0))
            if (len(pool) == 1 and pool[0]['name'] == 'Unown' and
                    (not gimmick.cloned_pokemon or
                     not gimmick.cloned_pokemon.form_was_specified)):
                pokeset['form'] = random.randint(0, 27)
            else:
                pokeset['form'] = form_id
            if category.randomize_ivs:
                pokeset['ivs']['hp'] = random.randint(0, 31)
                pokeset['ivs']['atk'] = random.randint(0, 31)
                pokeset['ivs']['def'] = random.randint(0, 31)
                pokeset['ivs']['spA'] = random.randint(0, 31)
                pokeset['ivs']['spD'] = random.randint(0, 31)
                pokeset['ivs']['spe'] = random.randint(0, 31)
            if category.randomize_evs:
                pokeset['evs']['hp'] = random.randint(0, 255)
                pokeset['evs']['atk'] = random.randint(0, 255)
                pokeset['evs']['def'] = random.randint(0, 255)
                pokeset['evs']['spA'] = random.randint(0, 255)
                pokeset['evs']['spD'] = random.randint(0, 255)
                pokeset['evs']['spe'] = random.randint(0, 255)
            if category.shinify_chance:
                if random.random() < category.shinify_chance:
                    pokeset['shiny'] = True
            if category.randomize_happiness:
                pokeset['happiness'] = random.randint(0, 255)
            pokecat.recalculate_pokeset_stats(pokeset)
            legalize_gender(pokeset)
    if 'ability_replace' in gimmick.categories:
        category = gimmick.categories['ability_replace']
        selections = minimal_reoccurrence_selections(category.select_pool(), num_pokemon)
        for pokeset in chain(*teams):
            pokeset['ability'] = deepcopy(selections.pop(0))
    if 'move_replace' in gimmick.categories:
        category = gimmick.categories['move_replace']
        if not category.replace_all:
            selections = minimal_reoccurrence_selections(category.select_pool(), num_pokemon)
            for pokeset in chain(*teams):
                new_move = deepcopy(selections.pop(0))
                move_i = None
                for existing_move_i, move in enumerate(pokeset['moves']):
                    if move['id'] == new_move['id']:
                        move_i = existing_move_i
                # Replace a random move only if the Pokemon doesn't already
                # have this move.
                if move_i is None:
                    if len(pokeset['moves']) == 4:
                        move_i = random.randint(0, len(pokeset['moves']) - 1)
                    else:
                        move_i = len(pokeset['moves'])
                        pokeset['moves'].append({})

                    pokeset['moves'][move_i] = deepcopy(new_move)
                    # Must fill in some fields that normally get filled
                    # during set instantiation.
                    pokeset['moves'][move_i]['pp_ups'] = 0
                    pokeset['moves'][move_i]['displayname'] = (
                        pokeset['moves'][move_i]['name'])

                if category.pp: # Ex: Trump card should have 1pp.
                    pokeset['moves'][move_i]['pp'] = category.pp
        else:
            for pokeset in chain(*teams):
                selections = minimal_reoccurrence_selections(
                    category.select_pool(), 4)
                pokeset['moves'] = []
                for move_i in range(0, 4):
                    new_move = deepcopy(selections.pop(0))
                    pokeset['moves'].append(deepcopy(new_move))
                    # Must fill in some fields that normally get filled
                    # during set instantiation.
                    pokeset['moves'][move_i]['pp_ups'] = 0
                    pokeset['moves'][move_i]['displayname'] = (
                        pokeset['moves'][move_i]['name'])

                    if category.pp: # Ex: Trump card should have 1pp.
                        pokeset['moves'][move_i]['pp'] = category.pp

    # Item replace is applied after species replace, because
    # Clone assigns items only for certain species.
    if 'item_replace' in gimmick.categories:
        category = gimmick.categories['item_replace']
        if gimmick.cloned_pokemon:
            clone_item = gimmick.cloned_pokemon.item_name
        else:
            clone_item = None
        pool = [category.finder(clone_item)] if clone_item else category.select_pool()
        selections = minimal_reoccurrence_selections(pool, num_pokemon)
        for pokeset in chain(*teams):
            if gimmick.cloned_pokemon:
                clone_name = gimmick.cloned_pokemon.clone_name
            else:
                clone_name = pokeset['species']['name']
            applies_to_species = (
                not category.only_for_species or
                clone_name in category.only_for_species
            )
            if ((clone_item or applies_to_species) and
                    'keep-item' not in pokeset['tags']):
                pokeset['item'] = deepcopy(selections.pop(0))
    # Battle changes are applied here so that fragile move pp
    # doesn't get overwritten by move replacements.
    if 'battle_change' in gimmick.categories:
        category = gimmick.categories['battle_change']
        if 'defeatist' in category.tags:
            for pokeset in chain(*teams):
                for move in pokeset['moves']:
                    move['pp'] = 2
        if 'fragile' in category.tags:
            for pokeset in chain(*teams):
                for move in pokeset['moves']:
                    move['pp'] = 1
        if 'status_nv_random' in category.tags:
            # No frz as per pbr-dev vote
            nv_statuses = ['slp', 'psn', 'brn', 'par', 'tox']
            for team in teams:
                team_statuses = minimal_reoccurrence_selections(
                    nv_statuses, max(len(teams[0]), len(teams[1])))
                random.shuffle(team_statuses)
                for i, pokeset in enumerate(team):
                    status = team_statuses[i]
                    pokeset['status']['nonvolatile'][status] = get_random_status_value(status)

        # Important to do this after species replace, which may alter HP.
        if '80_perc_hp' in category.tags:
            for pokeset in chain(*teams):
                pokeset["curr_hp"] = math.ceil(pokeset['stats']['hp'] * .8)
        if '1_hp' in category.tags:
            for pokeset in chain(*teams):
                pokeset["curr_hp"] = 1

    for pokeset in chain(*teams):
        # Apply any necessary adjustments
        pokecat.apply_pokeset_form_adjustments(pokeset)
        pokecat.fix_moves(pokeset)

    # This deepcopy could be moved to an earlier point in this function
    # to hide the 'x_replace' effects from public view.
    public_teams = deepcopy(teams)

    for pokeset in chain(*public_teams):
        pokeset['status']['nonvolatile']['slp'] = bool(pokeset['status']['nonvolatile']['slp'] )

    if 'team_change' in gimmick.categories:
        category = gimmick.categories['team_change']
        if 'traitor' in category.tags:
            # For match 1,2,3/4,5,6 swap either 1 and 4, 2 and 5, or 3 and 6.
            index = random.randint(0, min(len(teams[0]), len(teams[1])) - 1)
            teams[0][index], teams[1][index] = (teams[1][index], teams[0][index])
        if 'random_order' in category.tags:
            temp_teams = []
            for t_ind, team in enumerate(teams):
                new_order = list(range(len(team)))
                random.shuffle(new_order)
                new_team = [team[p_ind] for p_ind in new_order]
                temp_teams.append(new_team)
            teams = temp_teams
        if 'secrecy' in category.tags:
            indices = [random.randint(0, len(team) - 1) for team in public_teams]
            for team, index in zip(public_teams, indices):
                pokeset = team[index]
                pokecat.redact_pokeset_data(pokeset)
        if 'blind_bet' in category.tags:
            for pokeset in chain(*public_teams):
                pokecat.redact_pokeset_data(pokeset)

    return teams, public_teams


def get_random_status_value(status):
    if status == 'slp':
        return random.randint(2, 5)
    elif status == 'psn':
        return True
    elif status == 'brn':
        return True
    elif status == 'frz':
        return True
    elif status == 'par':
        return True
    elif status == 'tox':
        return 1


def legalize_gender(pokeset):
    gender_ratios = pokeset['species']['gender_ratios']
    if not gender_ratios:
        pokeset['gender'] = None
    else:
        if pokeset['gender'] not in gender_ratios:
            pokeset['gender'] = weighted_select(gender_ratios)
