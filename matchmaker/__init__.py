# -*- coding: utf-8 -*-
# source code owned by Twitch Plays Pokemon AUTHORIZED USE ONLY see LICENSE.MD
"""Create Pokemon matchups.

Usage:
    from . import Matchmaker
    mm = Matchmaker('standard', PokemonSetRepository, 'pbr')
    # Create some Match objects.
    match1 = mm.make()
    match2 = mm.make_from_bid('defiance 1,2,3/4,5,6')

    See matchmaker.py for details.
"""
from .matchmaker import Matchmaker, pretty_teams
from .exceptions import InvalidMatch
