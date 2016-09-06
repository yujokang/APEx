from error_handler import throw_error
from types import ListType

OUT_RANGE_DELIM = "_"
OUT_RANGES_DELIM = ","

def clone_count(count):
	if (count.__class__ == ListType):
		return map(lambda x: x, count)
	else:
		return count

class RangeNode:
	def __init__(self, least, most = None, count = 1):
		self.least = least
		if (most is None):
			self.most = least
		else:
			self.most = most
		self.children = None
		self.count = clone_count(count)
		self.flat_list = None
	def get_count(self):
		return clone_count(self.count)
	def overlaps(self, other):
		return self.least <= other.most and self.most >= other.least
	def contains(self, other):
		return self.least <= other.least and other.most <= self.most
	def _create_shrinked(self, least, most):
		new_least = None
		if (least > self.least):
			new_least = least
		else:
			new_least = self.least
		new_most = None
		if (most < self.most):
			new_most = most
		else:
			new_most = self.most
		return RangeNode(new_least, new_most, self.get_count())
	def create_shrinked(self, to_fit):
		return self._create_shrinked(to_fit.least, to_fit.most)
	def cut_above(self, cutter):
		cut = cutter.least - 1
		new_most = None
		if cut < self.most:
			new_most = cut
		else:
			new_most = self.most
		if (self.least > new_most):
			return None
		return RangeNode(self.least, new_most, self.get_count())
	def cut_below(self, cutter):
		cut = cutter.most + 1
		new_least = None
		if cut > self.least:
			new_least = cut
		else:
			new_least = self.least
		if (new_least > self.most):
			return None
		return RangeNode(new_least, self.most, self.get_count())
	def cut_between(self, low_cutter, high_cutter):
		lowest = low_cutter.most + 1
		highest = high_cutter.least - 1
		if (lowest > highest):
			return None
		return self._create_shrinked(lowest, highest)
	def clone(self, new_count = None):
		if (new_count is None):
			new_count = self.count
		new_count = clone_count(new_count)
		new = RangeNode(self.least, self.most, new_count)
		if (not self.children is None):
			new.children = []
			for child in self.children:
				new.children.append(child.clone())
		return new
	def clone_top(self, new_count = 1):
		return RangeNode(self.least, self.most, clone_count(new_count))
	def flatten(self):
		if (self.children is None):
			return [self.clone()]
		else:
			if (self.flat_list is None):
				self.flat_list = []
				for child in self.children:
					self.flat_list += child.flatten()
			return self.flat_list
	def _add(self, new):
		combo_count = self.get_count() + new.get_count()
		if (self.children is None):
			if (self.least < new.least):
				old_less = self.cut_above(new)
				new_combo = RangeNode(new.least, new.most, \
						      combo_count)
				if (self.most > new.most):
					self.children = [old_less, new_combo, \
							 self.cut_below(new)]
				else:
					self.children = [old_less, new_combo]
			elif (self.most > new.most):
				new_combo = RangeNode(new.least, new.most, \
						      combo_count)
				old_more = self.cut_below(new)
				self.children = [new_combo, old_more]
			else:
				self.count = combo_count
		else:
			self.flat_list = None
			for child in self.children:
				if (child.overlaps(new)):
					child.add(new.create_shrinked(child))
	def add(self, new):
		if (new is None):
			return
		new_shrinked = new.create_shrinked(self)
		if (new_shrinked.least <= new_shrinked.most):
			self._add(new_shrinked)
	def increment(self, addition):
		if (self.children is None):
			self.count += addition
		else:
			for child in self.children:
				child.increment(addition)
	def __str__(self):
		if (self.children is None):
			return "%d%s%d(%s)"%(self.least, OUT_RANGE_DELIM, \
					     self.most, self.get_count())
		else:
			return OUT_RANGES_DELIM.join(map(str, self.children))
	def short_str(self):
		return "%d%s%d"%(self.least, OUT_RANGE_DELIM, self.most)

class RangeIter:
	def __init__(self, range_list):
		self.range_list = range_list.clone_flat()
		self.state = -1
	def next(self):
		return_range = None
		return_value = None
		if (self.state == -1):
			return_value = self.range_list.rest
		elif (self.state < len(self.range_list.ranges)):
			return_range = self.range_list.ranges[self.state]
			return_value = return_range.get_count()
		else:
			raise StopIteration
		self.state += 1
		return (return_range, return_value)

