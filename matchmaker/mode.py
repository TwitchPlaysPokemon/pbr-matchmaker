from .settings import MatchSettings
from . import selections
from .utils.stringutils import stringify_list

import logging
from collections import OrderedDict

log = logging.getLogger(__name__)

class AbstractMode:
    """A game mode, i.e. a metagame or gimmick.

    Attributes:
        id: Unique str identifier for the mode.
        rarity: float for automated matchmaking selections.
        match_settings: MatchSettings object with any non-default settings
            specific to the mode.
        display_name: str name for display.
        bid_aliases: list of str aliases for manual match creation.
        icon_id: str filename of icon_id image for the mode.
        description: str describing the mode.
    """
    def __init__(self, id, cfg):
        for field in ['description', 'display_name']:
            if field not in cfg:
                raise ValueError('BaseMode %s must have %s' % (id, field))
        self.id = id
        self.rarity = cfg.get('rarity', 0.0)
        match_settings = cfg.get('match_settings', {})
        self.match_settings = MatchSettings.from_config(match_settings)
        self.display_name = cfg['display_name']
        self.bid_aliases = cfg.get('bid_aliases', [])
        self.icon_id = cfg.get('icon_id', id)
        self.description = cfg['description']
        self.emoji = cfg.get('emoji')
        self.short_description = cfg.get('short_description', "")
        self.sub_mode_ids = cfg.get('sub_modes', [])
        self.sub_mode_rarities = cfg.get('sub_mode_rarities', {})
        self.sub_mode_whitelist = cfg.get('sub_mode_rarities_whitelist', [])
        self.sub_mode_blacklist = cfg.get('sub_mode_rarities_blacklist', [])
        self.biddable = cfg.get('biddable', True)
        self.cooldown = cfg.get('cooldown', 0)
        if cfg.get('equalize_rarities'):
            if self.rarity != 0:
                self.rarity = 1
            self.sub_mode_rarities = {
                k: 1.0 for k, v in self.sub_mode_rarities.items() if v != 0
            }


    def first_bid_alias(self):
        if len(self.bid_aliases):
            return self.bid_aliases[0]
        return None

    def first_bid_alias_or_id(self, add_emoji=False):
        first_bid_alias = self.first_bid_alias()
        result = first_bid_alias if first_bid_alias else self.id
        if add_emoji and self.emoji:
            result += ' ' + self.emoji
        return result

    def is_combo_for_ids(self, sub_ids):
        if '*' in self.sub_mode_ids:
            return len(self.sub_mode_ids) == len(sub_ids)
        return all([id in self.sub_mode_ids for id in sub_ids])


class BaseMode(AbstractMode):
    """A base or 'unit' mode. It does not reference any other modes."""
    def __init__(self, id, cfg):
        super().__init__(id, cfg)
        if 'sub_modes' in cfg or 'sub_mode_rarities' in cfg:
            raise ValueError('BaseMode %s must not have sub_mode_ids' % id)


class ComboMode(AbstractMode):
    """A mode that combines effects from several BaseMode objects.

    Attributes:
        sub_mode_ids: List of BaseMode ids in this combo.
    """
    def __init__(self, id, cfg):
        super().__init__(id, cfg)
        if 'sub_modes' not in cfg:
            raise ValueError('ComboMode %s must have sub_mode_ids' % id)


class FakeMode(BaseMode):
    def __init__(self, icon_id):
        id = 'fake_' + icon_id
        cfg = {'display_name': id,
               'description': '',
               'icon_id': icon_id}
        super().__init__(id, cfg)


