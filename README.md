## Installation for matchmaker use
1. Install the package with `pip install git+https://github.com/TwitchPlaysPokemon/pbr-matchmaker.git@master#egg=pbrmatchmaker`  
1. Run `example.py` to generate a match. Modify according to your needs.
 
## Installation for matchmaker modification
1. Clone this repository.
1. Run `pip install -Ur requirements.txt` to install the necessary packages.
1. Modify existing configuration files, or add your own. See sections below.

## How Configuration Works
PBR Matchmaking is configured via **event** files such as `standard.yaml`, `inverse.yaml`, `defiance_only.yaml`, and `christmas.yaml` located at `matchmaker/config/events`.

An event may specify new values to override/supplement the default matchmaking settings documented in `matchmaker/config/settings.yaml`.

An event may specify new values to override/supplement the default metagame/gimmick settings, such as bonus, description, etc. documented in `matchmaker/config/metagames.yaml` and `matchmaker/config/gimmicks.yaml`.

For a mode (metagame/gimmick) to be biddable in an event, its name **must** be present in the event file.  
For a mode to occur in automatically generated matches, it must also be assigned a nonzero rarity value.

See the existing event files for examples.

## Testing
Testing for events exists at `matchmaker/tests/__init__.py`.

Each event contains one "short" test and one "long" test.  
The "short" test performs some small tests, such as whether all icon assets are present.  
The "long" test randomly generates 5000 matches to hopefully find any potential mode combinations that would throw an exception.  The `equalize_rarities=True` argument equalizes mode occurrences to ensure a wide variety of combinations is tested.  

When adding a new event, **also write new short and long test classes in this file for your event**. Run them and ensure all their tests pass. See existing tests for examples.

When short tests for an event are run, various files for that event are created under `matchmaker/tests/dump/<event name/`. Depending on the changes made, you may want to eyeball these to ensure the output is in line with your expectations.

When long tests are run, inspect `testoutput.info.log` to see what matches were generated.

## For TPP mods/operators

The `!reloadmatchmaker` command lets operators change the currently active event without requiring a core restart.  
Edits to the .yaml files can also be pushed and deployed with this command without requiring a core restart (e.g., decrease defiance frequency, remove a bugged mode from an event, add a mode combination to the blacklist).  Note changes to any .py files will still require an old core restart.

The currently active **event** must be specified in `tpp/config.yaml`, in the `match` section, as the `matchmaker_event` value.

Initially, match bet bonuses were exclusively determined by the matchmaker event.  However, some fields such as `early_bet_bonus` have been added to `config.yaml` which may override the matchmaker bonus values.