class CoverRange:
	def __init__(self, node):
		self.least = node.least
		self.most = node.most
	def __le__(self, other):
		self.least <= other.least
	def __lt__(self, other):
		self.least < other.least
	def __ge__(self, other):
		self.least >= other.least
	def __gt__(self, other):
		self.least > other.least
	def __eq__(self, other):
		return (self.least == other.least) and (self.most == other.most)
	def __hash__(self):
		hash_tuple = (self.least, self.most)
		return hash(hash_tuple)
	def short_str(self):
		return "%d%s%d"%(self.least, OUT_RANGE_DELIM, self.most)

class RangeBinder:
	def __init__(self, cover_ranges = []):
		self.ranges = set()
		for cover_range in cover_ranges:
			self.ranges.add(cover_range)
	def append(self, node):
		self.ranges.add(CoverRange(node))
	def __add__(self, other):
		combined_ranges = self.ranges.union(other.ranges)
		return RangeBinder(combined_ranges)
	def __iter__(self):
		return self.ranges.__iter__()

class RangeList:
	def _set_ranges(self, ranges, do_clone):
		self.ranges = []
		for range_member in ranges:
			if (len(self.ranges) > 0):
				last = self.ranges[-1]
				most = last.most
				if (range_member.least <= most):
					throw_error("Overlapping or " + \
						    "out-ouf-order ranges, " + \
						    "%s and %s"%(last, \
								 range_member))
			new_member = None
			if (do_clone):
				new_member = range_member.clone()
			else:
				new_member = range_member
			self.ranges += new_member.flatten()
		self.need_flatten = False
	def __init__(self, ranges = [], as_list = False, rest = None):
		self.as_list = as_list
		self._set_ranges(ranges, True)
		if (rest is None):
			if (as_list):
				rest = []
			else:
				rest = 0
		self.rest = rest
	def flatten(self):
		if (self.need_flatten):
			old_ranges = self.ranges
			self._set_ranges(old_ranges, False)
			self.need_flatten = False
	def clone_flat(self, as_list = None):
		if (as_list is None):
			as_list = self.as_list
		clone = RangeList(self.ranges, as_list)
		if (as_list == self.as_list):
			clone.rest += self.rest
		return clone
	def clone_top(self, value = 1, as_list = None):
		if (as_list is None):
			as_list = self.as_list
		clone = RangeList([], as_list)
		for top_range in self.ranges:
			clone.ranges.append(top_range.clone_top(value))
		return clone
	def clone_new_value(self, value, as_list = None):
		clone = RangeList(self.ranges, as_list)
		if (self.has_rest()):
			clone.rest = value
		for clone_range in clone.ranges:
			clone_range.count = value
		return clone
	def clone_binder(self):
		binder = RangeBinder()
		clone = self.clone_top(binder, as_list = False)
		for clone_range in clone.ranges:
			binder.append(clone_range)
		return clone
	def _gen_number(self, value):
		count = None
		if (self.as_list):
			count = len(value)
		else:
			count = value
		return float(count)
	def _gen_normal(self, value, base_number):
		return self._gen_number(value) / base_number
	def gen_normalized(self, base):
		base_number = self._gen_number(base)
		normalized = self.clone_flat(as_list = False)
		normalized.rest = self._gen_normal(self.rest, base_number)

		for range_stat in normalized.ranges:
			range_stat.count = self._gen_normal(range_stat.count, \
							    base_number)

		return normalized
	# Find the first range in the list whose "most" field
	# is greater than or equal to the "least" parameter,
	# ie. the lowest range that might still overlap
	# with a range whose "least" field is the "least" paramater.
	def _search_least(self, least, first, last = None):
		# Default maximum is the last range's index.
		if (last is None):
			last = len(self.ranges) - 1
		# Return 1 past the last range,
		# if there is no range that is large enough
		# to reach the least value.
		if (len(self.ranges) == 0 or least > self.ranges[last].most):
			return last + 1;
		# Otherwise, the last range meets the criterion,
		# and return it if it is the only criterion.
		if (first == last):
			return last
		if (first > last):
			print "Overshot during least-end search"
			exit(-1)
		# Binary recursion
		middle = (first + last + 1) / 2
		middle_range = self.ranges[middle]
		if (middle_range.most >= least):
			if (middle == first or \
			    self.ranges[middle - 1].most < least):
				return middle
			else:
				return self._search_least(least, first, \
							  middle - 1)
		else:
			return self._search_least(least, middle + 1, last)
	def _search_most(self, most, first, last = None):
		if (last is None):
			last = len(self.ranges) - 1
		if (len(self.ranges) == 0 or most < self.ranges[first].least):
			return first - 1
		if (first == last):
			return first
		if (first > last):
			print "Overshot during most-end search"
			exit(-1)
		middle = (first + last + 1) / 2
		middle_range = self.ranges[middle]
		if (middle_range.least <= most):
			if (middle == last or \
			    self.ranges[middle + 1].least > most):
				return middle
			else:
				return self._search_most(most, middle + 1, last)
		else:
			return self._search_most(most, first, middle - 1)
	def _add(self, new_range, start = 0):
		if (start > 0):
			skipped = self.ranges[start - 1]
			if (new_range.least <= skipped.most):
				print "At %d, %s overshot %s"%(start, \
							       str(skipped), \
							       str(new_range))
				exit(-1)

		add_first = self._search_least(new_range.least, start)
		add_last= self._search_most(new_range.most, start)

		new_ranges = []
		for pre_i in range(add_first):
			new_ranges.append(self.ranges[pre_i])

		if (add_first < len(self.ranges)):
			first = self.ranges[add_first]
			if (first.overlaps(new_range)):
				pre_cut = new_range.cut_above(first)
				if (pre_cut != None):
					new_ranges.append(pre_cut)
				first.add(new_range)
				new_ranges.append(first)
			else:
				new_ranges.append(new_range)
				new_ranges.append(first)
		else:
			new_ranges.append(new_range)

		for inter_i in range(add_first, add_last):
			current_range = self.ranges[inter_i]
			next_range = self.ranges[inter_i + 1]
			between_range = new_range.cut_between(current_range, \
							      next_range)
			if (between_range != None):
				new_ranges.append(between_range)
			if (inter_i < add_last - 1):
				next_range.add(new_range)
				new_ranges.append(next_range)

		last = self.ranges[add_last]
		if (last.overlaps(new_range)):
			post_cut = new_range.cut_below(last)
			if (add_last > add_first):
				last.add(new_range)
				new_ranges.append(last)
			if (post_cut != None):
				new_ranges.append(post_cut)

		if (add_last == add_first - 1):
			add_last = add_first
		if (add_last < add_first):
			print "End at %d, but start at %d"%(add_last, add_first)
			exit(-1)
		for post_i in range(add_last + 1, len(self.ranges)):
			new_ranges.append(self.ranges[post_i])

		self.ranges = new_ranges

		self.need_flatten = True

		return add_first

	def add(self, new_range_list):
		if (len(new_range_list.ranges) == 0 and \
		    new_range_list.has_rest()):
			self.increment(new_range_list.rest)
			return self
		if (len(self.ranges) == 0):
			temp_clone = new_range_list.clone_flat()
			self.ranges = temp_clone.ranges
			self.increment(self.rest)
			if (new_range_list.has_rest()):
				self.increment(new_range_list.rest)
			return self
		start = 0
		for new_range in new_range_list.ranges:
			start = self._add(new_range, start)
		return self
	def increment(self, to_add = 1):
		self.rest += to_add
	def __str__(self):
		self.flatten()
		return "Unspecified: %s\n%s"%(str(self.rest), \
				       OUT_RANGES_DELIM.join(map(str, \
								 self.ranges)))
	def has_rest(self):
		if (self.as_list):
			return len(self.rest) > 0
		else:
			return self.rest > 0
	def short_str(self):
		node_strs = []

		for node in self.ranges:
			node_strs.append(node.short_str())

		nodes_str = OUT_RANGES_DELIM.join(node_strs)
		if (self.has_rest()):
			return "Unspecified: %s %s"%(str(self.rest), nodes_str)
		else:
			return nodes_str
	def __iter__(self):
		return RangeIter(self)
	def contains(self, node):
		if (node is None):
			return self.has_rest()
		for child_node in self.ranges:
			if (child_node.contains(node)):
				return True
		return False
	def contains_list(self, other):
		if (other.has_rest()):
			return self.has_rest()
		for child_node in other.ranges:
			if (not self.contains(child_node)):
				return False
		return True
	def _overlaps_single(self, other_range, start = 0):
		new_start = self._search_least(other_range.least, start)
		new_end = self._search_most(other_range.most, start)
		return (new_start <= new_end, new_end)
	def overlaps_single(self, other_range):
		self.flatten()
		return self._overlaps_single(other_range)[0]
	def overlaps(self, other):
		if (self.has_rest() or other.has_rest()):
			return True
		self.flatten()
		other.flatten()

		current_start = 0
		for other_range in other.ranges:
			(result, next_start) = \
			self._overlaps_single(other_range, current_start)
			if (result):
				return True
			elif (next_start >= len(self.ranges)):
				return False
			elif (next_start < 0):
				current_start = 0
			else:
				current_start = next_start

		return False
	def _find_single_overlaps(self, other_range, start = 0):
		new_start = self._search_least(other_range.least, start)
		new_end = self._search_most(other_range.most, start)

		overlaps = []
		other_count = other_range.get_count()
		for current_range in self.ranges[new_start : new_end + 1]:
			if (current_range.overlaps(other_range)):
				overlap = \
				current_range.create_shrinked(other_range)
				overlap_pair = (current_range.get_count(), \
						other_count)
				overlaps.append((overlap, overlap_pair))
		return (overlaps, new_end)
	def find_single_overlaps(self, other_range):
		self.flatten()
		return self._find_single_overlaps(other_range)[0]
	def find_overlaps(self, other):
		self.flatten()
		other.flatten()

		current_start = 0
		overlaps = []
		for other_range in other.ranges:
			(new_overlaps, new_start) = \
			self._find_single_overlaps(other_range, current_start)
			current_start = new_start
			overlaps += new_overlaps
		return overlaps
	def get_coverers(self, node):
		if (node is None):
			return [None]
		least_index = self._search_least(node.least, 0)
		if (least_index < 0):
			return []
		most_index = self._search_most(node.most, 0)
		if (most_index >= len(self.ranges)):
			return []
		if (least_index > most_index):
			return []
		return self.ranges[least_index : most_index + 1]
	def is_exactly(self, value):
		if (self.has_rest()):
			return False
		if (len(self.ranges) != 1):
			return False
		single_range = self.ranges[0]
		return (single_range.least == value) and \
		       (single_range.most == value)
	def get_exact(self):
		if (self.has_rest()):
			return None
		if (len(self.ranges) != 1):
			return None
		single_range = self.ranges[0]
		if (single_range.least != single_range.most):
			return None
		return single_range.least
	def _includes_single(self, other_range, start = 0):
		new_start = self._search_least(other_range.least, start)
		new_end = self._search_most(other_range.most, start)

		does_overlap = False
		for current_range in self.ranges[new_start : new_end + 1]:
			if (current_range.contains(other_range)):
				does_overlap = True
				break

		return (does_overlap, new_end)
	def includes(self, other):
		self.flatten()
		other.flatten()

		current_start = 0
		for single_node in other.ranges:
			(does_overlap, next_start) = \
			self._includes_single(single_node, current_start)
			if (does_overlap):
				return True
			elif (next_start >= len(self.ranges)):
				return False
			elif (next_start < 0):
				current_start = 0
			else:
				current_start = next_start
		return False
	def get_most_known(self):
		if (len(self.ranges) == 0):
			return None
		return self.ranges[-1].most
	def get_least_known(self):
		if (len(self.ranges) == 0):
			return None
		return self.ranges[0].least

def generate_smooth(ranges):
	last_range = None
	smoothened_ranges = []

	for range_node in ranges:
		if (last_range is None):
			last_range = range_node.clone_top()
		elif (last_range.most == range_node.least):
			last_range = RangeNode(last_range.least, \
					       range_node.most)
		else:
			smoothened_ranges.append(last_range)
			last_range = range_node.clone_top()

	if (not last_range is None):
		smoothened_ranges.append(last_range)

	return RangeList(smoothened_ranges)

def smoothen(range_list):
	return generate_smooth(range_list.ranges)
