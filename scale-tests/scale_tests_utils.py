import itertools

# https://github.com/pytoolz/toolz/blob/c3a62944ea9502396f24ac68d3c70d954a368c9e/toolz/itertoolz.py#L468
def concat(seqs):
    """ Concatenate zero or more iterables, any of which may be infinite.
    An infinite sequence will prevent the rest of the arguments from
    being included.
    We use chain.from_iterable rather than ``chain(*seqs)`` so that seqs
    can be a generator.
    >>> list(concat([[], [1], [2, 3]]))
    [1, 2, 3]
    See also:
        itertools.chain.from_iterable  equivalent
    """
    return itertools.chain.from_iterable(seqs)


# https://github.com/pytoolz/toolz/blob/c3a62944ea9502396f24ac68d3c70d954a368c9e/toolz/itertoolz.py#L498
def mapcat(func, seqs):
    """ Apply func to each sequence in seqs, concatenating results.
    >>> list(mapcat(lambda s: [c.upper() for c in s],
    ...             [["a", "b"], ["c", "d", "e"]]))
    ['A', 'B', 'C', 'D', 'E']
    """
    return concat(map(func, seqs))


def normalize_string(s: str) -> str:
    return s.replace("/", "__").replace('-', '_')


def make_repeater(n):
    """Returns a lambda that returns a list (an iterable really) of `n` `x`s.

    >>> repeat_3 = make_repeater(3)
    >>> list(repeat_3('foo'))
    ['foo', 'foo', 'foo']
    >>> list(make_repeater(2)('bar'))
    ['bar', 'bar']
    """
    return lambda x: itertools.repeat(x, n)
