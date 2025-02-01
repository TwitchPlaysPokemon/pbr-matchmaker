from .exceptions import InvalidMatch, ModeNotExisting, IneligibleMode, ModeCoolingDown
from .mode import FakeModeCollection
from .metagame import MetagameCollection
from .gimmick import GimmickCollection, ClonedPokemon
from .moderestrictions import ModeRestrictions
from .moderarities import ModeRarities

import random, logging


log = logging.getLogger(__name__)


class MatchModeMaker:
    """Make instances of a MatchMode (MatchMetagame or MatchGimmick).

    Attributes:
        metagames: MetagameCollection containing AbstractMetagame descendants.
        gimmicks: GimmickCollection containing AbstractGimmick descendants.
        fake_modes: FakeModeCollection of FakeMode objects for displaying fake icons.
        restrictions: ModeRestrictions object.
        rarities: ModeRarities for mode id selection.
    """
    def __init__(self, cfg, game_id):
        self._cfg = cfg
        self.metagames = MetagameCollection(cfg)
        self.gimmicks = GimmickCollection(cfg)
        self.id_to_first_alias = {**self.metagames.get_id_to_first_bid_alias(),
                                  **self.gimmicks.get_id_to_first_bid_alias(),
                                  }
        self.fake_modes = FakeModeCollection(cfg['fake_mode_icon_ids'])
        self._validate_mode_collections()
        self.restrictions = ModeRestrictions(self.metagames, self.gimmicks,
                                             self.id_to_first_alias,
                                             cfg['restrictions'])
        self.rarities = ModeRarities(self.metagames, self.gimmicks,
                                     self.fake_modes, self.restrictions)

    def _validate_mode_collections(self):
        """Check for duplicate ids and bid_aliases."""
        all_ids = set()
        all_aliases = set()
        ids_by_emoji = {}
        mode_collections = [self.metagames, self.gimmicks, self.fake_modes]
        for mode_collection in mode_collections:
            for id in mode_collection.all_modes:
                if id in all_ids:
                    raise ValueError("Duplicate mode id: %s" % id)
                all_ids.add(id)
                mode = mode_collection.all_modes[id]
                for alias in mode.bid_aliases:
                    if alias in all_aliases:
                        raise ValueError("Duplicate mode alias for id {}: {}"
                                         .format(id, alias))
                    all_aliases.add(alias)
            for id in mode_collection.base_modes:
                mode = mode_collection.all_modes[id]
                if mode.emoji:
                    if mode.emoji in ids_by_emoji:
                        raise ValueError("Duplicate mode emoji {} for ids {} and {}"
                                         .format(mode.emoji, id, ids_by_emoji[mode.emoji]))
                    ids_by_emoji[mode.emoji] = id

        if self._cfg['default_metagame'] not in self.metagames.base_modes:
            raise ValueError('The default metagame `{}` is not present in this event,'
                             'or does not exist.'.format(self._cfg['default_metagame']))
        if self._cfg['default_gimmick'] not in self.gimmicks.base_modes:
            raise ValueError('The default gimmick `{}` is not present in this event,'
                             'or does not exist.'.format(self._cfg['default_gimmick']))

    def make_from_bid(self, mode_args, teams_are_specified, cooldowns, ally_hit):
        """Try to make modes from manually provided arguments.

        Args:
            mode_args: List of mode arguments in the bid.
            teams_are_specified: bool indicating whether teams were specified.

        Bids may only request BaseMode modes.
        Allowing ComboMode modes is possible, but quite complex to implement
        and possibly problematic in several ways.

        Returns: MatchMetagame, MatchGimmick
        """
        metagames = []
        gimmicks = []
        cloned_pokemon = None
        switching_is_requested = False
        if mode_args:
            for arg in mode_args:
                possible_metagame = self.metagames.get_by_alias(arg)
                possible_gimmick = self.gimmicks.get_by_alias(arg)
                possible_cloned_pokemon = ClonedPokemon.parse_cloned_pokemon(arg)
                possible_mode = possible_metagame or possible_gimmick
                if possible_mode:
                    if not possible_mode.biddable:
                        raise IneligibleMode(possible_mode.first_bid_alias_or_id())
                if possible_metagame:  # arg specifies a metagame
                    if possible_metagame not in metagames:
                        metagames.append(possible_metagame)
                    # else already appended, eg "advanced advanced". Just ignore
                elif possible_gimmick:  # arg specifies a gimmick
                    if possible_gimmick not in gimmicks:
                        gimmicks.append(possible_gimmick)
                    # else already appended, eg "defiance defiance". Just ignore
                elif arg == 'switch' or arg == 'switching':
                    switching_is_requested = True
                elif possible_cloned_pokemon:
                    cloned_pokemon = possible_cloned_pokemon
                    continue
                else:
                    raise ModeNotExisting(arg)

        primary_metagame, base_metagames = self._split_modes(
            metagames, self.metagames, self._cfg['default_metagame'])
        primary_gimmick, base_gimmicks = self._split_modes(
            gimmicks, self.gimmicks, self._cfg['default_gimmick'])

        for base_mode in base_metagames + base_gimmicks:
            if base_mode.id in cooldowns:
                raise ModeCoolingDown(base_mode.first_bid_alias_or_id(),
                                      cooldowns[base_mode.id])

        base_metagames = _get_sorted_sublist(
            base_metagames, self.metagames.base_modes.values())
        base_gimmicks = _get_sorted_sublist(
            base_gimmicks, self.gimmicks.base_modes.values())

        m_base_ids = [mode.id for mode in base_metagames]
        g_base_ids = [mode.id for mode in base_gimmicks]

        if len(m_base_ids) > self._cfg['max_metagames']:
            raise InvalidMatch("You may request at most %d metagames." % self._cfg['max_metagames'])
        if len(g_base_ids) > self._cfg['max_gimmicks']:
            raise InvalidMatch("You may request at most %d gimmicks." % self._cfg['max_gimmicks'])

        self.restrictions.validate_bid(m_base_ids, g_base_ids, cloned_pokemon,
                                       teams_are_specified)

        mandatory_modes_all = self._cfg['must_contain_all_gimmicks']
        if mandatory_modes_all and not all(mode in g_base_ids for mode in mandatory_modes_all):
            raise InvalidMatch("Match must include all of these gimmicks: {}."
                               .format(", ".join([self.id_to_first_alias[mode_id] for mode_id in mandatory_modes_all])))

        mandatory_modes_any = self._cfg['must_contain_any_gimmicks']
        if mandatory_modes_any and not any(mode in g_base_ids for mode in mandatory_modes_any):
            raise InvalidMatch("Match must include at least one of these gimmicks: {}."
                               .format(", ".join([self.id_to_first_alias[mode_id] for mode_id in mandatory_modes_any])))

        if ally_hit is not None and ('defiance' not in g_base_ids or 'doubles' not in g_base_ids):
            raise InvalidMatch("Ally target % must be accompanied by doubles and defiance.")

        # If a match bid is invalid, InvalidMatch() will usually
        # be raised by validate_bid above with a more helpful
        # error message.
        if not primary_metagame:
            raise InvalidMatch('Those metagames may not be combined.')
        elif not primary_gimmick:
            raise InvalidMatch('Those gimmicks may not be combined. '
                               'You may combine only up to 5 gimmicks.')

        if cloned_pokemon:
            _validate_clone(cloned_pokemon, base_gimmicks)

        match_metagame = primary_metagame.make(base_metagames)
        match_gimmick = primary_gimmick.make(
            base_gimmicks, cloned_pokemon, switching_is_requested)

        return match_metagame, match_gimmick

    def select_mode_icon_ids(self, amount, rarity_boost, allow_metagames,
                          allow_gimmicks, allow_fakes, allow_normal_gimmick):
        mode_ids = self.rarities.select_mode_ids(
            amount, rarity_boost, allow_metagames,
            allow_gimmicks, allow_fakes, allow_normal_gimmick)
        icon_ids = []
        all_modes = {**self.metagames.all_modes,
                     **self.gimmicks.all_modes,
                     **self.fake_modes.all_modes}
        for mode_id in mode_ids:
            icon_ids.append(all_modes[mode_id].icon_id)
        return icon_ids

    def get_mode_cooldown(self, mode_id):
        if mode_id == "_uneventeams":
            return self._cfg.get('uneven_teams_cooldown', 0)
        if mode_id == "_largeteams":
            return self._cfg.get('large_teams_cooldown', 0)
        all_modes = {**self.metagames.all_modes,
                     **self.gimmicks.all_modes}
        if mode_id not in all_modes:
            log.error("Cooldown requested for mode %s, which was not found")
        return all_modes[mode_id].cooldown if mode_id in all_modes else 0

    def get_all_icon_ids(self):
        all_modes = {**self.metagames.all_modes,
                     **self.gimmicks.all_modes,
                     **self.fake_modes.all_modes}.values()
        return [mode.icon_id for mode in all_modes]

    def get_mode_info_by_alias(self):
        result = {}
        for category, modes in [("metagame", self.metagames.base_modes.values()),
                                ("gimmick", self.gimmicks.base_modes.values())]:
            for mode in modes:
                info = {
                    "description": mode.description,
                    "display_name": mode.display_name,
                    "bid_alias": mode.first_bid_alias_or_id(add_emoji=True),
                    "category": category,
                }
                for alias in mode.bid_aliases:
                    result[alias] = info
                if mode.emoji:
                    result[mode.emoji] = info
        return result

    def get_biddable_modes(self):
        """Get bid_aliases for biddable modes.

        Returns: (list of metagames, list of gimmicks)
        """
        metagames = []
        gimmicks = []
        for metagame in self.metagames.base_modes.values():
            first_bid_alias = metagame.first_bid_alias()
            if first_bid_alias and metagame.biddable:
                metagames.append(metagame)

        for gimmick in self.gimmicks.base_modes.values():
            first_bid_alias = gimmick.first_bid_alias()
            if first_bid_alias and gimmick.id != 'normal' and gimmick.biddable:
                gimmicks.append(gimmick)

        return metagames, gimmicks

    def make_metagame(self, match_gimmick=None, forbidden_ids=None):
        """Make a MatchMetagame for the match.

        Args:
            match_gimmick: An optional prechosen MatchGimmick for the match.
                Gimmicks effectively specify different rarities for metagame
                selection. In addition, the returned MatchMetagame must be
                compatible with the prechosen MatchGimmick (eg, should not
                violate pair blacklists).
            forbidden_ids: Optional list of mode ids that shouldn't be selected.

        Returns: A MatchMetagame.
        """
        g_primary_id = match_gimmick.primary_id if match_gimmick else None
        g_base_ids = match_gimmick.base_ids if match_gimmick else []
        forbidden_ids = forbidden_ids if forbidden_ids else []

        m_primary_id = self.rarities.select_metagame_id(
            g_primary_id, g_base_ids, forbidden_ids)
        primary_metagame = self.metagames.get_mode(m_primary_id)
        if not primary_metagame:
            raise ValueError("The `%s` gimmick was selected, but it isn't present in "
                             "the event." % m_primary_id)
        if primary_metagame.sub_mode_ids:  # Combo mode
            combo_ids = primary_metagame.sub_mode_ids
            m_base_ids = self._select_metagame_base_ids(
                m_primary_id, combo_ids, g_primary_id, g_base_ids,
                forbidden_ids)
        else:  # Base mode
            m_base_ids = [m_primary_id]
        base_metagames = [self.metagames.get_mode(id) for id in m_base_ids]
        return primary_metagame.make(base_metagames)

    def make_rotation_gimmick(self, forbidden_ids=None):
        """Make a MatchGimmick for the Splatoon rotation."""
        return self.make_gimmick(forbidden_ids=forbidden_ids)

    def make_normal_gimmick(self):
        normal_gimmick = self.gimmicks.get_mode('normal')
        return normal_gimmick.make([normal_gimmick])

    def make_gimmick(self, match_metagame=None, forbidden_ids=None):
        """Make a MatchGimmick for the match.

        Args:
            match_metagame: An optional prechosen MatchMetagame for the match.
                Metagames effectively specify different rarities for gimmick
                selection.  In addition, the returned MatchGimmick must be
                compatible with the prechosen MatchMetagame (eg, should not
                violate pair blacklists).
            forbidden_ids: Optional list of mode ids that shouldn't be selected.

        Returns: A MatchGimmick.
        """
        m_primary_id = match_metagame.primary_id if match_metagame else None
        m_base_ids = match_metagame.base_ids if match_metagame else []
        forbidden_ids = forbidden_ids if forbidden_ids else []

        g_primary_id = self.rarities.select_gimmick_id(
            m_primary_id=m_primary_id,
            m_base_ids=m_base_ids,
            forbidden_ids=forbidden_ids)
        primary_gimmick = self.gimmicks.get_mode(g_primary_id)
        # print(primary_gimmick is None)
        # if primary_gimmick is None:
        #     pass
        if not primary_gimmick:
            raise ValueError("The `%s` gimmick was selected, but it isn't present in "
                             "the event." % g_primary_id)
        if primary_gimmick.sub_mode_ids:  # Combo
            combo_ids = primary_gimmick.sub_mode_ids
            g_base_ids = self._select_gimmick_base_ids(
                g_primary_id, combo_ids, m_primary_id, m_base_ids,
                forbidden_ids)
        else:  # Not a combo
            g_base_ids = [g_primary_id]
        base_gimmicks = [self.gimmicks.get_mode(id) for id in g_base_ids]

        return primary_gimmick.make(base_gimmicks)

    def _select_metagame_base_ids(self, m_primary_id, combo_ids,
                                  g_primary_id, g_base_ids, forbidden_ids):
        """Select base_ids for the ComboMode specified by m_primary_id.

        Ex: VersusMixMetagames specify a list of eligible metagame ids (combo_ids),
        and that it should be composed of 2 of these metagames (one for each team).
        This function selects which 2 metagames to use.

        Currently a much simpler procedure compared to gimmicks.

        Args:
            m_primary_id: Primary id of a ComboMode.
            combo_ids: list of metagame ids that are eligible for selection.
            g_primary_id: Primary id for a prechosen MatchGimmick.
            g_base_ids: Base ids for a prechosen MatchGimmick.
            forbidden_ids: List of mode ids that should not be selected.

        Returns: list of metagame ids.
        """
        combo_ids = [id for id in combo_ids if id not in forbidden_ids]
        if len(combo_ids) < 2:
            raise InvalidMatch("Combo mode {} had <2 valid combo ids ({})"
                               .format(m_primary_id, combo_ids))
        if self.metagames.is_versus(m_primary_id):
            combo_ids = random.sample(combo_ids, 2)
        m_base_ids = _get_sorted_sublist(combo_ids, self.metagames.base_modes)
        return m_base_ids

    def _select_gimmick_base_ids(self, g_primary_id, combo_ids,
                                 m_primary_id, m_base_ids, forbidden_ids):
        """Select base_ids for the ComboMode specified by g_primary_id.

        Ex: A RandomComboGimmick may specify that it is composed of 3 gimmicks.
        This function selects which 3 gimmicks to use.

        Args:
            g_primary_id: Primary id of a ComboMode.
            combo_ids: List of base gimmick ids to be in the combo (may be
                wildcard).
            m_primary_id: Primary id for a prechosen MatchMetagame.
            m_base_ids: Base ids for a prechosen MatchMetagame.
            forbidden_ids: List of mode ids that should not be selected.

        Returns: list of gimmick ids.
        """
        g_base_ids = []

        # Select composition ids, if necessary.
        for id in combo_ids:
            if id in self.gimmicks.base_modes:
                if id in forbidden_ids:
                    raise InvalidMatch(
                        "Primary gimmick {} specifies base gimmick {}, which is"
                        " in the forbidden ids list.".format(g_primary_id, id))
                selected_id = id
            elif id == '*':  # wildcard, choose any valid base gimmick id
                eligible_ids = list(self.gimmicks.base_modes)
                # Disallow the normal gimmick, it shouldn't be in a combo.
                forbidden_ids = forbidden_ids + ['normal']
                selected_id = self.rarities.select_gimmick_id(
                    eligible_ids=eligible_ids,
                    m_primary_id=m_primary_id,
                    m_base_ids=m_base_ids,
                    g_primary_id=g_primary_id,
                    g_base_ids = g_base_ids,
                    forbidden_ids=forbidden_ids,
                )
            else:
                raise ValueError('Didn\'t recognize id: %s' % id)
            g_base_ids.append(selected_id)
        sorted_base_ids = _get_sorted_sublist(g_base_ids, self.gimmicks.base_modes)
        return sorted_base_ids

    def _split_modes(self, modes, mode_collection, default_mode_id):
        """Splits a list of modes into one primary mode and a list of base modes"""
        if (len(modes) == 1 and
                modes[0].id in mode_collection.combo_modes):
            # Player requested one combo mode.
            primary_mode = modes[0]
            base_modes = [mode_collection.get_mode(id) for id in
                          modes[0].sub_mode_ids]
        else:
            for mode in modes:
                if mode.id not in mode_collection.base_modes:
                    # Player requested a combo mode alongside some other modes.
                    # Ex: "luckmons metronome simple"
                    # This is not supported.
                    raise InvalidMatch('{} may not be combined with other {}s.'
                                       .format(mode.first_bid_alias(),
                                               mode_collection.content_name))
            if not modes:
                # Assign the default mode.
                default_mode = mode_collection.get_mode(default_mode_id)
                primary_mode = default_mode
                base_modes = [default_mode]
            elif len(modes) == 1:
                # Assign the requested mode.
                primary_mode = modes[0]
                base_modes = [modes[0]]
            else:
                # Assign the appropriate combo for the requested modes.
                # Assigns None if a combo could not be found.
                primary_mode = mode_collection.get_biddable_combo_for_modes(modes)
                base_modes = modes
        return primary_mode, base_modes


def _validate_clone(cloned_pokemon, base_gimmicks):
    # Bidder chose a specific pokemon to clone
    clone_gimmick = None
    for gimmick in base_gimmicks:
        if gimmick.id == 'clone':
            clone_gimmick = gimmick
    if not clone_gimmick:
        raise InvalidMatch('Clone Pokémon found in modes, but '
                           'Clone was not requested.')
    else:
        category = clone_gimmick.get_category('species_replace')
        if not category.pool_contains(cloned_pokemon.species_name):
            raise InvalidMatch('{} may not be cloned.'
                               .format(cloned_pokemon.species_name))


def _get_sorted_sublist(sub_list, sorted_list):
    """Get sorted list of items according to a presorted list.

    Args:
        sub_list: Unsorted collection of items, each of which is in sorted_list.
        sorted_list: Ordered collection of items.

    Returns: Sorted list of items.
    """
    for item in sub_list:
        if item not in sorted_list:
            raise ValueError('{} was not found in provided sorted list'.format(item))
    result = []
    for item in sorted_list:
        if item in sub_list:
            result.append(item)
    return result
