from .mode import AbstractMode, BaseMode, ComboMode, ModeCollection, MatchMode
from .settings import MatchSettings
from .utils.stringutils import stringify_list
from .exceptions import InvalidMatch
from . import parsing

import pokecat
import random, logging
from copy import deepcopy
from collections import OrderedDict

log = logging.getLogger(__name__)


class AbstractGimmick(AbstractMode):
    """A gimmick mode."""

    def __init__(self, id, cfg):
        # Ensure cfg has rarity for all modes except the 'normal' mode.
        if id == 'normal':
            if 'rarity' in cfg:
                raise ValueError('Rarity cannot be assigned to the normal gimmick.'
                                 'Set default_gimmick_chance instead.')
        super().__init__(id, cfg)

        # Add categories automatically.
        self.categories = {}
        for k, cl in CATEGORIES.items():
            if k in cfg:
                self.categories[k] = cl(k, cfg[k])

    def conflicts_with(self, other_gimmick):
        for category_id in CATEGORIES.keys():
            if (category_id in self.categories and
                    category_id in other_gimmick.categories and
                    category_id not in ['battle_change', 'team_change']):
                return True
        return False

    def get_category(self, name):
        if name in self.categories:
            return self.categories[name]
        return None


class BaseGimmick(AbstractGimmick, BaseMode):
    """A base or 'unit' gimmick. It does not reference any other gimmicks."""

    def __init__(self, id, cfg):
        super().__init__(id, cfg)

    def make(self, base_gimmicks, cloned_pokemon=None, switching_is_requested=None):
        """Make a MatchGimmick for a specific match.

        Args:
            base_gimmicks: BaseGimmick objects to include in the match.
            cloned_pokemon: Manually requested Pokemon for Clone gimmick.
        """
        if len(base_gimmicks) != 1 or base_gimmicks[0].id != self.id:
            raise ValueError("BaseGimmick cannot reference other gimmicks")

        return MatchGimmick(self, [self], self.match_settings, self.description,
                            self.categories, cloned_pokemon, switching_is_requested)


class ClonedPokemon:
    ARCEUS_PLATES = {type.lower(): plate for plate, type in
                     pokecat.forms.multitype_plates.items()}

    def __init__(self, species_id, form_id=None, item_name=None):
        self.species_id = species_id
        self.species_name = parsing.name_from_id(species_id)
        self.form_was_specified = form_id is not None
        if form_id is None:
            form_id = 0
        self.form_name = pokecat.forms.get_formname(species_id, form_id)
        self.form_id = form_id
        self.item_name = item_name
        self.clone_name = self.species_name
        if self.form_name and self.form_was_specified:
            self.clone_name += '-' + self.form_name
        elif (species_id == 493 and item_name and
              item_name in pokecat.forms.multitype_plates):
            self.clone_name = (self.species_name + '-' +
                               pokecat.forms.multitype_plates[item_name])
        else:
            self.clone_name = self.species_name

    def __str__(self):
        return self.clone_name

    @classmethod
    def parse_cloned_pokemon(cls, arg):
        try:
            species_id, form_name = parsing.parse_pokeset(arg)
            if form_name:
                if species_id == 493:  # Assign appropriate Arceus plate.
                    form_id = 0
                    item_name = cls.ARCEUS_PLATES[form_name.lower()]
                else:
                    form_id = pokecat.forms.get_formnumber(species_id, form_name)
                    if form_id is None:
                        return None
                    item_name = None
            else:
                form_id = None
                item_name = None
        except (InvalidMatch, LookupError, ValueError):
            return None
        return ClonedPokemon(species_id, form_id, item_name)


class ComboGimmick(AbstractGimmick, ComboMode):
    """A gimmick that combines effects from several BaseGimmick objects."""

    def __init__(self, id, cfg):
        super().__init__(id, cfg)

    def _generate_description(self, display_names):
        raise NotImplementedError

    def make(self, base_gimmicks, cloned_pokemon=None, switching_is_requested=None):
        """Make a MatchGimmick for a specific match.

        Args:
            base_gimmicks: BaseGimmick objects to include in the match.
            cloned_pokemon: ClonedPokemon representing a manual Clone request.
        """
        # Generate description.
        description = self._generate_description(base_gimmicks)

        # Combine non-default match settings.
        all_match_settings = ([g.match_settings for g in base_gimmicks] +
                              [self.match_settings])
        match_settings = MatchSettings.from_merge(all_match_settings)

        # Combine categories.
        all_categories = []
        for g in base_gimmicks:
            for id, c in g.categories.items():
                all_categories.append(c)
        categories = Category.from_merge(all_categories)

        return MatchGimmick(self, base_gimmicks, match_settings, description,
                            categories, cloned_pokemon, switching_is_requested)


