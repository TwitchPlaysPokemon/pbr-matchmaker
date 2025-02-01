"""
Test a specific event:
python -m unittest matchmaker.tests.ChristmasTestsShort -fv
python -m unittest matchmaker.tests.ChristmasTestsLong -fv

Run main (runs all existing Short tests):
python -m matchmaker.tests

Run all unittests (takes a long time):
python -m unittest matchmaker.tests -fv

"""
import yaml
import sys
import pymongo
import logging
import os
import unittest
import time
from os import path
from collections import OrderedDict
from rainbow_logging_handler import RainbowLoggingHandler

from matchmaker import Matchmaker, InvalidMatch
from matchmaker.utils.pokemondb import PokemonSetRepository

_matchmaker_dir = os.path.join(os.curdir, os.path.dirname(__file__))

# Setup console logger
formatter = logging.Formatter(
    '%(name)s %(funcName)s():%(lineno)d %(levelname)s\n\t%(message)s')
console_handler = RainbowLoggingHandler(sys.stderr)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
# Setup file loggers
info_file_handler = logging.FileHandler(os.path.join(_matchmaker_dir, 'testoutput.info.log'),
                                         mode='w', encoding='utf-8')
info_file_handler.setLevel(logging.INFO)
info_file_handler.setFormatter(formatter)
debug_file_handler = logging.FileHandler(os.path.join(_matchmaker_dir, 'testoutput.debug.log'),
                                         mode='w', encoding='utf-8')
debug_file_handler.setLevel(logging.DEBUG)
debug_file_handler.setFormatter(formatter)
# Setup root logger
log = logging.getLogger('')
log.setLevel(logging.DEBUG)
log.addHandler(console_handler)
log.addHandler(debug_file_handler)
log.addHandler(info_file_handler)


# Runs all short tests
def main():
    tests = [
        StandardTestsShort,
    ]
    for base in tests.copy():
        for cls in base.__subclasses__():
            tests.append(cls)
    run_suites(tests)

def print_mode_icons_selections(mm):
    for _ in range(50):
        icons = mm.select_mode_icon_ids(amount=5, rarity_boost=99, allow_fakes=True)
        log.info(icons)


# Test suite selection/execution functions
def run_suites(test_cases):
    runner = unittest.TextTestRunner(failfast=True)
    for test_case in test_cases:
        suite = unittest.TestSuite()
        suite.addTests(unittest.makeSuite(test_case))
        result = runner.run(suite)
        if result.errors or result.failures:
            exit(1)  # failfast on a per-testcase basis


# Matchmaker setup function. PokemonSetRepository loads the pokesets from json into the db, which takes a few seconds.

def setup_matchmaker(event, bet_bonus_enabled=True, equalize_rarities=False):
    log.info("Setting up matchmaker for the %s event..." % event)
    log.info("Loading Pokemon set repository...")
    mongodb_client = pymongo.MongoClient()
    db = mongodb_client['tpp3']
    pokemon_sets = PokemonSetRepository(db, 'pbr')
    log.info("Creating matchmaker object...")
    debug_cfg = {
        "equalize_rarities": equalize_rarities
    }
    mm = Matchmaker(event, pokemon_sets, 'pbr',bet_bonus_enabled=bet_bonus_enabled, debug_cfg=debug_cfg)
    log.info("Done setting up.")
    return mm


# Automated testing classes & functions

