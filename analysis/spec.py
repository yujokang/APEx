from parser_utils import OutputParser
from value_parser import BOOL_STRS, PTR_STRS, BOOL_UNKNOWN, PTR_UNKNOWN, \
			 BOOL_TYPE_START, PTR_TYPE_START, INT_TYPE_START, \
			 is_undefined, \
			 BOOL_TRUE_STR, BOOL_FALSE_STR, \
			 PTR_NOT_NULL_STR, PTR_NULL_STR
from ranges import RangeNode, RangeList, OUT_RANGE_DELIM, OUT_RANGES_DELIM
from error_handler import throw_error
from os import path

class SpecValue:
	def __init__(self, type_marker):
		self.type_marker = type_marker
		pass
	def clone(self):
		return self
	def contains(self, parsed_value):
		return False
	def _inside(self, parsed_value):
		return self.contains(parsed_value)
	def inside(self, parsed_value):
		return parsed_value.is_unknown() or self._inside(parsed_value)
	def overlaps(self, parsed_value):
		return False
	def _overlaps_key(self, key):
		return False
	def overlaps_key(self, key):
		if (is_undefined(self.type_marker, key)):
			return True
		return self._overlaps_key(key)
	def outside(self, parsed_value):
		return not self.overlaps(parsed_value)
	def _val_to_str(self):
		return ""
	def __str__(self):
		return self.type_marker + " " + self._val_to_str()

class SimpleSpecValue(SpecValue):
	def __init__(self, type_marker, key):
		SpecValue.__init__(self, type_marker)
		self.key = key
	def _val_to_str(self):
		return self.key
	def __eq__(self, other):
		return self.key == other.key
	def _overlaps_key(self, key):
		return self.key == key

class BoolSpecValue(SimpleSpecValue):
	def __init__(self, key):
		SimpleSpecValue.__init__(self, BOOL_TYPE_START, key)
	def clone(self):
		return BoolSpecvalue(self.key)
	def contains(self, parsed_value):
		return self.key == BOOL_STRS[parsed_value.boolean]
	def overlaps(self, parsed_value):
		if (parsed_value.boolean == BOOL_UNKNOWN):
			return True
		return self.key == BOOL_STRS[parsed_value.boolean]

class PtrSpecValue(SimpleSpecValue):
	def __init__(self, key):
		SimpleSpecValue.__init__(self, PTR_TYPE_START, key)
	def clone(self):
		return PtrSpecvalue(self.key)
	def contains(self, parsed_value):
		return self.key == PTR_STRS[parsed_value.pointer]
	def overlaps(self, parsed_value):
		if (parsed_value.pointer == PTR_UNKNOWN):
			return True
		return self.key == PTR_STRS[parsed_value.pointer]

NOT_MARKER = "!"
NON_ERROR_DELIM = ";"

class IntSpecValuePart:
	def __init__(self, opposite, range_spec):
		self.opposite = opposite
		self.range_spec = range_spec
	def clone(self):
		cloned = IntSpecValuePart(self.opposite, self.range_spec)
		cloned.opposite = self.opposite
		cloned.range_spec = self.range_spec.clone_flat()
		return cloned
	def contains(self, parsed_value):
		if (parsed_value.range_value is None):
			return False
		if (self.opposite):
			return not self.range_spec \
				       .overlaps(parsed_value.range_value)
		return self.range_spec.includes(parsed_value.range_value)
	def inside(self, parsed_value):
		range_value = parsed_value.range_value
		if (range_value == None):
			return True
		if (self.opposite):
			return False
		return range_value.includes(self.range_spec)
	def overlaps(self, parsed_value):
		if (parsed_value.range_value == None):
			return True
		if (self.opposite):
			return not self.range_spec \
				       .includes(parsed_value.range_value)
		return self.range_spec.overlaps(parsed_value.range_value)
	def overlaps_key(self, key):
		if (is_undefined(INT_TYPE_START, key)):
			return True
		if (self.opposite):
			return not self.range_spec.contains(key)
		return self.range_spec.overlaps_single(key)
	def _val_to_str(self):
		basic_str = self.range_spec.short_str()
		if (self.opposite):
			return NOT_MARKER + basic_str
		else:
			return basic_str