class RandomComboGimmick(ComboGimmick):
    def __init__(self, id, cfg):
        super().__init__(id, cfg)

    def _generate_description(self, base_gimmicks):
        if self.description:
            description = self.description
        else:
            display_names = [g.display_name for g in base_gimmicks]
            description = ('Gimmicks in this match are {}.'
                           .format(stringify_list(display_names)))
        return description


class GimmickCollection(ModeCollection):
    """Store AbstractGimmick descendants.

    Attributes:
        random_combos: dict of RandomComboGimmick objects by id.

    """

    def __init__(self, cfg):
        base_modes = OrderedDict()
        combo_modes = OrderedDict()
        default_gimmick_chance = cfg['default_gimmick_chance']
        ids = set()

        must_contain_gimmicks_all = [id_ for id_ in cfg['must_contain_all_gimmicks'] if id_ in cfg['gimmicks']['base']]
        must_contain_gimmicks_any = [id_ for id_ in cfg['must_contain_any_gimmicks'] if id_ in cfg['gimmicks']['base']]
        # log.info("cfg: %s", cfg)

        # Create default sub_mode_rarities (needed for non-empty must_contain_gimmicks_all)
        default_sub_mode_rarities = {}
        for id, gimmick in cfg['gimmicks']['base'].items():
            if gimmick.get('disabled', False):
                continue  # Explicitly disabled mode.
            elif id not in cfg['event']['gimmicks'].get("base", []):
                continue  # Mode not present in this event; treat as disabled.
            if id != 'normal':
                default_sub_mode_rarities[id] = gimmick["rarity"]

        if must_contain_gimmicks_any:
            gimmicks_to_add_permutations = [must_contain_gimmicks_all + [gimmick_any]
                                            for gimmick_any in must_contain_gimmicks_any]
        elif must_contain_gimmicks_all:
            gimmicks_to_add_permutations = [must_contain_gimmicks_all]
        else:
            gimmicks_to_add_permutations = []

        rarity_adjust_required = []  # only required when there are gimmicks to add

        for type, gimmicks in cfg['gimmicks'].items():
            for id, gimmick in gimmicks.items():
                if gimmick.get('disabled', False):
                    continue  # Explicitly disabled mode.
                elif id != 'normal' and id not in cfg['event']['gimmicks'].get(type, []):
                    continue  # Mode not present in this event; treat as disabled.

                # Debugging feature
                gimmick['equalize_rarities'] = cfg.get('equalize_rarities', False)

                if not gimmicks_to_add_permutations:
                    if type == 'base':
                        base_modes[id] = BaseGimmick(id, gimmick)
                    elif type == 'random_combos':
                        combo_modes[id] = RandomComboGimmick(id, gimmick)
                    else:
                        raise ValueError('Unrecognized gimmick combo type: {}'.format(type))

                # Extra work to add in all the `gimmicks_to_add`.
                else:
                    if type == 'base':
                        if id == 'normal':
                            # log.info("C: %s: %s", id, gimmick)
                            base_modes[id] = BaseGimmick(id, gimmick)
                        elif any([id] == perm for perm in gimmicks_to_add_permutations):
                            # log.info("A: %s: %s", id, gimmick)
                            base_modes[id] = BaseGimmick(id, gimmick)
                            rarity_adjust_required.append(base_modes[id])
                        else:
                            rarity = gimmick["rarity"]
                            # Add the base gimmick, but with 0 rarity so it never gets selected
                            gimmick["rarity"] = 0
                            base_modes[id] = BaseGimmick(id, gimmick)
                            # Add combos for base gimmick + additional gimmicks
                            for gimmicks_to_add in gimmicks_to_add_permutations:
                                gimmick = {
                                    "rarity": rarity,
                                    "sub_modes": [id] + gimmicks_to_add,
                                    "display_name": "Combo",
                                    "icon_id": "combo",
                                    "description": "",
                                    "sub_mode_rarities": default_sub_mode_rarities,
                                }
                                new_id = id + "+" + "+".join(gimmicks_to_add) + "_autogenerated"
                                # log.info("B: %s: %s", id, gimmick)
                                combo_modes[new_id] = RandomComboGimmick(new_id, gimmick)
                                if new_id in ids:
                                    # Ensure there are no duplicate ids.
                                    raise ValueError('Duplicate gimmicks with name {}'.format(new_id))
                    elif type == 'random_combos':
                        gimmick_original = gimmick
                        for gimmicks_to_add in gimmicks_to_add_permutations:
                            gimmick = deepcopy(gimmick_original)
                            # Avoid adding duplicates
                            gimmicks_to_add_nonduplicate = [g for g in gimmicks_to_add if g not in gimmick["sub_modes"]]
                            gimmick["sub_modes"] = gimmicks_to_add_nonduplicate + gimmick["sub_modes"]
                            if "sub_mode_rarities" not in gimmick:
                                gimmick["sub_mode_rarities"] = default_sub_mode_rarities
                            if len(gimmick["sub_modes"]) > 4:
                                raise ValueError("After adding the `must_contain` gimmicks, %s has"
                                                 " too many modes! (%s > %s)" %
                                                 (id, len(gimmick["sub_modes"]), 4))
                            # log.info("D: %s: %s", id, gimmick)
                            new_id = id + "+" + "+".join(gimmicks_to_add) + "_autogenerated"
                            combo_modes[new_id] = RandomComboGimmick(new_id, gimmick)
                    else:
                        raise ValueError('Unrecognized gimmick combo type: {}'.format(type))

                if id in ids:
                    # Ensure there are no duplicate ids.
                    raise ValueError('Duplicate gimmicks with name {}'.format(type))
                ids.add(id)

        # Extra work to add in all the `gimmicks_to_add`.
        if must_contain_gimmicks_all and len(gimmicks_to_add_permutations[0]) > 1:
            for gimmicks_to_add in gimmicks_to_add_permutations:
                gimmick = {
                    "rarity": 1,  # To be adjusted later
                    "sub_modes": gimmicks_to_add,
                    "display_name": "Combo",
                    "icon_id": "combo",
                    "description": "",
                    "sub_mode_rarities": default_sub_mode_rarities,
                }
                new_id = "+".join(gimmicks_to_add) + "_autogenerated"
                # log.info("B: %s: %s", id, gimmick)
                combo_modes[new_id] = RandomComboGimmick(new_id, gimmick)
                if new_id in ids:
                    # Ensure there are no duplicate ids.
                    raise ValueError('Duplicate gimmicks with name {}'.format(new_id))
                ids.add(new_id)
                rarity_adjust_required.append(combo_modes[new_id])

        super().__init__(base_modes, combo_modes, 'gimmick')

        # Calculate and assign rarity for Normal gimmick.
        if default_gimmick_chance == 0:
            for g in self.all_modes.values():
                g.rarity = 0
            self.base_modes['normal'].rarity = 1.0
        elif default_gimmick_chance == 1:
            self.base_modes['normal'].rarity = 0
        elif default_gimmick_chance < 0 or 1 < default_gimmick_chance:
            raise ValueError('default_gimmick_chance must be'
                             'between 0 and 1, inclusive.')
        else:
            rarity_sum = sum(g.rarity for g in self.all_modes.values())
            normal_rarity = (rarity_sum / default_gimmick_chance) - rarity_sum

            if not gimmicks_to_add_permutations:
                self.base_modes['normal'].rarity = normal_rarity
            else:
                self.base_modes['normal'].rarity = 0
                # Split "normal" rarity evenly among the permutations.
                permutation_avg_rarity = normal_rarity / len(rarity_adjust_required)
                for gimmick in rarity_adjust_required:
                    gimmick.rarity = permutation_avg_rarity


