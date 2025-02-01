from __future__ import division
import random
import logging
import os
import pokecat
import copy

log = logging.getLogger("pbrmm")
TurnLimit = 9  # this flags "cancer" matches, if a 1v1 lasts longer than TurnLimit, throw a flag (EX. Wobbuffet vs wynaut lasts 95 theoretical turns)


class MatchMaker(object):
    def __init__(self):
        self.log = log

        # Type dictionary, u is an attacking type only, grounded is a defending flying type with an iron ball
        self._Types = {"normal": 0, "fire": 1, "water": 2, "electric": 3, "grass": 4,
                       "ice": 5, "fighting": 6, "poison": 7, "ground": 8, "flying": 9,
                       "psychic": 10, "bug": 11, "rock": 12, "ghost": 13, "dragon": 14,
                       "dark": 15, "steel": 16, "u": 17, "grounded": 17, "fairy": 17}

        self._typeEffectivenessTables = {
            "normal": [  # Fe1k's Design
                #                                     Defenders
                # NOR  FIR  WAT  ELE  GRA  ICE  FIG  POI  GRO  FLY  PSY  BUG  ROC  GHO  DRA  DAR  STE GRD
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5, 0, 1, 1, 0.5, 1],  # NOR
                [1, 0.5, 0.5, 1, 2, 2, 1, 1, 1, 1, 1, 2, 0.5, 1, 0.5, 1, 2, 1],  # FIR
                [1, 2, 0.5, 1, 0.5, 1, 1, 1, 2, 1, 1, 1, 2, 1, 0.5, 1, 1, 1],  # WAT
                [1, 1, 2, 0.5, 0.5, 1, 1, 1, 0, 2, 1, 1, 1, 1, 0.5, 1, 1, 2],  # ELE
                [1, 0.5, 2, 1, 0.5, 1, 1, 0.5, 2, 0.5, 1, 0.5, 2, 1, 0.5, 1, 0.5, 0.5],  # GRA
                [1, 0.5, 0.5, 1, 2, 0.5, 1, 1, 2, 2, 1, 1, 1, 1, 2, 1, 0.5, 2],  # ICE
                [2, 1, 1, 1, 1, 2, 1, 0.5, 1, 0.5, 0.5, 0.5, 2, 0, 1, 2, 2, 0.5],  # FIG
                [1, 1, 1, 1, 2, 1, 1, 0.5, 0.5, 1, 1, 1, 0.5, 0.5, 1, 1, 0, 1],  # POI
                [1, 2, 1, 2, 0.5, 1, 1, 2, 1, 0, 1, 0.5, 2, 1, 1, 1, 2, 1],  # GRO   Attackers
                [1, 1, 1, 0.5, 2, 1, 2, 1, 1, 1, 1, 2, 0.5, 1, 1, 1, 0.5, 1],  # FLY
                [1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 0.5, 1, 1, 1, 1, 0, 0.5, 1],  # PSY
                [1, 0.5, 1, 1, 2, 1, 0.5, 0.5, 1, 0.5, 2, 1, 1, 0.5, 1, 2, 0.5, 0.5],  # BUG
                [1, 2, 1, 1, 1, 2, 0.5, 1, 0.5, 2, 1, 2, 1, 1, 1, 1, 0.5, 2],  # ROC
                [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 1, 0.5, 0.5, 1],  # GHO
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 0.5, 1],  # DRA
                [1, 1, 1, 1, 1, 1, 0.5, 1, 1, 1, 2, 1, 1, 2, 1, 0.5, 0.5, 1],  # DAR
                [1, 0.5, 0.5, 0.5, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 0.5, 1],  # STE
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],  # U
            ],
            "inverse": [  # Fe1k's Design
                #                                     Defenders
                # NOR  FIR  WAT  ELE  GRA  ICE  FIG  POI  GRO  FLY  PSY  BUG  ROC  GHO  DRA  DAR  STE GRD
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 2, 1],  # NOR
                [1, 2, 2, 1, 0.5, 0.5, 1, 1, 1, 1, 1, 0.5, 2, 1, 2, 1, 0.5, 1],  # FIR
                [1, 0.5, 2, 1, 2, 1, 1, 1, 0.5, 1, 1, 1, 0.5, 1, 2, 1, 1, 1],  # WAT
                [1, 1, 0.5, 2, 2, 1, 1, 1, 2, 0.5, 1, 1, 1, 1, 2, 1, 1, 0.5],  # ELE
                [1, 2, 0.5, 1, 2, 1, 1, 2, 0.5, 2, 1, 2, 0.5, 1, 2, 1, 2, 2],  # GRA
                [1, 2, 2, 1, 0.5, 2, 1, 1, 0.5, 0.5, 1, 1, 1, 1, 0.5, 1, 2, 0.5],  # ICE
                [0.5, 1, 1, 1, 1, 0.5, 1, 2, 1, 2, 2, 2, 0.5, 2, 1, 0.5, 0.5, 2],  # FIG
                [1, 1, 1, 1, 0.5, 1, 1, 2, 2, 1, 1, 1, 2, 2, 1, 1, 2, 1],  # POI
                [1, 0.5, 1, 0.5, 2, 1, 1, 0.5, 1, 2, 1, 2, 0.5, 1, 1, 1, 0.5, 1],  # GRO   Attackers
                [1, 1, 1, 2, 0.5, 1, 0.5, 1, 1, 1, 1, 0.5, 2, 1, 1, 1, 2, 1],  # FLY
                [1, 1, 1, 1, 1, 1, 0.5, 0.5, 1, 1, 2, 1, 1, 1, 1, 2, 2, 1],  # PSY
                [1, 2, 1, 1, 0.5, 1, 2, 2, 1, 2, 0.5, 1, 1, 2, 1, 0.5, 2, 2],  # BUG
                [1, 0.5, 1, 1, 1, 0.5, 2, 1, 2, 0.5, 1, 0.5, 1, 1, 1, 1, 2, 0.5],  # ROC
                [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5, 1, 1, 0.5, 1, 2, 2, 1],  # GHO
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5, 1, 2, 1],  # DRA
                [1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 0.5, 1, 1, 0.5, 1, 2, 2, 1],  # DAR
                [1, 2, 2, 2, 1, 0.5, 1, 1, 1, 1, 1, 1, 0.5, 1, 1, 1, 2, 1],  # STE
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],  # U
            ],
            "ice-se-on-bug": [  # Fe1k's Design
                #                                     Defenders
                # NOR  FIR  WAT  ELE  GRA  ICE  FIG  POI  GRO  FLY  PSY  BUG  ROC  GHO  DRA  DAR  STE GRD
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5, 0, 1, 1, 0.5, 1],  # NOR
                [1, 0.5, 0.5, 1, 2, 2, 1, 1, 1, 1, 1, 2, 0.5, 1, 0.5, 1, 2, 1],  # FIR
                [1, 2, 0.5, 1, 0.5, 1, 1, 1, 2, 1, 1, 1, 2, 1, 0.5, 1, 1, 1],  # WAT
                [1, 1, 2, 0.5, 0.5, 1, 1, 1, 0, 2, 1, 1, 1, 1, 0.5, 1, 1, 2],  # ELE
                [1, 0.5, 2, 1, 0.5, 1, 1, 0.5, 2, 0.5, 1, 0.5, 2, 1, 0.5, 1, 0.5, 0.5],  # GRA
                [1, 0.5, 0.5, 1, 2, 0.5, 1, 1, 2, 2, 1, 2, 1, 1, 2, 1, 0.5, 2],  # ICE
                [2, 1, 1, 1, 1, 2, 1, 0.5, 1, 0.5, 0.5, 0.5, 2, 0, 1, 2, 2, 0.5],  # FIG
                [1, 1, 1, 1, 2, 1, 1, 0.5, 0.5, 1, 1, 1, 0.5, 0.5, 1, 1, 0, 1],  # POI
                [1, 2, 1, 2, 0.5, 1, 1, 2, 1, 0, 1, 0.5, 2, 1, 1, 1, 2, 1],  # GRO   Attackers
                [1, 1, 1, 0.5, 2, 1, 2, 1, 1, 1, 1, 2, 0.5, 1, 1, 1, 0.5, 1],  # FLY
                [1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 0.5, 1, 1, 1, 1, 0, 0.5, 1],  # PSY
                [1, 0.5, 1, 1, 2, 1, 0.5, 0.5, 1, 0.5, 2, 1, 1, 0.5, 1, 2, 0.5, 0.5],  # BUG
                [1, 2, 1, 1, 1, 2, 0.5, 1, 0.5, 2, 1, 2, 1, 1, 1, 1, 0.5, 2],  # ROC
                [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 2, 1, 0.5, 0.5, 1],  # GHO
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 0.5, 1],  # DRA
                [1, 1, 1, 1, 1, 1, 0.5, 1, 1, 1, 2, 1, 1, 2, 1, 0.5, 0.5, 1],  # DAR
                [1, 0.5, 0.5, 0.5, 1, 2, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 0.5, 1],  # STE
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],  # U
            ],
            "inverse-of-ice-se-on-bug": [  # Fe1k's Design
                #                                     Defenders
                # NOR  FIR  WAT  ELE  GRA  ICE  FIG  POI  GRO  FLY  PSY  BUG  ROC  GHO  DRA  DAR  STE GRD
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 2, 1],  # NOR
                [1, 2, 2, 1, 0.5, 0.5, 1, 1, 1, 1, 1, 0.5, 2, 1, 2, 1, 0.5, 1],  # FIR
                [1, 0.5, 2, 1, 2, 1, 1, 1, 0.5, 1, 1, 1, 0.5, 1, 2, 1, 1, 1],  # WAT
                [1, 1, 0.5, 2, 2, 1, 1, 1, 2, 0.5, 1, 1, 1, 1, 2, 1, 1, 0.5],  # ELE
                [1, 2, 0.5, 1, 2, 1, 1, 2, 0.5, 2, 1, 2, 0.5, 1, 2, 1, 2, 2],  # GRA
                [1, 2, 2, 1, 0.5, 2, 1, 1, 0.5, 0.5, 1, 0.5, 1, 1, 0.5, 1, 2, 0.5],  # ICE
                [0.5, 1, 1, 1, 1, 0.5, 1, 2, 1, 2, 2, 2, 0.5, 2, 1, 0.5, 0.5, 2],  # FIG
                [1, 1, 1, 1, 0.5, 1, 1, 2, 2, 1, 1, 1, 2, 2, 1, 1, 2, 1],  # POI
                [1, 0.5, 1, 0.5, 2, 1, 1, 0.5, 1, 2, 1, 2, 0.5, 1, 1, 1, 0.5, 1],  # GRO   Attackers
                [1, 1, 1, 2, 0.5, 1, 0.5, 1, 1, 1, 1, 0.5, 2, 1, 1, 1, 2, 1],  # FLY
                [1, 1, 1, 1, 1, 1, 0.5, 0.5, 1, 1, 2, 1, 1, 1, 1, 2, 2, 1],  # PSY
                [1, 2, 1, 1, 0.5, 1, 2, 2, 1, 2, 0.5, 1, 1, 2, 1, 0.5, 2, 2],  # BUG
                [1, 0.5, 1, 1, 1, 0.5, 2, 1, 2, 0.5, 1, 0.5, 1, 1, 1, 1, 2, 0.5],  # ROC
                [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5, 1, 1, 0.5, 1, 2, 2, 1],  # GHO
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.5, 1, 2, 1],  # DRA
                [1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 0.5, 1, 1, 0.5, 1, 2, 2, 1],  # DAR
                [1, 2, 2, 2, 1, 0.5, 1, 1, 1, 1, 1, 1, 0.5, 1, 1, 1, 2, 1],  # STE
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],  # U
            ],
        }
        self._statmultipliers = [0.25, 0.28, 0.33, 0.40, 0.50, 0.66, 1, 1.5, 2, 2.5, 3, 3.5, 4]
        self._critmultipliers = [0.0625, 0.125, 0.25, 0.333, 0.5, 0.5, 0.5]

        self._GamesPlayed = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        self._TypeBoostItem = {'blackbelt': 'fighting', 'blackglasses': 'dark', 'charcoal': 'fire',
                               'dragonfang': 'dragon', 'hardstone': 'rock', 'magnet': 'electric', 'metalcoat': 'steel',
                               'miracleseed': 'grass', 'mysticwater': 'water', 'nevermeltice': 'ice',
                               'poisonbarb': 'poison', 'sharpbeak': 'flying', 'silkscarf': 'normal',
                               'silverpowder': 'bug', 'softsand': 'ground', 'spelltag': 'ghost',
                               'twistedspoon': 'psychic', 'fistplate': 'fighting', 'dreadplate': 'dark',
                               'flameplate': 'fire', 'dracoplate': 'dragon', 'stoneplate': 'rock',
                               'zapplate': 'electric', 'ironplate': 'steel', 'meadowplate': 'grass',
                               'splashplate': 'water', 'icicleplate': 'ice', 'toxicplate': 'poison',
                               'skyplate': 'flying', 'insectplate': 'bug', 'earthplate': 'ground',
                               'spookyplate': 'ghost', 'mindplate': 'psychic', 'oddincense': 'psychic',
                               'seaincense': 'water', 'waveincense': 'water', 'rockincense': 'rock',
                               'roseincense': 'grass'}

        self._BerryDamageReduction = {'occaberry': 'fire', 'passhoberry': 'water', 'wacanberry': 'electric',
                                      'rindoberry': 'grass', 'yacheberry': 'ice', 'chopleberry': 'fighting',
                                      'kebiaberry': 'poison', 'shucaberry': 'ground', 'cobaberry': 'flying',
                                      'payapaberry': 'psychic', 'tangaberry': 'bug', 'chartiberry': 'rock',
                                      'kasibberry': 'ghost', 'habanberry': 'dragon', 'colburberry': 'dark',
                                      'babiriberry': 'steel', 'roseliberry': 'fairy'}

        self._NaturalGift = {'none': ('normal', 0), 'watmelberry': ('fire', 80), 'durinberry': ('water', 80),
                             'belueberry': ('electric', 80), 'liechiberry': ('grass', 80), 'ganlonberry': ('ice', 80),
                             'salacberry': ('fighting', 80), 'petayaberry': ('poison', 80),
                             'apicotberry': ('ground', 80), 'lansatberry': ('flying', 80),
                             'starfberry': ('psychic', 80), 'enigmaberry': ('bug', 80), 'micleberry': ('rock', 80),
                             'custapberry': ('ghost', 80), 'jabocaberry': ('dragon', 80), 'rowapberry': ('dark', 80),
                             'blukberry': ('fire', 70), 'nanabberry': ('water', 70), 'wepearberry': ('electric', 70),
                             'pinapberry': ('grass', 70), 'pomegberry': ('ice', 70), 'kelpsyberry': ('fighting', 70),
                             'qualotberry': ('poison', 70), 'hondewberry': ('ground', 70), 'grepaberry': ('flying', 70),
                             'tamatoberry': ('psychic', 70), 'cornnberry': ('bug', 70), 'magostberry': ('rock', 70),
                             'rabutaberry': ('ghost', 70), 'nomelberry': ('dragon', 70), 'spelonberry': ('dark', 70),
                             'pamtreberry': ('steel', 70), 'cheriberry': ('fire', 60), 'chestoberry': ('water', 60),
                             'pechaberry': ('electric', 60), 'rawstberry': ('grass', 60), 'aspearberry': ('ice', 60),
                             'leppaberry': ('fighting', 60), 'oranberry': ('poison', 60), 'persimberry': ('ground', 60),
                             'lumberry': ('flying', 60), 'sitrusberry': ('psychic', 60), 'figyberry': ('bug', 60),
                             'wikiberry': ('rock', 60), 'magoberry': ('ghost', 60), 'aguavberry': ('dragon', 60),
                             'iapapaberry': ('dark', 60), 'razzberry': ('steel', 60), 'occaberry': ('fire', 60),
                             'passhoberry': ('water', 60), 'wacanberry': ('electric', 60), 'rindoberry': ('grass', 60),
                             'yacheberry': ('ice', 60), 'chopleberry': ('fighting', 60), 'kebiaberry': ('poison', 60),
                             'shucaberry': ('ground', 60), 'cobaberry': ('flying', 60), 'payapaberry': ('psychic', 60),
                             'tangaberry': ('bug', 60), 'chartiberry': ('rock', 60), 'kasibberry': ('ghost', 60),
                             'habanberry': ('dragon', 60), 'colburberry': ('dark', 60), 'babiriberry': ('steel', 60),
                             'chilanberry': ('normal', 60)}

        self._PokemonWeight = [0, 6.9, 13.0, 100.0, 8.5, 19.0, 90.5, 9.0, 22.5, 85.5, 2.9, 9.9, 32.0, 3.2, 10.0, 29.5,
                               1.8, 30.0, 39.5, 3.5, 18.5, 2.0, 38.0, 6.9, 65.0, 6.0, 30.0, 12.0, 29.5, 7.0, 20.0, 60.0,
                               9.0, 19.5, 62.0, 7.5, 40.0, 9.9, 19.9, 5.5, 12.0, 7.5, 55.0, 5.4, 8.6, 18.6, 5.4, 29.5,
                               30.0, 12.5, 0.8, 33.3, 4.2, 32.0, 19.6, 76.6, 28.0, 32.0, 19.0, 155.0, 12.4, 20.0, 54.0,
                               19.5, 56.5, 48.0, 19.5, 70.5, 130.0, 4.0, 6.4, 15.5, 45.5, 55.0, 20.0, 105.0, 300.0,
                               30.0, 95.0, 36.0, 78.5, 6.0, 60.0, 15.0, 39.2, 85.2, 90.0, 120.0, 30.0, 30.0, 4.0, 132.5,
                               0.1, 0.1, 40.5, 210.0, 32.4, 75.6, 6.5, 60.0, 10.4, 66.6, 2.5, 120.0, 6.5, 45.0, 49.8,
                               50.2, 65.5, 1.0, 9.5, 115.0, 120.0, 34.6, 35.0, 80.0, 8.0, 25.0, 15.0, 39.0, 34.5, 80.0,
                               54.5, 56.0, 40.6, 30.0, 44.5, 55.0, 88.4, 10.0, 235.0, 220.0, 4.0, 6.5, 29.0, 24.5, 25.0,
                               36.5, 7.5, 35.0, 11.5, 40.5, 59.0, 460.0, 55.4, 52.6, 60.0, 3.3, 16.5, 210.0, 122.0, 4.0,
                               6.4, 15.8, 100.5, 7.9, 19.0, 79.5, 9.5, 25.0, 88.8, 6.0, 32.5, 21.2, 40.8, 10.8, 35.6,
                               8.5, 33.5, 75.0, 12.0, 22.5, 2.0, 3.0, 1.0, 1.5, 3.2, 2.0, 15.0, 7.8, 13.3, 61.5, 5.8,
                               8.5, 28.5, 38.0, 33.9, 0.5, 1.0, 3.0, 11.5, 1.8, 8.5, 38.0, 8.5, 75.0, 26.5, 27.0, 2.1,
                               79.5, 1.0, 5.0, 28.5, 41.5, 7.2, 125.8, 14.0, 64.8, 400.0, 7.8, 48.7, 3.9, 118.0, 20.5,
                               54.0, 28.0, 8.8, 125.8, 35.0, 55.0, 6.5, 55.8, 5.0, 12.0, 28.5, 16.0, 220.0, 50.5, 10.8,
                               35.0, 152.0, 33.5, 120.0, 32.5, 71.2, 58.0, 21.0, 48.0, 6.0, 23.5, 21.4, 75.5, 46.8,
                               178.0, 198.0, 187.0, 72.0, 152.0, 202.0, 216.0, 199.0, 5.0, 5.0, 21.6, 52.2, 2.5, 19.5,
                               52.0, 7.6, 28.0, 81.9, 13.6, 37.0, 17.5, 32.5, 3.6, 10.0, 28.4, 11.5, 31.6, 2.6, 32.5,
                               55.0, 4.0, 28.0, 59.6, 2.3, 19.8, 9.5, 28.0, 6.6, 20.2, 48.4, 1.7, 3.6, 4.5, 39.2, 24.0,
                               46.5, 130.5, 5.5, 12.0, 1.2, 16.3, 40.5, 84.0, 86.4, 253.8, 2.0, 97.0, 11.0, 32.6, 11.0,
                               11.5, 60.0, 120.0, 360.0, 11.2, 31.5, 15.2, 40.2, 4.2, 4.2, 17.7, 17.7, 2.0, 10.3, 80.0,
                               20.8, 88.8, 130.0, 398.0, 24.0, 220.0, 80.4, 30.6, 71.5, 5.0, 15.0, 15.3, 82.0, 51.3,
                               77.4, 1.2, 20.6, 40.3, 52.5, 168.0, 154.0, 1.9, 23.6, 11.5, 32.8, 21.5, 108.0, 23.8,
                               60.4, 12.5, 68.2, 7.4, 162.0, 0.8, 22.0, 2.3, 12.5, 15.0, 30.6, 100.0, 1.0, 47.0, 14.0,
                               16.8, 256.5, 39.5, 87.6, 150.6, 52.5, 27.0, 22.6, 23.4, 8.7, 42.1, 110.5, 102.6, 95.2,
                               202.5, 550.0, 230.0, 175.0, 205.0, 40.0, 60.0, 352.0, 950.0, 206.5, 1.1, 60.8, 10.2,
                               97.0, 310.0, 6.2, 22.0, 55.0, 5.2, 23.0, 84.5, 2.0, 15.5, 24.9, 20.0, 31.5, 2.2, 25.5,
                               9.5, 30.5, 42.0, 1.2, 14.5, 31.5, 102.5, 57.0, 149.5, 3.4, 6.5, 23.3, 5.5, 38.5, 3.9,
                               29.5, 33.5, 3.3, 9.3, 6.3, 29.9, 20.3, 1.2, 15.0, 5.5, 33.3, 4.4, 27.3, 3.9, 43.8, 0.6,
                               19.2, 38.0, 60.5, 187.0, 15.0, 13.0, 24.4, 1.9, 108.0, 20.5, 56.0, 95.0, 105.0, 20.2,
                               54.0, 49.5, 300.0, 12.0, 61.5, 23.0, 44.4, 27.0, 7.0, 24.0, 65.0, 50.5, 135.5, 34.0,
                               180.0, 140.0, 282.8, 128.6, 138.6, 68.0, 38.0, 51.5, 25.5, 25.9, 42.5, 291.0, 34.0, 52.0,
                               340.0, 106.6, 26.6, 0.3, 0.3, 0.3, 0.3, 683.0, 336.0, 430.0, 420.0, 750.0, 85.6, 3.1,
                               1.4, 50.5, 2.1, 320.0]

    def getEff(self, type1name, type2name, defenderability):
        """
        Calculates the effectiveness of an attack

        Arguments:
                type1name:
                    Attacking move type
                type2name:
                    One of the Defending pokemon's types
                defenderability:
                    Ability to the Defender


        Returns:
                tempx:
                    float, effectiveness of the attack (1 = neutral, 2 = super effective)
        """

        if type2name == 'none':
            return (1)
        type1 = self._Types[type1name]
        type2 = self._Types[type2name]
        tempx = self._typeEffectivenessTables[self._effectiveness][type1][type2]
        if defenderability.lower() == 'waterabsorb' and type1name == 'water':
            tempx = 0
        elif defenderability.lower() in ('voltabsorb', 'motordrive') and type1name == 'electric':
            tempx = 0
        elif defenderability.lower() == 'levitate' and type1name == 'ground':
            tempx = 0
        elif defenderability.lower() == 'flashfire' and type1name == 'fire':
            tempx = 0
        elif defenderability.lower() == 'dryskin':
            if type1name == 'water':
                tempx = 0
            if type1name == 'fire':
                tempx = tempx * 1.25
        if defenderability.lower() == 'thickfat' and type1name in ('ice', 'fire'):
            tempx = tempx * 0.5
        if defenderability.lower() == 'heatproof' and type1name == 'fire':
            tempx = tempx * 0.5
        if defenderability.lower() in ('filter', 'solidrock') and tempx > 1:
            tempx = tempx * 0.75
        return tempx

    def DamageDealt(self, Attacker, Defender, moveset2, PokemonData, BattlerStats, dmg, AttackerCurrentHP,
                    DefenderCurrentHP):
        """
        This calculates the damage a single move will do against a defending pokemon

        Arguments:
                Attacker:
                    Position of Attacker in PokemonData
                Defender:
                    Position of Defender in PokemonData
                moveset2:
                    Position of the attack the attacker is using in PokemonData
                PokemonData:
                    All the data for all pokemon in the match
                BattlerStats:
                    Stats for all pokemon in the match AFTER they go through abilities
                dmg:
                    recorded damage of other moves by pokemon in this 1v1
                AttackerCurrentHP:
                    Attacker current HP, float, 0-1
                DefenderCurrentHP:
                    Defender current HP, float, 0-1

        Returns:
                dmg:
                    Damage of the move calculated here
        """

        # set up items
        BattlerStats[Attacker]['item'] = 'none'
        if PokemonData[Attacker]['item']['name'] is not None:
            BattlerStats[Attacker]['item'] = PokemonData[Attacker]['item']['name'].lower().replace(' ', '').replace("'",
                                                                                                                    '')
        BattlerStats[Defender]['item'] = 'none'
        if PokemonData[Defender]['item']['name'] is not None:
            BattlerStats[Defender]['item'] = PokemonData[Defender]['item']['name'].lower().replace(' ', '').replace("'",
                                                                                                                    '')
        # Attacking move
        AttackerMoveName = PokemonData[Attacker]['moves'][moveset2]['name'].lower().replace(' ', '').replace('-',
                                                                                                             '')  # Name
        AttackerMoveType = PokemonData[Attacker]['moves'][moveset2]['type'].lower().replace(' ', '')  # type
        if AttackerMoveType == '???':
            AttackerMoveType = 'ghost'
        AttackerMoveCategory = PokemonData[Attacker]['moves'][moveset2]['category'].lower().replace(' ', '')  # category
        AttackerMovePower = PokemonData[Attacker]['moves'][moveset2]['power']  # power
        AttackerMoveAccuracy = PokemonData[Attacker]['moves'][moveset2]['accuracy']  # accuracy
        if AttackerMoveAccuracy is None:
            AttackerMoveAccuracy = 101
        else:
            if BattlerStats[Attacker]['ability'] == 'hustle' and AttackerMoveCategory == 'physical':
                AttackerMoveAccuracy *= 0.8
            if BattlerStats[Defender]['item'] in ('brightpowder', 'laxincense'):
                AttackerMoveAccuracy *= 0.9
            if BattlerStats[Attacker]['item'] == 'widelens':
                AttackerMoveAccuracy *= 1.1
            if BattlerStats[Attacker]['item'] == 'zoomlens' and BattlerStats[Attacker]['speed'] < \
                    BattlerStats[Defender]['speed']:
                AttackerMoveAccuracy *= 1.2
            if BattlerStats[Attacker]['ability'] == 'compoundeyes':
                AttackerMoveAccuracy *= 1.3

        # Mon types
        AttackerType = ['', 'none']
        DefenderType = ['', 'none']
        AttackerType[0] = PokemonData[Attacker]['species']['types'][0].lower()
        if len(PokemonData[Attacker]['species']['types']) == 2:
            AttackerType[1] = PokemonData[Attacker]['species']['types'][1].lower()
        DefenderType[0] = PokemonData[Defender]['species']['types'][0].lower()
        if len(PokemonData[Defender]['species']['types']) == 2:
            DefenderType[1] = PokemonData[Defender]['species']['types'][1].lower()
        if DefenderType[0] == 'flying' and BattlerStats[Defender]['item']:
            DefenderType[0] = 'grounded'
        if DefenderType[1] == 'flying' and BattlerStats[Defender]['item']:
            DefenderType[1] = 'grounded'
        if BattlerStats[Attacker]['ability'] == 'multitype':
            if PokemonData[Attacker]['item']['name'] in self._TypeBoostItem:
                AttackerType[0] = self._TypeBoostItem[BattlerStats[Attacker]['item']]
                if AttackerMoveName == 'judgement':
                    AttackerMoveType = self._TypeBoostItem[BattlerStats[Attacker]['item']]
        if BattlerStats[Defender]['ability'] == 'multitype':
            if PokemonData[Defender]['item']['name'] in self._TypeBoostItem:
                DefenderType[0] = self._TypeBoostItem[BattlerStats[Defender]['item']]

        # moves that change based on unique factors
        if AttackerMoveName == 'weatherball':
            AttackerMoveType = 'normal'
            AttackerMovePower = 50
            SunnyDay = False
            RainDance = False
            SandStorm = False
            Hailing = False
            for tempx in range(0, len(PokemonData[Attacker]['moves'])):
                if PokemonData[Attacker]['moves'][tempx]['name'] == "sunnyday":
                    SunnyDay = True
                if PokemonData[Attacker]['moves'][tempx]['name'] == "raindance":
                    RainDance = True
                if PokemonData[Attacker]['moves'][tempx]['name'] == "sandstorm":
                    SandStorm = True
                if PokemonData[Attacker]['moves'][tempx]['name'] == "hail":
                    Hailing = True
            if SunnyDay == True or BattlerStats[Attacker]['ability'] == 'drought' or BattlerStats[Defender][
                'ability'] == 'drought':
                AttackerMoveType = 'fire'
                AttackerMovePower = 100
            if RainDance == True or BattlerStats[Attacker]['ability'] == 'drizzle' or BattlerStats[Defender][
                'ability'] == 'drizzle':
                AttackerMoveType = 'water'
                AttackerMovePower = 100
            if SandStorm == True or BattlerStats[Attacker]['ability'] == 'sandstream' or BattlerStats[Defender][
                'ability'] == 'sandstream':
                AttackerMoveType = 'rock'
                AttackerMovePower = 80
            if Hailing == True or BattlerStats[Attacker]['ability'] == 'snowwarning' or BattlerStats[Defender][
                'ability'] == 'snowwarning':
                AttackerMoveType = 'ice'
                AttackerMovePower = 80
        elif AttackerMoveName == 'gyroball':
            AttackerMovePower = 25 * BattlerStats[Defender]['speed'] / BattlerStats[Attacker]['speed']
            if AttackerMovePower > 150:
                AttackerMovePower = 150
        elif AttackerMoveName in ('doomdesire', 'futuresight'):
            AttackerMovePower = 40
        elif AttackerMoveName == 'snore':
            AttackerMovePower = 0
        elif AttackerMoveName == 'present':
            AttackerMovePower = 40
        elif AttackerMoveName in ('skullbash', 'skyattack', 'razorwind', 'solarbeam', 'lastresort'):
            AttackerMovePower = AttackerMovePower * 0.5
        elif AttackerMoveName in (
        'hyperbeam', 'gigaimpact', 'rockwrecker', 'blastburn', 'hydrocannon', 'frenzyplant', 'roaroftime'):
            AttackerMovePower = AttackerMovePower * 0.59
        elif AttackerMoveName in ('selfdestruct', 'explosion'):
            AttackerMovePower = AttackerMovePower * (1 - AttackerCurrentHP)
            if Attacker in ((self._NmbBlumons - 1), (len(PokemonData) - 1)):
                AttackerMovePower = 0
        elif AttackerMoveName in (
        'takedown', 'doubleedge', 'submission', 'volttackle', 'flareblitz', 'bravebird', 'woodhammer', 'headsmash',
        'bravebird') and BattlerStats[Attacker]['ability'] == 'rockhead':
            AttackerMovePower = AttackerMovePower / 1.2
        elif AttackerMoveName in ('leafstorm', 'overheat', 'psychoboost', 'dracometeor'):
            AttackerMovePower = AttackerMovePower * 0.611
        elif AttackerMoveName == 'superpower':
            AttackerMovePower = AttackerMovePower * 0.722
        elif AttackerMoveName in (
        'doubleslap', 'armthrust', 'barrage', 'bonerush', 'bulletseed', 'cometpunch', 'furyattack', 'furyswipes',
        'iciclespear', 'pinmissle', 'rockblast', 'spikecannon'):
            if BattlerStats[Attacker]['ability'] == 'skilllink':
                AttackerMovePower = AttackerMovePower * 5
            else:
                AttackerMovePower = AttackerMovePower * 3
        elif AttackerMoveName == 'magnitude':
            AttackerMovePower = 71
        elif AttackerMoveName == 'fling':
            if BattlerStats[Attacker]['item'] != 'none':  # every other item in the game is 30bp
                AttackerMovePower = 30
            if BattlerStats[Attacker]['item'] in (
            'liechiberry', 'ganlonberry', 'salacberry', 'petayaberry', 'apicotberry', 'lansatberry',
            'starfberryoccaberry', 'passhoberry', 'wacanberry', 'rindoberry', 'yacheberry', 'chopleberry', 'kebiaberry',
            'shucaberry', 'cobaberry', 'payapaberry', 'tangaberry', 'chartiberry', 'kasibberry', 'habanberry',
            'colburberry', 'babiriberry', 'chilanberry', 'sitrusberry', 'enigmaberry', 'micleberry', 'custapberry',
            'jabocaberry', 'rowapberry', 'lumberry', 'pomegberry', 'kelpsyberry', 'qualotberry', 'hondewberry',
            'grepaberry', 'tamatoberry', 'spelonberry', 'pamtreberry', 'watmelberry', 'durinberry', 'belueberry',
            'figyberry', 'wikiberry', 'magoberry', 'aguavberry', 'iapapaberry', 'cornnberry', 'magostberry',
            'rabutaberry', 'nomelberry', 'cheriberry', 'chestoberry', 'pechaberry', 'rawstberry', 'aspearberry',
            'leppaberry', 'oranberry', 'persimberry', 'razzberry', 'blukberry', 'nanabberry', 'wepearberry',
            'pinapberry', 'airballoon', 'bigroot', 'brightpowder', 'choiceband', 'choicescarf', 'choicespecs',
            'destinyknot', 'expertbelt', 'focusband', 'focussash', 'laggingtail', 'leftovers', 'mentalherb',
            'metalpowder', 'muscleband', 'powerherb', 'quickpowder', 'reapercloth', 'redcard', 'ringtarget',
            'shedshell', 'silkscarf', 'silverpowder', 'smoothrock', 'softsand', 'soothebell', 'whiteherb', 'widelens',
            'wiseglasses', 'zoomlens'):
                AttackerMovePower = 10
            elif BattlerStats[Attacker]['item'] in ('eviolite', 'icyrock', 'luckypunch'):
                AttackerMovePower = 40
            elif BattlerStats[Attacker]['item'] in ('dubiousdisc', 'sharpbeak'):
                AttackerMovePower = 50
            elif BattlerStats[Attacker]['item'] in (
            'adamantorb', 'damprock', 'griseousorb', 'heatrock', 'lustrousorb', 'machobrace', 'rockyhelmet', 'stick'):
                AttackerMovePower = 60
            elif BattlerStats[Attacker]['item'] in (
            'dragonfang', 'poisonbarb', 'poweranklet', 'powerband', 'powerbelt', 'powerbracer', 'powerlens',
            'powerweight'):
                AttackerMovePower = 70
            elif BattlerStats[Attacker]['item'] in (
            'assaultvest', 'dawnstone', 'duskstone', 'electirizer', 'magmarizer', 'oddkeystone', 'ovalstone',
            'protector', 'quickclaw', 'razorclaw', 'shinystone', 'stickybarb'):
                AttackerMovePower = 80
            elif BattlerStats[Attacker]['item'] in (
            'deepseatooth', 'gripclaw', 'thickclub', 'dracoplate', 'dreadplate', 'earthplate', 'fistplate',
            'flameplate', 'icicleplate', 'insectplate', 'ironplate', 'meadowplate', 'mindplate', 'pixieplate',
            'skyplate', 'splashplate', 'spookyplate', 'stoneplate', 'toxicplate', 'zapplate'):
                AttackerMovePower = 90
            elif BattlerStats[Attacker]['item'] in (
            'helixfossil', 'domefossil', 'oldamber', 'rootfossil', 'clawfossil', 'skullfossil', 'armorfossil',
            'coverfossil', 'plumefossil', 'jawfossil', 'sailfossil'):
                AttackerMovePower = 100
            elif BattlerStats[Attacker]['item'] == 'ironball':
                AttackerMovePower = 130
        elif AttackerMoveName == 'naturalgift':
            AttackerMoveType = 'normal'
            AttackerMovePower = 0
            if BattlerStats[Attacker]['item'] in self._NaturalGift:
                AttackerMoveType = self._NaturalGift[BattlerStats[Attacker]['item']][0]
                AttackerMovePower = self._NaturalGift[BattlerStats[Attacker]['item']][1] / 2
        elif AttackerMoveName == 'facade' and BattlerStats[Attacker]['item'] in ('flameorb', 'toxicorb'):
            AttackerMovePower *= 2
        # altered for accuracy
        elif AttackerMoveName in ('reversal', 'flail'):
            if AttackerCurrentHP >= 0.71 and AttackerCurrentHP <= 1:
                AttackerMovePower = 5
            elif AttackerCurrentHP >= 0.36 and AttackerCurrentHP < 0.71:
                AttackerMovePower = 20
            elif AttackerCurrentHP >= 0.21 and AttackerCurrentHP < 0.36:
                AttackerMovePower = 60
            elif AttackerCurrentHP >= 0.11 and AttackerCurrentHP < 0.21:
                AttackerMovePower = 80
            elif AttackerCurrentHP >= 0.5 and AttackerCurrentHP < 0.11:
                AttackerMovePower = 125
            elif AttackerCurrentHP < 0.5:
                AttackerMovePower = 150
        elif AttackerMoveName in ('waterspout', 'eruption'):
            AttackerMovePower = 150 * round(
                BattlerStats[Attacker]['hp'] * AttackerCurrentHP / BattlerStats[Attacker]['hp'])
        elif AttackerMoveName in ('crushgrip', 'wringout'):
            AttackerMovePower = 1 + 120 * round(
                BattlerStats[Defender]['hp'] * DefenderCurrentHP / BattlerStats[Defender]['hp'])
        elif AttackerMoveName == 'brine' and DefenderCurrentHP <= 0.5:
            AttackerMovePower *= 2
        elif AttackerMoveName in ('lowkick', 'grassknot'):
            if self._PokemonWeight[PokemonData[Defender]['species']['id']] < 10:
                AttackerMovePower = 20
            elif self._PokemonWeight[PokemonData[Defender]['species']['id']] < 25:
                AttackerMovePower = 40
            elif self._PokemonWeight[PokemonData[Defender]['species']['id']] < 50:
                AttackerMovePower = 60
            elif self._PokemonWeight[PokemonData[Defender]['species']['id']] < 100:
                AttackerMovePower = 80
            elif self._PokemonWeight[PokemonData[Defender]['species']['id']] < 200:
                AttackerMovePower = 100
            else:
                AttackerMovePower = 120

        # pre-calc abilities
        if BattlerStats[Attacker]['ability'] == 'technician':
            if AttackerMovePower <= 60:
                AttackerMovePower = AttackerMovePower * 1.5
        if BattlerStats[Attacker]['ability'] == 'normalize':
            AttackerMoveType = 'normal'

        # stab
        if AttackerMoveType == AttackerType[0] or AttackerMoveType == AttackerType[1]:
            AttackerMovePower = AttackerMovePower * 1.5
        if PokemonData[Attacker]['moves'][moveset2]['power'] < AttackerMovePower:
            if BattlerStats[Attacker]['ability'] == 'adaptability':
                AttackerMovePower = PokemonData[Attacker]['moves'][moveset2]['power'] * 2

        # categories
        if AttackerMoveCategory.lower() == 'status':
            AttackerMovePower = 0
        if AttackerMoveCategory.lower() == 'physical':
            DamageD = ((((0.84 * (
            BattlerStats[Attacker]['atk'] / BattlerStats[Defender]['def']) * AttackerMovePower) + 2) * 0.86) /
                       BattlerStats[Defender]['hp'])
        else:
            DamageD = ((((0.84 * (
            BattlerStats[Attacker]['satk'] / BattlerStats[Defender]['sdef']) * AttackerMovePower) + 2) * 0.86) /
                       BattlerStats[Defender]['hp'])

        # if attacking pokemon's ability is moldbreaker, temporarily ignore defending mon's ability
        effmulti = 1
        TempDefenderAbility = BattlerStats[Defender]['ability']
        if BattlerStats[Attacker]['ability'] == 'moldbreaker':
            TempDefenderAbility = 'moldbreaker'
        effmulti = self.getEff(AttackerMoveType, DefenderType[0], TempDefenderAbility) * self.getEff(AttackerMoveType,
                                                                                                     DefenderType[1],
                                                                                                     TempDefenderAbility)

        # special abilities/items based off effectiveness
        if TempDefenderAbility == 'wonderguard' and effmulti < 2:
            effmulti = 0
        if BattlerStats[Attacker]['ability'] == 'tintedlens' and effmulti < 1:
            effmulti *= 2
        if BattlerStats[Attacker]['item'] == 'expertbelt' and effmulti >= 2:
            effmulti *= 1.2

        # item boosts
        if BattlerStats[Attacker]['item'] in self._TypeBoostItem:
            if AttackerMoveType == self._TypeBoostItem[BattlerStats[Attacker]['item']]:
                DamageD *= 1.20

        if BattlerStats[Attacker]['item'] == 'adamantorb' and PokemonData[Attacker]['species'][
            'id'] == 483 and AttackerMoveType in ('dragon', 'steel'):
            DamageD *= 1.20
        if BattlerStats[Attacker]['item'] == 'lustrousorb' and PokemonData[Attacker]['species'][
            'id'] == 484 and AttackerMoveType in ('dragon', 'water'):
            DamageD *= 1.20
        if BattlerStats[Attacker]['item'] == 'griseousorb' and PokemonData[Attacker]['species'][
            'id'] == 487 and AttackerMoveType in ('dragon', 'ghost'):
            DamageD *= 1.20
        if BattlerStats[Attacker]['item'] == 'lifeorb':
            DamageD *= 1.30
        if AttackerMoveCategory.lower() == 'physical':
            if BattlerStats[Attacker]['item'] == 'muscleband':
                DamageD *= 1.10
        else:
            if BattlerStats[Attacker]['item'] == 'wiseglasses':
                DamageD *= 1.10

        if BattlerStats[Defender]['item'] in self._BerryDamageReduction:
            if AttackerMoveType == self._BerryDamageReduction[BattlerStats[Defender]['item']]:
                DamageD *= 0.75
        if BattlerStats[Defender]['item'] == 'chilanberry' and AttackerMoveType == 'normal':
            DamageD *= 0.75

        # basic weather ability boosts
        if AttackerMoveType == 'fire' and (
                BattlerStats[Attacker]['ability'] == 'drought' or BattlerStats[Defender]['ability'] == 'drought'):
            DamageD *= 1.5
        if AttackerMoveType == 'water' and (
                BattlerStats[Attacker]['ability'] == 'drizzle' or BattlerStats[Defender]['ability'] == 'drizzle'):
            DamageD *= 1.5
        if AttackerMoveType == 'water' and (
                BattlerStats[Attacker]['ability'] == 'drought' or BattlerStats[Defender]['ability'] == 'drought'):
            DamageD *= 0.5
        if AttackerMoveType == 'fire' and (
                BattlerStats[Attacker]['ability'] == 'drizzle' or BattlerStats[Defender]['ability'] == 'drizzle'):
            DamageD *= 0.5

        # crit consideration
        if BattlerStats[Defender]['ability'] not in ('shellarmor', 'battlearmor'):
            critmodifier = 0
            if BattlerStats[Attacker]['item'] in ('scopelens', 'razorclaw'):
                critmodifier = 1
            elif BattlerStats[Attacker]['item'] == 'luckypunch' and PokemonData[Attacker]['species']['id'] == 113:
                critmodifier = 2
            elif BattlerStats[Attacker]['item'] == 'stick' and PokemonData[Attacker]['species']['id'] == 83:
                critmodifier = 2
            if BattlerStats[Attacker]['ability'] == 'superluck':
                critmodifier += 1
            if AttackerMoveName in (
            'aeroblast', 'aircutter', 'blazekick', 'crosspoison', 'leafblade', 'crabhammer', 'nightslash', 'psychocut',
            'crosschop', 'karatechop', 'razorleaf', 'shadowclaw', 'slash', 'skyattack', 'razorwind', 'attackorder',
            'spacialrend', 'stoneedge'):
                critmodifier += 1
            critdamage = 2
            if BattlerStats[Attacker]['ability'] == 'sniper':
                critdamage = 3
            DamageD = (DamageD * (1 - self._critmultipliers[critmodifier])) + (
            DamageD * critdamage * self._critmultipliers[critmodifier])

        # accuracy
        if AttackerMoveAccuracy < 101 and BattlerStats[Defender]['ability'] != 'noguard' and BattlerStats[Attacker][
            'ability'] != 'noguard':
            DamageD *= (AttackerMoveAccuracy / 100)

        # flinch probability
        if BattlerStats[Defender]['item'] in ('razorfang', 'kingsrock') and BattlerStats[Defender]['speed'] > \
                BattlerStats[Attacker]['speed']:
            DamageD *= 0.9
        # bad berry return damage consideration
        if BattlerStats[Defender]['item'] == 'jabocaberry' and AttackerMoveCategory.lower() == 'physical':
            DamageD *= 0.9
        if BattlerStats[Defender]['item'] == 'rowapberry' and AttackerMoveCategory.lower() == 'special':
            DamageD *= 0.9
        if effmulti > 1 and BattlerStats[Defender]['item'] == 'enigmaberry':
            DamageD *= 0.9

        DamageD *= effmulti

        # ohko
        if AttackerMoveName in ('horndrill', 'sheercold', 'fissure', 'guillotine') and (
            BattlerStats[Defender]['ability'] != 'sturdy'):
            DamageD = (DefenderCurrentHP / 3) + 0.01
        # no guard special cases
        if BattlerStats[Defender]['ability'] == 'noguard' or BattlerStats[Attacker]['ability'] == 'noguard':
            if AttackerMoveName in ('horndrill', 'sheercold', 'fissure', 'guillotine'):
                DamageD = 1
            # If no guard exists - turn the two turn invulnerable moves (dig,dive,fly,etc) into two turn vulnerable moves
            if AttackerMoveName in ('fly', 'dive', 'dig', 'bounce', 'shadowforce'):
                DamageD = DamageD / 2

        if AttackerMoveName == 'endeavor':
            DamageD = (
            ((DefenderCurrentHP * BattlerStats[Defender]['hp']) - (BattlerStats[Attacker]['hp'] * AttackerCurrentHP)) /
            BattlerStats[Defender]['hp'])

        # reckless
        if AttackerMoveName in (
        'takedown', 'doubleedge', 'submission', 'volttackle', 'flareblitz', 'bravebird', 'woodhammer', 'headsmash',
        'bravebird') and BattlerStats[Attacker]['ability'] == 'reckless':
            DamageD *= 1.2

        # static damage moves
        if (AttackerMoveName == 'seismictoss') or (AttackerMoveName == 'nightshade') or (AttackerMoveName == 'psywave'):
            DamageD = 100 / BattlerStats[Defender]['hp']
        if AttackerMoveName == 'dragonrage':
            DamageD = 40 / BattlerStats[Defender]['hp']
        if AttackerMoveName == 'sonicboom':
            DamageD = 20 / BattlerStats[Defender]['hp']
        if AttackerMoveName == 'superfang':
            DamageD = DefenderCurrentHP / 2

        # if for whatever reason DamageD still equals something and the type muliplier is less than 1/4, set DamageD to 0
        if effmulti < 0.125:
            DamageD = 0

        # toxic
        if AttackerMoveName == 'toxic':
            DamageD = 0.21

        # weather damage
        if (BattlerStats[Attacker]['ability'] == 'sandstream' or BattlerStats[Defender][
            'ability'] == 'sandstream') and (
                DefenderType[0] not in ('rock', 'steel', 'ground') or DefenderType[1] not in (
        'rock', 'steel', 'ground')):
            DamageD += 0.0625
        if (BattlerStats[Attacker]['ability'] == 'snowwarning' or BattlerStats[Defender][
            'ability'] == 'snowwarning') and (DefenderType[0] != 'ice' or DefenderType[1] != 'ice'):
            DamageD += 0.0625

        # Curse
        if AttackerMoveName == 'curse':
            if AttackerType[0] == 'ghost' or AttackerType[1] == 'ghost':
                DamageD = 0.24

        # wonderguard special cases
        if BattlerStats[Defender]['ability'] == 'wonderguard':
            if AttackerMoveName in ('willowisp', 'poisonpowder', 'supersonic', 'perishsong'):
                DamageD = 0.34
            if AttackerMoveName in (
            'sandstorm', 'hail', 'confuseray', 'swagger', 'worryseed', 'toxic', 'gastroacid', 'nightmare', 'leechseed',
            'teeterdance'):
                DamageD = 0.51
            if AttackerMoveName == 'metronome':
                DamageD = 0.26
            if BattlerStats[Attacker]['item'] in ('jabocaberry', 'rowapberry', 'stickybarb') or BattlerStats[Attacker][
                'ability'] in ('flamebody', 'effectspore', 'roughskin', 'poisonpoint',):
                # [physical, special]
                WonderCount = [0, 0]
                for moveset in range(0, len(PokemonData[Defender]['moves'])):
                    if PokemonData[Defender]['moves'][moveset]['category'] == 'Physical':
                        WonderCount[0] += 1
                    elif PokemonData[Defender]['moves'][moveset]['category'] == 'Special':
                        WonderCount[1] += 1
                if WonderCount[0] + WonderCount[1] != 0:
                    if BattlerStats[Attacker]['item'] in ('jabocaberry', 'stickybarb') or BattlerStats[Attacker][
                        'ability'] == 'roughskin':
                        DamageD = (WonderCount[0] / (WonderCount[0] + WonderCount[1])) ** 2
                    if BattlerStats[Attacker]['item'] == 'rowapberry':
                        DamageD = (WonderCount[1] / (WonderCount[0] + WonderCount[1])) ** 2
                    if BattlerStats[Attacker]['ability'] in ('flamebody', 'poisonpoint'):
                        DamageD = ((WonderCount[0] / (WonderCount[0] + WonderCount[1])) ** 2) * 0.3
                    if BattlerStats[Attacker]['ability'] == 'effectspore':
                        DamageD = ((WonderCount[0] / (WonderCount[0] + WonderCount[1])) ** 2) * 0.1

        if BattlerStats[Defender]['ability'] == 'soundproof' and AttackerMoveName in (
        'hypervoice', 'bugbuzz', 'snore', 'chatter'):
            DamageD = 0

        if DamageD == 1 and BattlerStats[Defender]['item'] == 'focussash':
            DamageD = 0.99

        # who am i doing this for?
        if Attacker < self._NmbBlumons:
            dmg[moveset2] = DamageD
        if Attacker > self._NmbBlumons - 1:
            dmg[4 + moveset2] = DamageD
        return (dmg)

    def Core_Fight(self, PokemonData):
        """
        Arguments:
                PokemonData:
                    All the data for all pokemon in the match

        Returns:
                batper:
                    Value of the individual pokemon, used to calculate balance
        """
        BattlerStats = {}
        CurrentHp = []
        StatBonus = []
        batper = []
        for allmons in range(0, len(PokemonData)):
            # setup hp percents of both teams(100% == 1)
            CurrentHp.append(1)
            # set up BattlerStats
            BattlerStats[allmons] = {}
            StatBonus.append({})
            StatBonus[allmons] = {'atk': 0, 'def': 0, 'satk': 0, 'sdef': 0, 'speed': 0}
            # prevents dividing by 0
            batper.append(10)
            # intial item set up
            BattlerStats[allmons]['item'] = 'none'
            if PokemonData[allmons]['item']['name'] is not None:
                BattlerStats[allmons]['item'] = PokemonData[allmons]['item']['name'].lower().replace(' ', '')
            BattlerStats[allmons]['ability'] = 'none'
            if PokemonData[allmons]['ability']['name'] is not None:
                BattlerStats[allmons]['ability'] = PokemonData[allmons]['ability']['name'].lower().replace(' ', '')
        CurrentRedMon = self._NmbBlumons
        error = ''
        self._badturns = False
        RedIntimidated = False
        BluIntimidated = False
        RechargeBlu = False
        RechargeRed = False
        for blumons in range(0, self._NmbBlumons):
            for redmons in range(CurrentRedMon, len(PokemonData)):
                DeadMon = False
                FightTurns = 0
                # super ditto calc
                for allmons in (blumons, redmons):
                    if PokemonData[allmons]['species']['id'] == 132:
                        if allmons == blumons:
                            EnemyMon = redmons
                        else:
                            EnemyMon = blumons
                        # figures out stats for all mons in the theoretical match
                        for tempx in (blumons, redmons):
                            BattlerStats[tempx]['hp'] = PokemonData[tempx]['stats']['hp']
                            BattlerStats[tempx]['atk'] = PokemonData[tempx]['stats']['atk'] * self._statmultipliers[
                                StatBonus[tempx]['atk'] + 6]
                            BattlerStats[tempx]['def'] = PokemonData[tempx]['stats']['def'] * self._statmultipliers[
                                StatBonus[tempx]['def'] + 6]
                            BattlerStats[tempx]['satk'] = PokemonData[tempx]['stats']['spA'] * self._statmultipliers[
                                StatBonus[tempx]['satk'] + 6]
                            BattlerStats[tempx]['sdef'] = PokemonData[tempx]['stats']['spD'] * self._statmultipliers[
                                StatBonus[tempx]['sdef'] + 6]
                            BattlerStats[tempx]['speed'] = PokemonData[tempx]['stats']['spe'] * self._statmultipliers[
                                StatBonus[tempx]['speed'] + 6]

                            # "important" abilities that effect stats
                            if BattlerStats[tempx]['ability'] == 'hugepower':
                                BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 2)
                            if BattlerStats[tempx]['ability'] == 'purepower':
                                BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 2)
                            if BattlerStats[tempx]['ability'] == 'hustle':
                                BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 1.25)
                            if BattlerStats[tempx]['ability'] == 'speedboost':
                                BattlerStats[tempx]['speed'] = round(BattlerStats[tempx]['speed'] * 1.7)
                            if BattlerStats[tempx]['ability'] == 'slowstart':
                                BattlerStats[tempx]['speed'] = round(BattlerStats[tempx]['speed'] * 0.5)
                                BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 0.5)
                            if BattlerStats[tempx]['ability'] == 'truant':
                                BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 0.5)
                                BattlerStats[tempx]['satk'] = round(BattlerStats[tempx]['satk'] * 0.5)
                        DittoAttacked = False
                        if PokemonData[allmons]['stats']['spe'] < PokemonData[EnemyMon]['stats']['spe']:
                            DittoAttacked = True
                            dmg = [0, 0, 0, 0, 0, 0, 0, 0]
                            move = ['', '', '', '', '', '', '', '']
                            for moveset in range(0, len(PokemonData[EnemyMon]['moves'])):
                                move[moveset] = PokemonData[EnemyMon]['moves'][moveset]['name'].lower().replace(' ',
                                                                                                                '').replace(
                                    '-', '')
                                dmg = self.DamageDealt(EnemyMon, allmons, moveset, PokemonData, BattlerStats, dmg,
                                                       CurrentHp[EnemyMon], CurrentHp[allmons])
                            BestMoveDamage = []
                            for tempx in range(0, len(PokemonData)):
                                BestMoveDamage.append(-1)
                            for moveset in range(0, len(PokemonData[EnemyMon]['moves'])):
                                if dmg[moveset] > BestMoveDamage[EnemyMon]:
                                    BestMoveDamage[EnemyMon] = dmg[moveset]
                            CurrentHp[allmons] -= BestMoveDamage[EnemyMon]
                        DittoItem = 'none'
                        if PokemonData[allmons]['item']['name'] is not None:
                            DittoItem = PokemonData[allmons]['item']['name'].lower().replace(' ', '').replace("'", '')
                        PokemonData[allmons] = copy.deepcopy(PokemonData[EnemyMon])
                        PokemonData[allmons]['item']['name'] = DittoItem
                        PokemonData[allmons]['displayname'] = 'ditto(' + PokemonData[EnemyMon]['displayname'] + ')'
                        if not DittoAttacked:
                            dmg = [0, 0, 0, 0, 0, 0, 0, 0]
                            move = ['', '', '', '', '', '', '', '']
                            for moveset in range(0, len(PokemonData[EnemyMon]['moves'])):
                                move[moveset] = PokemonData[EnemyMon]['moves'][moveset]['name'].lower().replace(' ',
                                                                                                                '').replace(
                                    '-', '')
                                dmg = self.DamageDealt(EnemyMon, allmons, moveset, PokemonData, BattlerStats, dmg,
                                                       CurrentHp[EnemyMon], CurrentHp[allmons])
                            BestMoveDamage = []
                            for tempx in range(0, len(PokemonData)):
                                BestMoveDamage.append(-1)
                            for moveset in range(0, len(PokemonData[EnemyMon]['moves'])):
                                if dmg[moveset] > BestMoveDamage[EnemyMon]:
                                    BestMoveDamage[EnemyMon] = dmg[moveset]
                            CurrentHp[allmons] -= BestMoveDamage[EnemyMon]
                # stats up calcs
                for allmons in (blumons, redmons):
                    if allmons == blumons:
                        EnemyMon = redmons
                    else:
                        EnemyMon = blumons
                    for moveset in range(0, len(PokemonData[allmons]['moves'])):
                        TempType = ['', 'none']
                        TempType[0] = PokemonData[allmons]['species']['types'][0].lower()
                        if len(PokemonData[allmons]['species']['types']) == 2:
                            TempType[1] = PokemonData[allmons]['species']['types'][1].lower()
                        TempMoveName = PokemonData[allmons]['moves'][moveset]['name'].lower().replace(' ', '').replace(
                            '-', '')
                        if TempMoveName in (
                        'howl', 'meditate', 'sharpen', 'growth', 'nastyplot', 'swordsdance', 'tailglow', 'defensecurl',
                        'withdraw', 'harden', 'acidarmor', 'barrier', 'irondefense', 'defendorder', 'cosmicpower',
                        'stockpile', 'amnesia', 'calmmind', 'bulkup', 'dragondance', 'rockpolish', 'agility',
                        'heartswap') or (TempMoveName == 'curse' and 'ghost' not in TempType):
                            for tempx in (blumons, redmons):
                                BattlerStats[tempx]['hp'] = PokemonData[tempx]['stats']['hp']
                                BattlerStats[tempx]['atk'] = PokemonData[tempx]['stats']['atk'] * self._statmultipliers[
                                    StatBonus[tempx]['atk'] + 6]
                                BattlerStats[tempx]['def'] = PokemonData[tempx]['stats']['def'] * self._statmultipliers[
                                    StatBonus[tempx]['def'] + 6]
                                BattlerStats[tempx]['satk'] = PokemonData[tempx]['stats']['spA'] * \
                                                              self._statmultipliers[StatBonus[tempx]['satk'] + 6]
                                BattlerStats[tempx]['sdef'] = PokemonData[tempx]['stats']['spD'] * \
                                                              self._statmultipliers[StatBonus[tempx]['sdef'] + 6]
                                BattlerStats[tempx]['speed'] = PokemonData[tempx]['stats']['spe'] * \
                                                               self._statmultipliers[StatBonus[tempx]['speed'] + 6]

                                # "important" abilities that effect stats
                                if BattlerStats[tempx]['ability'] == 'hugepower':
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 2)
                                if BattlerStats[tempx]['ability'] == 'purepower':
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 2)
                                if BattlerStats[tempx]['ability'] == 'hustle':
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 1.25)
                                if BattlerStats[tempx]['ability'] == 'speedboost':
                                    BattlerStats[tempx]['speed'] = round(BattlerStats[tempx]['speed'] * 1.7)
                                if BattlerStats[tempx]['ability'] == 'slowstart':
                                    BattlerStats[tempx]['speed'] = round(BattlerStats[tempx]['speed'] * 0.5)
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 0.5)
                                if BattlerStats[tempx]['ability'] == 'truant':
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 0.5)
                                    BattlerStats[tempx]['satk'] = round(BattlerStats[tempx]['satk'] * 0.5)
                            dmg = [0, 0, 0, 0, 0, 0, 0, 0, 0]
                            for i in range(0, len(PokemonData[EnemyMon]['moves'])):
                                dmg = self.DamageDealt(EnemyMon, allmons, i, PokemonData, BattlerStats, dmg,
                                                       CurrentHp[EnemyMon], CurrentHp[allmons])
                            # [Blue move 1, 2, 3, 4, Red move 1, 2, 3, 4]
                            BestMoveDamage = []
                            for tempx in range(0, 8):
                                if dmg[tempx] == 0:
                                    dmg[tempx] = 0.01
                            for tempx in range(0, len(PokemonData)):
                                BestMoveDamage.append(-1)
                            for i in range(0, len(PokemonData[EnemyMon]['moves'])):
                                tempx = i
                                if EnemyMon == redmons:
                                    tempx = i + 4
                                if dmg[tempx] > BestMoveDamage[EnemyMon]:
                                    BestMoveDamage[EnemyMon] = dmg[tempx]
                            HaveSwagger = False
                            HaveFlatter = False
                            for i in range(0, len(PokemonData[allmons]['moves'])):
                                if PokemonData[allmons]['moves'][i]['name'].lower().replace(' ', '').replace('-',
                                                                                                             '') == 'swagger':
                                    HaveSwagger = True
                                if PokemonData[allmons]['moves'][i]['name'].lower().replace(' ', '').replace('-',
                                                                                                             '') == 'flatter':
                                    HaveFlatter = True
                            if (CurrentHp[allmons] / BestMoveDamage[EnemyMon]) > 4:
                                if TempMoveName == 'stockpile':  # stockpile
                                    StatBonus[allmons]['def'] += 1
                                    StatBonus[allmons]['sdef'] += 1
                                    if StatBonus[allmons]['def'] > 3:
                                        StatBonus[allmons]['def'] = 3
                                    if StatBonus[allmons]['sdef'] > 3:
                                        StatBonus[allmons]['sdef'] = 3
                                if TempMoveName == 'heartswap':
                                    if HaveSwagger:
                                        StatBonus[allmons]['atk'] += 1
                                    if HaveFlatter:
                                        StatBonus[allmons]['satk'] += 1
                                if TempMoveName in ('howl', 'meditate', 'sharpen'):  # attack stats +1
                                    StatBonus[allmons]['atk'] += 1
                                if TempMoveName == 'swordsdance':  # swords dance
                                    StatBonus[allmons]['atk'] += 2
                                if TempMoveName == 'growth':  # growth
                                    StatBonus[allmons]['satk'] += 1
                                if TempMoveName in ('nastyplot', 'tailglow'):  # attack stats +2
                                    StatBonus[allmons]['satk'] += 2
                                if TempMoveName in ('defensecurl', 'withdraw', 'harden'):  # defense +1
                                    StatBonus[allmons]['def'] += 1
                                if TempMoveName in ('acidarmor', 'barrier', 'irondefense'):  # defense +2
                                    StatBonus[allmons]['def'] += 2
                                if TempMoveName in ('defendorder', 'cosmicpower'):  # Both defenses +1
                                    StatBonus[allmons]['def'] += 1
                                    StatBonus[allmons]['sdef'] += 1
                                if TempMoveName == 'amnesia':  # special defense +2
                                    StatBonus[allmons]['atk'] += 1
                                if TempMoveName == 'calmmind':  # calmmind
                                    StatBonus[allmons]['atk'] += 1
                                    StatBonus[allmons]['sdef'] += 1
                                if TempMoveName == 'bulkup':  # bulkup
                                    StatBonus[allmons]['atk'] += 1
                                    StatBonus[allmons]['def'] += 1
                                if TempMoveName == 'dragondance':  # dragon dance
                                    StatBonus[allmons]['atk'] += 1
                                    StatBonus[allmons]['speed'] += 1
                                if TempMoveName in ('rockpolish', 'agility'):  # speed +2
                                    StatBonus[allmons]['speed'] += 2
                                if TempMoveName == 'curse' and 'ghost' not in TempType:
                                    StatBonus[allmons]['atk'] += 1
                                    StatBonus[allmons]['def'] += 1
                                    StatBonus[allmons]['speed'] -= 1
                            for temptext in ('atk', 'def', 'satk', 'sdef', 'speed'):
                                if StatBonus[allmons][temptext] > 6:
                                    StatBonus[allmons][temptext] = 6
                                if StatBonus[allmons][temptext] < -6:
                                    StatBonus[allmons][temptext] = -6
                # heal cancer check
                for allmons in (blumons, redmons):
                    if allmons == blumons:
                        EnemyMon = redmons
                    else:
                        EnemyMon = blumons
                    for moveset in range(0, len(PokemonData[allmons]['moves'])):
                        TempType = ['', 'none']
                        TempType[0] = PokemonData[allmons]['species']['types'][0].lower()
                        if len(PokemonData[allmons]['species']['types']) == 2:
                            TempType[1] = PokemonData[allmons]['species']['types'][1].lower()
                        TempMoveName = PokemonData[allmons]['moves'][moveset]['name'].lower().replace(' ', '').replace(
                            '-', '')
                        if TempMoveName in ('ingrain', 'aquaring'):
                            for moveset2 in range(0, len(PokemonData[allmons]['moves'])):
                                if PokemonData[allmons]['moves'][moveset2]['name'].lower().replace(' ', '').replace('-',
                                                                                                                    '') in (
                                'detect', 'protect'):
                                    TempMoveName = 'doubletime'
                        if TempMoveName == 'rest':
                            if BattlerStats[allmons]['ability'] == 'hydration':
                                for moveset2 in range(0, len(PokemonData[allmons]['moves'])):
                                    if PokemonData[allmons]['moves'][moveset2]['name'].lower().replace(' ', '').replace(
                                            '-', '') in ('raindance'):
                                        TempMoveName = 'oprest'
                            if BattlerStats[allmons]['ability'] == 'shedskin' or BattlerStats[allmons]['item'] in (
                            'lumberry', 'chestoberry'):
                                TempMoveName = 'recover'
                        if TempMoveName in (
                        'recover', 'morningsun', 'softboiled', 'rest', 'slackoff', 'roost', 'synthesis', 'milkdrink',
                        'healorder', 'ingrain', 'aquaring', 'moonlight', 'doubletime', 'oprest'):
                            for tempx in (blumons, redmons):
                                BattlerStats[tempx]['hp'] = PokemonData[tempx]['stats']['hp']
                                BattlerStats[tempx]['atk'] = PokemonData[tempx]['stats']['atk'] * self._statmultipliers[
                                    StatBonus[tempx]['atk'] + 6]
                                BattlerStats[tempx]['def'] = PokemonData[tempx]['stats']['def'] * self._statmultipliers[
                                    StatBonus[tempx]['def'] + 6]
                                BattlerStats[tempx]['satk'] = PokemonData[tempx]['stats']['spA'] * \
                                                              self._statmultipliers[StatBonus[tempx]['satk'] + 6]
                                BattlerStats[tempx]['sdef'] = PokemonData[tempx]['stats']['spD'] * \
                                                              self._statmultipliers[StatBonus[tempx]['sdef'] + 6]
                                BattlerStats[tempx]['speed'] = PokemonData[tempx]['stats']['spe'] * \
                                                               self._statmultipliers[StatBonus[tempx]['speed'] + 6]

                                # "important" abilities that effect stats
                                if BattlerStats[tempx]['ability'] == 'hugepower':
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 2)
                                if BattlerStats[tempx]['ability'] == 'purepower':
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 2)
                                if BattlerStats[tempx]['ability'] == 'hustle':
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 1.25)
                                if BattlerStats[tempx]['ability'] == 'speedboost':
                                    BattlerStats[tempx]['speed'] = round(BattlerStats[tempx]['speed'] * 1.7)
                                if BattlerStats[tempx]['ability'] == 'slowstart':
                                    BattlerStats[tempx]['speed'] = round(BattlerStats[tempx]['speed'] * 0.5)
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 0.5)
                                if BattlerStats[tempx]['ability'] == 'truant':
                                    BattlerStats[tempx]['atk'] = round(BattlerStats[tempx]['atk'] * 0.5)
                                    BattlerStats[tempx]['satk'] = round(BattlerStats[tempx]['satk'] * 0.5)
                            dmg = [0, 0, 0, 0, 0, 0, 0, 0, 0]
                            for i in range(0, len(PokemonData[allmons]['moves'])):
                                dmg = self.DamageDealt(allmons, EnemyMon, i, PokemonData, BattlerStats, dmg,
                                                       CurrentHp[allmons], CurrentHp[EnemyMon])
                            for i in range(0, len(PokemonData[EnemyMon]['moves'])):
                                dmg = self.DamageDealt(EnemyMon, allmons, i, PokemonData, BattlerStats, dmg,
                                                       CurrentHp[EnemyMon], CurrentHp[allmons])
                            BestMoveDamage = []
                            for tempx in range(0, 8):
                                if dmg[tempx] == 0:
                                    dmg[tempx] = 0.01
                            for tempx in range(0, len(PokemonData)):
                                BestMoveDamage.append(-1)
                            # enemy best move
                            for i in range(0, len(PokemonData[EnemyMon]['moves'])):
                                tempx = i
                                if EnemyMon == redmons:
                                    tempx = i + 4
                                if dmg[tempx] > BestMoveDamage[EnemyMon]:
                                    BestMoveDamage[EnemyMon] = dmg[tempx]
                            for i in range(0, len(PokemonData[EnemyMon]['moves'])):
                                tempx = i
                                if EnemyMon == redmons:
                                    tempx = i + 4
                                if dmg[tempx] > BestMoveDamage[EnemyMon]:
                                    BestMoveDamage[EnemyMon] = dmg[tempx]
                            # simplifies this section
                            if TempMoveName in (
                            'recover', 'morningsun', 'softboiled', 'slackoff', 'roost', 'synthesis', 'milkdrink',
                            'healorder', 'moonlight'):
                                HealingAmount = 0.51
                            if TempMoveName in ('ingrain', 'aquaring'):
                                HealingAmount = 0.07
                            if TempMoveName == 'rest':
                                HealingAmount = 0.34
                            if TempMoveName == 'oprest':
                                HealingAmount = 0.81
                            if TempMoveName == 'doubletime':
                                HealingAmount = 0.13
                            # Double Healers
                            for moveset2 in range(0, len(PokemonData[EnemyMon]['moves'])):
                                NoDamage = False
                                if PokemonData[EnemyMon]['moves'][moveset2]['name'].lower().replace(' ', '').replace(
                                        '-', '') in (
                                'recover', 'morningsun', 'softboiled', 'slackoff', 'roost', 'synthesis', 'milkdrink',
                                'healorder', 'moonlight'):
                                    if BestMoveDamage[allmons] < 0.51:
                                        NoDamage = True
                                if PokemonData[EnemyMon]['moves'][moveset2]['name'].lower().replace(' ', '').replace(
                                        '-', '') == 'rest':
                                    if BestMoveDamage[allmons] < 0.34:
                                        NoDamage = True
                                if PokemonData[EnemyMon]['moves'][moveset2]['name'].lower().replace(' ', '').replace(
                                        '-', '') in ('ingrain', 'aquaring'):
                                    if BestMoveDamage[allmons] < 0.07:
                                        NoDamage = True
                                if NoDamage is True:
                                    if BestMoveDamage[EnemyMon] < HealingAmount:
                                        self._matchdict['CancerChecks']['UseMatch'] = False
                                        self._matchdict['CancerChecks']['HealCancer'] = True
                                        # healer can't kill enemy non-healer quickly
                            if CurrentHp[EnemyMon] / BestMoveDamage[allmons] > TurnLimit:
                                tempx = (BestMoveDamage[EnemyMon] - HealingAmount)
                                if tempx <= 0:
                                    tempx = 0.001
                                # and enemy can't kill healer quickly
                                if CurrentHp[EnemyMon] / tempx > TurnLimit:
                                    self._matchdict['CancerChecks']['UseMatch'] = False
                                    self._matchdict['CancerChecks']['HealCancer'] = True
                stillAliveIterations = 0
                while DeadMon is False:
                    stillAliveIterations += 1
                    for allmons in range(0, len(PokemonData)):
                        if allmons < self._NmbBlumons:
                            EnemyMon = redmons
                        else:
                            EnemyMon = blumons
                        # figures out stats for all mons in the theoretical match
                        BattlerStats[allmons]['hp'] = PokemonData[allmons]['stats']['hp']
                        BattlerStats[allmons]['atk'] = PokemonData[allmons]['stats']['atk'] * self._statmultipliers[
                            StatBonus[allmons]['atk'] + 6]
                        BattlerStats[allmons]['def'] = PokemonData[allmons]['stats']['def'] * self._statmultipliers[
                            StatBonus[allmons]['def'] + 6]
                        BattlerStats[allmons]['satk'] = PokemonData[allmons]['stats']['spA'] * self._statmultipliers[
                            StatBonus[allmons]['satk'] + 6]
                        BattlerStats[allmons]['sdef'] = PokemonData[allmons]['stats']['spD'] * self._statmultipliers[
                            StatBonus[allmons]['sdef'] + 6]
                        BattlerStats[allmons]['speed'] = PokemonData[allmons]['stats']['spe'] * self._statmultipliers[
                            StatBonus[allmons]['speed'] + 6]

                        # "important" abilities that effect stats
                        if BattlerStats[allmons]['ability'] == 'hugepower':
                            BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 2)
                        if BattlerStats[allmons]['ability'] == 'purepower':
                            BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 2)
                        if BattlerStats[allmons]['ability'] == 'hustle':
                            BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 1.25)
                        if BattlerStats[allmons]['ability'] == 'speedboost':
                            BattlerStats[allmons]['speed'] = round(BattlerStats[allmons]['speed'] * 1.7)
                        if BattlerStats[allmons]['ability'] == 'slowstart':
                            BattlerStats[allmons]['speed'] = round(BattlerStats[allmons]['speed'] * 0.5)
                            BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 0.5)
                        if BattlerStats[allmons]['ability'] == 'truant':
                            BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 0.5)
                            BattlerStats[allmons]['satk'] = round(BattlerStats[allmons]['satk'] * 0.5)

                        # items that effect stats
                        if BattlerStats[allmons]['item'] == 'ironball':
                            HasFling = False
                            for moveset in range(0, len(PokemonData[allmons]['moves'])):
                                if PokemonData[allmons]['moves'][moveset]['name'].lower().replace(' ', '').replace('-',
                                                                                                                   '') == 'fling':
                                    HasFling = True
                            if not HasFling:
                                BattlerStats[allmons]['speed'] = round(BattlerStats[allmons]['speed'] * 0.5)
                        if BattlerStats[allmons]['item'] == 'stickybarb' and BattlerStats[allmons][
                            'ability'] != 'magicguard':
                            BattlerStats[allmons]['hp'] = round(BattlerStats[allmons]['hp'] * 0.8)

                        # if klutz, items dont count, cept for iron ball for some reason
                        if BattlerStats[allmons]['ability'] != 'klutz':
                            if BattlerStats[allmons]['item'] == 'choiceband':
                                BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 1.5)
                            if BattlerStats[allmons]['item'] == 'choicespecs':
                                BattlerStats[allmons]['satk'] = round(BattlerStats[allmons]['satk'] * 1.5)
                            if BattlerStats[allmons]['item'] == 'choicescarf':
                                BattlerStats[allmons]['speed'] = round(BattlerStats[allmons]['speed'] * 1.5)
                            if BattlerStats[allmons]['item'] in (
                            'machobrace', 'powerweight', 'powerbracer', 'powerbelt', 'powerlens', 'powerband',
                            'poweranklet'):
                                BattlerStats[allmons]['speed'] = round(BattlerStats[allmons]['speed'] * 0.5)

                            # pokemon Specific
                            if BattlerStats[allmons]['item'] == 'lightball' and PokemonData[allmons]['species'][
                                'id'] == 25:
                                BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 2)
                                BattlerStats[allmons]['satk'] = round(BattlerStats[allmons]['satk'] * 2)
                            if BattlerStats[allmons]['item'] == 'deepseascale' and PokemonData[allmons]['species'][
                                'id'] == 366:
                                BattlerStats[allmons]['sdef'] = round(BattlerStats[allmons]['sdef'] * 2)
                            if BattlerStats[allmons]['item'] == 'deepseatooth' and PokemonData[allmons]['species'][
                                'id'] == 366:
                                BattlerStats[allmons]['satk'] = round(BattlerStats[allmons]['satk'] * 2)
                            if BattlerStats[allmons]['item'] == 'metalpowder' and PokemonData[allmons]['species'][
                                'id'] == 132:
                                BattlerStats[allmons]['def'] = round(BattlerStats[allmons]['def'] * 2)
                                BattlerStats[allmons]['sdef'] = round(BattlerStats[allmons]['sdef'] * 2)
                            if BattlerStats[allmons]['item'] == 'quickpowder' and PokemonData[allmons]['species'][
                                'id'] == 132:
                                BattlerStats[allmons]['speed'] = round(BattlerStats[allmons]['speed'] * 2)
                            if BattlerStats[allmons]['item'] == 'thickclub' and PokemonData[allmons]['species'][
                                'id'] in (104, 105):
                                BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 2)
                            if BattlerStats[allmons]['item'] == 'souldew' and PokemonData[allmons]['species']['id'] in (
                            380, 381):
                                BattlerStats[allmons]['satk'] = round(BattlerStats[allmons]['satk'] * 2)
                                BattlerStats[allmons]['sdef'] = round(BattlerStats[allmons]['sdef'] * 2)

                            # Flame orb
                            FireCheck = False
                            ItemGone = False
                            PoisonSteelCheck = False
                            if PokemonData[allmons]['species']['types'][0].lower() != 'fire':
                                FireCheck = True
                            if len(PokemonData[allmons]['species']['types']) == 2:
                                if PokemonData[allmons]['species']['types'][1].lower() != 'fire':
                                    FireCheck = True
                            if PokemonData[allmons]['species']['types'][0].lower() in ('poison', 'steel'):
                                PoisonSteelCheck = True
                            if len(PokemonData[allmons]['species']['types']) == 2:
                                if PokemonData[allmons]['species']['types'][1].lower() in ('poison', 'steel'):
                                    PoisonSteelCheck = True
                            for moveset in range(0, len(PokemonData[allmons]['moves'])):
                                if PokemonData[allmons]['moves'][moveset]['name'] == 'fling' or (
                                            PokemonData[allmons]['moves'][moveset]['name'] in (
                                        'trick', 'switcheroo') and BattlerStats[EnemyMon]['ability'] not in (
                                    'stickyhold', 'multitype') and BattlerStats[EnemyMon]['item'] != 'griseousorb'):
                                    ItemGone = True
                            if BattlerStats[allmons]['item'] == 'flameorb' and BattlerStats[allmons][
                                'ability'] != 'waterveil' and FireCheck is False and ItemGone is False:
                                if BattlerStats[allmons]['ability'] == 'guts':
                                    BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 1.5)
                                else:
                                    BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 0.5)
                                if BattlerStats[allmons]['ability'] == 'quickfeet':
                                    BattlerStats[allmons]['speed'] = round(BattlerStats[allmons]['speed'] * 1.5)
                                elif BattlerStats[allmons]['ability'] == 'marvelscale':
                                    BattlerStats[allmons]['def'] = round(BattlerStats[allmons]['def'] * 1.5)
                            if BattlerStats[allmons][
                                'item'] == 'toxicorb' and PoisonSteelCheck is False and ItemGone is False:
                                if BattlerStats[allmons]['ability'] == 'guts':
                                    BattlerStats[allmons]['atk'] = round(BattlerStats[allmons]['atk'] * 1.5)
                                elif BattlerStats[allmons]['ability'] == 'quickfeet':
                                    BattlerStats[allmons]['speed'] = round(BattlerStats[allmons]['speed'] * 1.5)
                                elif BattlerStats[allmons]['ability'] == 'marvelscale':
                                    BattlerStats[allmons]['def'] = round(BattlerStats[allmons]['def'] * 1.5)

                            # Berries
                            if BattlerStats[allmons]['item'] == 'oranberry':
                                BattlerStats[allmons]['hp'] += 10
                            if BattlerStats[allmons]['item'] == 'sitrusberry':
                                BattlerStats[allmons]['hp'] = round(BattlerStats[allmons]['hp'] * 1.25)
                            if BattlerStats[allmons]['item'] == 'figyberry' and PokemonData[allmons]['nature'][
                                'name'].lower().replace(' ', '') not in ('bold', 'calm', 'modest', 'timid'):
                                BattlerStats[allmons]['hp'] = round(BattlerStats[allmons]['hp'] * 1.125)
                            if BattlerStats[allmons]['item'] == 'wikiberry' and PokemonData[allmons]['nature'][
                                'name'].lower().replace(' ', '') not in ('adamant', 'careful', 'impish', 'jolly'):
                                BattlerStats[allmons]['hp'] = round(BattlerStats[allmons]['hp'] * 1.125)
                            if BattlerStats[allmons]['item'] == 'magoberry' and PokemonData[allmons]['nature'][
                                'name'].lower().replace(' ', '') not in ('brave', 'quiet', 'relaxed', 'sassy'):
                                BattlerStats[allmons]['hp'] = round(BattlerStats[allmons]['hp'] * 1.125)
                            if BattlerStats[allmons]['item'] == 'aguavberry' and PokemonData[allmons]['nature'][
                                'name'].lower().replace(' ', '') not in ('lax', 'naive', 'naughty', 'rash'):
                                BattlerStats[allmons]['hp'] = round(BattlerStats[allmons]['hp'] * 1.125)
                            if BattlerStats[allmons]['item'] == 'iapapaberry' and PokemonData[allmons]['nature'][
                                'name'].lower().replace(' ', '') not in ('lonely', 'hasty', 'mild', 'gentle'):
                                BattlerStats[allmons]['hp'] = round(BattlerStats[allmons]['hp'] * 1.125)

                    # intimidate
                    if (BattlerStats[blumons]['ability'] == 'intimidate' and CurrentHp[blumons] == 1 and
                                BattlerStats[redmons]['ability'] not in (
                            'clearbody', 'hypercutter', 'whitesmoke')) or RedIntimidated is True:
                        RedIntimidated = True
                        BattlerStats[redmons]['atk'] = round(BattlerStats[redmons]['atk'] * 0.66)
                    if (BattlerStats[redmons]['ability'] == 'intimidate' and CurrentHp[redmons] == 1 and
                                BattlerStats[blumons]['ability'] not in (
                            'clearbody', 'hypercutter', 'whitesmoke')) or BluIntimidated is True:
                        BluIntimidated = True
                        BattlerStats[blumons]['atk'] = round(BattlerStats[blumons]['atk'] * 0.66)

                    # used for charging attacks [Blue move 1, 2, 3, 4, Red move 1, 2, 3, 4]
                    dmg = [0, 0, 0, 0, 0, 0, 0, 0]
                    move = ['', '', '', '', '', '', '', '']
                    for moveset in range(0, len(PokemonData[blumons]['moves'])):
                        move[moveset] = PokemonData[blumons]['moves'][moveset]['name'].lower().replace(' ', '').replace(
                            '-', '')
                        dmg = self.DamageDealt(blumons, redmons, moveset, PokemonData, BattlerStats, dmg,
                                               CurrentHp[blumons], CurrentHp[redmons])

                    for moveset in range(0, len(PokemonData[redmons]['moves'])):
                        move[moveset + 4] = PokemonData[redmons]['moves'][moveset]['name'].lower().replace(' ',
                                                                                                           '').replace(
                            '-', '')
                        dmg = self.DamageDealt(redmons, blumons, moveset, PokemonData, BattlerStats, dmg,
                                               CurrentHp[redmons], CurrentHp[blumons])
                    # [Blue move 1, 2, 3, 4, Red move 1, 2, 3, 4]
                    BestMoveDamage = []
                    for allmons in range(len(PokemonData)):
                        BestMoveDamage.append(-1)
                    bestblui = 0
                    bestredi = 0
                    for moveset in range(0, len(PokemonData[blumons]['moves'])):
                        if dmg[moveset] > BestMoveDamage[blumons]:
                            BestMoveDamage[blumons] = dmg[moveset]
                            bestblui = moveset
                            move[moveset] = PokemonData[blumons]['moves'][moveset]['name'].lower().replace(' ',
                                                                                                           '').replace(
                                '-', '')
                    for moveset in range(0, len(PokemonData[redmons]['moves'])):
                        if dmg[4 + moveset] > BestMoveDamage[redmons]:
                            BestMoveDamage[redmons] = dmg[4 + moveset]
                            bestredi = 4 + moveset
                            move[4 + moveset] = PokemonData[redmons]['moves'][moveset]['name'].lower().replace(' ',
                                                                                                               '').replace(
                                '-', '')

                    # if any move deals more than 100% damage, make it deal only 100%
                    if redmons != 5:
                        if BestMoveDamage[blumons] > 1:
                            BestMoveDamage[blumons] = 1
                        if BestMoveDamage[blumons] > CurrentHp[redmons]:
                            BestMoveDamage[blumons] = CurrentHp[redmons] + (
                            (BestMoveDamage[blumons] - CurrentHp[redmons]) / 2)
                    if blumons != 2:
                        if BestMoveDamage[redmons] > 1:
                            BestMoveDamage[redmons] = 1
                        if BestMoveDamage[redmons] > CurrentHp[blumons]:
                            BestMoveDamage[redmons] = CurrentHp[blumons] + (
                            (BestMoveDamage[redmons] - CurrentHp[blumons]) / 2)

                    # if a pokemon would be killed before they could use a charging move, use a different move, foo
                    if move[bestblui] in (
                    'hyperbeam', 'gigaimpact', 'rockwrecker', 'blastburn', 'hydrocannon', 'frenzyplant', 'roaroftime',
                    'skullbash', 'skyattack', 'razorwind', 'solarbeam'):
                        if BattlerStats[blumons]['speed'] > BattlerStats[redmons]['speed'] and BestMoveDamage[
                            redmons] == 1:
                            BestMoveDamage[blumons] = 0
                            tempx = bestblui
                            for moveset in range(0, 4):
                                if dmg[moveset] > BestMoveDamage[blumons] and moveset != tempx:
                                    BestMoveDamage[blumons] = dmg[moveset]
                                    bestblui = moveset
                        if BattlerStats[blumons]['speed'] <= BattlerStats[redmons]['speed'] and BestMoveDamage[
                            redmons] >= 0.5:
                            BestMoveDamage[blumons] = 0
                            tempx = bestblui
                            for moveset in range(0, 4):
                                if dmg[moveset] > BestMoveDamage[blumons] and moveset != tempx:
                                    BestMoveDamage[blumons] = dmg[moveset]
                                    bestblui = moveset

                    if move[bestredi] in (
                    'hyperbeam', 'gigaimpact', 'rockwrecker', 'blastburn', 'hydrocannon', 'frenzyplant', 'roaroftime',
                    'skullbash', 'skyattack', 'razorwind', 'solarbeam'):
                        if BattlerStats[blumons]['speed'] < BattlerStats[redmons]['speed'] and BestMoveDamage[
                            blumons] == 1:
                            BestMoveDamage[redmons] = 0
                            tempx = bestredi
                            for moveset in range(0, 4):
                                if dmg[4 + moveset] > BestMoveDamage[redmons] and moveset != tempx:
                                    BestMoveDamage[redmons] = dmg[4 + moveset]
                                    bestredi = 4 + moveset
                        if BattlerStats[blumons]['speed'] >= BattlerStats[redmons]['speed'] and BestMoveDamage[
                            blumons] >= 0.5:
                            BestMoveDamage[redmons] = 0
                            tempx = bestredi
                            for moveset in range(0, 4):
                                if dmg[4 + moveset] > BestMoveDamage[redmons] and moveset != tempx:
                                    BestMoveDamage[redmons] = dmg[4 + moveset]
                                    bestredi = 4 + moveset

                    # Damage corrections
                    TwoTurnCheck = 1

                    # recharge turn moves (predamage)
                    if move[bestblui] in (
                    'hyperbeam', 'gigaimpact', 'rockwrecker', 'blastburn', 'hydrocannon', 'frenzyplant', 'roaroftime'):
                        BestMoveDamage[blumons] /= 0.59
                        TwoTurnCheck = 2
                    elif RechargeBlu:
                        RechargeBlu = False
                        BestMoveDamage[blumons]
                    if move[bestredi] in (
                    'hyperbeam', 'gigaimpact', 'rockwrecker', 'blastburn', 'hydrocannon', 'frenzyplant', 'roaroftime'):
                        BestMoveDamage[redmons] /= 0.59
                        TwoTurnCheck = 2
                        RechargeBlu = True
                        RechargeRed = True
                    elif RechargeRed:
                        RechargeRed = False
                        BestMoveDamage[redmons]

                    # Charging turn moves
                    if move[bestblui] in ('skullbash', 'skyattack', 'razorwind', 'solarbeam'):
                        BestMoveDamage[blumons] *= 2
                        CurrentHp[blumons] = CurrentHp[blumons] - BestMoveDamage[redmons]
                        batper[redmons] = batper[redmons] + BestMoveDamage[redmons] * 100
                        TwoTurnCheck = 2
                    if move[bestredi] in ('skullbash', 'skyattack', 'razorwind', 'solarbeam'):
                        BestMoveDamage[redmons] *= 2
                        CurrentHp[redmons] = CurrentHp[redmons] - BestMoveDamage[blumons]
                        batper[blumons] = batper[blumons] + BestMoveDamage[blumons] * 100
                        TwoTurnCheck = 2

                        # recoil moves
                    if move[bestblui] in (
                    'takedown', 'doubleedge', 'submission', 'volttackle', 'flareblitz', 'bravebird', 'woodhammer',
                    'headsmash') and BattlerStats[blumons]['ability'] != 'rockhead':
                        BestMoveDamage[blumons] *= 1.2
                    if move[bestredi] in (
                    'takedown', 'doubleedge', 'submission', 'volttackle', 'flareblitz', 'bravebird', 'woodhammer',
                    'headsmash') and BattlerStats[redmons]['ability'] != 'rockhead':
                        BestMoveDamage[redmons] *= 1.2

                    if BattlerStats[blumons]['item'] in ('laggingtail', 'fullincense'):
                        BattlerStats[blumons]['speed'] = BattlerStats[blumons]['speed'] / 100
                    if BattlerStats[redmons]['item'] in ('laggingtail', 'fullincense'):
                        BattlerStats[redmons]['speed'] = BattlerStats[redmons]['speed'] / 100

                    # code to figure out who wins in ideal conditions, blue faster
                    if BattlerStats[blumons]['speed'] > BattlerStats[redmons]['speed'] or (
                            BattlerStats[blumons]['item'] == 'quickclaw' and CurrentHp[blumons] == 1):
                        if CurrentHp[blumons] > 0:
                            CurrentHp[redmons] = CurrentHp[redmons] - BestMoveDamage[blumons]
                            batper[blumons] = batper[blumons] + BestMoveDamage[blumons] * 100
                        if CurrentHp[redmons] > 0:
                            CurrentHp[blumons] = CurrentHp[blumons] - BestMoveDamage[redmons]
                            batper[redmons] = batper[redmons] + BestMoveDamage[redmons] * 100
                    # same as above, just red is faster, and attacks first
                    if BattlerStats[blumons]['speed'] < BattlerStats[redmons]['speed'] or (
                            BattlerStats[redmons]['item'] == 'quickclaw' and CurrentHp[redmons] == 1):
                        if CurrentHp[redmons] > 0:
                            CurrentHp[blumons] = CurrentHp[blumons] - BestMoveDamage[redmons]
                            batper[redmons] = batper[redmons] + BestMoveDamage[redmons] * 100
                        if CurrentHp[blumons] > 0:
                            CurrentHp[redmons] = CurrentHp[redmons] - BestMoveDamage[blumons]
                            batper[blumons] = batper[blumons] + BestMoveDamage[blumons] * 100
                    # Speed tie
                    if BattlerStats[blumons]['speed'] == BattlerStats[redmons]['speed']:
                        CurrentHp[blumons] = CurrentHp[blumons] - BestMoveDamage[redmons]
                        CurrentHp[redmons] = CurrentHp[redmons] - BestMoveDamage[blumons]
                        batper[blumons] = batper[blumons] + BestMoveDamage[blumons] * 100
                        batper[redmons] = batper[redmons] + BestMoveDamage[redmons] * 100

                    if move[bestblui] not in ('horndrill', 'sheercold', 'fissure', 'guillotine') and move[
                        bestredi] not in ('horndrill', 'sheercold', 'fissure', 'guillotine'):
                        FightTurns += 1

                        # End of turn
                    for allmons in (blumons, redmons):
                        if allmons < self._NmbBlumons:
                            EnemyMon = redmons
                            BestTemp = bestblui
                        else:
                            BestTemp = bestredi - 4
                            EnemyMon = blumons
                        # item factor checks
                        PoisonSteelCheck = False
                        PoisonCheck = False
                        FireCheck = False
                        ItemGone = False
                        if PokemonData[allmons]['species']['types'][0].lower() == 'fire':
                            FireCheck = True
                        if len(PokemonData[allmons]['species']['types']) == 2:
                            if PokemonData[allmons]['species']['types'][1].lower() == 'fire':
                                FireCheck = True
                        if PokemonData[allmons]['species']['types'][0].lower() in ('poison', 'steel'):
                            PoisonSteelCheck = True
                        if len(PokemonData[allmons]['species']['types']) == 2:
                            if PokemonData[allmons]['species']['types'][1].lower() in ('poison', 'steel'):
                                PoisonSteelCheck = True
                        if PokemonData[allmons]['species']['types'][0].lower() == 'poison':
                            PoisonCheck = True
                        if len(PokemonData[allmons]['species']['types']) == 2:
                            if PokemonData[allmons]['species']['types'][1].lower() == 'poison':
                                PoisonCheck = True
                        for moveset in range(0, len(PokemonData[allmons]['moves'])):
                            if PokemonData[allmons]['moves'][moveset]['name'] == 'fling' or (
                                        PokemonData[allmons]['moves'][moveset]['name'] in ('trick', 'switcheroo') and
                                        BattlerStats[EnemyMon]['ability'] not in ('stickyhold', 'multitype') and
                                    BattlerStats[EnemyMon]['item'] != 'griseousorb') or BattlerStats[allmons][
                                'ability'] != 'klutz':
                                ItemGone = True
                        # end of turn items
                        if FightTurns > 1:
                            if BattlerStats[allmons]['item'] == 'flameorb' and BattlerStats[allmons][
                                'ability'] != 'waterveil' and FireCheck is False and ItemGone is False:
                                CurrentHp[allmons] -= 0.125 * TwoTurnCheck
                            if BattlerStats[allmons][
                                'item'] == 'toxicorb' and PoisonSteelCheck is False and ItemGone is False:
                                if BattlerStats[allmons]['ability'] == 'poisonheal' and CurrentHp[allmons] > 0:
                                    CurrentHp[allmons] += 0.125 * TwoTurnCheck
                                if BattlerStats[allmons]['ability'] == 'shedskin':
                                    CurrentHp[allmons] -= 0.10 * TwoTurnCheck
                                if BattlerStats[allmons]['ability'] != 'immunity':
                                    CurrentHp[allmons] -= (0.0625 * (FightTurns - 1)) + (
                                    (0.0625 * (FightTurns - 1)) * (TwoTurnCheck - 1))
                        if BattlerStats[allmons]['item'] == 'shellbell' and CurrentHp[allmons] > 0:
                            CurrentHp[allmons] = ((BattlerStats[allmons]['hp'] * CurrentHp[allmons]) + (
                            (0.125 * (BestMoveDamage[allmons] * BattlerStats[EnemyMon]['hp'])) * TwoTurnCheck)) / \
                                                 BattlerStats[allmons]['hp']
                        if BattlerStats[allmons]['item'] == 'lifeorb' and BattlerStats[allmons][
                            'ability'] != 'magicguard':
                            CurrentHp[allmons] -= 0.10 * TwoTurnCheck
                        if BattlerStats[allmons]['item'] == 'leftovers' or (
                                PoisonCheck is True and BattlerStats[allmons]['item'] == 'blacksludge') and CurrentHp[
                            allmons] > 0:
                            CurrentHp[allmons] += 0.0625 * TwoTurnCheck
                        if PoisonCheck is False and BattlerStats[allmons]['item'] == 'blacksludge':
                            CurrentHp[allmons] -= 0.125 * TwoTurnCheck
                        if PokemonData[allmons]['moves'][moveset]['name'] in (
                        'absorb', 'megadrain', 'gigadrain', 'drainpunch', 'leechlife'):
                            HPDrainHeal = ((BattlerStats[allmons]['hp'] * CurrentHp[allmons]) + (
                            (0.5 * (BestMoveDamage[allmons] * BattlerStats[EnemyMon]['hp'])) * TwoTurnCheck)) / \
                                          BattlerStats[allmons]['hp']
                            if BattlerStats[allmons]['item'] == 'bigroot':
                                HPDrainHeal = ((BattlerStats[allmons]['hp'] * CurrentHp[allmons]) + ((0.5 * (
                                BestMoveDamage[allmons] * BattlerStats[EnemyMon]['hp'])) * TwoTurnCheck * 1.3)) / \
                                              BattlerStats[allmons]['hp']
                            if BattlerStats[EnemyMon]['ability'] != 'liquidooze' and CurrentHp[allmons] > 0:
                                CurrentHp[allmons] += HPDrainHeal
                            if BattlerStats[EnemyMon]['ability'] == 'liquidooze':
                                CurrentHp[allmons] -= HPDrainHeal
                        if BattlerStats[EnemyMon]['ability'] == 'roughskin' and PokemonData[allmons]['moves'][BestTemp][
                            'category'] == 'physical':
                            CurrentHp[redmons] -= 0.125

                        if BattlerStats[allmons]['ability'] != 'rockhead':
                            if move[BestTemp] == 'headsmash':
                                CurrentHp[redmons] -= ((BattlerStats[allmons]['hp'] * CurrentHp[allmons]) + (
                                (0.5 * (BestMoveDamage[allmons] * BattlerStats[EnemyMon]['hp'])) * TwoTurnCheck)) / \
                                                      BattlerStats[allmons]['hp']
                            if move[BestTemp] in ('doubleedge', 'volttackle', 'flareblitz', 'bravebird', 'woodhammer'):
                                CurrentHp[redmons] -= ((BattlerStats[allmons]['hp'] * CurrentHp[allmons]) + (
                                (0.33 * (BestMoveDamage[allmons] * BattlerStats[EnemyMon]['hp'])) * TwoTurnCheck)) / \
                                                      BattlerStats[allmons]['hp']
                            if move[BestTemp] in ('takedown', 'submission'):
                                CurrentHp[redmons] -= ((BattlerStats[allmons]['hp'] * CurrentHp[allmons]) + (
                                (0.25 * (BestMoveDamage[allmons] * BattlerStats[EnemyMon]['hp'])) * TwoTurnCheck)) / \
                                                      BattlerStats[allmons]['hp']
                        if CurrentHp[allmons] > 1:
                            CurrentHp[allmons] = 1
                    BoostBonus = 1
                    # anti-infinity
                    # Kill the Pokemon instantly if this loops too many times.
                    # For ubers matches, which have a higher potential for cancer due to stall sets, the iterations
                    # typically range from 1-10.  In rare cases (~1%) extremely cancerous matches will iterate
                    # indefinitely, even with a decrease of 1% HP per iteration.
                    if stillAliveIterations < 50:
                        CurrentHp[blumons] -= 0.001
                        CurrentHp[redmons] -= 0.001
                    else:
                        CurrentHp[blumons] = 0
                        CurrentHp[redmons] = 0

                    if CurrentHp[blumons] <= 0:
                        RechargeBlu = False
                        DeadMon = True
                        batper[blumons] -= 0.0001
                    else:
                        TempType = ['', 'none']
                        TempType[0] = PokemonData[blumons]['species']['types'][0].lower()
                        if len(PokemonData[blumons]['species']['types']) == 2:
                            TempType[1] = PokemonData[blumons]['species']['types'][1].lower()
                        for moveset in range(0, len(PokemonData[blumons]['moves'])):
                            TempMoveName = PokemonData[blumons]['moves'][moveset]['name'].lower().replace(' ',
                                                                                                          '').replace(
                                '-', '')
                            if TempMoveName in ('howl', 'meditate', 'sharpen', 'growth'):  # attack stats +1
                                batper[blumons] += BoostBonus * 1
                            if TempMoveName in ('nastyplot', 'swordsdance', 'tailglow'):  # attack stats +2
                                batper[blumons] += BoostBonus * 7.5
                            if TempMoveName in ('defensecurl', 'withdraw', 'harden'):  # defense +1
                                batper[blumons] += BoostBonus * 1.2
                            if TempMoveName in ('acidarmor', 'barrier', 'irondefense'):  # defense +2
                                batper[blumons] += BoostBonus * 4
                            if TempMoveName in ('defendorder', 'cosmicpower'):  # Both defenses +1
                                batper[blumons] += BoostBonus * 3
                            if TempMoveName == 'stockpile':  # stockpile
                                batper[blumons] += BoostBonus * 1.2
                            if TempMoveName == 'amnesia':  # special defense +2
                                batper[blumons] += BoostBonus * 5
                            if TempMoveName == 'calmmind':  # calmmind
                                batper[blumons] += BoostBonus * 3
                            if TempMoveName == 'bulkup':  # bulkup
                                batper[blumons] += BoostBonus * 2.5
                            if TempMoveName == 'dragondance':  # dragon dance
                                batper[blumons] += BoostBonus * 4
                            if TempMoveName == 'acupressure':  # acupressure
                                batper[blumons] += BoostBonus * 9
                            if TempMoveName in ('rockpolish', 'agility'):  # speed +2
                                batper[blumons] += BoostBonus * 0.75
                            if TempMoveName == 'curse' and 'ghost' not in TempType:
                                batper[blumons] += BoostBonus * 3.25

                    if CurrentHp[redmons] <= 0:
                        RechargeRed = False
                        CurrentRedMon = CurrentRedMon + 1
                        DeadMon = True
                        batper[redmons] -= 0.0001
                    else:
                        TempType = ['', 'none']
                        TempType[0] = PokemonData[redmons]['species']['types'][0].lower()
                        if len(PokemonData[redmons]['species']['types']) == 2:
                            TempType[1] = PokemonData[redmons]['species']['types'][1].lower()
                        for moveset in range(0, len(PokemonData[redmons]['moves'])):
                            TempMoveName = PokemonData[redmons]['moves'][moveset]['name'].lower().replace(' ',
                                                                                                          '').replace(
                                '-', '')
                            if TempMoveName in ('howl', 'meditate', 'sharpen', 'growth'):  # attack stats +1
                                batper[redmons] += BoostBonus * 1
                            if TempMoveName in ('nastyplot', 'swordsdance', 'tailglow'):  # attack stats +2
                                batper[redmons] += BoostBonus * 7.5
                            if TempMoveName in ('defensecurl', 'withdraw', 'harden'):  # defense +1
                                batper[redmons] += BoostBonus * 1.2
                            if TempMoveName in ('acidarmor', 'barrier', 'irondefense'):  # defense +2
                                batper[redmons] += BoostBonus * 4
                            if TempMoveName in ('defendorder', 'cosmicpower'):  # Both defenses +1
                                batper[redmons] += BoostBonus * 3
                            if TempMoveName == 'stockpile':  # stockpile
                                batper[redmons] += BoostBonus * 1.2
                            if TempMoveName == 'amnesia':  # special defense +2
                                batper[redmons] += BoostBonus * 5
                            if TempMoveName == 'calmmind':  # calmmind
                                batper[redmons] += BoostBonus * 3
                            if TempMoveName == 'bulkup':  # bulkup
                                batper[redmons] += BoostBonus * 2.5
                            if TempMoveName == 'dragondance':  # dragon dance
                                batper[redmons] += BoostBonus * 4
                            if TempMoveName == 'acupressure':  # acupressure
                                batper[redmons] += BoostBonus * 9
                            if TempMoveName in ('rockpolish', 'agility'):  # speed +2
                                batper[redmons] += BoostBonus * 0.75
                            if TempMoveName == 'curse' and 'ghost' not in TempType:
                                batper[redmons] += BoostBonus * 3.25

                # End while
                RedIntimidated = False
                BluIntimidated = False
                self._matchdict['CancerChecks']['MatchTurns'] += FightTurns
                if FightTurns > self._matchdict['CancerChecks']['1v1HighestTurns']:
                    self._matchdict['CancerChecks']['1v1HighestTurns'] = FightTurns
                if CurrentHp[redmons] <= 0:
                    self._matchdict['MatchPrediction'].append('red died: ' + str(
                        PokemonData[blumons]['displayname'].replace("\u2642", "m").replace("\u2640", "f")) + ', ' + str(
                        bestblui) + '.' + str(move[bestblui]) + ' has killed ' + str(
                        PokemonData[redmons]['displayname'].replace("\u2642", "m").replace("\u2640", "f")) + ', ' + str(
                        bestredi - 4) + '.' + str(move[bestredi]) + ' in ' + str(
                        FightTurns) + ' turns with {0:6.2f}'.format(CurrentHp[blumons] * 100) + '% hp left')
                if CurrentHp[blumons] <= 0:
                    self._matchdict['MatchPrediction'].append('blue died: ' + str(
                        PokemonData[redmons]['displayname'].replace("\u2642", "m").replace("\u2640", "f")) + ', ' + str(
                        bestredi - 4) + '.' + str(move[bestredi]) + ' has killed ' + str(
                        PokemonData[blumons]['displayname'].replace("\u2642", "m").replace("\u2640", "f")) + ', ' + str(
                        bestblui) + '.' + str(move[bestblui]) + ' in ' + str(
                        FightTurns) + ' turns with {0:6.2f}'.format(CurrentHp[redmons] * 100) + '% hp left')
                # if blue lost, increase the for loop
                if CurrentHp[blumons] <= 0:
                    break
        return (batper)

    def analyze(self, BlueTeam, RedTeam, effectiveness='normal'):
        """
        This function Analyzes a match for TPP PBR of two teams of any number of pokemon as long as both teams have 1 pokemon

        Arguments:
                BlueTeam:
                    a list of pokemon data on the blue team
                RedTeam:
                    a list of pokemon data on the red team

        3v3EX: analyze([{blue_pokemon_data}, {blue_pokemon_data}, {blue_pokemon_data}], [{red_pokemon_data}, {red_pokemon_data}, {red_pokemon_data}])

        Returns a dict, structured like:
            {
                'Pokemon':
                    index order goes blue first, then red
                    [
                    'Team':
                        Team the pokemon is on, 'Red' or 'Blue'
                    'Value':
                        How valuable the pokemon is to their team
                    'Name':
                        Name of the pokemon
                    'Position':
                        What position on the team they are, 1 is the lead
                    'Notes':
                        'Unused': never fought, 'Useless': fought but didn't do anything, 'None': not one of the other variables, unused is bad, useless is fine. Ideally, the best match would have neither of these notes
                    ]
                'WinPercentage':
                    the chance that the 'Winner' wins, the closer this is to 50, the better, more balance the match is
                'CancerChecks':
                    {
                    'UselessMons':
                        True if any pokemon has this note. If true, UseMatch is False
                    'UnusedMons':
                        True if any pokemon has this note.
                    'MatchTurns':
                        the total number of turns a match will last.
                    '1v1HighestTurns':
                        the highest turn prediction in the 'MatchPrediction', if this is higher than TurnLimit, UseMatch is False
                    'UseMatch':
                        The analyzer's suggestion to use the match or not, based SOLELY on cancerchecks, true means the analyzer is fine with it.
                    'HealCancer':
                        If a mon with a healing move would make the match last long, this is set to true. If true, UseMatch is False
                    }
                'MatchPrediction':
                    [
                    Text indexed based on specific pokemon combinations, on what the analyzer thinks will happen, roughly
                    Example: '`team_of_killed_pokemon` died: `winner_pokemon_name`, `winner_best_move_index`.`winner_best_move_name` has killed `loser_pokemon_name`, `loser_best_move_index`.`loser_best_move_name` in  `length_of_1v1` turns with  `winner_percent_hp`% hp left'
                    ]
                'Winner':
                    Predicted Winner of the match, 'Red' or 'Blue'
            }
        """
        text = []
        winpere = []
        battlers = []
        passes = 0
        batnumber = []
        position = []
        self._effectiveness = effectiveness
        self._matchdict = {'Pokemon': [], 'CancerChecks': {'1v1HighestTurns': 0, 'MatchTurns': 0, 'UnusedMons': False,
                                                           'UselessMons': False, 'UseMatch': True, 'HealCancer': False},
                           'MatchPrediction': []}
        '''
        for i in range(random.randint(1,1)):
            BlueTeam.append(pokecat.generate_random_pokemon())
        for i in range(random.randint(1,1)):
            RedTeam.append(pokecat.generate_random_pokemon())'''
        self._NmbBlumons = len(BlueTeam)
        PokemonData = BlueTeam + RedTeam
        for i in range(len(PokemonData)):
            self._matchdict['Pokemon'].append({})
            self._matchdict['Pokemon'][i]['Notes'] = 'none'
            batnumber.append(-1)

        # match math
        UnusedMonError = 0
        # self.log.debug(PokemonData)
        batper = self.Core_Fight(PokemonData)

        # if any mon has a rating less than 0, make it 0.01 (this shouldn't happen, but a division by 0 could happen if it does)
        for allmons in range(len(PokemonData)):
            if batper[allmons] < 0:
                batper[allmons] = 0.01
            if batper[allmons] == 9.999:
                self._matchdict['CancerChecks']['UselessMons'] = True
                self._matchdict['Pokemon'][allmons]['Notes'] = 'Useless'
            if batper[allmons] == 10:
                self._matchdict['CancerChecks']['UnusedMons'] = True
                self._matchdict['Pokemon'][allmons]['Notes'] = 'Unused'
                self._matchdict['CancerChecks']['UseMatch'] = False
                batper[allmons] = 150
        if self._matchdict['CancerChecks']['1v1HighestTurns'] > TurnLimit:
            self._matchdict['CancerChecks']['UseMatch'] = False
        # figure out the average
        blueper = 0.00
        for allmons in range(0, self._NmbBlumons):
            blueper += batper[allmons]
        redper = 0.00
        for allmons in range(self._NmbBlumons, len(PokemonData)):
            redper += batper[allmons]

        if blueper > redper:
            winper = blueper / (blueper + redper) * 100
        if blueper < redper:
            winper = redper / (blueper + redper) * 100
        if blueper == redper:
            winper = 50

        goodmatch = False
        if self._badturns is True:
            goodmatch = False

        self.log.debug(winper)

        temptext = ''
        for allmons in range(0, len(PokemonData)):
            temptext = temptext + str(batper[allmons]) + ' '
            if allmons == len(BlueTeam) - 1:
                temptext = temptext + 'vs '
        self.log.debug(temptext)
        temptext = ''

        for allmons in range(0, len(PokemonData)):
            temptext = temptext + PokemonData[allmons]['displayname'] + ' '
            if allmons == len(BlueTeam) - 1:
                temptext = temptext + 'vs '

        for allmons in range(0, len(PokemonData)):
            self._matchdict['Pokemon'][allmons]['Team'] = 'Blue'
            tempx = allmons + 1
            if allmons >= self._NmbBlumons:
                tempx = allmons + 1 - self._NmbBlumons
                self._matchdict['Pokemon'][allmons]['Team'] = 'Red'
            self._matchdict['Pokemon'][allmons]['Position'] = tempx
            self._matchdict['Pokemon'][allmons]['Name'] = PokemonData[allmons]['displayname']
            self._matchdict['Pokemon'][allmons]['Value'] = batper[allmons]

        if blueper > redper:
            winper = blueper / (blueper + redper) * 100
            self.log.debug(temptext + '---' + str(winper) + '% blue wins')
            self._matchdict['Winner'] = 'blue'

        if blueper < redper:
            winper = redper / (blueper + redper) * 100
            self.log.debug(temptext + '---' + str(winper) + '% red wins')
            self._matchdict['Winner'] = 'red'

        if blueper == redper:
            winper = blueper / (blueper + redper) * 100
            self.log.debug(temptext + '---' + str(winper) + '% either wins')
            self._matchdict['Winner'] = 'either'

        self._matchdict['WinPercentage'] = winper
        self.log.debug(self._matchdict)
        return self._matchdict


def main():
    logging.basicConfig(level=logging.DEBUG)
    matchmaker = MatchMaker()
    while True:
        BlueTeam = []
        RedTeam = []
        whatever = matchmaker.analyze(BlueTeam, RedTeam)


if __name__ == '__main__':
    main()
