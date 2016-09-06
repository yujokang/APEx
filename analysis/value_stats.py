from value_parser import BOOL_TYPE_START, PTR_TYPE_START, INT_TYPE_START, \
			 BOOL_TRUE, BOOL_FALSE, BOOL_UNKNOWN, BOOL_STRS, \
			 PTR_NOT_NULL, PTR_NULL, PTR_UNKNOWN, PTR_STRS, \
			 ParsedValue, LiteralIntValue, AssignmentsIntValue, \
			 RangeRightSideValue, UNKNOWN_STR, \
			 BOOL_TRUE_STR, BOOL_FALSE_STR, \
			 PTR_NOT_NULL_STR, PTR_NULL_STR
from ranges import RangeNode, RangeList, RangeBinder, smoothen
from error_handler import throw_error

class ValueIter:
	def __init__(self):
		pass
	def next(self):
		raise StopIteration

COVER_EXACT = 0
COVER_UNDER = -1
COVER_OVER = 1

class ValueStat:
	def __init__(self, type_marker, as_list = False):
		self.type_marker = type_marker
		if (as_list):
			self.total_count = []
		else:
			self.total_count = 0
		self.as_list = as_list
	def typed_update(self, parsed_value):
		return []
	def update(self, parsed_value):
		if (self.type_marker != parsed_value.type_marker):
			throw_error("Expected to add type " + \
				    "%s, but got %s"%(self.type_marker, \
						      parsed_value.type_marker))
		updated_counts = self.typed_update(parsed_value)
		self.total_count += parsed_value.to_add
		return updated_counts
	def _gen_unnormalized(self):
		return ValueStat(self.type_marker)
	def gen_unnormalized(self):
		unnormalized = self._gen_unnormalized()
		unnormalized.total_count = self.gen_count(self.total_count)
		return unnormalized
	def _gen_normalized(self):
		return ValueStat(self.type_marker)
	def gen_normalized(self):
		normalized = self._gen_normalized()
		normalized.total_count = 1.0
		return normalized
	def gen_count(self, value):
		if self.as_list:
			return len(value)
		else:
			return int(value)
	def get_total_count(self):
		return self.gen_count(self.total_count)
	def _gen_normal(self, value):
		total_count = self.get_total_count()
		number = self.gen_count(value)
		return float(number) / float(total_count)
	def _add(self, other):
		return ValueStat(self.type_marker, self.as_list)
	def __add__(self, other):
		total = self._add(other)
		total.total_count = self.total_count + other.total_count
		return total
	def show_data(self):
		return None
	def __str__(self):
		return self.type_marker + self.show_data()
	def __iter__(self):
		return ValueIter()
	def is_wanted_key(self, target_key, candidate_key):
		return target_key == candidate_key
	def split_stats(self, split_key):
		wanted = []
		others = []
		for entry in self:
			(key, value) = entry
			if self.is_wanted_key(split_key, key):
				wanted.append[entry]
			else:
				others.append[entry]
		return (wanted, others)
	def non_empty(self, value):
		int_value = None
		if (self.as_list):
			int_value = len(value)
		else:
			int_value = int(value)
		return int_value > 0
	def covers(self, key):
		return (COVER_UNDER, key)
	def key_is_unknown(self, key):
		return key == UNKNOWN_STR
	def has_unknown(self):
		return False
	def contains_parsed(self, parsed_value):
		for (key, value) in self:
			if (self.gen_count(value) > 0 and \
			    (parsed_value.overlaps(key))):
				return True
		return False
	def overlaps_parsed(self, parsed_value):
		for (key, value) in self:
			if (not self.key_is_unknown(key) and \
			    self.gen_count(value) > 0 and \
			    (parsed_value.overlaps(key))):
				return True
		return False
	def get_overlaps(self, other):
		self_ordered = []
		for entry in self:
			(key, value) = entry
			if (not self.key_is_unknown(key)):
				self_ordered.append(entry)
		other_ordered = []
		for entry in other:
			(key, value) = entry
			if (not self.key_is_unknown(key)):
				other_ordered.append(entry)

		overlaps = []
		for entry_i in range(len(self_ordered)):
			(self_key, self_value) = self_ordered[entry_i]
			(other_key, other_value) = other_ordered[entry_i]
			if (self_key != other_key):
				throw_error("Entry %d does not match: %s, %s", \
					    entry_i, self_key, other_key)
			if (self.gen_count(self_value) > 0 and \
			    self.gen_count(other_value) > 0):
				overlaps.append(key, (self_value, other_value))

		return overlaps
	def get_parsed_overlaps(self, parsed):
		overlaps = []
		for entry in self:
			(key, value) = entry
			if (not self.key_is_unknown(key) and \
			    key == parsed.get_key() and \
			    self.gen_count(value) > 0):
				overlaps.append((key, (value, parsed.to_add)))

		return overlaps

