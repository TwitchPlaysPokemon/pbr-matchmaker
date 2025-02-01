# -*- coding: utf-8 -*-
# source code owned by Twitch Plays Pokemon AUTHORIZED USE ONLY see LICENSE.MD

import unicodedata
import random
from string import ascii_lowercase
from datetime import timedelta


def remove_diacritics(text):
    """
    Returns a string with all diacritics (aka non-spacing marks) removed.
    For example "Héllô" will become "Hello".
    Useful for comparing strings in an accent-insensitive fashion.
    """
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def genitive(name):
    if name[-1] == 's':
        return name + "'"
    return name + "'s"


vowels = tuple("aeiou")
consonants = tuple(set(ascii_lowercase) - set(vowels))

# avoid anything that might be used as a slur by malicious people
_blacklist = ("naz", "rape", "rapy", "nig", "neg", "fag", "jew", "jiz", "kike", "pedo", "tard", "jap", "coon")
_double_consonants = ("ch", "ck", "sh", "ng", "mp", "rd", "rt")
_ending_consonants = ("y", "s", "l", "f")


def generate_pronouncable_word():
    # 1) consonant
    # 2) vowel
    # 3) anything
    # 4) it depends, was 3) a vowel?
    #    yes: anything
    #    no: one of:
    #      - vowel
    #      - the same consonant again
    #      - one of a list of usually pronouncable consonants at the end of a word
    #      - one of a list of pronouncable consonants if part of a double consonant
    char1 = random.choice(consonants)
    char2 = random.choice(vowels)
    char3 = random.choice(ascii_lowercase)
    allowed_consonants = tuple(cc[1] for cc in _double_consonants if cc[0] == char3)
    char4 = random.choice(ascii_lowercase if char3 in vowels
                          else tuple(set(vowels + (char3,) + _ending_consonants + allowed_consonants)))
    word = char1 + char2 + char3 + char4
    if any(part in word for part in _blacklist):
        return generate_pronouncable_word()
    else:
        return word


def format_cooldown(seconds):
    """Takes seconds and turns it into a string of a form like 15h8m, 12m34s or 49s"""
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return "{}h{}m".format(hours, minutes)
    elif minutes:
        return "{}m{}s".format(minutes, seconds)
    else:
        return "{}s".format(seconds)


def format_duration(seconds_or_timedelta):
    """Takes some number of seconds or a timedelta and turns it into a string of a form like '7d', '12h', or '1w2d5h10m30s'"""
    if isinstance(seconds_or_timedelta, timedelta):
        seconds = int(seconds_or_timedelta.total_seconds())
    else:
        seconds = int(seconds_or_timedelta)
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    weeks, days = divmod(days, 7)
    duration_text = ""
    if weeks:
        duration_text += "%dw" % weeks
    if days:
        duration_text += "%dd" % days
    if hours:
        duration_text += "%dh" % hours
    if minutes:
        duration_text += "%dm" % minutes
    if seconds:
        duration_text += "%ds" % seconds
    return duration_text or "0s"


def stringify_list(lst, itemgetter=str, andify=True, separator=", "):
    """
    Nicely stringifies a list of things into a human-readable,
    comma-separated string.
    Arguments:
        itemgetter: function that retrieves a string representation for
                    for each item. Default is str()
        andify: whether the last element should be appended with "and" or not.
                Default is True.
        separator: specify an alternative to comma-separation.
    """
    if not list:
        return ""
    if andify:
        if len(lst) == 1:
            return str(itemgetter(lst[0]))
        s = separator.join(itemgetter(i) for i in lst[:-1])
        return s + " and " + itemgetter(lst[-1])
    else:
        return separator.join(itemgetter(i) for i in lst)


if __name__ == "__main__":
    for _ in range(300):
        print(generate_pronouncable_word(), end=", ")
