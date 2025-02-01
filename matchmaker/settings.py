import random
from collections import namedtuple
import logging

log = logging.getLogger(__name__)


Setting = namedtuple('Setting', ['name', 'val', 'priority'])


def team_sizes_merge(team_sizes_data_for_each_mode):
    merged_team_sizes = {}
    for i, team_sizes_dict in enumerate(team_sizes_data_for_each_mode):
        for team_sizes, data in team_sizes_dict.items():
            rarity = data['rarity']
            biddable = data['biddable']
            properties = {'rarity': rarity, 'biddable': biddable}
            if i == 0:
                merged_team_sizes[team_sizes] = properties
            else:
                if team_sizes in merged_team_sizes:
                    if not biddable:
                        merged_team_sizes[team_sizes]['biddable'] = False
                    elif rarity < merged_team_sizes[team_sizes]['rarity']:
                        merged_team_sizes[team_sizes]['rarity'] = rarity
                else:
                    merged_team_sizes[team_sizes] = properties
    if not merged_team_sizes:
        raise ValueError("No valid team sizes available! Input was: %s"
                         % team_sizes_data_for_each_mode)
    # Add mirrored team size if not present
    # E.g.: Set (3,1) team size to the same properties as (1,3) team size if (3,1) isn't present
    for team_sizes, properties in list(merged_team_sizes.items()):
        if (team_sizes[1], team_sizes[0]) not in merged_team_sizes:
            merged_team_sizes[(team_sizes[1], team_sizes[0])] = properties
    return merged_team_sizes


def switching_min(values):
    if 'permanently_disabled' in values:
        return 'permanently_disabled'
    elif 'special' in values:
        return 'special'
    else:
        return min([v for v in values if type(v) is int or type(v) is float])


class MatchSettings:
    def __init__(self, setting_instance_list):
        self._settings_dict = {}
        for setting_instance in setting_instance_list:
            self._settings_dict[setting_instance.name] = setting_instance

    def get_setting_value(self, name):
        if name in self._settings_dict:
            return self._settings_dict[name].val

    def get_setting(self, name):
        if name in self._settings_dict:
            return self._settings_dict[name]

    def get_all_settings(self):
        return self._settings_dict.values()

    @classmethod
    def from_merge(cls, settings_instances):
        new_settings_list = []
        settings_dicts = [i._settings_dict for i in settings_instances]
        setting_names = set().union(*[set(d.keys()) for d in settings_dicts])
        for setting_name in setting_names:
            settings = [i[setting_name] for i in settings_dicts if setting_name in i]
            highest_priority = max([s.priority for s in settings])
            highest_priority_values = [s.val for s in settings if s.priority == highest_priority]

            if (setting_name in ['regular_delay', 'switch_only_delay', 'bet_bonus',
                                 'switching_bet_bonus', 'bet_ceiling', 'inputless_random_switch_chance']):
                dominant_val = min(highest_priority_values)
            elif setting_name in ['animation_speed_multiplier',
                                  'turns_expected_max']:
                dominant_val = max(highest_priority_values)
            elif setting_name == 'switching':
                dominant_val = switching_min(highest_priority_values)
            elif setting_name in ['check_cancer_recommendation', 'bet_bonus_has_decay',
                                  'always_allow_self_target']:
                dominant_val = any(highest_priority_values)
            elif setting_name in ['team_sizes']:
                dominant_val = team_sizes_merge(highest_priority_values)
            elif setting_name in ['pbr', 'ally_hit', 'battle_timer']:
                dominant_val = random.choice(highest_priority_values)
            elif setting_name in ['effectiveness']:
                if len(highest_priority_values) > 1:
                    raise ValueError('Multiple values within a bracket are not supported'
                                     f'for this setting. Values: {highest_priority_values}')
                dominant_val = highest_priority_values[0]
            else:
                raise ValueError('Did not recognize setting {}'.format(setting_name))

            new_settings_list.append(Setting(setting_name, dominant_val, highest_priority))
        return cls(new_settings_list)

    def __dict__(self):
        d = {}
        for setting in self._settings_dict.values():
            d[setting.name] = setting.val
        return d

    @classmethod
    def from_config(cls, cfg):
        settings_list = []
        for priority, settings in cfg.items():
            for k, v in settings.items():
                settings_list.append(Setting(k, v, priority))
        return cls(settings_list)