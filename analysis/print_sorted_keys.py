def sort_by_key(keyed_map):
	sorted_keys = []
	for key in keyed_map.keys():
		sorted_keys.append(key)
	sorted_keys.sort()

	pairs = []
	for key in sorted_keys:
		pairs.append((key, keyed_map[key]))
	return pairs

DEFAULT_PREFIX = ""
DEFAULT_PAIR_SEP = ": "
DEFAULT_DELIM = "\n"

def sorted_keys_string(keyed_map, prefix = DEFAULT_PREFIX, \
		       pair_sep = DEFAULT_PAIR_SEP, delim = DEFAULT_DELIM):
	return_string = ""
	sorted_pairs = sort_by_key(keyed_map)

	for (key, value) in sorted_pairs:
		return_string += prefix + str(key) + pair_sep + \
				 str(value) + delim
	return return_string

def print_sorted_keys(keyed_map, prefix = DEFAULT_PREFIX, \
		      pair_sep = DEFAULT_PAIR_SEP, delim = DEFAULT_DELIM):
	print sorted_keys_string(keyed_map, prefix, pair_sep, delim)