class MatchGimmick(MatchMode):
    """Gimmick data specific to a particular match.

    A MatchGimmick is like an instantiation of a "primary" gimmick,
    which can be either a BaseGimmick or ComboGimmick.

    Ex: If the random_combo gimmick is selected, the resulting
    MatchGimmick might have these attributes:
    primary_mode = random_combo gimmick
    base_modes = list containing: duel gimmick and speed gimmick

    Attributes:
        categories: Categories for the match, to be used by the matchmaker.
        tags: Category tags for the match, to be exported for external use.
    """

    def __init__(self, base_gimmick, single_gimmicks, match_settings,
                 description, categories, cloned_pokemon, switching_is_requested):
        super().__init__(base_gimmick, single_gimmicks, match_settings,
                         description)
        self.categories = categories
        tags = []
        for c in categories.values():
            if isinstance(c, TaggedCategory):
                tags.extend(c.tags)
        self.tags = tags
        self.cloned_pokemon = cloned_pokemon
        self.switching_is_requested = switching_is_requested


class Category:
    def __init__(self, id, cfg):
        self.id = id
        if id not in CATEGORIES.keys():
            raise ValueError("Didn't recognize category: {}".format(id))

    def __dict__(self):
        return {'id': self.id}

    @classmethod
    def from_merge(cls, category_instances):
        new_categories = {}
        category_ids = set([c.id for c in category_instances])
        for id in category_ids:
            categories = [c for c in category_instances if c.id == id]
            if len(categories) > 1:
                if id in ['team_change', 'battle_change']:
                    tags = sum([c.tags for c in categories], [])
                    new_category = TaggedCategory(id, {'tags': tags})
                else:
                    raise ValueError('Cannot merge {} categories'.format(id))
            else:
                new_category = categories[0]
            new_categories[id] = new_category
        return new_categories