class StandardTestsShort(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.event = 'standard'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def setUp(self):
        self.startTime = time.time()

    def tearDown(self):
        t = time.time() - self.startTime
        print("\n%s: Test took %.3f seconds" % (self.id(), t))

    def test_dump(self):
        dump_formatted_data(self.mm)

    def test_assets(self):
        assets_folder = os.path.abspath(os.path.join(
            os.curdir, os.path.dirname(__file__),
            "..", "matchmakermodes"))
        log.info(assets_folder)
        self.assertTrue(self.mm.validate_icons(assets_folder))

    def test_make_metagame(self):
        for _ in range(100):
            assert(self.mm._mode_maker.make_metagame())
            assert(self.mm._mode_maker.make_metagame(forbidden_ids=['normal']))
            assert(self.mm._mode_maker.make_metagame(forbidden_ids=['audio_only']))
            assert(self.mm._mode_maker.make_metagame(forbidden_ids=['nonexistent_mode']))

    def test_make_gimmick(self):
        for _ in range(100):
            assert(self.mm._mode_maker.make_gimmick())
            assert(self.mm._mode_maker.make_gimmick(forbidden_ids=['normal']))
            assert(self.mm._mode_maker.make_gimmick(forbidden_ids=['audio_only']))
            assert(self.mm._mode_maker.make_gimmick(forbidden_ids=['nonexistent_mode']))

    def test_custom_commands(self):
        custom_commands_file = path.join(_matchmaker_dir, 'custom_match_commands.yaml')
        with open(custom_commands_file, 'r', encoding='utf-8') as f:
            custom_commands = yaml.safe_load(f)
            if self.event in custom_commands:
                for test in custom_commands[self.event]:
                    self._test_custom_command(test)

    def _test_custom_command(self, test):
        command = test['command']
        expected_success = test['success']
        try:
            match = self.mm.make_from_bid(command)
            test_match_commands(match)
        except InvalidMatch as e:
            if expected_success:
                raise ValueError('Custom command "{}" failed to produce a valid '
                                 'match as expected. Exception: {}'
                                 .format(command, e))
        else:
            if not expected_success:
                raise ValueError('Custom command "{}" produced a valid match, '
                                 'but was expected to fail.'
                                 .format(command))

    def test_select_mode_icons(self):
        for _ in range(50):
            icons = self.mm.select_mode_icon_ids(amount=5, rarity_boost=99, allow_fakes=True)


class LanguageTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'language'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=False)


class HalloweenTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'halloween'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class HalloweenProfitTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'halloweenprofit'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class ChristmasTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'christmas'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class ChristmasProfitTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'christmasprofit'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class DoublesInputtingTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'doubles_inputting'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def test_custom_commands(self):
        pass  # none atm


class HiddenBetsTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'hidden_bets'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def test_custom_commands(self):
        pass  # none atm


class DefianceOnlyTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'defiance_only'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def test_custom_commands(self):
        pass  # none atm


class DoublesDefianceTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'doubles_defiance'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class BotBets1TestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'botbets1'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def test_custom_commands(self):
        pass  # none atm


class AprilFoolsTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'aprilfools'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def test_custom_commands(self):
        pass  # none atm


class DefianceProfitBonusesTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'defianceprofitbonuses'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class InverseTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'inverse'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class CommunismTestsShort(StandardTestsShort):
    @classmethod
    def setUpClass(cls):
        cls.event = 'communism'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class DisabledBonusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.event = 'standard'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True, bet_bonus_enabled=False)

    def test_make(self):
        make_match(self.mm, num_tests=1, custom_command="defiance", test_hook=self._test_make_hook)
        make_match(self.mm, num_tests=1, custom_command="standard", test_hook=self._test_make_hook)
        make_match(self.mm, num_tests=500, test_hook=self._test_make_hook)

    def _test_make_hook(self, match):
        bonus = match.settings['bet_bonus']
        assert bonus == 0, "Bet bonus was %r instead of zero" % bonus


