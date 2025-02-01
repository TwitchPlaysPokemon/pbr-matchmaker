"""Create Pokemon matchups.

    mm = Matchmaker('pbr-5.0.yaml', my_set_repository)
    # Create some Match objects.
    match1 = mm.make()
    match2 = mm.make_from_bid('defiance 1,2,3/4,5,6')

    # Rotate gimmick selections.
    mm.rotate()

"""
import gevent
import logging
import random
import yaml
import os
from itertools import chain
from copy import deepcopy

from .modemaker import MatchModeMaker
from .teamsmaker import TeamsMaker
from .settings import MatchSettings
from .exceptions import InvalidMatch, SwitchingNotPermitted
from .selections import weighted_select
from .matchrestrictions import restricted_clone_ids_team_size_4, restricted_clone_ids_team_size_3
from .utils import matchanalyzer
from .utils.dict_merge import dict_merge
from .utils.stringutils import stringify_list
from . import parsing


log = logging.getLogger(__name__)


class Match:
    """Match objects created by a Matchmaker.

    Attributes:
        teams: 2D list containing team Pokemon in the match.
        public_teams: 2D list of teams prior to hidden gimmick alterations.
        settings: dict with match settings.
        metagame: MatchMetagame for the match.
        gimmick: MatchGimmick for the match.
        analysis: dict with match analysis results, as described in
            tpp/utils/matchanalyzer/analyzer.py.
    """

    def __init__(self, teams, public_teams, settings, metagame, gimmick):
        self.teams = teams
        self.public_teams = public_teams
        self.settings = settings
        self.metagame = metagame
        self.gimmick = gimmick
        blue, red = self.teams[0], self.teams[1]
        effectiveness = 'normal'
        for tag in self.gimmick.tags:
            if 'effectiveness=' in tag:
                effectiveness = tag[14:]
        self.analysis = matchanalyzer.analyze(blue, red, effectiveness)

    def pretty(self, use_set_display_names=False, use_bid_aliases=True,
               use_public_teams=False, show_prediction=True):
        """Return formatted match info."""
        modes_str = self._pretty_modes(use_bid_aliases)
        teams_str = self.pretty_teams(use_public_teams)
        bonus = self.settings['bet_bonus']
        prediction = '~{:.0f}% {} wins'.format(
            self.analysis["WinPercentage"],
            self.analysis["Winner"])
        if show_prediction:
            extra = '({}% bonus, {})'.format(bonus, prediction)
        else:
            extra = '({}% bonus)'.format(bonus)
        return '{} {} {}'.format(modes_str, teams_str, extra)

    def pretty_teams(self, use_set_display_names=False,
                     use_public_teams=False):
        """Return formatted teams info."""
        teams = self.public_teams if use_public_teams else self.teams
        return pretty_teams(teams, use_set_display_names)

    def pretty_token(self, use_set_display_names=False, use_bid_aliases=True,
               use_public_teams=False, show_prediction=False):
        """Return formatted match info."""
        modes_str = self._pretty_modes(use_bid_aliases)
        bonus = self.settings['bet_bonus']
        prediction = '~{:.0f}% {} wins'.format(
            self.analysis["WinPercentage"],
            self.analysis["Winner"])
        if show_prediction:
            extra = '({}% bonus, {})'.format(bonus, prediction)
        else:
            extra = '({}% bonus)'.format(bonus)
        return '{} {}'.format(modes_str, extra)

    def _pretty_modes(self, use_bid_aliases):
        """Return formatted modes info."""
        if use_bid_aliases:
            modes = self.metagame.base_first_bid_aliases_or_ids(add_emoji=True)
            modes.extend(self.gimmick.base_first_bid_aliases_or_ids(add_emoji=True))
        else:
            modes = self.metagame.base_display_names
            modes.extend(self.gimmick.base_display_names)
        if self.gimmick.cloned_pokemon:
            for i, mode in enumerate(modes):
                if mode.startswith('clone'):
                    modes[i] = mode + " " + str(self.gimmick.cloned_pokemon)
        if self.settings['switching'] == 'on':
            modes.append('switching')
        modes_str = ' '.join(modes)
        return modes_str

    def __str__(self):
        return self.pretty()