class TaggedCategory(Category):
    def __init__(self, id, cfg):
        super().__init__(id, cfg)
        if 'tag' in cfg:
            self.tags = [cfg['tag']]
        elif 'tags' in cfg:
            self.tags = cfg['tags']
        else:
            raise ValueError("Didn't have a tag: {}".format(cfg))

    def __dict__(self):
        return {'id': self.id, 'tags': self.tags}


class PoolCategory(Category):
    def __init__(self, id, cfg, finder, full_list=None):
        super().__init__(id, cfg)
        self._one_per_match = cfg['one_per_match'] if 'one_per_match' in cfg else False
        cfg_pool = cfg['pool'] if 'pool' in cfg else []
        pool_blacklist = cfg['pool_blacklist'] if 'pool_blacklist' in cfg else []
        pool_whitelist = cfg['pool_whitelist'] if 'pool_whitelist' in cfg else []
        self.finder = finder
        if cfg_pool:
            # Only allow items in provided pool.
            self._pool = cfg_pool
            for item in cfg_pool:
                if not self.finder(item):
                    raise ValueError('Could not find pool item: {}'.format(item))
        else:
            # No pool provided; set pool to full list of values.
            if full_list:
                self._pool = full_list
            else:
                raise ValueError('No full list or pool provided')

        # Remove items in blacklist and not in whitelist.
        for item in list(self._pool):
            if item in pool_blacklist:
                self._pool.remove(item)
            if pool_whitelist and item not in pool_whitelist:
                self._pool.remove(item)

    def select_pool(self, forbidden=None):
        pool = self._pool
        if forbidden:
            pool = [e for e in pool if e not in forbidden]

        if self._one_per_match:
            id_pool = [random.choice(pool)]
        else:
            id_pool = pool
        pool = [self.finder(id) for id in id_pool]
        return pool

    def pool_contains(self, item):
        return any(item.lower() == i.lower() for i in self._pool)


class SpeciesReplaceCategory(PoolCategory):
    def __init__(self, id, cfg):
        finder = pokecat.gen4data.get_pokemon
        self.randomize_ivs = cfg.get('randomize_ivs', False)
        self.randomize_evs = cfg.get('randomize_evs', False)
        self.randomize_happiness = cfg.get('randomize_happiness', False)
        self.shinify_chance = cfg.get('shinify_chance', 0)
        full_list = [e['name'] for e in pokecat.gen4data.POKEDEX if e]
        super().__init__(id, cfg, finder, full_list=full_list)


class AbilityReplaceCategory(PoolCategory):
    def __init__(self, id, cfg):
        finder = pokecat.gen4data.get_ability
        full_list = [e['name'] for e in pokecat.gen4data.ABILITIES if e['name']]
        super().__init__(id, cfg, finder, full_list=full_list)


class MoveReplaceCategory(PoolCategory):
    def __init__(self, id, cfg):
        self.pp = cfg['pp'] if 'pp' in cfg else 0
        self.replace_all = cfg['replace_all'] if 'replace_all' in cfg else False
        finder = pokecat.gen4data.get_move
        full_list = [e['name'] for e in pokecat.gen4data.MOVES if e and e['name'] != "Struggle"]
        super().__init__(id, cfg, finder, full_list=full_list)


class ItemReplaceCategory(PoolCategory):
    def __init__(self, id, cfg):
        finder = pokecat.gen4data.get_item
        full_list = [e['name'] for i, e in enumerate(pokecat.gen4data.ITEMS)
                     if 149 <= i <= 327]  # Berries and usable held items only.
        super().__init__(id, cfg, finder, full_list=full_list)
        if 'only_for_species' in cfg:
            self.only_for_species = cfg['only_for_species']
        else:
            self.only_for_species = []


class ThemeCategory(Category):
    def __init__(self, id, cfg):
        super().__init__(id, cfg)
        self._tags_any = cfg['any_tags'] if 'any_tags' in cfg else []
        self._tags_all = cfg['all_tags'] if 'all_tags' in cfg else []

    @property
    def tags_any(self):
        return deepcopy(self._tags_any)

    @property
    def tags_all(self):
        return deepcopy(self._tags_all)


CATEGORIES = {
    'input_change': TaggedCategory,
    'team_change': TaggedCategory,
    'battle_change': TaggedCategory,
    'species_replace': SpeciesReplaceCategory,
    'ability_replace': AbilityReplaceCategory,
    'move_replace': MoveReplaceCategory,
    'item_replace': ItemReplaceCategory,
    'pokemon_theme': ThemeCategory,
}
