from .mode import AbstractMode, BaseMode, ComboMode, ModeCollection, MatchMode
from .settings import MatchSettings
from .utils.stringutils import stringify_list

import logging
from collections import OrderedDict

log = logging.getLogger(__name__)


class AbstractMetagame(AbstractMode):
    """A metagame mode."""
    def __init__(self, id, cfg):
        super().__init__(id, cfg)
        self.gimmick_rarities = cfg.get('gimmick_rarities', {})
        self.gimmick_rarity_whitelist = cfg.get('gimmick_rarity_whitelist', [])
        self.gimmick_rarity_blacklist = cfg.get('gimmick_rarity_blacklist', [])
        self.is_versus = False
        self.default_teams = cfg.get('default_teams', None)
        self.rarify_shinies = cfg.get('rarify_shinies', None)


class BaseMetagame(AbstractMetagame, BaseMode):
    """A base or 'unit' metagame. It does not reference any other metagames."""
    def __init__(self, id, cfg):
        super().__init__(id, cfg)
        if 'set_tag' not in cfg:
            raise ValueError("base_modes metagame {} must have set tag(s)\n"
                             .format(id))
        self.set_tags = [cfg['set_tag']]
        self.versus_tags = cfg.get('versus_tags', None)
        self.rarify_shinies = cfg.get('rarify_shinies', True)
        self.allow_duplicate_pokesets = cfg.get('allow_duplicate_pokesets', False)
        self.allow_duplicate_team_species = cfg.get('allow_duplicate_team_species', False)
    
    def make(self, base_metagames):
        """Make a MatchMetagame for a specific match."""
        if len(base_metagames) != 1 or base_metagames[0].id != self.id:
            raise ValueError("Basemetagame cannot reference other metagames")
        return MatchMetagame(
            self, [self], self.match_settings, self.description, self.set_tags,
            versus_tags=self.versus_tags, rarify_shinies=self.rarify_shinies,
            allow_duplicate_pokesets=self.allow_duplicate_pokesets,
            allow_duplicate_team_species=self.allow_duplicate_team_species)


class ComboMetagame(AbstractMetagame, ComboMode):
    """A metagame that combines effects from several BaseMetagame objects."""
    def __init__(self, id, cfg):
        super().__init__(id, cfg)

    def _generate_description(self, display_names):
        raise NotImplementedError

    def make(self, base_metagames):
        """Make a MatchMetagame for a specific match.

        Args:
            base_metagames: BaseMetagame objects to include in the match.
        """
        # Generate description.
        display_names = [m.display_name for m in base_metagames]
        description = self._generate_description(display_names)

        # Combine non-default match settings.
        all_match_settings = ([m.match_settings for m in base_metagames] +
                              [self.match_settings])
        match_settings = MatchSettings.from_merge(all_match_settings)

        # Combine the set tags.
        set_tags = sum([m.set_tags for m in base_metagames], [])

        if self.rarify_shinies is None:
            self.rarify_shinies = all(metagame.rarify_shinies for metagame in base_metagames)

        return MatchMetagame(self, base_metagames, match_settings,
                             description, set_tags, is_versus=self.is_versus,
                             rarify_shinies=self.rarify_shinies)


class VersusComboMetagame(ComboMetagame):
    """Selects two BaseMetagame objects in a match- one for each team."""
    def __init__(self, id, cfg):
        super().__init__(id, cfg)
        self.is_versus = True

    def _generate_description(self, display_names):
        return (self.description if self.description else
                "It's a showdown between Pokémon from"
                " the {} and {} metagames."
                .format(display_names[0], display_names[1]))

    def is_combo_for_ids(self, sub_ids):
        return False


class RandomComboMetagame(ComboMetagame):
    """A metagame that combines several BaseMetagame objects in the match."""
    def __init__(self, id, cfg):
        super().__init__(id, cfg)

    def _generate_description(self, display_names):
        return (self.description if self.description else
                "Metagames in this match are {}."
                .format(stringify_list(display_names)))