class StandardTestsLong(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.event = 'standard'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def setUp(self):
        self.startTime = time.time()

    def tearDown(self):
        t = time.time() - self.startTime
        print("%s: Test took %.3f seconds" % (self.id(), t))

    def test_make(self):
        make_match(self.mm, num_tests=5000, test_hook=self._test_make_hook)

    def _test_make_hook(self, match):
        "Function that tests each match. To be overwritten if desired."
        pass

    def test_gimmick_chance(self):

        log.info("Testing gimmick chance...")
        count_gimmicks = 0
        count_all = 0

        rate_expected = self.mm._cfg['default_gimmick_chance']
        if self.mm._cfg['must_contain_all_gimmicks'] or self.mm._cfg['must_contain_any_gimmicks'] :
            rate_expected = 1.0

        def make_gimmick(mm):
            return mm._mode_maker.make_gimmick()

        def make_gimmick2(mm):
            metagame = mm._mode_maker.make_metagame()
            return mm._mode_maker.make_gimmick(metagame)

        for make_func in (make_gimmick, make_gimmick2):
            for _ in range(500):
                gimmick = make_func(self.mm)
                if gimmick.primary_id != "normal":
                    count_gimmicks += 1
                count_all += 1
            rate_actual = count_gimmicks / count_all
            if abs(rate_actual - rate_expected) > 0.08:
                raise ValueError("Default gimmick chance was {}, expected closer to {}"
                                 .format(rate_actual, rate_expected))


class LanguageTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'language'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=False)

    def _test_make_hook(self, match):
        languages = ['spanish', 'french', 'italian', 'german', 'japanese']
        if sum([l in match.gimmick.base_ids for l in languages]) != 1:
            raise ValueError(f"Match did not have exactly one language gimmick: {match.gimmick.base_ids}")


class ChristmasTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'christmas'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class ChristmasProfitTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'christmasprofit'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class HalloweenTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'halloween'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class HalloweenProfitTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'halloweenprofit'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)


class DoublesInputtingTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'doubles_inputting'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def _test_make_hook(self, match):
        if 'doubles' not in match.gimmick.base_ids:
            raise ValueError(f"Match did not contain the doubles mode: {match.gimmick.base_ids}")
        if 'defiance' in match.gimmick.base_ids:
            raise ValueError(f"Match contained the defiance mode: {match.gimmick.base_ids}")


class HiddenBetsTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'hidden_bets'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def _test_make_hook(self, match):
        if 'hidden_bets' not in match.gimmick.base_ids:
            raise ValueError(f"Match did not contain the hidden bets mode: {match.gimmick.base_ids}")


class DefianceOnlyTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'defiance_only'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def _test_make_hook(self, match):
        if 'defiance' not in match.gimmick.base_ids:
            raise ValueError(f"Match did not contain the defiance mode: {match.gimmick.base_ids}")


class DoublesDefianceTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'doubles_defiance'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def _test_make_hook(self, match):
        if any(mode not in match.gimmick.base_ids for mode in ['defiance', 'doubles']):
            raise ValueError(f"Match did not contain defiance and doubles mode: {match.gimmick.base_ids}")


class BotBets1TestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'botbets1'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def _test_make_hook(self, match):
        bonus = match.settings['bet_bonus']
        # As of commit 0d59467d2 it seems the bet bonus check was moved to tpp's global config.
        # assert bonus == 0, "Bet bonus was %r instead of zero" % bonus


class AprilFoolsTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'aprilfools'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def _test_make_hook(self, match):
        pass


class DefianceProfitBonusesTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'defianceprofitbonuses'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def _test_make_hook(self, match):
        if 'defiance' not in match.gimmick.base_ids:
            raise ValueError(f"Match did not contain the defiance mode: {match.gimmick.base_ids}")


class InverseTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'inverse'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def _test_make_hook(self, match):
        if 'inverse' not in match.gimmick.base_ids:
            raise ValueError(f"Match did not contain the inverse mode: {match.gimmick.base_ids}")


class CommunismTestsLong(StandardTestsLong):
    @classmethod
    def setUpClass(cls):
        cls.event = 'communism'
        cls.mm = setup_matchmaker(cls.event, equalize_rarities=True)

    def _test_make_hook(self, match):
        if 'communism' not in match.gimmick.base_ids:
            raise ValueError(f"Match did not contain the communist mode: {match.gimmick.base_ids}")