class BooleanIter(ValueIter):
	def __init__(self, boolean_stat):
		ValueIter.__init__(self)
		self.stat = boolean_stat
		self.state = BOOL_TRUE
	def next(self):
		return_key = self.state
		return_value = None
		if (self.state == BOOL_TRUE):
			self.state = BOOL_FALSE
			return_value = self.stat.true_count
		elif (self.state == BOOL_FALSE):
			self.state = BOOL_UNKNOWN
			return_value = self.stat.false_count
		elif (self.state == BOOL_UNKNOWN):
			self.state = None
			return_value = self.stat.unknown_count
		elif (self.state == None):
			raise StopIteration
		return (BOOL_STRS[return_key], return_value)

class BooleanStat(ValueStat):
	def __init__(self, as_list = False):
		ValueStat.__init__(self, BOOL_TYPE_START, as_list)
		if (as_list):
			self.true_count = []
			self.false_count = []
			self.unknown_count = []
		else:
			self.true_count = 0
			self.false_count = 0
			self.unknown_count = 0
	def typed_update(self, parsed_value):
		value = parsed_value.boolean
		to_add = parsed_value.to_add
		updated_counts = []
		if (value & BOOL_UNKNOWN != value):
			throw_error("Unknown boolean value: %d"%value)
		if (value == BOOL_TRUE):
			self.true_count += to_add
			updated_counts.append(self.true_count)
		if (value == BOOL_FALSE):
			self.false_count += to_add
			updated_counts.append(self.false_count)
		if (value == BOOL_UNKNOWN):
			self.unknown_count += to_add
			updated_counts.append(self.unknown_count)
		return updated_counts
	def show_data(self):
		return "%s; %s; %s; %s"%(str(self.total_count), \
					 str(self.true_count), \
					 str(self.false_count), \
					 str(self.unknown_count))
	def _gen_unnormalized(self):
		unnormalized = BooleanStat()
		unnormalized.true_count = self.gen_count(self.true_count)
		unnormalized.false_count = self.gen_count(self.false_count)
		unnormalized.unknown_count = self.gen_count(self.unknown_count)
		return unnormalized
	def _gen_normalized(self):
		normalized = BooleanStat()
		normalized.true_count = self._gen_normal(self.true_count)
		normalized.false_count = self._gen_normal(self.false_count)
		normalized.unknown_count = \
		self._gen_normal(self.unknown_count)
		return normalized
	def _add(self, other):
		total = BooleanStat(self.as_list)
		total.true_count = self.true_count + other.true_count
		total.false_count = self.false_count + other.false_count
		total.unknown_count = self.unknown_count + \
				      other.unknown_count
		return total
	def __iter__(self):
		return BooleanIter(self)
	def has_unknown(self):
		return self.gen_count(self.unknown_count) > 0
	def covers(self, key):
		if (self.non_empty(self.unknown_count)):
			if (key == UNKNOWN_STR):
				return (COVER_EXACT, None)
			else:
				return (COVER_OVER, UNKNOWN_STR)
		elif (key == UNKNOWN_STR):
			return (COVER_UNDER, key)

		return (COVER_EXACT, None)

class PointerIter(ValueIter):
	def __init__(self, pointer_stat):
		ValueIter.__init__(self)
		self.stat = pointer_stat
		self.state = PTR_NOT_NULL
	def next(self):
		return_key = self.state
		return_value = None
		if (self.state == PTR_NOT_NULL):
			self.state = PTR_NULL
			return_value = self.stat.not_null_count
		elif (self.state == PTR_NULL):
			self.state = PTR_UNKNOWN
			return_value = self.stat.null_count
		elif (self.state == PTR_UNKNOWN):
			self.state = None
			return_value = self.stat.unknown_count
		elif (self.state == None):
			raise StopIteration
		return (PTR_STRS[return_key], return_value)

