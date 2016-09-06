from ranges import OUT_RANGE_DELIM, OUT_RANGES_DELIM, RangeNode, RangeList

from types import ListType
from sets import Set

UNKNOWN_STR = "u"

class ParsedValue:
	def value_to_string(self):
		return "."
	def clone_new_data(self, value):
		return None
	def same_assignments(self, other):
		if (self.symbol_str is None or other.symbol_str is None):
			return False
		return self.symbol_str == other.symbol_str
	def listify(self):
		return self.clone_new_data([self.to_add])
	def __str__(self):
		return "%s%s"%(self.type_marker, self.value_to_string())
	def __init__(self, type_marker, symbol_str, to_add = 1):
		self.symbol_str = symbol_str
		self.type_marker = type_marker
		self.to_add = to_add
		self.as_list = to_add.__class__ == ListType
	def __hash__(self):
		return hash(str(self))
	def _overlaps(self, other_key):
		return False
	def is_unknown(self):
		return False
	def overlaps(self, other_key):
		if (other_key == UNKNOWN_STR):
			return True
		return self._overlaps(other_key)
	def get_key(self):
		return None
	def have_symbol(self):
		return (not self.symbol_str is None)

VOID_TYPE_START = "V"
BOOL_TYPE_START = "B"
PTR_TYPE_START = "P"
INT_TYPE_START = "I"

def parse_void(to_add = 1):
	return ParsedVoid(to_add)
def reparse_void(to_add = 1):
	return ParsedVoid(to_add)

class ParsedVoid(ParsedValue):
	def __init__(self, to_add = 1):
		ParsedValue.__init__(self, VOID_TYPE_START, \
				     None, to_add)
	def clone_new_data(self, data):
		return ParsedVoid(data)
	def value_to_string(self):
		return ""
	def _overlaps(self, other_key):
		return False
	def __eq__(self, other):
		return False

BOOL_TRUE = 1
BOOL_FALSE = 1 << 2
BOOL_UNKNOWN = BOOL_TRUE | BOOL_FALSE
BOOL_STR_MEANINGS = {"true": BOOL_TRUE, "false": BOOL_FALSE,
		     "trueorfalse": BOOL_UNKNOWN}
BOOL_TRUE_STR = "t"
BOOL_FALSE_STR = "f"
BOOL_STRS = {BOOL_TRUE: BOOL_TRUE_STR, BOOL_FALSE: BOOL_FALSE_STR, \
	     BOOL_UNKNOWN: UNKNOWN_STR}
REVERSE_BOOL_STRS = {BOOL_TRUE_STR: BOOL_TRUE, \
		     BOOL_FALSE_STR: BOOL_FALSE, \
		     UNKNOWN_STR: BOOL_UNKNOWN}

def parse_boolean(symbol_str, value_str, to_add = 1):
	return ParsedBoolean(symbol_str, BOOL_STR_MEANINGS[value_str], to_add)
def reparse_boolean(label, to_add = 1):
	return ParsedBoolean(None, REVERSE_BOOL_STRS[label], to_add)

class ParsedBoolean(ParsedValue):
	def __init__(self, symbol_str, boolean, to_add = 1):
		ParsedValue.__init__(self, BOOL_TYPE_START, \
				     symbol_str, to_add)
		self.boolean = boolean
	def clone_new_data(self, data):
		return ParsedBoolean(self.symbol_str, self.boolean, data)
	def value_to_string(self):
		return BOOL_STRS[self.boolean]
	def _overlaps(self, other_key):
		if self.boolean == BOOL_UNKNOWN:
			return True
		return BOOL_STRS[self.boolean] == other_key
	def is_unknown(self):
		return self.boolean == BOOL_UNKNOWN
	def __eq__(self, other):
		if ((self is None) != (other is None)):
			return False
		if other.__class__ != ParsedBoolean:
			return False
		return self.boolean == other.boolean
	def get_key(self):
		return BOOL_STRS[self.boolean]