def pretty_teams(teams, use_set_display_names=False):
    """Return formatted teams info."""
    return '{} / {}'.format(_pretty_team(teams[0], use_set_display_names),
                            _pretty_team(teams[1], use_set_display_names))


def _pretty_team(team, use_set_display_names):
    """Return formatted team info."""
    if use_set_display_names:
        return ', '.join('{displayname}-{setname}'.format(**pokeset)
                        for pokeset in team)
    else:
        return ', '.join('{original_species[name]}-{setname}'.format(**pokeset)
                        for pokeset in team)


class ReusedData:
    def __init__(self):
        self.sets = None


class Rotation:
    """Rotating group of gimmicks.  Inspired by Splatoon map selection"""
    def __init__(self, cfg, mode_maker):
        self.gimmick_chance = cfg['gimmick_chance']
        self.enabled = cfg['enabled']
        self._rotation = []
        self._mode_maker = mode_maker
        self._gimmicks_per_rotation = cfg['gimmicks_per_rotation']
        if self.enabled:
            self.rotate()

    def get(self):
        """Return a random gimmick in the rotation."""
        return random.choice(self._rotation)

    def rotate(self):
        """Update rotation with a new group of gimmicks"""
        # Prevent the previous rotation's MatchGimmicks from being selected again.
        unselectable_gimmicks = self._rotation
        self._rotation = []
        logstr = 'Gimmicks selected for rotation:'
        for _ in range(self._gimmicks_per_rotation):
            # Prevent duplicate MatchGimmicks from being selected.
            gimmick = self._select_for_rotation(unselectable_gimmicks)
            unselectable_gimmicks.append(gimmick)
            logstr += '\n\t{}'.format(gimmick)
            self._rotation.append(gimmick)
        log.info(logstr)

    def _select_for_rotation(self, unselectable_gimmicks):
        """Select a gimmick for the new rotation"""
        gimmick = self._mode_maker.make_rotation_gimmick(
            forbidden_ids=unselectable_gimmicks)
        return gimmick