class PointerStat(ValueStat):
	def __init__(self, as_list = False):
		ValueStat.__init__(self, PTR_TYPE_START, as_list)
		if (as_list):
			self.not_null_count = []
			self.null_count = []
			self.unknown_count = []
		else:
			self.not_null_count = 0
			self.null_count = 0
			self.unknown_count = 0
	def typed_update(self, parsed_value):
		value = parsed_value.pointer
		to_add = parsed_value.to_add
		updated_counts = []
		if (value & PTR_UNKNOWN != value):
			throw_error("Unknown pointer value: %d"%value)
		if (value == PTR_NOT_NULL):
			self.not_null_count += to_add
			updated_counts.append(self.not_null_count)
		if (value == PTR_NULL):
			self.null_count += to_add
			updated_counts.append(self.null_count)
		if (value == PTR_UNKNOWN):
			self.unknown_count += to_add
			updated_counts.append(self.unknown_count)
		return updated_counts
	def show_data(self):
		return "%s; %s; %s; %s"%(str(self.total_count), \
					 str(self.not_null_count), \
					 str(self.null_count), \
					 str(self.unknown_count))
	def _gen_unnormalized(self):
		unnormalized = PointerStat()
		unnormalized.not_null_count = \
		self.gen_count(self.not_null_count)
		unnormalized.null_count = self.gen_count(self.null_count)
		unnormalized.unknown_count = self.gen_count(self.unknown_count)
		return unnormalized
	def _gen_normalized(self):
		normalized = PointerStat()
		normalized.not_null_count = \
		self._gen_normal(self.not_null_count)
		normalized.null_count = self._gen_normal(self.null_count)
		normalized.unknown_count = \
		self._gen_normal(self.unknown_count)
		return normalized
	def _add(self, other):
		total = PointerStat(self.as_list)
		total.not_null_count = self.not_null_count + \
				       other.not_null_count
		total.null_count = self.null_count + other.null_count
		total.unknown_count = self.unknown_count + \
				      other.unknown_count
		return total
	def __iter__(self):
		return PointerIter(self)
	def has_unknown(self):
		return self.gen_count(self.unknown_count) > 0
	def covers(self, key):
		if (self.non_empty(self.unknown_count)):
			if (key == UNKNOWN_STR):
				return (COVER_EXACT, None)
			else:
				return (COVER_OVER, UNKNOWN_STR)
		elif (key == UNKNOWN_STR):
			return (COVER_UNDER, key)

		return (COVER_EXACT, None)

class IntegerIter(ValueIter):
	def __init__(self, integer_stat):
		ValueIter.__init__(self)
		self.range_iter = integer_stat.range_list.__iter__()
	def next(self):
		return self.range_iter.next()