class MatchMode:
    """Mode data specific to a particular match.

    A MatchMode is like an instantiation of a "primary" mode,
    which can be either a BaseMode or ComboMode.

    When a BaseMode b is selected:
        primary_mode = b
        base_modes = [b]

    When a ComboMode c is selected:
        primary_mode = c
        base_modes = [b1, b2, b3] where b1..b3
            are BaseMode objects in the combo.

    Attributes:
        primary_mode: AbstractMode of the primary mode.
        primary_id: str id of primary_mode.
        base_modes: All BaseMode objects involved in the mode.
        base_ids: list of ids of all base_modes.
        match_settings: MatchSettings object.
        display_name: str name for display.
        base_display_names: list of display_name attributes of all base_modes.
        icon_id: str filename of icon_id image for the mode.
        base_icon_ids: list of icon_id attributes of all base_modes.
        description: str describing the mode.
        base_emojis: list of emoji of all base_modes.
    """

    def __init__(self, primary_mode, base_modes, match_settings, description):
        self.primary_mode = primary_mode
        self.primary_id = self.primary_mode.id
        self.base_modes = base_modes
        self.base_ids = [mode.id for mode in self.base_modes]
        self.match_settings = match_settings
        self.display_name = self.primary_mode.display_name
        self.base_display_names = [mode.display_name for mode in self.base_modes]
        self.icon_id = self.primary_mode.icon_id
        self.base_icon_ids = [mode.icon_id for mode in self.base_modes]
        self.base_emojis = [mode.emoji for mode in self.base_modes]
        self.description = description
        self.base_short_descriptions = [mode.short_description for mode in self.base_modes]
        if (len(self.base_ids) == 0 or
            len(self.base_ids) == 1 and self.primary_id != self.base_ids[0]):
            raise ValueError("Invalid MatchMode. \nPrimary id: {} \nBase ids: {}"
                             .format(self.primary_id, self.base_ids))
        # Combo iff mode has >1 base_modes.
        self.is_combo = len(self.base_modes) > 1

    def base_first_bid_aliases(self):
        return [mode.first_bid_alias() for mode in self.base_modes]

    def base_first_bid_aliases_or_ids(self, add_emoji=False):
        return [mode.first_bid_alias_or_id(add_emoji=add_emoji) for mode in self.base_modes]

    def __str__(self):
        primary_display_name = self.primary_mode.display_name
        if not self.is_combo:
            return '{}'.format(primary_display_name)
        else:
            base_display_names = [mode.display_name for mode in self.base_modes]
            return '{} ({})'.format(primary_display_name,
                                    stringify_list(base_display_names))

    def __eq__(self, other):
        return self.primary_id == other.primary_id and self.base_ids == other.base_ids


class ModeCollection:
    """Store BaseMode objects.

    Attributes:
        base_modes: OrderedDict of BaseMode objects by id.
        combo_modes: OrderedDict of ComboMode objects by id.
        all_modes: OrderedDict of all AbstractMode objects by id.
    """

    def __init__(self, base_modes, combo_modes, content_name='mode'):
        self.content_name = content_name
        self.base_modes = base_modes
        self.combo_modes = combo_modes
        self.all_modes = {**base_modes, **combo_modes}

    def _get_bid_aliases_to_ids(self):
        """Return a mapping of bid_aliases to ids. Includes emoji as an alias."""
        bid_aliases = {}
        for id, mode in self.all_modes.items():
            for bid_alias in mode.bid_aliases:
                bid_aliases[bid_alias] = id
        for id, mode in self.base_modes.items():
            if mode.emoji:
                bid_aliases[mode.emoji] = id
        return bid_aliases

    def get_id_to_first_bid_alias(self):
        """Return a mapping of mode ids to the mode's first alias."""
        mapping = {}
        for id, mode in self.all_modes.items():
            first_alias = mode.first_bid_alias()
            if first_alias:
                mapping[id] = first_alias
        return mapping

    def get_mode(self, mode_name):
        if mode_name in self.all_modes:
            return self.all_modes[mode_name]
        else:
            return self.get_by_alias(mode_name)

    def get_by_alias(self, mode_name):
        mode_name = mode_name.lower()
        aliases_to_ids = self._get_bid_aliases_to_ids()
        if mode_name.lower() in aliases_to_ids:
            return self.all_modes[aliases_to_ids[mode_name]]
        else:
            return None

    def get_biddable_combo_for_modes(self, modes):
        ids = [mode.id for mode in modes]
        for mode in self.combo_modes.values():
            if mode.biddable and mode.is_combo_for_ids(ids):
                return mode
        return None


class FakeModeCollection(ModeCollection):
    def __init__(self, icon_ids):
        base_modes = OrderedDict()
        for icon_id in icon_ids:
            mode = FakeMode(icon_id)
            base_modes[mode.id] = mode
        all_modes = base_modes
        super().__init__(base_modes, all_modes)