class Matchmaker:
    """Create Pokemon matchups.

    Attributes:
        _cfg_filename: filename of matchmaker config in package directory.
        _mode_maker: MatchModeMaker for choosing game modes.
        _teams_maker: TeamsMaker for constructing teams from modes.
        _fixed_match_settings: dict with match settings that are fixed
            for all matches. Ex: bet_limits, bet_bonus_decay.
        _default_modifiable_match_settings: MatchSettings object with default
            values for settings that may differ from match to match.
            Ex: bet_bonus, regular_delay.
        _ompp_match_settings: MatchSettings object with setting modifications
            that activate when there is one move per Pokemon.
        _team_choice_settings:
        rotation: Rotation object.
    """

    def __init__(self, event, set_repository, game_id, bet_bonus_enabled=True, debug_cfg=None):
        """Init a matchmaker.

        Args:
            event: Id of the event, e.g. `standard`, `christmas`, etc.
            set_repository: AbstractSetRepository for getting sets.
            game_id: str of the Pokemon game.
        """
        cfg = self._get_config(event, debug_cfg)
        self._cfg = cfg
        self._mode_maker = MatchModeMaker(cfg, game_id)
        self._teams_maker = TeamsMaker(set_repository, cfg)
        self._settings_mergeable = {}
        for mergeable_subset_name in cfg['mergeable']:
            self._settings_mergeable[mergeable_subset_name] = MatchSettings.from_config(
            cfg['mergeable'][mergeable_subset_name])
        self.rotation = Rotation(cfg['rotations'], self._mode_maker)
        self.unselectable_mode_ids = []
        self.cooldowns = {}
        self.bet_bonus_enabled = bet_bonus_enabled


    def make(self, from_rotation=None, retries_max=20):
        """Make a match."""
        log.info("Making match.")
        if from_rotation is None:
            from_rotation = self.rotation.enabled
        metagame = gimmick = None
        retries_remaining = retries_max
        while True:
            try:
                (metagame, gimmick) = self._select_modes(from_rotation)
                log.info("Metagame: {}".format(metagame))
                log.info("Gimmick: {}".format(gimmick))
                match = self._make_balanced_match(metagame, gimmick)
            except InvalidMatch as e:
                if retries_remaining == 0:
                    raise
                retries_remaining -= 1
                log.error("({}/{}) Automated matchmaking failed: {}\n"
                            "Metagame: {}\nGimmick: {}"
                            .format(retries_max - retries_remaining, retries_max,
                                    e, metagame, gimmick))
            else:
                break
        return match

    def make_from_bid(self, match_bid_command):
        """Make a match from a bid command."""
        log.info("Making custom match from command: %s" % match_bid_command)
        mode_args, team_args, team_sizes, bid_ally_hit, bid_battle_timer, unrecognized = (
            parsing.parse_match_bid_command(match_bid_command))
        if unrecognized:
            raise InvalidMatch('Your bid appears to be formatted incorrectly. '
                               'Type "match help" to view the expected format.')

        log.info("Bid modes detected: {}\n\tBid teams detected: {}"
                 .format(mode_args, team_args))

        # Enforce cooldown on large or uneven matches
        is_even = True
        is_large_teams = False
        if team_sizes:
            is_even = team_sizes[0] == team_sizes[1]
            is_large_teams = (team_sizes[0] > self._cfg['team_size_soft_limit']
                or team_sizes[1] > self._cfg['team_size_soft_limit'])
        elif team_args:
            is_even = len(team_args[0]) == len(team_args[1])
            is_large_teams = (len(team_args[0]) > self._cfg['team_size_soft_limit']
                or len(team_args[1]) > self._cfg['team_size_soft_limit'])
        if not is_even and '_uneventeams' in self.cooldowns:
            raise InvalidMatch('Matches with uneven teams are on cooldown for '
                                '{} more token matches.'
                                .format(self.cooldowns['_uneventeams']))
        if is_large_teams and '_largeteams' in self.cooldowns:
            raise InvalidMatch('Matches with more than {} Pokemon per team are '
                                'on cooldown for {} more token matches.'
                                .format(self._cfg['team_size_soft_limit'], self.cooldowns['_largeteams']))

        metagame, gimmick = self._mode_maker.make_from_bid(
            mode_args, bool(team_args), self.cooldowns, bid_ally_hit)
        log.info("Metagame: {}\n\tGimmick: {}".format(metagame, gimmick))

        if team_sizes or team_args:
            if team_sizes:
                sizes = team_sizes[0], team_sizes[1]
            else:
                sizes = len(team_args[0]), len(team_args[1])

            if all(size == 1 for size in sizes):
                if 'secrecy' in gimmick.base_ids:
                    raise InvalidMatch('secrecy may not be requested for a 1v1 match.')
                if 'random_order' in gimmick.base_ids:
                    raise InvalidMatch('randomorder may not be requested for a 1v1 match.')
            if any(size == 1 for size in sizes):
                if 'doubles' in gimmick.base_ids:
                    raise InvalidMatch('doubles may not be requested for a match where one team '
                                       'has only one Pokemon.')
                if 'traitor' in gimmick.base_ids:
                    raise InvalidMatch('traitor may not be requested for a match where one team '
                                       'has only one Pokemon.')
            if any(size > 3 for size in sizes):
                for mode in gimmick.base_modes:
                    if mode.id in ['fog', 'letdown', 'sketchy']:
                        raise InvalidMatch(f'{mode.first_bid_alias_or_id()} may not be requested '
                                           f'for a match where one team has over 3 Pokemon.')
                if 'clone' in gimmick.base_ids and gimmick.cloned_pokemon:
                    if gimmick.cloned_pokemon.species_id in restricted_clone_ids_team_size_3:
                        raise InvalidMatch(f'{gimmick.cloned_pokemon} may not be cloned '
                                           f'for a match where one team has over 3 Pokemon.')
            if any(size > 4 for size in sizes):
                for mode in gimmick.base_modes:
                    if mode.id in ['rainbow', 'hit_and_run', 'boing']:
                        raise InvalidMatch(f'{mode.first_bid_alias_or_id()} may not be requested '
                                           f'for a match where one team has over 4 Pokemon.')
                if 'clone' in gimmick.base_ids and gimmick.cloned_pokemon:
                    if gimmick.cloned_pokemon.species_id in restricted_clone_ids_team_size_4:
                        raise InvalidMatch(f'{gimmick.cloned_pokemon} may not be cloned '
                                           f'for a match where one team has over 4 Pokemon.')

        # Create the match
        if team_args:
            match = self._make_from_modes_and_teams(metagame, gimmick, team_args=team_args)
            # Different analysis for matches with teams specified.
            turn_limit = match.settings['turns_expected_max']

            if (match.analysis["CancerChecks"]["HealCancer"] or
                (turn_limit != 0 and
                 match.analysis["CancerChecks"]["MatchTurns"] > turn_limit)):
                # Reject cancer matches, and matches over the turn limit.
                raise InvalidMatch("This matchup got rejected because"
                                   " it potentially takes too long.")

        else:  # Teams weren't specified
            match = self._make_balanced_match(metagame, gimmick, team_sizes)
            ceilings = self._cfg['multi_mode_ceilings']
            ignore = ceilings['ignore']
            metagame_unignored_ids = [m for m in metagame.base_ids if m not in ignore]
            gimmick_unignored_ids = [m for m in gimmick.base_ids if m not in ignore]
            if len(metagame_unignored_ids) > 1 or len(gimmick_unignored_ids) > 1:
                # Calc and apply ceiling to bet bonus.
                full_exemptions = ceilings['full_exemptions']
                defiance_exemptions = ceilings['defiance_subset_exemptions']
                if any (m in gimmick.base_ids for m in full_exemptions):
                    pass  # Exempt from any ceiling.
                elif ('defiance' in gimmick.base_ids and
                        not gimmick.cloned_pokemon and
                        set(metagame.base_ids).issubset(defiance_exemptions)):
                    bonuses = [bonus for mode, bonus in defiance_exemptions.items()
                               if mode in metagame.base_ids]
                    bonuses.append(match.settings['bet_bonus'])
                    match.settings['bet_bonus'] = min(bonuses)
                else:
                    match.settings['bet_bonus'] = ceilings['default']

        self._set_ally_hit(match, bid_ally_hit)
        self._set_battle_timer(match, bid_battle_timer)

        return match

    def _set_battle_timer(self, match, bid_battle_timer=None):
        match_battle_timer = match.settings['battle_timer']
        if bid_battle_timer is not None:
            battle_timer = bid_battle_timer
        elif match_battle_timer == 'random':
            battle_timer = match_battle_timer
        elif isinstance(match_battle_timer, int):
            battle_timer = int(match_battle_timer)
        else:
            battle_timer = weighted_select(match_battle_timer)
        match.settings['battle_timer'] = battle_timer

    def _set_ally_hit(self, match, bid_ally_hit=None):
        match_ally_hit = match.settings['ally_hit']
        if bid_ally_hit is not None:
            ally_hit = bid_ally_hit
        elif isinstance(match_ally_hit, int):
            ally_hit = int(match_ally_hit)
        else:
            ally_hit = weighted_select(match_ally_hit)
        match.settings['ally_hit'] = ally_hit

    def updateCooldowns(self, winning_match=None, ticks_down=1):
        recent_modes = (winning_match.metagame.base_ids + winning_match.gimmick.base_ids
                        if winning_match else None)
        if winning_match:
            if len(winning_match.teams[0]) != len(winning_match.teams[1]):
                recent_modes.append('_uneventeams')
            if (len(winning_match.teams[0]) > self._cfg['team_size_soft_limit'] 
                    or len(winning_match.teams[1]) > self._cfg['team_size_soft_limit']):
                recent_modes.append('_largeteams')
        if recent_modes:
            for mode_id in recent_modes:
                if mode_id in self.cooldowns:
                    log.error("Mode %s played when it should have been on cooldown. "
                              "Cooldowns: %s" % (mode_id, self.cooldowns))
        # Tick down cooldownsupd
        for mode_id, cooldown in list(self.cooldowns.items()):
            if cooldown < 1:
                log.error("Mode had cooldown of <1, shouldn't be possible")
            if cooldown <= 1:
                del self.cooldowns[mode_id]
            else:
                self.cooldowns[mode_id] = cooldown - ticks_down
        if recent_modes:
            for mode_id in recent_modes:
                cooldown = self._mode_maker.get_mode_cooldown(mode_id)
                if cooldown > 0:
                    self.cooldowns[mode_id] = cooldown

    def _make_from_modes_and_teams(
            self, metagame, gimmick, reusedData=None, team_args=None, team_sizes=None):
        """Make a match with provided modes and team args.

        Args:
            metagame: MatchMetagame for the match.
            gimmick: MatchGimmick for the match.
            team_args: Parsed team args from match bid.  None if
                this is an automatically generated match, or if
                the bidder did not specify teams.

        Returns: A Match.
        """
        teams_are_specified = bool(team_args)
        intermediate_settings = self._get_intermediate_settings(
            metagame, gimmick, teams_are_specified)
        self._validate_team_sizes(intermediate_settings, gimmick, team_args, team_sizes)
        if teams_are_specified:
            teams, public_teams = (
                    self._teams_maker.make_from_team_choice(
                        metagame, gimmick, intermediate_settings, team_args))
        else:
            teams, public_teams = (
                self._teams_maker.make(metagame, gimmick, intermediate_settings, reusedData, team_sizes))
        gevent.sleep(0.002)
        modifiable_settings = self._get_modifiable_match_settings(
            teams, metagame, gimmick, intermediate_settings,
        )
        match = Match(teams, public_teams,
                      modifiable_settings, metagame, gimmick)
        self._set_ally_hit(match)
        gevent.sleep(0.002)
        return match

    def _make_balanced_match(self, metagame, gimmick, team_sizes=None):
        """Make several matches and choose the most balanced one."""
        max_attempts = self._cfg['max_attempts']
        acceptable_est_winchance = self._cfg['acceptable_estimated_winchance']
        best_match = None
        best_est_winchance = 1.0 * 100
        remaining_attempts = max_attempts
        reusedData = ReusedData()
        while True:
            match = self._make_from_modes_and_teams(metagame, gimmick,
                                                    reusedData=reusedData, team_sizes=team_sizes)
            remaining_attempts -= 1
            if remaining_attempts <= 0:
                break
            attempt_info = "Match attempt {}/{}. ".format(
                max_attempts - remaining_attempts,
                max_attempts)
            if (match.settings['check_cancer_recommendation'] and
                    not match.analysis["CancerChecks"]["UseMatch"]):
                log.debug("{} Failed cancer check recommendation."
                          .format(attempt_info))
                continue
            # Winchance returned is between 50 and 100.
            # Lower = more balanced.
            est_winchance = match.analysis["WinPercentage"]
            log.debug("{} Estimated winchance: {:.2f}"
                      .format(attempt_info, est_winchance))

            if est_winchance < acceptable_est_winchance:
                # Found an acceptably balanced match.
                best_match = match
                best_est_winchance = est_winchance
                break
            if est_winchance < best_est_winchance:
                # Record the most balanced match found so far.
                best_match = match
                best_est_winchance = est_winchance
        # Info for logging.
        all_attempts_info = ("Remaining attempts: {}/{} Estimated winchance: {:.2f}"
                             .format(remaining_attempts,
                             max_attempts,
                             best_est_winchance))
        if best_match is None:
            # Matchmaker is way out of its league- all attempts failed basic
            # validation or cancer checks.  Just use the last match.
            log.warning("All attempted matches failed cancer recommendations. "
                        "Matchmaker was unable to provide any match balancing.")
            best_match = match
        elif best_est_winchance < acceptable_est_winchance:
            if remaining_attempts > 10:
                log.info("Found acceptably balanced match. " + all_attempts_info)
            else:
                log.warning("Struggled to find acceptably balanced match. " + all_attempts_info)
        else:
            log.warning("Failed to find acceptably balanced match. " + all_attempts_info)
        return best_match

    def set_unselectable_modes(self, modes_list):
        self.unselectable_mode_ids = modes_list

    def _select_modes(self, from_rotation=False):
        """Select the MatchMetagame and MatchGimmick.

        Returns: (MatchMetagame, MatchGimmick) tuple.
        """
        if from_rotation:
            if random.random() < self.rotation.gimmick_chance:
                gimmick = self.rotation.get()
            else:
                gimmick = self._mode_maker.make_normal_gimmick()
            metagame = self._mode_maker.make_metagame(gimmick)
        else:
            metagame = self._mode_maker.make_metagame(
                forbidden_ids=self.unselectable_mode_ids)
            gimmick = self._mode_maker.make_gimmick(
                metagame, forbidden_ids=self.unselectable_mode_ids)
        return metagame, gimmick

    def get_fixed_match_settings(self):
        settings = {}
        for s in ('bet_limits', 'bet_bonus_decay'):
            settings[s] = self._cfg[s]
        return deepcopy(settings)

    def _get_intermediate_settings(self, metagame, gimmick, teams_are_specified=False):
        """
        Merge mode settings together with the default ones, for use by the teamsmaker.
        These aren't the final settings yet- the final settings depend on the pokemon in the match.
        """
        settings_to_merge = [self._settings_mergeable['default'],
                             metagame.match_settings,
                             gimmick.match_settings]
        if teams_are_specified:
            settings_to_merge.append(self._settings_mergeable['team_choice'])
        merged_settings = MatchSettings.from_merge(settings_to_merge)
        return merged_settings

    def _validate_team_sizes(self, intermediate_settings, gimmick, team_args, team_sizes=None):
        if team_args:
            # this is a match bid with teams specified
            team_sizes = (len(team_args[0]), len(team_args[1]))
        if not team_sizes:
            return

        if 'doubles' in gimmick.base_ids:
            if team_sizes[0] == 1 or team_sizes[1] == 1:
                raise InvalidMatch('Invalid team size- Double Battles require at least two Pokemon per side.')

        team_sizes_dict = intermediate_settings.get_setting_value('team_sizes')
        if (team_sizes not in team_sizes_dict or
                not team_sizes_dict[team_sizes]['biddable']):
            raise InvalidMatch('Invalid team size')

    def _get_modifiable_match_settings(self, teams, metagame, gimmick,
                                       match_settings):
        """Get final match settings.

        Args:
            teams: 2D list of Pokemon teams in the match.
            metagame: MatchMetagame for the match.
            gimmick: MatchGimmick for the match.
            match_settings: MatchSettings object of merged settings so far

        Returns: dict with final values for all modifiable match settings.
        """
        switching = self._select_switching(
            match_settings.get_setting_value('switching'),
            gimmick.switching_is_requested)
        if switching == 'off' and _is_one_move_per_pokemon(teams):
            match_settings = MatchSettings.from_merge(
                [match_settings, self._settings_mergeable['one_move_per_pokemon']])
        settings = match_settings.__dict__()
        settings['switching'] = switching
        # Set bet_bonus to the correct value, according to switching.
        if switching == 'on':
            settings['bet_bonus'] = settings['switching_bet_bonus']
        if gimmick.cloned_pokemon:
            settings['bet_bonus'] = 0
        if not self.bet_bonus_enabled:
            settings['bet_bonus'] = 0

        # Reduce bet bonus for smaller team sizes
        if len(teams[0]) == 2 or ('doubles' in gimmick.base_ids and len(teams[0]) == 3):
            settings['bet_bonus'] = round(2 * int(settings['bet_bonus']) / 3)

        if len(teams[0]) == 1 or ('doubles' in gimmick.base_ids and len(teams[0]) == 2):
            settings['bet_bonus'] = round(int(settings['bet_bonus']) / 3)

        # Set bet bonus to 0 for mismatched team sizes
        if len(teams[0]) != len(teams[1]):
            settings['bet_bonus'] = 0

        del settings['switching_bet_bonus']
        return settings

    def _select_switching(self, switching, switching_is_requested):
        """Set the final switching value, rolling if necessary.

        Valid values are 'on', 'off', and 'special'.
        """
        if type(switching) is int or type(switching) is float:
            if switching_is_requested is not None:
                if switching_is_requested:
                    if switching > 0:
                        return 'on'
                    else:
                        raise SwitchingNotPermitted()
                else:
                    return 'off'
            elif switching < random.random():
                return 'off'
            else:
                return 'on'
        elif switching_is_requested:
            raise SwitchingNotPermitted()
        elif switching == 'permanently_disabled':
            return 'off'
        elif switching == 'special':
            return 'special'
        else:
            log.error("Didn't recognize switching value: %s" % switching)
            return 'off'

    def get_pretty_biddable_metagames(self):
        return self._get_pretty_biddable_modes()[0]

    def get_pretty_biddable_gimmicks(self):
        return self._get_pretty_biddable_modes()[1]

    def _get_pretty_biddable_modes(self):
        """Get primary mode bid_aliases for modes permitted in manual matchmaking.

        Returns: (list of metagame bid_aliases, list of gimmick bid_aliases)
        """
        biddable_modes = self._mode_maker.get_biddable_modes()
        return [
            stringify_list(
                [mode.first_bid_alias_or_id(add_emoji=True) +
                    ("(%d-tokenmatch cooldown)" % self.cooldowns[mode.id]
                     if mode.id in self.cooldowns else "")
                    for mode in modelist]
                , separator=' , ')
            for modelist in biddable_modes
        ]

    def select_mode_icon_ids(
            self, amount=1,rarity_boost=0.0, allow_metagames=True,
            allow_gimmicks=True, allow_fakes=True, allow_normal_gimmick=False):
        return self._mode_maker.select_mode_icon_ids(
            amount, rarity_boost, allow_metagames,
            allow_gimmicks, allow_fakes, allow_normal_gimmick)

    def get_all_icon_ids(self):
        return self._mode_maker.get_all_icon_ids()

    def validate_icons(self, assets_folder):
        icon_ids = self.get_all_icon_ids()
        import os
        icons_missing = False
        for icon_id in icon_ids:
            icon_path = os.path.join(assets_folder, '{}.png'.format(icon_id))
            if not os.path.isfile(icon_path):
                log.error('Missing mode icon: {}'.format(icon_path))
                icons_missing = True
        if not icons_missing:
            log.debug('No missing mode icons detected.')
        return not icons_missing

    def get_mode_info_by_alias(self):
        return self._mode_maker.get_mode_info_by_alias()

    def _get_config(self, event, debug_cfg=None):
        try:
            _root_dir = os.path.dirname(os.path.abspath(__file__))
            cfg = {}
            # Combine these three files into a single config.
            for cfg_name in ('settings', 'metagames', 'gimmicks'):
                cfg_path = os.path.join(_root_dir, 'config', cfg_name + '.yaml')
                cfg_file = open(cfg_path, 'r', encoding='utf-8')
                cfg_part = yaml.load(cfg_file, Loader=yaml.Loader)
                if cfg_name in ('metagames', 'gimmicks'):
                    cfg_part = {cfg_name: cfg_part}
                cfg = {**cfg, **cfg_part}
                cfg_file.close()
            # Merge in event-specific modifications.
            event_cfg_path = os.path.join(_root_dir, 'config', 'events', event + '.yaml')
            event_file = open(event_cfg_path, 'r', encoding='utf-8')
            event_cfg = yaml.load(event_file, Loader=yaml.Loader)
            dict_merge(cfg, event_cfg)  # Merge in event modifications
            cfg['event'] = event_cfg  # Also keep a reference to the unmerged event
            cfg['event_id'] = event
            event_file.close()
            if debug_cfg:
                dict_merge(cfg, debug_cfg)
        except IOError:
            log.exception("A matchmaker config file was not found")
            raise
        return cfg


def _is_one_move_per_pokemon(teams):
    """Determine if there is only one move per Pokemon, for all Pokemon."""
    for p in chain(*teams):
        if not all(m == p['moves'][0] for m in p['moves']):
            return False
    return True