class IntegerStat(ValueStat):
	def __init__(self, as_list = False):
		ValueStat.__init__(self, INT_TYPE_START, as_list)
		self.range_list = RangeList([], as_list)
		self.bound_ranges = RangeList([], False, rest = RangeBinder())
	def add_range_list(self, new_range_list):
		self.bound_ranges.add(new_range_list.clone_binder())
		self.range_list.add(new_range_list)
	def typed_update(self, parsed_value):
		int_value = parsed_value.value
		to_add = parsed_value.to_add
		updated_counts = []
		if (int_value == None):
			parsed_range_value = parsed_value.range_value
			if (parsed_range_value is None):
				self.range_list.increment(to_add)
			else:
				self.add_range_list(parsed_range_value)
		elif (int_value.__class__ == LiteralIntValue):
			value = int_value.value
			self.add_range_list(RangeList([RangeNode(value, value, \
								 to_add)], \
						      self.as_list))
		elif (int_value.__class__ == AssignmentsIntValue):
			right = int_value.main_value.right
			if (right == None):
				self.range_list.increment(to_add)
			else:
				right_ranges = right.ranges
				new_ranges = []
				for rr in right_ranges:	
					new_ranges.append(RangeNode(rr[0], \
								    rr[1], \
								    to_add))
				range_list = RangeList(new_ranges, \
						       self.as_list)
				if (len(new_ranges) == 0):
					range_list.increment(to_add)
				self.add_range_list(range_list)
		else:
			throw_error(str(int_value) + \
				    " is of unknown integer type, " + \
				    str(int_value.__class__))
		if (len(self.range_list.ranges) == 0):
			rest_count = None
			if (self.range_list.as_list):
				rest_count = len(self.range_list.rest)
			else:
				rest_count = self.range_list.rest
			if (rest_count == 0):
				throw_error("No ranges added")
		return updated_counts
	def show_data(self):
		return "%s; %s"%(str(self.total_count), \
				 str(self.range_list))
	def _gen_unnormalized(self):
		unnormalized = IntegerStat()

		base = None
		if (self.as_list):
			base = [1]
		else:
			base = 1
		unnormalized.range_list = \
		self.range_list.gen_normalized(base)

		return unnormalized
	def _gen_normalized(self):
		normalized = IntegerStat()

		normalized.range_list = \
		self.range_list.gen_normalized(self.total_count)

		return normalized
	def _add(self, other):
		total = IntegerStat(self.as_list)
		total.range_list = self.range_list.clone_flat()
		total.range_list.add(other.range_list)
		return total
	def __iter__(self):
		return IntegerIter(self)
	def short_str(self):
		return range_list.short_str()
	def is_wanted_key(self, target_key, candidate_key):
		if (target_key is None):
			return candidate_key is None
		elif (candidate_key is None):
			return False
		return target_key.contains(candidate_key)
	def key_is_unknown(self, key):
		return key == None
	def has_unknown(self):
		return self.range_list.has_rest()
	def covers(self, key):
		if (self.range_list.has_rest()):
			if (key is None):
				return (COVER_EXACT, None)
			else:
				return (COVER_OVER, UNKNOWN_STR)
		elif (key is None):
			return (COVER_UNDER, UNKNOWN_STR)

		coverers = self.bound_ranges.get_coverers(key)

		if (len(coverers) == 0):
			return (COVER_UNDER, key.short_str())

		least = key.least
		most = key.most
		beginning = coverers[0].least
		if (beginning < least):
			return (COVER_OVER, coverers[0].short_str())
		if (beginning > least):
			missing = RangeNode(least, beginning - 1)
			return (COVER_UNDER, missing.short_str())
		end = coverers[-1].most
		if (end > most):
			return (COVER_OVER, coverers[-1].short_str())
		if (end < most):
			missing = RangeNode(end + 1, most)
			return (COVER_UNDER, missing.short_str())

		last_end = least
		found_over = False
		over = None
		for coverer in coverers:
			binder = coverer.count

			for bound in binder:
				if (bound.least < least or most < bound.most):
					over = bound
					found_over = True
			pre_gap = coverer.least - 1
			if (last_end < pre_gap):
				missing = RangeNode(last_end, pre_gap)
				return (COVER_UNDER, missing.short_str())
			last_end = coverer.most + 1

		if (found_over):
			return (COVER_OVER, over.short_str())
		return (COVER_EXACT, None)
	def contains_parsed(self, parsed_value):
		if (self.range_list.has_rest):
			return True
		else:
			smooth = smoothen(self.range_list)
			return smooth.contains_list(parsed_value.range_value)
	def get_overlaps(self, other):
		return self.range_list.find_overlaps(other.range_list)
	def get_parsed_overlaps(self, other):
		return self.range_list.find_overlaps(other.range_value)

def initialize_raw_stat(type_marker, as_list = False):
	if (type_marker == BOOL_TYPE_START):
		return BooleanStat(as_list)
	elif (type_marker == PTR_TYPE_START):
		return PointerStat(as_list)
	elif (type_marker == INT_TYPE_START):
		return IntegerStat(as_list)
	else:
		throw_error("Unknown type " + type_marker)

def initialize_stat(parsed_val, as_list = False):
	if (parsed_val == None):
		return None
	return initialize_raw_stat(parsed_val.type_marker, as_list)

UNSPECIFIED_STR = "Unspecified"

def to_label(key):
	if (key is None):
		return UNSPECIFIED_STR
	else:
		key_class = key.__class__
		if (key_class == RangeNode):
			return key.short_str()
		else:
			return str(key)