class IntSpecValue(SpecValue):
	def __init__(self, error, non_error = None):
		SpecValue.__init__(self, INT_TYPE_START)
		self.error = error
		self.non_error = non_error
	def clone(self):
		cloned = IntSpecvalue(self.error, self.non_error)
		return cloned
	def contains(self, parsed_value):
		return self.error.contains(parsed_value)
	def overlaps(self, parsed_value):
		return self.error.overlaps(parsed_value)
	def _overlaps_key(self, key):
		return self.error.overlaps_key(key)
	def outside(self, parsed_value):
		if (self.non_error is None):
			return not self.error.overlaps(parsed_value)
		else:
			return self.non_error.contains(parsed_value)
	def _inside(self, parsed_value):
		return self.error.inside(parsed_value)
	def _val_to_str(self):
		error_str = self.error._val_to_str()
		if (self.non_error is None):
			return error_str
		else:
			return error_str + NON_ERROR_DELIM + \
			       self.non_error._val_to_str()

def parse_int_spec_value_part(range_string):
	opposite = False
	if (len(range_string) > 1 and range_string[0] == NOT_MARKER):
		opposite = True
		range_string = range_string[1 : ]
	ranges = []
	range_strings = range_string.split(OUT_RANGES_DELIM)
	for range_string in range_strings:
		(least_str, most_str) = range_string.split(OUT_RANGE_DELIM)
		least = int(least_str)
		most = int(most_str)
		ranges.append(RangeNode(least, most))
	range_spec = RangeList(ranges)
	return IntSpecValuePart(opposite, range_spec)

def parse_int_spec_value(spec_string):
	error_end = spec_string.find(NON_ERROR_DELIM)
	error = None
	non_error = None
	if (error_end < 0):
		error = parse_int_spec_value_part(spec_string)
	else:
		error_str = spec_string[ : error_end]
		non_error_start = error_end + len(NON_ERROR_DELIM)
		non_error_str = spec_string[non_error_start : ]
		error = parse_int_spec_value_part(error_str)
		non_error = parse_int_spec_value_part(non_error_str)
	return IntSpecValue(error, non_error)

SPEC_DELIM = " "
INFALLIBLE_LEN = 2
NAME_ID = 0
TYPE_MARKER_ID = NAME_ID + 1
EXPRESSION_ID = TYPE_MARKER_ID + 1

INFALLIBLE_MARKER = "INFALLIBLE"

def parse_spec_value(string):
	parts = string.split(SPEC_DELIM)
	name = parts[NAME_ID]
	type_marker = parts[TYPE_MARKER_ID]
	expression = parts[EXPRESSION_ID]
	if (expression == INFALLIBLE_MARKER):
		return (name, type_marker, None)

	value = None
	if (type_marker == BOOL_TYPE_START):
		value = BoolSpecValue(expression)
	elif (type_marker == PTR_TYPE_START):
		value = PtrSpecValue(expression)
	elif (type_marker == INT_TYPE_START):
		value = parse_int_spec_value(expression)
	else:
		throw_error("Unknown error specification type, " + type_marker)
	return (name, type_marker, value)

ERROR_SPEC_PREFIX = "ErrorSpec: "
NOTES_DELIM = "\t"

class FullErrorSpec(OutputParser):
	def __init__(self, input_handle):
		OutputParser.__init__(self, ERROR_SPEC_PREFIX, \
				      None, input_handle)
		self.specs = {}
		self.infallibles = set([])
	def to_key(self, name, return_type):
		return (name, return_type)
	def handle_line(self, line):
		data_end = line.find(NOTES_DELIM)
		if (data_end >= 0):
			line = line[ : data_end]
		parsed_spec = parse_spec_value(line)
		(name, type_marker, result) = parsed_spec
		key = self.to_key(name, type_marker)
		if (result is None):
			self.infallibles.add(key)
		else:
			self.specs[key] = result
	def get(self, key):
		if (self.specs.has_key(key)):
			return self.specs[key]
		return None
	def get_spec(self, name, type_marker):
		key = self.to_key(name, type_marker)
		return self.get(key)
	def is_infallible(self, key):
		return (key in self.infallibles)
	def is_known(self, key):
		return (not self.get(key) is None) or \
		       (self.is_infallible(key))
	def __len__(self):
		return len(self.specs)
