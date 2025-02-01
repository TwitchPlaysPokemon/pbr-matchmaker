from .exceptions import ModesConflict, InvalidMatch, TeamChoiceRestriction

import logging
from copy import deepcopy
from contextlib import suppress

log = logging.getLogger(__name__)


class ModeRestrictions:
    """Mode restrictions.

    Attributes:
        auto_pair_blacklists: dict of sets that specifies modes which cannot be combined
        in automated matchmaking.  All mode(metagame and gimmick) ids have an entry.
        Ex: {m1: set(m1, m4, ...), m2: set(m2, m3, m8, ...), ... }
        Symmetric- if mode ids m1 and m2 are pair blacklisted, then:
        (m2 in auto_pair_blacklists[m1]) == (m1 in auto_pair_blacklists[m2]) == True.
    """
    def __init__(self, metagames, gimmicks, id_to_first_alias, cfg):
        """

        Args:
            metagames: MetagameCollection containing AbstractMetagame descendants.
            gimmicks: GimmickCollection containing AbstractGimmick descendants.
            cfg:
        """
        self.metagames = metagames
        self.gimmicks = gimmicks
        self.id_to_first_alias = id_to_first_alias

        auto_cfg = cfg['automated_matchmaking']
        manual_cfg = cfg['token_matchmaking']
        all_cfg = cfg['automated_and_token_matchmaking']
        lifted_restrictions = cfg['lift_restrictions']

        # Apply lifted restrictions.  Currently only works with mode pair blacklists
        for restrictions_cfg in [auto_cfg, manual_cfg, all_cfg]:
            for lifted_restriction in lifted_restrictions:
                with suppress(ValueError):
                    restrictions_cfg['mode_pair_blacklists'].remove(lifted_restriction)

        # Blacklist normal gimmick with all other gimmicks.
        for g_id in gimmicks.base_modes:
            if g_id != 'normal':
                all_cfg['mode_pair_blacklists'].append(['normal', g_id])

        # Merge in shared config values.
        for k in all_cfg:
            for cfg_ in [auto_cfg, manual_cfg]:
                if k in cfg_:
                    cfg_[k] = cfg_[k] + all_cfg[k]

        # Set up basic pair blacklists.
        self.auto_pair_blacklists = self._get_self_pair_blacklists(
            metagames, gimmicks)
        self.manual_pair_blacklists = deepcopy(self.auto_pair_blacklists)

        # Manual matchmaking- account for whitelisted metagame mixes.
        # First disallow all metagame combinations.
        for i, m1 in enumerate(metagames.all_modes):
            for j, m2 in enumerate(metagames.all_modes):
                if i == j:
                    continue
                self.manual_pair_blacklists[m1].add(m2)
        # Then allow permitted combinations.
        for metagame in metagames.combo_modes.values():
            if metagame.biddable:
                sub_mode_ids = metagame.sub_mode_ids
                for i, m_id1 in enumerate(sub_mode_ids):
                    for j, m_id2 in enumerate(sub_mode_ids):
                        if i == j:
                            continue
                        if m_id1 in self.manual_pair_blacklists:
                            self.manual_pair_blacklists[m_id1].discard(m_id2)

        def _blacklist_pair(blacklists, mode1, mode2):
            if mode1 in blacklists and mode2 in blacklists:
                blacklists[mode1].add(mode2)
                blacklists[mode2].add(mode1)

        # Add pair blacklists from config.
        def add_pair_blacklists(blacklists, pairs):
            for pair in pairs:
                    if isinstance(pair[0], list):
                        for mode1 in pair[0]:
                            for mode2 in pair[1]:
                                _blacklist_pair(blacklists, mode1, mode2)
                    else:
                        _blacklist_pair(blacklists, pair[0], pair[1])

        add_pair_blacklists(self.auto_pair_blacklists,
                            auto_cfg['mode_pair_blacklists'])
        add_pair_blacklists(self.manual_pair_blacklists,
                            manual_cfg['mode_pair_blacklists'])

        # Add blacklists from gimmick category restrictions.
        self.auto_pair_blacklists = _get_pair_blacklist_merge(
            self.auto_pair_blacklists,
            self._get_gimmick_category_pair_blacklists(gimmicks))

        self.manual_pair_blacklists = _get_pair_blacklist_merge(
            self.manual_pair_blacklists,
            self._get_gimmick_category_pair_blacklists(gimmicks))

        self.team_choice_blacklist = manual_cfg['team_choice_blacklist']

        # Apply blacklists to combo modes.
        all_modes = {**metagames.all_modes, **gimmicks.all_modes}
        combo_modes = {**metagames.combo_modes, **gimmicks.combo_modes}
        for combo_mode in combo_modes.values():
            for sub_mode_id in combo_mode.sub_mode_ids:
                if sub_mode_id == "*":
                    continue    # Wildcard will automatically apply restrictions.
                for mode_id in all_modes:
                    for blacklists in [self.auto_pair_blacklists,
                                       self.manual_pair_blacklists]:
                        if sub_mode_id in blacklists[mode_id]:
                            if (combo_mode.id in metagames.all_modes and
                                    sub_mode_id in metagames.all_modes):
                                # No need to ban a metagame with another metagame.
                                continue
                            blacklists[combo_mode.id].add(mode_id)
                            blacklists[mode_id].add(combo_mode.id)


    def validate_auto(self, all_modes, m_primary_id, m_base_ids, g_primary_id, g_base_ids):
        """Raise exception if invalid modes are found.

        Args:
            modes: list of all mode ids.

        Raises:
            ModesConflict
            IneligibleMode
        """
        all_ids = list(set([m_primary_id] + [g_primary_id] + m_base_ids + g_base_ids))

        for i, m_id1 in enumerate(all_ids):
            for j, m_id2 in enumerate(all_ids):
                if i == j:
                    continue
                if m_id2 in self.auto_pair_blacklists[m_id1]:
                    alias1 = all_modes[m_id1].first_bid_alias()
                    alias2 = all_modes[m_id2].first_bid_alias()
                    raise ModesConflict(alias1, alias2)

    def validate_bid(self, m_base_ids, g_base_ids, cloned_pokemon=None,
                     teams_chosen=False):
        """Raise exception if invalid modes are found.

        Args:
            base_metagames: BaseMetagame objects in the match bid.
            base_gimmicks: BaseGimmicks objects in the match bid.
            teams_are_specified: bool indicating whether teams were specified.

        Raises:
            InvalidMatch
            ModesConflict
            TeamChoiceRestriction
        """
        # Check for blacklisted modes.
        all_ids = m_base_ids + g_base_ids

        # Check for mode pair conflicts.
        for i, m_id1 in enumerate(all_ids):
            for j, m_id2 in enumerate(all_ids):
                if i == j:
                    continue
                if m_id2 in self.manual_pair_blacklists[m_id1]:
                    raise ModesConflict(self.id_to_first_alias[m_id1],
                                        self.id_to_first_alias[m_id2])

        if teams_chosen:
            # Check special restrictions when teams are specified.
            for id in all_ids:
                if id in self.team_choice_blacklist:
                    # Teams are specified, but match contains a blacklisted mode.
                    raise TeamChoiceRestriction(self.id_to_first_alias[id])

        if cloned_pokemon:
            if len([g_id for g_id in g_base_ids
                    if g_id not in ('doubles', 'speed', 'inverse', 'spanish',
                                    'french', 'italian', 'german', 'japanese')]) > 2:
                raise InvalidMatch("When choosing the cloned Pokemon, you may choose at "
                                   "most one other gimmick (with the exception of "
                                   "doubles, speed, inverse, and language gimmicks).")

            conflicts = ('rainbow', 'hit_and_run', 'letdown', 'boing')
            for g_base_id in g_base_ids:
                if g_base_id in conflicts:
                    raise InvalidMatch('When choosing the cloned Pokemon, clone may not '
                                       'be combined with %s.' %
                                       self.id_to_first_alias[g_base_id])

    def zero_automated_conflicts(self, modes):
        """Set zero rarities for conflicting modes under automated matchmaking.

        Args:
            modes: 2D dict of modes.
        """
        for id1, modes2 in list(modes.items()):
            for id2 in list(modes2):
                if id2 in self.auto_pair_blacklists[id1]:
                    modes[id1][id2] = 0

    def zero_automated_conflicts_with(self, mode_rarities, preselected_ids):
        """Set zero rarities for conflicting modes under automated matchmaking.

        Args:
            mode_rarities: dict of {mode id: rarity}, which will be modified.
            preselected_ids: list of preselected mode ids for the match.

        Prevent `mode_rarities` from having a non-zero rarity for modes that
        conflict with any of the preselected modes.
        """
        for preselected_id in preselected_ids:
            # Get a list of ids that conflict with this preselected id.
            conflicting_ids = self.auto_pair_blacklists[preselected_id]
            # Prevent the conflicting ids from being selected.
            for id in conflicting_ids:
                if id in mode_rarities:
                    mode_rarities[id] = 0

    @staticmethod
    def zero_restricted(modes, blacklist=None, whitelist=None):
        """Set zero rarities for modes that are blacklisted or not whitelisted.

        Args:
            modes: dict of mode id: mode rarity.
            blacklist: Optional list of blacklisted modes ids.
            whitelist: Optional list of whitelisted modes ids.  Note the empty
                list is considered as equivalent to None.
        """
        for _id in list(modes):
            if (blacklist and _id in blacklist or
                    whitelist and _id not in whitelist):
                modes[_id] = 0

    def _get_self_pair_blacklists(self, metagames, gimmicks):
        """Return pair blacklists that blacklist modes with themselves."""
        all_mode_ids = list(metagames.all_modes) + list(gimmicks.all_modes)
        pair_blacklists = {id: {id} for id in all_mode_ids}
        return pair_blacklists

    def _get_gimmick_category_pair_blacklists(self, gimmicks):
        """Get pair blacklists for gimmick category restrictions."""
        g_base_modes = gimmicks.base_modes
        pair_blacklists = {id: set() for id in g_base_modes.keys()}
        for g1 in g_base_modes.values():
            for g2 in g_base_modes.values():
                if g1.conflicts_with(g2):
                    pair_blacklists[g1.id].add(g2.id)
                    pair_blacklists[g2.id].add(g1.id)
        return pair_blacklists


def _get_pair_blacklist_merge(pb1, pb2):
    """Merge two pair blacklists. Each is a dict of sets."""
    keys = set(pb1) | set(pb2)
    result = {}
    for k in keys:
        if k in pb1 and k in pb2:
            result[k] = pb1[k] | pb2[k]
        elif k in pb1:
            result[k] = pb1[k]
        else:
            result[k] = pb2[k]
    return result


