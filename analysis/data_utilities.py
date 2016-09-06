def do_to_dict(dictionary, key, new_data, init, increase):
	if (dictionary.has_key(key)):
		dictionary[key] = increase(dictionary[key], new_data)
	else:
		dictionary[key] = init(new_data)

def add_to_dict(dictionary, key, to_add):
	if (dictionary.has_key(key)):
		dictionary[key] += to_add
	else:
		dictionary[key] = to_add

def or_to_dict(dictionary, key, to_or):
	if (dictionary.has_key(key)):
		dictionary[key] += to_or
	else:
		dictionary[key] = to_or

def counts_to_stats(counts):
	n_counts = len(counts)

	if (n_counts == 0):
		return None

	counts.sort()
	middle = n_counts / 2
	median = int(counts[middle])
	if (n_counts % 2 == 0):
		median = (median + int(counts[middle - 1])) / 2.0
	lower = int(counts[n_counts / 20])
	upper = int(counts[n_counts * 19 / 20])
	return (n_counts, lower, median, upper)

def counts_to_stats_string(counts):
	stats = counts_to_stats(counts)
	if (stats is None):
		return "0"
	(n_counts, lower, median, upper) = stats
	return "%d, [%d, %.1f, %d]"%(n_counts, lower, median, upper)

def get_max(pairs):
	max_point = None
	max_count = None
	for (point, count) in pairs:
		if (max_count is None or count > max_count):
			max_point = point
			max_count = count
	return max_point

def get_most(counts):
	max_count = None
	for count in counts:
		if ((not count is None) and \
		    (max_count is None or count > max_count)):
			max_count = count
	return max_count

def get_least(counts):
	least_count = None
	for count in counts:
		if ((count is None) and \
		    (least_count is None or count < least_count)):
			least_count = count
	return least_count

def get_least(counts):
	min_count = None
	for count in counts:
		if (min_count is None or count < min_count):
			min_count = count
	return min_count

def get_mode(points):
	counts = {}
	for point in points:
		add_to_dict(counts, point, 1)
	max_point = get_max(counts.items())
	return max_point
