"""
python tpp/utils/matchmaker/selections.py
"""
from itertools import accumulate
from bisect import bisect
import random, logging

log = logging.getLogger(__name__)

def weighted_select(collection, raritygetter=lambda el,coll: coll[el]):
    """Select a random-weighted choice.

    Args:
        collection: Iterable collection of weighted objects.
        raritygetter: Obtains rarity of an element in the collection.

    Returns: An element in the collection.
    """
    elements = collection if isinstance(collection, list) else list(collection)
    weights = (raritygetter(el, collection) for el in elements)
    weights_accumulated = list(accumulate(weights))
    try:
        random_i = bisect(weights_accumulated, random.random() * weights_accumulated[-1])
        return elements[random_i]
    except LookupError:
        return None


def minimal_reoccurrence_selections(values, num_selections):
    """Make selections that look random but minimize value reoccurrence.

    selections returned are similar to:
    [random.choice(values) for _ in range(num_selections)]

    but with the guarantee that
    selections.count(x) <= selections.count(y) + 1
    for all x, y in values.

    Args:
        values: list of values to select from.
        num_selections: number of selections to make.

    Returns: list of selections.
    """
    if len(values) == 0:
        raise ValueError("No options were provided")

    temp_options = list(values)
    random.shuffle(temp_options)
    selections = []
    for _ in range(num_selections):
        if not temp_options:
            temp_options = list(values)
            random.shuffle(temp_options)
        option = temp_options.pop()
        selections.append(option)
    random.shuffle(selections)
    return selections


def main():
    # Weighted select.
    options = {
        ' ':    3.0,
        'a':    1.0,
        'rare': 0.1,
    }
    print('Weighted select:')
    for _ in range(5):
        print([weighted_select(options) for _ in range(30)])

    # Minimal reoccurrence selections.
    values = ['a', 'b', 'c', 'd']
    for i in range(1, 5):
        sub_values = values[:i]
        for j in range(0,7):
            print('Requesting {} selections from {}'.format(j, sub_values))
            selections = minimal_reoccurrence_selections(sub_values, j)
            print('Result: {}\n'.format(selections))
            for k in sub_values:
                for l in sub_values:
                    if selections.count(k) > selections.count(l) + 1:
                        raise ValueError()


if __name__ == '__main__':
    main()
