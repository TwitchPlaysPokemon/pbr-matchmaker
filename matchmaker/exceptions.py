class InvalidMatch(Exception):
    pass


class ModeNotExisting(InvalidMatch):
    """Raise when a mode id is not recognized."""
    def __init__(self, m1):
        msg = '{} is not a recognized mode name.'.format(m1)
        super().__init__(msg)


class IneligibleMode(InvalidMatch):
    """Raise when a mode is ineligible for bidding."""
    def __init__(self, m1):
        msg = '{} is ineligible for match bidding.'.format(m1)
        super().__init__(msg)


class ModeCoolingDown(InvalidMatch):
    def __init__(self, mode_name, cooldown_rounds):
        msg = '%s is on cooldown for %d more token matches.' % (mode_name, cooldown_rounds)
        super().__init__(msg)


class ModesConflict(InvalidMatch):
    """Raise when two mode ids are in conflict."""
    def __init__(self, m1, m2):
        msg = '{} may not be combined with {}.'.format(m1, m2)
        super().__init__(msg)


class TeamChoiceRestriction(InvalidMatch):
    """Raise when teams can't be chosen for the requested modes."""
    def __init__(self, m):
        msg = 'You may not choose teams when requesting {} mode.'.format(m)
        super().__init__(msg)


class SpeciesWithoutClone(InvalidMatch):
    """Raise when a species is in the match bid modes, but Clone was not requested."""
    def __init__(self):
        msg = 'Species found in modes, but Clone was not requested.'
        super().__init__(msg)


class SwitchingNotPermitted(InvalidMatch):
    """Raise when switching on is requested, but not possible."""
    def __init__(self):
        msg = 'Switching is not permitted with those modes.'
        super().__init__(msg)