PTR_NOT_NULL = 1
PTR_NULL = 1 << 2
PTR_UNKNOWN = PTR_NOT_NULL | PTR_NULL
PTR_STR_MEANINGS = {"notnull": PTR_NOT_NULL, "null": PTR_NULL,
		    "nullornotnull": PTR_UNKNOWN,
		    "notnullornull": PTR_UNKNOWN}
PTR_NOT_NULL_STR = "m"
PTR_NULL_STR = "n"
PTR_STRS = {PTR_NOT_NULL: PTR_NOT_NULL_STR, PTR_NULL: PTR_NULL_STR, \
	    PTR_UNKNOWN: UNKNOWN_STR}
REVERSE_PTR_STRS = {PTR_NOT_NULL_STR: PTR_NOT_NULL, \
		    PTR_NULL_STR: PTR_NULL, UNKNOWN_STR: PTR_UNKNOWN}

def parse_pointer(symbol_str, value_str, to_add = 1):
	return ParsedPointer(symbol_str, PTR_STR_MEANINGS[value_str], to_add)
def reparse_pointer(label, to_add = 1):
	return ParsedPointer(None, REVERSE_PTR_STRS[label], to_add)

class ParsedPointer(ParsedValue):
	def __init__(self, symbol_str, pointer, to_add = 1):
		ParsedValue.__init__(self, PTR_TYPE_START, \
				     symbol_str, to_add)
		self.pointer = pointer
	def clone_new_data(self, data):
		return ParsedPointer(self.symbol_str, self.pointer, data)
	def value_to_string(self):
		return PTR_STRS[self.pointer]
	def _overlaps(self, other_key):
		if self.pointer == PTR_UNKNOWN:
			return True
		return PTR_STRS[self.pointer] == other_key
	def is_unknown(self):
		return self.pointer == PTR_UNKNOWN
	def __eq__(self, other):
		if ((self is None) != (other is None)):
			return False
		if other.__class__ != ParsedPointer:
			return False
		return self.pointer == other.pointer
	def get_key(self):
		return PTR_STRS[self.pointer]

NEGATIVE_START = "-"
UNSIGNED_END = "U"

def parse_literal(value):
	signed = True
	negative = False
	if (value[-1] == UNSIGNED_END):
		signed = False
		value = value[ : -1]
	number = None
	if (value[0] == NEGATIVE_START):
		if (signed):
			negative = True
			value = value[1 : ]
		else:
			print "Integer can't be unsigned and negative"
			exit(-1)
	if (value.isdigit()):
		number = int(value)
		if (negative):
			number = -number
	return (signed, number)

def literal_to_str(value, signed):
	base = str(value)
	if signed:
		return base
	else:
		return base + UNSIGNED_END

class IntValue:
	def __init__(self):
		pass

class LiteralIntValue(IntValue):
	def __init__(self, value, signed = True):
		IntValue.__init__(self)
		self.value = value
		self.signed = signed
	def __str__(self):
		return literal_to_str(self.value, self.signed)
	def __eq__(self, other):
		if ((self is None) != (other is None)):
			return False
		return self.value == other.value

class LeftExpression:
	def __init__(self):
		pass

class LiteralLeftExpression(LeftExpression):
	def __init__(self, value, signed):
		LeftExpression.__init__(self)
		self.value = value
		self.signed = signed
	def __str__(self):
		return literal_to_str(self.value, self.signed)

class SingleLeftExpression(LeftExpression):
	def __init__(self, single_str):
		LeftExpression.__init__(self)
		self.single_str = single_str
	def __str__(self):
		return self.single_str

class BinaryLeftExpression(LeftExpression):
	def __init__(self, op, a, b):
		LeftExpression.__init__(self)
		self.op = op
		self.a = a
		self.b = b
	def __str__(self):
		return "(%s%s%s)"%(str(self.a), op, str(self.b))

class RightSideValue:
	def __init__(self):
		pass

RANGE_START = " ["
RANGES_START = "{" + RANGE_START
RANGES_START_LEN = len(RANGES_START)
RANGE_END = "]"
RANGES_END = RANGE_END + " }"
RANGES_END_LEN = len(RANGES_END)
RANGES_DELIM = RANGE_END + "," + RANGE_START
RANGE_DELIM = ", "