def make_match(mm, num_tests=50, custom_command=None, test_hook=None):
    for _ in range(num_tests):
        if custom_command:
            match = mm.make_from_bid(custom_command)
        else:
            match = mm.make(retries_max=0)
        test_match_commands(match)
        if test_hook:
            test_hook(match)
        log.info('Match: ' + match.pretty())


# Verify various match operations don't throw exceptions
def test_match_commands(match):
    for use_set_display_names in (True, False):
        for use_bid_aliases in (True, False):
            for use_public_teams in (True, False):
                for show_prediction in (True, False):
                    match.pretty(use_set_display_names=use_set_display_names,
                                 use_bid_aliases=use_bid_aliases,
                                 use_public_teams=use_public_teams,
                                 show_prediction=show_prediction)
                    match.pretty_token(use_set_display_names=use_set_display_names,
                                       use_bid_aliases=use_bid_aliases,
                                       use_public_teams=use_public_teams,
                                       show_prediction=show_prediction)
    for use_set_display_names in (True, False):
        match.pretty_teams(match.teams, use_set_display_names)


def make_match_from_rotation(mm, num_tests=50):
    rotation_interval = min(50, num_tests // 5)
    for _ in range(num_tests):
        if num_tests % rotation_interval == 0:
            mm.rotation.rotate()
        match = mm.make(from_rotation=True, retries_max=0)
        log.info('Match: ' + match.pretty())


def test_make_teams(mm):
    metagame, gimmick = mm.select_modes()
    teams = mm._teams_maker.make(metagame, gimmick)


def test_disable_audio_only(mm, num_tests=50):
    normalgimmicks = 0
    is_ao_selectable = True
    make_unselectable_interval = min(num_tests // 10, 50)
    for i in range(num_tests):
        match = mm.make(retries_max=0)
        log.info('Match: ' + match.pretty())

        if i % (make_unselectable_interval // 2) == 0:
            if i % make_unselectable_interval == 0:
                mm.set_unselectable_modes(['audio_only'])
                is_ao_selectable = False
            else:
                mm.set_unselectable_modes([])
                is_ao_selectable = True
        if match.gimmick.primary_id == 'normal':
            normalgimmicks += 1
        if not is_ao_selectable:
            if 'audio_only' in match.gimmick.base_ids:
                raise ValueError("match #%d: audio only appeared when "
                                 "it shouldn't!" % i)


# Functions for dumping pretty data to dump/

def dump_formatted_data(mm):
    """Write nicely formatted metadata to dump folder"""
    log.info("Dumping nicely formatted txt and yaml data to dump/...")
    rarities = mm._mode_maker.rarities
    restrictions = mm._mode_maker.restrictions
    tables = {
        'default_metagame_rarities': rarities.default_metagame_rarities,
        'default_gimmick_rarities': rarities.default_gimmick_rarities,
        'gimmick_rarities_by_metagame': rarities.gimmick_rarities_by_metagame,
        'metagame_rarities_by_gimmick': rarities.metagame_rarities_by_gimmick,
        'auto_pair_blacklists': restrictions.auto_pair_blacklists,
        'manual_pair_blacklists': restrictions.manual_pair_blacklists,
        'team_choice_blacklist': restrictions.team_choice_blacklist,
    }
    for filename, value in tables.items():
        yamldump(mm, filename, value)

    for table_name in ['default_metagame_rarities',
                       'default_gimmick_rarities']:
        dump_pretty_rarity_table(mm, table_name, tables[table_name])

    dump_pretty_settings(mm)
    dump_descriptions(mm)


def dump_descriptions(mm):
    # Dump mode descriptions
    modes = {**mm._mode_maker.metagames.base_modes,
              **mm._mode_maker.gimmicks.base_modes}
    pretty = ''
    for mode in modes.values():
        pretty += '{:<15}: {}\n'.format(
            mode.first_bid_alias_or_id(),
            mode.description)
        if mode in mm._mode_maker.gimmicks.base_modes.values():
            pretty += '{:<15}: {} (short)\n'.format(
                mode.first_bid_alias_or_id(),
                mode.short_description)
    txtwrite(mm, 'descriptions', pretty)


def dump_pretty_rarity_table(mm, filename, table):
    # Dump mode rarities
    table = OrderedDict(sorted(table.items(), key=lambda t: -t[1]))
    pretty = ''
    rsum = sum(table.values(), 0)
    for mode_id, rarity in table.items():
        perc = rarity / rsum * 100
        pretty += '{:>5.2f}{:>8.2f}%{:3}{}\n'.format(rarity, perc, ' ', mode_id)
    txtwrite(mm, filename, pretty)


def dump_pretty_settings(mm):
    # Dump mergeable mode settings
    metagames = mm._mode_maker.metagames.all_modes
    gimmicks = mm._mode_maker.gimmicks.all_modes
    modes = {**metagames, **gimmicks}

    settings_instances = {}
    for mode_id, mode in modes.items():
        settings_instances[mode_id] = mode.match_settings
    for name, subset in mm._settings_mergeable.items():
        settings_instances[name] = subset

    settings = {}
    for instance_id, settings_instance in settings_instances.items():
        mode_settings = settings_instance.get_all_settings()
        for mode_setting in mode_settings:
            priority = mode_setting.priority
            val = mode_setting.val
            name = mode_setting.name

            if name not in settings:
                settings[name] = {}

            if priority not in settings[name]:
                settings[name][priority] = {}

            settings[name][priority][instance_id] = val

    for setting, priorities in settings.items():
        for priority, mode_data in priorities.items():
            for mode_id, val in mode_data.items():
                if setting == 'switching_bet_bonus':
                    if priority in settings['bet_bonus']:
                        if mode_id in settings['bet_bonus'][priority]:
                            settings['bet_bonus'][priority][mode_id] = (
                                settings['bet_bonus'][priority][mode_id],
                                val
                            )
    del settings['switching_bet_bonus']

    pretty = ''
    for name, priorities in settings.items():
        priorities = OrderedDict(sorted(priorities.items(), key=lambda t: t[0]))
        pretty += '{}:\n'.format(name)
        for priority, mode_data in priorities.items():
            # Sort if possible
            try:
                mode_data = OrderedDict(sorted(mode_data.items(), key=lambda t: t[1]))
            except TypeError:
                pass
            pretty += '\t{}:\n'.format(priority)
            for mode_id, val in mode_data.items():
                pretty += '\t\t{:<20}: {}\n'.format(mode_id, val)
    txtwrite(mm, 'settings', pretty)


# Utility functions

def txtwrite(mm, filename, value):
    dir_path =os.path.join(_matchmaker_dir, 'dump', mm._cfg['event_id'])
    os.makedirs(dir_path, exist_ok=True)
    with open(os.path.join(dir_path, filename + '.txt'),
              'w', encoding='utf-8') as f:
        f.write(value)


def yamldump(mm, filename, value):
    dir_path =os.path.join(_matchmaker_dir, 'dump', mm._cfg['event_id'])
    os.makedirs(dir_path, exist_ok=True)
    with open(os.path.join(dir_path, filename + '.yaml'),
              'w', encoding='utf-8') as f:
        yaml.dump(value, f, default_flow_style=False,
                  indent=4, allow_unicode=True)


def yamlprint(value):
    yaml.dump(value, sys.stdout, default_flow_style=False, indent=4)


def _filter_log():
    """For filtering log info to certain matchmaker lines"""
    matches = []
    with open('matchmake_test_output.log', 'r', encoding='utf-8') as f:
        for line in f:
            if 'metronome' in line:
                matches.append(line)
        with open('matchmaker_out.log', 'w', encoding='utf-8') as f2:
            f2.write('\n'.join(matches))
