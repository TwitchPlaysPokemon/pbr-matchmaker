from .moderestrictions import ModeRestrictions
from . import selections
from .exceptions import InvalidMatch

import logging
from copy import deepcopy

log = logging.getLogger(__name__)


class ModeRarities:
    """Select mode ids based on rarities and known restrictions.

    Attributes:
        restrictions: ModeRestrictions object specifying restrictions that
            mode id selection must comply with.
        default_metagame_rarities: Store default rarities for metagame selection.
        default_gimmick_rarities: Store default rarities for gimmick selection.
        gimmick_rarities_by_metagame: Store rarities for gimmick selection
            specific to a preselected metagame.
        metagame_rarities_by_gimmick: Store rarities for metagame selection
            specific to a preselected gimmick.
    """
    def __init__(self, metagames, gimmicks, fake_modes, restrictions):
        """Fill rarity tables.

        Args:
            metagames: MetagameCollection containing AbstractMetagame descendants.
            gimmicks: GimmickCollection containing AbstractGimmick descendants.
            fake_modes: FakeModeCollection of FakeMode objects for displaying fake icons.
            restrictions: ModeRestrictions object with mode conflict data.
        """
        self.restrictions = restrictions
        self.fake_rarities = self._get_default_rarities(fake_modes)
        self.default_metagame_rarities = self._get_default_rarities(metagames)
        self.default_gimmick_rarities = self._get_default_rarities(gimmicks)
        self.gimmick_rarities_by_metagame = self._get_gimmick_rarities_by_metagame(
            metagames, gimmicks)
        self.optional_sub_rarities_by_gimmick = (
            self._get_optional_gimmick_sub_rarities(gimmicks))
        self.metagame_rarities_by_gimmick = self._get_metagame_rarities_by_gimmick()

    def select_mode_ids(self, amount, rarity_boost, allow_metagames,
                        allow_gimmicks, allow_fakes, allow_normal_gimmick):
        """Roll to select a certain amount of mode ids."""
        metagames = self.default_metagame_rarities if allow_metagames else {}
        gimmicks = self.default_gimmick_rarities if allow_gimmicks else {}
        fakes = self.fake_rarities if allow_fakes else {}
        available = {**metagames, **gimmicks, **fakes}

        for id in available:
            available[id] += rarity_boost

        # Prevent normal gimmick if necessary.
        if not allow_normal_gimmick:
            ModeRestrictions.zero_restricted(available, ['normal'])

        selected = []
        for _ in range(amount):
            selected.append(selections.weighted_select(available))
        return selected

    def select_metagame_id(self, g_primary_id=None, g_base_ids=None,
                           forbidden_ids=None):
        """Roll to select a compatible metagame id.

        Args:
            g_primary_id: Optional id of a preselected primary gimmick. If
                present, use metagame rarities specific to this primary gimmick.
            g_base_ids: Optional list of ids of preselected base gimmicks- the
                selected metagame must not be in conflict with these gimmicks.
            forbidden_ids: Optional list of ids forbidden from selection.

        Returns: A metagame id.
        """
        # Get rarities for available metagames.
        g_base_ids = g_base_ids if g_base_ids else []
        forbidden_ids = forbidden_ids if forbidden_ids else []

        preselected_ids = g_base_ids
        if g_primary_id:
            available = deepcopy(self.metagame_rarities_by_gimmick[g_primary_id])
            preselected_ids.append(g_primary_id)
        else:
            available = deepcopy(self.default_metagame_rarities)

        # Prevent selection of any forbidden or conflicting ids.
        self.restrictions.zero_restricted(available, forbidden_ids)
        self.restrictions.zero_automated_conflicts_with(available,
                                                        preselected_ids)

        # Select a random-weighted choice from the available metagames.
        result = selections.weighted_select(available)
        if not result:
            raise InvalidMatch("No valid metagames available. \ng_primary_id: "
                               "{}\ng_base_ids: {}\forbidden_ids: {}"
                               .format(g_primary_id, g_base_ids, forbidden_ids))
        return result

    def select_gimmick_id(self, eligible_ids=None, m_primary_id=None,
                          m_base_ids=None, g_primary_id=None,
                          g_base_ids=None, forbidden_ids=None):
        """Roll to select a compatible gimmick id.

        Args:
            eligible_ids: Optional list of gimmick ids eligible for selection.
            m_primary_id: Optional id of a preselected primary metagame. If
                present, use gimmick rarities specific to this primary metagame.
            m_base_ids: Optional list of ids of preselected base metagames- the
                selected gimmicks must not be in conflict with these metagames.
            g_primary_id: Optional id of a preselected primary gimmick.
            g_base_ids: Optional list of ids of preselected base gimmicks- the
                selected gimmicks must not be in conflict with these gimmicks.
            forbidden_ids: Optional list of gimmick ids forbidden from selection.

        Returns: A gimmick id.
        """
        m_base_ids = m_base_ids if m_base_ids else []
        g_base_ids = g_base_ids if g_base_ids else []

        all_conflict_ids = m_base_ids + g_base_ids

        # Get rarities for available gimmicks.
        if m_primary_id:
            available = deepcopy(self.gimmick_rarities_by_metagame[m_primary_id])
            all_conflict_ids.append(m_primary_id)
        else:
            available = deepcopy(self.default_gimmick_rarities)

        if g_primary_id:
            all_conflict_ids.append(g_primary_id)
            # Don't use gimmick rarities by metagame- the gimmick was already chosen.
            if g_primary_id in self.optional_sub_rarities_by_gimmick:
                # Optional sub rarities for this gimmick combo were specified.
                # Use those instead.
                available = deepcopy(
                    self.optional_sub_rarities_by_gimmick[g_primary_id])
            else:
                available = deepcopy(self.default_gimmick_rarities)

        # Prevent selection of any forbidden or conflicting ids.
        ModeRestrictions.zero_restricted(available, forbidden_ids, eligible_ids)
        self.restrictions.zero_automated_conflicts_with(available,
                                                        all_conflict_ids)

        # Select a random-weighted choice from the available gimmicks.
        result = selections.weighted_select(available)
        if not result:
            raise InvalidMatch(
                "No valid gimmicks available.\neligible_ids: {}\nm_primary_id:"
                " {}\nm_base_ids: {}\ng_primary_id: {}\ng_base_ids: {}"
                "\nforbidden_ids: {}"
                .format(eligible_ids, m_primary_id, m_base_ids, g_primary_id,
                        g_base_ids, forbidden_ids))
        return result

    def _get_default_rarities(self, modes):
        """Get default rarities for all modes in the ModeCollection.

        Args:
            repo: ModeCollection containing mode rarities.

        Returns: dict of rarities by id.
        """
        rarities = {}
        for id, mode in modes.all_modes.items():
            rarities[id] = mode.rarity
        return rarities

    def _get_metagame_rarities_by_gimmick(self):
        """Get metagame rarities for every gimmick.

        Constructed with gimmick_rarities_by_metagame and default rarities.

        Returns: The 2D dict
            {g1: {m1: rarity, m2: rarity, ...}, g2: {m1: rarity, ...}, ... }
            for all gimmick ids g* and metagame ids m*.
        """
        metagame_rarities_by_gimmick = {}
        for m_id, g_rarities in self.gimmick_rarities_by_metagame.items():
            m_default_rarity = self.default_metagame_rarities[m_id]
            for g_id, rarity in g_rarities.items():
                if g_id not in self.default_gimmick_rarities:
                    continue  # May occur if this gimmick isn't present in the event
                g_default_rarity = self.default_gimmick_rarities[g_id]
                if g_id not in metagame_rarities_by_gimmick:
                    metagame_rarities_by_gimmick[g_id] = {}

                if m_id in metagame_rarities_by_gimmick[g_id]:
                    raise ValueError('metagame_rarities_by_gimmick saw duplicate'
                                     'rarity entries for gimmick {} and metagame {}'
                                     '. This should be impossible.'
                                     .format(g_id, m_id))
                metagame_rarities_by_gimmick[g_id][m_id] = m_default_rarity * rarity
                if g_default_rarity:
                    metagame_rarities_by_gimmick[g_id][m_id] /= g_default_rarity

        return metagame_rarities_by_gimmick

    def _get_optional_gimmick_sub_rarities(self, gimmicks):
        """Get gimmick rarities for combo gimmicks."""
        # Create 2-dimensional dict with default rarities.
        sub_rarities_by_gimmick = {}
        default_rarities = self.default_gimmick_rarities
        for g_id, gimmick in gimmicks.combo_modes.items():
            specified_rarities = gimmick.sub_mode_rarities
            whitelist = gimmick.sub_mode_whitelist
            blacklist = gimmick.sub_mode_blacklist

            if not (specified_rarities or whitelist or blacklist):
                continue

            rarities = deepcopy(default_rarities)
            if specified_rarities:
                rarities = deepcopy(specified_rarities)
            if whitelist:
                rarities = {_id: rarity for _id, rarity in rarities.items()
                            if _id in whitelist}
            if blacklist:
                rarities = {_id: rarity for _id, rarity in rarities.items()
                            if _id not in blacklist}
            rarities.pop("normal", None)  # Not permitted in combos.

            sub_rarities_by_gimmick[g_id] = rarities
        return sub_rarities_by_gimmick

    def _get_gimmick_rarities_by_metagame(self, metagames, gimmicks):
        """Get metagame rarities for every gimmick.

        Args:
            metagames: MetagameCollection containing AbstractMetagame descendants.
            gimmicks: GimmickCollection containing AbstractGimmick descendants.

        Returns: The 2D dict
            {m1: {g1: rarity, g2: rarity, ...}, m2: {g1: rarity, ...}, ... }
            for all metagame ids m* and gimmick ids g*.
        """
        metagames = metagames.all_modes

        # Create 2-dimensional dict with default rarities.
        gimmick_rarities_by_metagame = {}
        for m_id, metagame in metagames.items():
            gimmick_rarities_by_metagame[m_id] = (
                deepcopy(self.default_gimmick_rarities))

        # Prevent conflicting modes under automated matchmaking restrictions.
        self.restrictions.zero_automated_conflicts(gimmick_rarities_by_metagame)

        # Apply metagame-specific rarity changes as per the config.
        for m_id, g_rarities in gimmick_rarities_by_metagame.items():
            metagame = metagames[m_id]
            # Prevent selection of gimmicks that are blacklisted or not whitelisted.
            whitelist = metagame.gimmick_rarity_whitelist
            blacklist = metagame.gimmick_rarity_blacklist
            ModeRestrictions.zero_restricted(g_rarities, blacklist, whitelist=whitelist)
            # Set manually specified rarities.
            for g_id, rarity in metagame.gimmick_rarities.items():
                if ((blacklist and g_id in blacklist) or
                    (whitelist and g_id not in whitelist)):
                    log.error('Metagame {} specifies a rarity for BaseGimmick {}, '
                              'but that gimmick is blacklisted or not whitelisted.'
                              .format(m_id, g_id, m_id))
                else:
                    g_rarities[g_id] = rarity
        return gimmick_rarities_by_metagame