class RangeRightSideValue(RightSideValue):
	def __init__(self, value_str):
		RightSideValue.__init__(self)
		bare_ranges_str = value_str[RANGES_START_LEN : -RANGES_END_LEN]
		bare_ranges = bare_ranges_str.split(RANGES_DELIM)

		self.ranges = []
		for bare_range in bare_ranges:
			(min_str, max_str) = bare_range.split(RANGE_DELIM)
			self.ranges += [(int(min_str), int(max_str))]
	def __str__(self):
		range_strs = []

		for (lowest, highest) in self.ranges:
			range_str = "%d%s%s"%(lowest, OUT_RANGE_DELIM, highest)
			range_strs += [range_str]

		return OUT_RANGES_DELIM.join(range_strs)
	def __eq__(self, other):
		if ((self is None) != (other is None)):
			return False
		if (len(self.ranges) != len(other.ranges)):
			return False
		for range_i in range(len(self.ranges)):
			if (self.ranges[range_i] != other.ranges[range_i]):
				return False
		return True

OPEN_PAREN = "("
CLOSE_PAREN = ")"
OPS = Set(["+", "-", "*", "/", "&", "|", "^", "%", ">>", "<<", "!="])
OP_SPACE = " "
OP_SPACE_LEN = len(OP_SPACE)

ASSIGNMENT_DELIM = ":="

UNRESTRICTED_INT_STR = "u"

class Assignment:
	def range_expr(self, left_str):
		if (left_str[0] != OPEN_PAREN):
			return len(left_str)

		n_opened = 1
		char_i = 1
		while char_i < len(left_str):
			if (n_opened == 0):
				break
			left_str_char = left_str[char_i]
			if (left_str_char == OPEN_PAREN):
				n_opened += 1
			if (left_str_char == CLOSE_PAREN):
				if (n_opened == 0):
					print "Too many close-parentheses"
					exit(-1)
				n_opened -= 1
			char_i += 1
		if (n_opened != 0):
			print "%s still has %d open parentheses"%(left_str, \
								  n_opened)
			exit(-1)
		return char_i
	def str_to_expr_part(self, expr_part_str, old_assignments):
		(signed, number) = parse_literal(expr_part_str)
		if (number != None):
			return LiteralLeftExpression(signed, number)
		if (expr_part_str[0] == OPEN_PAREN):
			expr_part_str = expr_part_str[len(OPEN_PAREN) :
						      -len(CLOSE_PAREN)]
		return old_assignments[expr_part_str]
	def parse_left(self, left_str, old_assignments):
		a_end = self.range_expr(left_str)
		if (a_end == len(left_str)):
			return SingleLeftExpression(left_str)
		op_start = a_end + OP_SPACE_LEN
		if (left_str[a_end] != OP_SPACE):
			print left_str[a_end : ] + "does not have a space " + \
			      "before the operation"
		op_end = left_str.find(OP_SPACE, op_start)
		if (op_end < 0):
			print left_str[op_start : ] + \
			      "does not have an operation " + \
			      "followed by a space"
		b_start = op_end + OP_SPACE_LEN
		op = left_str[op_start : op_end]
		if (not op in OPS):
			print op + " is not a valid binary operation"
			exit(-1)
		a_expr = self.str_to_expr_part(left_str[ : a_end], \
					       old_assignments)
		b_expr = self.str_to_expr_part(left_str[b_start : ], \
					       old_assignments)
		return BinaryLeftExpression(op, a_expr, b_expr)
	def parse_lefts(self, left_strs, old_assignments):
		lefts = []

		left_strs.reverse()
		for left_str in left_strs:
			lefts.append(self.parse_left(left_str, old_assignments))
		lefts.reverse()

		return lefts

	def parse_right(self, right_str):
		if (len(right_str) == 0):
			return None
		return RangeRightSideValue(right_str)

	def __init__(self, assignment_str, old_assignments):
		assignment_parts = assignment_str.split(ASSIGNMENT_DELIM)
		left_strs = assignment_parts[ : -1]
		right_str = assignment_parts[-1]
		self.left_strs = left_strs

		self.lefts = self.parse_lefts(left_strs, old_assignments)
		self.right = self.parse_right(right_str)

	def __str__(self):
		right_str = None
		if (self.right == None):
			right_str = UNRESTRICTED_INT_STR
		else:
			right_str = str(self.right)
		return right_str
	def __eq__(self, other):
		if ((self is None) != (other is None)):
			return False
		return self.right == other.right

