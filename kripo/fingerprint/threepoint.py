from intbitset import intbitset
from typing import List, Generator, Tuple

import pkg_resources

from .bitinfo import load_bitinfo
from .utils import calc_bins, bin_distance

"""Constants and methods for 3 point pharmacophore fingerprints"""

"""List of distance bin thresholds"""
BINS = calc_bins(fp_width=0.8, fp_multiplier=1, max_bins=20, max_distance=float(23))

"""Dictionary of that maps a 3 point pharmacophore to a fingerprint bit position

The key is a string formatted as `XYZabc`. Where `XYZ` are the pharmacophore type short names in alphabetical order
and where `abc` are the binned charified distances between the features in shortest distance first order.
The shortest bin distance gets char `a` and each next bin is the next char in the alphabet.
"""
BIT_INFO = load_bitinfo(pkg_resources.resource_filename('kripo', 'data/PHARMACKEY_3PFP_25BINS_6FEATURES_new.txt.bz2'))

"""Pharmacophore feature type name to fingerprint bit short name"""
FEATURE2BIT = {
    'LIPO': 'H',
    'POSC': 'P',
    'NEGC': 'N',
    'HDON': 'O',
    'HACC': 'A',
    'AROM': 'R'
}


def calculate_distance_matrix(ordered_features) -> List[List[float]]:
    """Calculate distances between list of features

    Args:
        ordered_features (List[Feature]):

    Returns:
        Where row/column list indices are same a ordered_features indices and
            value is the distance between the row and column feature
    """
    n = len(ordered_features)
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            dist = ordered_features[i].distance(ordered_features[j])
            row.append(dist)
        matrix.append(row)

    return matrix


def fuzzy_offsets(fuzzy_factor: int=1) -> Generator[Tuple[int, int, int], None, None]:
    """Generator for the fuzzy offsets

    Args:
        fuzzy_factor: The amount of fuzz to add. Special values:

        * -1, Offsets used by kripo v1
        * -2, Fuzz in one axis at a time

    Yields:
        The offsets as x, y, z coordinates
    """
    if fuzzy_factor >= 0:
        for i in range((0 - fuzzy_factor), fuzzy_factor + 1):
            for j in range((0 - fuzzy_factor), fuzzy_factor + 1):
                for k in range((0 - fuzzy_factor), fuzzy_factor + 1):
                    yield i, j, k
    elif fuzzy_factor == -1:
        theset = [(1, 2, 1), (1, 1, -1), (1, -1, -1), (1, 0, -1), (0, -1, -1), (-1, -1, -1), (1, 2, 0)]
        for i, j, k in theset:
            yield i, j, k
    elif fuzzy_factor == -2:
        theset = [(0, 0, 0), (-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1)]
        for i, j, k in theset:
            yield i, j, k
    else:
        raise ValueError('Invalid fuzzy_factor')


def from_pharmacophore(pharmacophore, subs=True, fuzzy_factor=1) -> intbitset:
    """Build a fingerprint from a pharmacophore

    Args:
        pharmacophore (Pharmacophore): The pharmacophore
        subs (bool): Include bits for 1 point and 2 points
        fuzzy_factor (int): Number of bins below/above actual bin to include in fingerprint

    Returns:
        Fingerprint
    """
    ordered_features = sorted(list(pharmacophore.features), key=lambda f: FEATURE2BIT[f.kind])
    nr_features = len(ordered_features)
    nr_bins = len(BINS)

    dist_matrix = calculate_distance_matrix(ordered_features)

    bits = set()

    if subs:
        for a in ordered_features:
            bit_info = FEATURE2BIT[a.kind]
            bit_index = BIT_INFO[bit_info]
            bits.add(bit_index)

    if subs:
        pair_fuzzy_factor = fuzzy_factor
        if pair_fuzzy_factor < 0:
            pair_fuzzy_factor = 1
        for a in range(nr_features - 1):
            for b in range(a + 1, nr_features):
                distance = dist_matrix[a][b]
                bin_id = bin_distance(distance, BINS)
                ids = [
                    FEATURE2BIT[ordered_features[a].kind],
                    FEATURE2BIT[ordered_features[b].kind]
                ]
                bit_info = ids[0] + chr(bin_id + 97) + ids[1]
                bit_index = BIT_INFO[bit_info]
                bits.add(bit_index)

                for i in range((0 - pair_fuzzy_factor), pair_fuzzy_factor + 1):
                    if nr_bins < bin_id + i or bin_id + i < 0:
                        continue

                    bit_info = ids[0] + chr(bin_id + 97 + i) + ids[1]
                    bit_index = BIT_INFO[bit_info]
                    bits.add(bit_index)

    offsets = list(fuzzy_offsets(fuzzy_factor))
    for a in range(nr_features - 2):
        for b in range(a + 1, nr_features - 1):
            for c in range(b + 1, nr_features):
                distances = [{
                    'id': FEATURE2BIT[ordered_features[c].kind],
                    'bin': bin_distance(dist_matrix[a][b], BINS)
                }, {
                    'id': FEATURE2BIT[ordered_features[b].kind],
                    'bin': bin_distance(dist_matrix[a][c], BINS)
                }, {
                    'id': FEATURE2BIT[ordered_features[a].kind],
                    'bin': bin_distance(dist_matrix[b][c], BINS)
                }]
                distances.sort(key=lambda d: (d['bin'], ord(d['id'])))

                bit_info = distances[0]['id'] + distances[1]['id'] + distances[2]['id']
                bit_info += chr(distances[0]['bin'] + 97)
                bit_info += chr(distances[1]['bin'] + 97)
                bit_info += chr(distances[2]['bin'] + 97)
                bit_index = BIT_INFO[bit_info]
                bits.add(bit_index)

                for i, j, k in offsets:
                    # test if is bit outside bins
                    bin_i = distances[0]['bin'] + i
                    bin_j = distances[1]['bin'] + j
                    bin_k = distances[2]['bin'] + k
                    if nr_bins <= bin_i or bin_i < 0 or \
                            nr_bins <= bin_j or bin_j < 0 or \
                            nr_bins <= bin_k or bin_k < 0:
                        continue

                    fdistances = [{
                        'id': distances[0]['id'],
                        'bin': bin_i,
                    }, {
                        'id': distances[1]['id'],
                        'bin': bin_j,
                    }, {
                        'id': distances[2]['id'],
                        'bin': bin_k,
                    }]

                    fdistances.sort(key=lambda d: (d['bin'], ord(d['id'])))

                    bit_info = fdistances[0]['id'] + fdistances[1]['id'] + fdistances[2]['id']
                    bit_info += chr(fdistances[0]['bin'] + 97)
                    bit_info += chr(fdistances[1]['bin'] + 97)
                    bit_info += chr(fdistances[2]['bin'] + 97)
                    bit_index = BIT_INFO[bit_info]
                    bits.add(bit_index)

    return intbitset(bits)
