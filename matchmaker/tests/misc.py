"""
Test with:
python -m unittest tests.misc -v
"""

import yaml, sys, pymongo, logging, re
from rainbow_logging_handler import RainbowLoggingHandler

log = logging.getLogger("tests")
log.setLevel(logging.INFO)

# set up the console logger
formatter = logging.Formatter("%(name)s %(funcName)s():%(lineno)d %(levelname)s\n\t%(message)s")
console_handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
# console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
log.addHandler(console_handler)

def main():
    test_bid_patterns()

def test_bid_patterns():
    match_bid_pat = re.compile(r"""
        (
            (?P<modes> [^,]+)  \s+
        )?  
        (?P<teams>
            (?P<team1>[^/]+) 
            /
            (?P<team2>[^/]+)
        )?
        .*""", re.IGNORECASE | re.VERBOSE)

    tests = [
        "defiance ",
        "ubers defiance ",
        "1,2,3/4,5,6 ",
        "1, 2, 3/4, 5, 6 ",
        "1, 2, 3 /4, 5, 6",
        "1, 2, 3/ 4, 5, 6",
        "1, 2, 3 / 4, 5, 6",
        "duel 1,2,3/4,5,6",
        "duel 1,2,3 /4,5,6",
        "duel 1,2,3/ 4,5,6",
        "duel 1,2,3 / 4,5,6",
        "duel 1,2, 3 / 4,5, 6",
        "ubers advanced defiance clone jolteon 1,2,3/4,5,6",
        "ubers advanced defiance clone jolteon 1,2,3 /4,5,6",
        "ubers advanced defiance clone jolteon 1,2,3/ 4,5,6",
        "ubers advanced defiance clone jolteon 1,2,3 / 4,5,6",
        "ubers advanced defiance clone jolteon 1,2, 3 / 4,5, 6",
        "Bulbasaur-Special, Noctowl-Standard, Venusaur-Physical"
        " / Charmander-Physical, Charmeleon-Blaze, Charizard-Standard",
    ]

    for bid in tests:
        m = match_bid_pat.match(bid)
        if m:
            msg = 'BID: %s\n\t' % bid
            if m.group('modes'):
                msg += 'Modes: %s\n\t' % m.group('modes')
            if m.group('teams'):
                msg += 'Teams: %s\n\t' % m.group('teams')
            if m.group('team1'):
                msg += 'Team 1: %s\n\t' % m.group('team1')
            if m.group('team2'):
                msg += 'Team 2: %s\n\t' % m.group('team2')
            log.info(msg)
        else:
            log.warning('No match')
        print()

main()