ASSIGNMENTS_DELIM = "\\"

class AssignmentsIntValue(IntValue):
	def __init__(self, assignments_str):
		IntValue.__init__(self)

		assignment = None
		assignment_strs = assignments_str.split(ASSIGNMENTS_DELIM)
		assignments = {}
		for assignment_i in range(len(assignment_strs) - 1 - 1, -1, -1):
			assignment_str = assignment_strs[assignment_i]
			assignment = Assignment(assignment_str, assignments)

			for left_str in assignment.left_strs:
				assignments[left_str] = assignment
		if (assignment == None):
			print assignments_str + " does not contain assignments"
			exit(-1)
		self.main_value = assignment
	def __str__(self):
		return str(self.main_value)
	def __eq__(self, other):
		if ((self is None) != (other is None)):
			return False
		return self.main_value == other.main_value

def parse_int(symbol_str, value_str, to_add = 1):
	as_list = to_add.__class__ == ListType
	assignments_str = None
	value = None
	range_value = None
	if (len(value_str) > 0):
		(signed, number) = parse_literal(value_str)
		if (number != None):
			value = LiteralIntValue(number, signed)
			int_value = value.value
			range_value = (RangeList([RangeNode(int_value,
							    int_value, \
							    to_add)], \
						 as_list))
		else:
			assignments_str = value_str
			value = AssignmentsIntValue(value_str)
			right = value.main_value.right
			if (right == None):
				range_value = None
			else:
				right_ranges = right.ranges
				new_ranges = []
				for rr in right_ranges:	
					new_ranges.append(RangeNode(rr[0], \
								    rr[1], \
								    to_add))
				if (len(new_ranges) == 0):
					range_value = None
				else:
					range_value = RangeList(new_ranges, \
								as_list)
	return ParsedInt(symbol_str, value, range_value, to_add)

def reparse_int(value_string, to_add = 1):
	range_value = None

	if (len(value_string) > 0 and value_string != UNKNOWN_STR):
		ranges = []
		range_strings = value_string.split(OUT_RANGES_DELIM)
		for range_string in range_strings:
			(least_str, most_str) = \
			range_string.split(OUT_RANGE_DELIM)
			least = int(least_str)
			most = int(most_str)
			ranges.append(RangeNode(least, most))
		range_value = RangeList(ranges, to_add)

	return ParsedInt(None, None, range_value, to_add)

class ParsedInt(ParsedValue):
	def __init__(self, symbol_str, value, range_value, to_add = 1):
		ParsedValue.__init__(self, INT_TYPE_START, symbol_str, to_add)

		self.value = value
		self.range_value = range_value
	def clone_new_data(self, data):
		new_range_value = None
		if (not self.range_value is None):
			new_range_value = self.range_value.clone_new_value(data)
		return ParsedInt(self.symbol_str, self.value, \
				 new_range_value, data)
	def value_to_string(self):
		if self.range_value is None:
			return UNRESTRICTED_INT_STR
		return self.range_value.short_str()
	def __eq__(self, other):
		if ((self is None) != (other is None)):
			return False
		if other.__class__ != ParsedInt:
			return False

		value_class = self.value.__class__
		other_value = other.value
		if other_value.__class__ != value_class:
			return False

		return self.value == other.value
	def is_unknown(self):
		return self.range_value == None
	def _overlaps(self, other_key):
		if (other_key is None or self.range_value == None):
			return True
		pre_self_range = str(hash(self.range_value))
		return self.range_value.overlaps_single(other_key)
	def is_exactly(self, value):
		if (self.range_value is None):
			return False
		else:
			return self.range_value.is_exactly(value)
	def contains(self, parsed_value):
		if (self.range_value is None):
			return True
		else:
			parsed_range = parsed_value.range_value
			return self.range_value.contains_list(parsed_range)
	def strictly_contains(self, other):
		return (not other.contains(self)) and self.contains(other)