class MetagameCollection(ModeCollection):
    """Store AbstractMetagame descendants.

    Attributes:
        versus_combos: dict of VersusComboMetagame objects by id.
        random_combos: dict of RandomComboMetagame objects by id.
    """

    def __init__(self, cfg):
        base_modes = OrderedDict()
        combo_modes = OrderedDict()
        ids = set()

        for type, metagames in cfg['metagames'].items():
            for id, metagame in metagames.items():
                if metagame.get('disabled', False):
                    continue  # Explicitly disabled mode.
                elif id not in cfg['event']['metagames'].get(type, []):
                    continue  # Mode not present in this event; treat as disabled.

                # Debugging feature
                metagame['equalize_rarities'] = cfg.get('equalize_rarities', False)

                # Adjust gimmick whitelist/rarities when `must_contain` gimmicks are present
                adjust_ids_for_must_contain_gimmicks(metagame, cfg)

                if type == 'base':
                    base_modes[id] = BaseMetagame(id, metagame)
                elif type == 'versus_mixes':
                    combo_modes[id] = VersusComboMetagame(id, metagame)
                elif type == 'random_mixes':
                    combo_modes[id] = RandomComboMetagame(id, metagame)
                else:
                    raise ValueError("Unrecognized metagame mix type: {}".format(type))
                if id in ids:
                    # Ensure there are no duplicate ids.
                    raise ValueError("Duplicate metagames with name {}".format(type))
                ids.add(id)
        super().__init__(base_modes, combo_modes, 'metagame')

    def is_versus(self, id):
        return self.all_modes[id].is_versus


def adjust_ids_for_must_contain_gimmicks(metagame, cfg):
    """Update metagame 'gimmick rarity' fields with id modifications done when `must_contain` gimmicks are present.

    The id modifications are performed in gimmick.py.
    """
    must_contain_gimmicks_all = [id_ for id_ in cfg['must_contain_all_gimmicks'] if
                                 id_ in cfg['gimmicks']['base']]
    must_contain_gimmicks_any = [id_ for id_ in cfg['must_contain_any_gimmicks'] if
                                 id_ in cfg['gimmicks']['base']]

    if must_contain_gimmicks_any:
        gimmicks_to_add_permutations = [must_contain_gimmicks_all + [gimmick_any]
                                        for gimmick_any in must_contain_gimmicks_any]
    elif must_contain_gimmicks_all:
        gimmicks_to_add_permutations = [must_contain_gimmicks_all]
    else:
        gimmicks_to_add_permutations = []

    def get_id_replacements(ids):
        id_replacements = {}
        for id in ids:
            if any([id] == perm for perm in gimmicks_to_add_permutations):
                continue
            for gimmicks_to_add in gimmicks_to_add_permutations:
                id_replacements.setdefault(id, [])
                id_replacements[id].append(id + "+" + "+".join(gimmicks_to_add) + "_autogenerated")
        return id_replacements

    if must_contain_gimmicks_any or must_contain_gimmicks_all:
        if 'gimmick_rarity_whitelist' in metagame:
            whitelist = metagame['gimmick_rarity_whitelist']
            for id, replacement_ids in get_id_replacements(whitelist).items():
                whitelist.remove(id)
                whitelist.extend(replacement_ids)
        if 'gimmick_rarities' in metagame:
            rarities = metagame['gimmick_rarities']
            for id, replacement_ids in get_id_replacements(rarities.keys()).items():
                value = rarities[id]
                del rarities[id]
                for replacement_id in replacement_ids:
                    rarities[replacement_id] = value


class MatchMetagame(MatchMode):
    """Metagame data specific to a particular match.

    A MatchMetagame is like an instantiation of a "primary" metagame,
    which can be either a BaseMetagame or ComboMetagame.

    Ex: If the class_warfare metagame is selected, the resulting
    MatchMetagame might have these attributes:
    primary_mode = class_warfare metagame
    base_modes = list containing: simple metagame and runmons metagame

    Attributes:
        set_tags: list of set tags for all the metagames in the match.
        is_versus: bool indicating whether to assign one metagame to each team.
    """
    def __init__(self, base_metagame, single_metagames, match_settings,
                 description, set_tags, is_versus=False, versus_tags=None,
                 rarify_shinies=True, allow_duplicate_pokesets=False,
                 allow_duplicate_team_species=False):
        super().__init__(base_metagame, single_metagames, match_settings,
                         description)
        self.set_tags = set_tags
        self.is_versus = is_versus
        self.versus_tags = versus_tags
        self.rarify_shinies = rarify_shinies
        self.allow_duplicate_pokesets = allow_duplicate_pokesets
        self.allow_duplicate_team_species = allow_duplicate_team_species