SYMBOL_PRE = "&"

def parse_value(value_expr, to_add = 1):
	if (len(value_expr) == 0):
		return None
	type_str = value_expr[0]

	untyped_str = value_expr[1 : ]
	symbol_str = None
	value_str = None
	if (len(untyped_str) > 0 and untyped_str[0] == SYMBOL_PRE):
		symbol_end = untyped_str.find(ASSIGNMENT_DELIM)
		val_start = symbol_end + len(ASSIGNMENT_DELIM)

		symbol_str = untyped_str[ : symbol_end]
		value_str = untyped_str[val_start : ]
	else:
		value_str = untyped_str
	data = None
	if (type_str == VOID_TYPE_START):
		data = parse_void(to_add)
	elif (type_str == BOOL_TYPE_START):
		data = parse_boolean(symbol_str, value_str, to_add)
	elif (type_str == PTR_TYPE_START):
		data = parse_pointer(symbol_str, value_str, to_add)
	elif (type_str == INT_TYPE_START):
		data = parse_int(symbol_str, value_str, to_add)
	else:
		return None
	return type_str, data

def reparse_value(type_str, value_expr, to_add = 1):
	if (type_str == VOID_TYPE_START):
		data = reparse_void(to_add)
	elif (type_str == BOOL_TYPE_START):
		data = reparse_boolean(value_expr, to_add)
	elif (type_str == PTR_TYPE_START):
		data = reparse_pointer(value_expr, to_add)
	elif (type_str == INT_TYPE_START):
		data = reparse_int(value_expr, to_add)
	else:
		return None
	return data

def raw_to_value(type_str, raw, to_add = 1):
	if (type_str == VOID_TYPE_START):
		data = reparse_void(to_add)
	elif (type_str == BOOL_TYPE_START):
		data = reparse_boolean(raw, to_add)
	elif (type_str == PTR_TYPE_START):
		data = reparse_pointer(raw, to_add)
	elif (type_str == INT_TYPE_START):
		data = ParsedInt(None, None, raw, to_add)
	else:
		return None
	return data

def raw_to_str(type_marker, raw):
	if (type_marker == BOOL_TYPE_START):
		if (raw == BOOL_TRUE_STR):
			return BOOL_FALSE_STR
		elif (raw == BOOL_FALSE_STR):
			return BOOL_TRUE_STR
		else:
			return UNKNOWN_STR
	elif (type_marker == PTR_TYPE_START):
		if (raw == PTR_NOT_NULL_STR):
			return PTR_NULL_STR
		elif (raw == PTR_NULL_STR):
			return PTR_NOT_NULL_STR
		else:
			return UNKNOWN_STR
	elif (type_marker == INT_TYPE_START):
		return raw.short_str()
	else:
		return None

def binary_alternative(value_type, value_key):
	if (value_type == BOOL_TYPE_START):
		if (value_key == BOOL_TRUE_STR):
			return BOOL_FALSE_STR
		elif (value_key == BOOL_FALSE_STR):
			return BOOL_TRUE_STR
	elif (value_type == PTR_TYPE_START):
		if (value_key == PTR_NOT_NULL_STR):
			return PTR_NULL_STR
		elif (value_key == PTR_NULL_STR):
			return PTR_NOT_NULL_STR
	return None

def is_undefined(value_type, value_key):
	if (value_type == BOOL_TYPE_START and \
	    value_key == BOOL_STRS[BOOL_UNKNOWN]):
		return True
	elif (value_type == PTR_TYPE_START and \
	    value_key == PTR_STRS[PTR_UNKNOWN]):
		return True
	elif (value_type == INT_TYPE_START and value_key is None):
		return True
	return False
