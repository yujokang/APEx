# the main parser for parsing path information
# and generating error specifications
from parser_utils import OutputParser
from value_parser import parse_value, \
			 BOOL_TYPE_START, PTR_TYPE_START, INT_TYPE_START, \
			 VOID_TYPE_START, reparse_value, is_undefined
from ranges import RangeNode, RangeList, generate_smooth
from value_stats import initialize_stat, initialize_raw_stat, \
			BooleanStat, PointerStat, IntegerStat, to_label
from print_sorted_keys import sort_by_key, sorted_keys_string
from spec import ERROR_SPEC_PREFIX, INFALLIBLE_MARKER

from vote import ExtremeVote

from error_handler import throw_error

from sys import stdin, argv
from data_utilities import counts_to_stats, counts_to_stats_string

# delimits function name and location
FUNC_LOC_DELIM = " "
# delimits location and value
LOC_VAL_DELIM = ";"

# marks the end of the file name in the location
FILE_END_DELIM = ":"

# raw segment of the path string, without any parsed values
# original: the original string
# function: the function name
# location: the location at the end of the path segment
# value_str: the unparsed value string
class PreBasicPathSegment:
	# segment_str: the unparsed segment text
	def __init__(self, segment_str):
		function_end = segment_str.find(FUNC_LOC_DELIM)
		loc_start = function_end + len(FUNC_LOC_DELIM)
		loc_end = segment_str.find(LOC_VAL_DELIM)
		val_start = loc_end + len(LOC_VAL_DELIM)

		self.original = segment_str
		self.function = segment_str[ : function_end]
		self.location = segment_str[loc_start : loc_end]
		self.value_str = segment_str[val_start : ]
	# Generate the key to identify the section text.
	# returns the key representing the section text
	def get_key(self):
		return self.function + FUNC_LOC_DELIM + self.location + \
		       LOC_VAL_DELIM + self.value_str

# Converts the function call site to a key.
# function: the callee function
# location: the call site location
# returns the unique function-location key
def call_site_to_key(function, location):
	return (function, location)

# the base class for a parsed path segment
# have_data: do the othe fields in the segment exist?
# function: the function name in the segment text
# location: the code location in the segment text
# value: the parsed value
# count: the path length at this segment
class BasicPathSegment:
	# pre_segment: the partly-parsed segment data
	# to_add: the weight of the parsed value for statistics
	def __init__(self, pre_segment, to_add = 1):
		if (len(pre_segment.original) > 0):
			self.have_data = True

			self.function = pre_segment.function
			self.location = pre_segment.location

			value_pair = parse_value(pre_segment.value_str, to_add)
			if (value_pair is None):
				throw_error("Failed to parse return value, " + \
					    pre_segment.value_str)
			self.value = value_pair[1]
		else:
			self.have_data = False
		self.count = 0
	def __str__(self):
		if (self.have_data):
			return "%s->%s()->%s"%(self.location, self.function, \
					       str(self.value))
		else:
			return "_"
	# Generate a short representation of the segment
	# returns the short representation of the segment
	def short_str(self):
		return "%s->%s()"%(self.location, self.function)
	# Generate a short representation of the segment and those after it.
	# By default, there are no followers.
	# returns the short representation of the segment and those after it
	def short_follow_str(self):
		return self.short_str()
	# Generate the key to identify the segment's function and location.
	# returns the key representing the function and location of the site
	def get_key(self):
		return call_site_to_key(self.function, self.location)

# the segments following a call-site segment, sortable by the length
# follower: the next segment
# count: the length after this segment
# part_count: the partial count of the current segment
# path: the segment containing the segment
# index: the index of the following segment
class FollowerEdge:
	def __init__(self, follower, part_count, path, index):
		self.follower = follower
		self.count = part_count + follower.count
		self.path = path
		self.index = index
	def __gt__(self, o):
		return self.count > o.count
	def __ge__(self, o):
		return self.count >= o.count
	def __lt__(self, o):
		return self.count < o.count
	def __le__(self, o):
		return self.count <= o.count
	def __int__(self):
		return self.count

# marks the length of the segment
PRE_COUNT_DELIM = "#"

# partly parsed data of intermediate call site segments
class PreCalleeSegment(PreBasicPathSegment):
	# main_segment_str: the unparsed segment text
	# count: the length of the segment
	def __init__(self, main_segment_str, count):
		PreBasicPathSegment.__init__(self, main_segment_str)
		self.count = count
	# Are the function, location and value equal?
	# other: the other segment data to compare against
	# returns true iff the function, location and value string are equal
	def same_segment(self, other):
		return self.function == other.function and \
		       self.location == other.location and \
		       self.value_str == other.value_str;

# Generate preliminary data of segment string.
# segment_str: the unparsed segment text
# returns the partially-parsed data, of type PreCalleeSegment
def generate_pre_callee_segment(segment_str):
	main_end = segment_str.find(PRE_COUNT_DELIM)
	count_start  = main_end + len(PRE_COUNT_DELIM)

	main_segment_str = segment_str[ : main_end]
	part_count = int(segment_str[count_start : ])
	return PreCalleeSegment(main_segment_str, part_count)

# the segment iterator for a path
# segments: all the segments
# index: the index of the current segment to be returned
class SegmentIter:
	def __init__(self, path, index):
		self.segments = path.callees
		self.index = index
	def next(self):
		if (self.index == len(self.segments)):
			raise StopIteration
		else:
			old_segment = self.segments[self.index]
			self.index += 1
			return old_segment

# the intermediate segment identified by a call site
# index: the index of the segment
# follower_edge: the part of the path that follows
# path: the path containing this segment
# count: the count of the segment
class CalleePathSegment(BasicPathSegment):
	# pre_callee_segment: the partly-parsed data
	# index: index
	# follower_edge: follower_edge
	def __init__(self, pre_callee_segment, index, follower_edge):
		BasicPathSegment.__init__(self, pre_callee_segment,
					  [follower_edge])
		self.index = index
		self.follower_edge = follower_edge
		self.path = follower_edge.path
		self.count = pre_callee_segment.count
	def __str__(self):
		return "%s[%d]"%(BasicPathSegment.__str__(self), \
				 self.follower_edge.count)
	def short_follow_str(self):
		return self.short_str() + "," + \
		       self.follower_edge.follower.short_follow_str()
	def __iter__(self):
		return SegmentIter(self.path, self.index)

# Completely parse an intermediate segment.
# pre_callee_segment: the partly-parsed data
# follower: the follower edge
# path: the path containing the segment
# index: the index of the segment in the path
def generate_callee_segment(pre_callee_segment, follower, path, index):
	return CalleePathSegment(pre_callee_segment, index, \
				 FollowerEdge(follower, \
					      pre_callee_segment.count, path, \
					      index))

# the partly-generated segment at the end of the path,
# representing the end of the caller
class PreCallerSegment(PreBasicPathSegment):
	def __init__(self, segment_str):
		PreBasicPathSegment.__init__(self, segment_str)

# the final segment that contains caller exit data
# general_location: combined text for the file and function name
class CallerPathSegment(BasicPathSegment):
	def __init__(self, pre_caller_segment):
		BasicPathSegment.__init__(self, pre_caller_segment)
		if (self.have_data):
			file_end = self.location.find(FILE_END_DELIM)
			file_name = self.location[ : file_end]
			self.general_location = file_name + FUNC_LOC_DELIM + \
						self.function


# delimiter between path segments
PATH_SEGMENT_DELIM = "@"
# denotes if the path ended because of an exit function
EXIT_PATH_SUFFIX = "$"

# contains partially-parsed segments for a path,
# normalized to eliminate loops
# is_exit: did the path end because of an exit?
# caller: the caller segment
# callees: the intermediate segments
# n_callees: the number of callees
class PreCallPath:
	# line: the line containing the path text
	def __init__(self, line):
		if (len(line) > 0 and line[-1] == EXIT_PATH_SUFFIX):
			line = line[ : -1]
			self.is_exit = True
		else:
			self.is_exit = False

		segment_strs = line.split(PATH_SEGMENT_DELIM)
		self.caller = PreCallerSegment(segment_strs[-1])
		unnormalized_callees = map(generate_pre_callee_segment, \
					   segment_strs[ : -1])
		last_callee = unnormalized_callees[0]
		self.callees = [last_callee]

		for callee in unnormalized_callees:
			if not last_callee.same_segment(callee):
				last_callee = callee
				self.callees.append(last_callee)
		self.n_callees = len(self.callees)
	# Generate the key that represents the unique, normalized path.
	# returns the key made up of all the segments and whether or not
	#	  the path ended with an exit
	def get_key(self):
		key = ""
		for callee in self.callees:
			key += callee.get_key() + PATH_SEGMENT_DELIM
		key += self.caller.get_key()
		if (self.is_exit):
			key += EXIT_PATH_SUFFIX
		return key

# contains the processed path data
# is_exit: did the path end because of an exit?
# caller: the final, caller segment
# caller_location: the end location of the path
# is_error_exit: did the path exit because of an error?
# callees: the intermediate, callee segments
# length: the length of the path
class CallPath:
	def __init__(self, pre_call_path):
		self.is_exit = pre_call_path.is_exit
		self.caller = CallerPathSegment(pre_call_path.caller)
		self.caller_location = self.caller.general_location
		self.is_error_exit = False
		if (self.is_exit):
			self.is_error_exit = not self.caller.value.is_exactly(0)

		follower = self.caller
		n_callees = pre_call_path.n_callees
		self.callees = [None] * n_callees
		for callee_i in range(n_callees - 1, -1, -1):
			follower_i = callee_i + 1
			segment_str = pre_call_path.callees[callee_i]
			callee = generate_callee_segment(segment_str, \
							 follower, self, \
							 follower_i)
			self.callees[callee_i] = callee
			follower = callee
		self.length = 0
		if (n_callees > 1):
			self.length = self.callees[0].count
	def __str__(self):
		header = str(self.caller) + "\n" + str(len(self.callees))
		segment_list_str =  "\n".join(map(str, self.callees))
		return header + "\n" + segment_list_str

	# Generate a short version of the string, without the full value data.
	# returns a short string representation of this path
	def short_str(self):
		header = self.caller.short_str()
		segment_list_str = \
		";".join(map(lambda callee: callee.short_str(), self.callees))
		return header + ":" + segment_list_str

# prefix for vote statistic lines
VOTE_STAT_PREFIX = "Votes:"
# denotes that the information is about the function
FUNCTION_VOTE_MARKER = "F"
# denotes that the information is about the VotePoint
VOTE_POINT_MARKER = "P"

# for the output text, separates function and type
FUNC_TYPE_DELIM = " "
# for the output text, separates the constraint and the VotePoint
VOTE_FUNC_DELIM = ":"
# separates the fields in the string representation of the VotePoint
VOTE_COORD_DELIM = ","

# data used to determine whether a constraint is an error constraint or not
# count: the path count
# length: the length of the path following the call site
# chosen_threshold: has this vote passed the threshold?
class VotePoint:
	# count: count
	# length: length
	def __init__(self, count, length):
		self.count = count
		self.length = length
		self.chosen_threshold = False
	# Set chosen_threshold to true
	def choose_threshold(self):
		self.chosen_threshold = True
	def __str__(self):
		return VOTE_COORD_DELIM.join([str(self.count), \
					      str(self.length), \
					      str(self.chosen_threshold)])

# information about calls to a function in a program
# name: the name of the function
# branch_stat: branch statistics for each return value constraint
# callee_type: the return type
# rangify: is the return value represented as a type?
# site_paths: maps call sites to paths that pass through them
# bin_limit: the maximum number of bins
# low_ratio: the number of standard deviations that a low value should be
#	     below the average
# high_ratio: the number of standard deviations that a high value should be
#	      above the average
# vote_points: the VotePoints objects for each constraint
# exit_votes: votes based on paths that exit with an error
# threshold_infallible: is the function infallible according to this program?
# threshold_votes: the votes based on path characteristics
# unknown_count: the number of sites
#		  where the return value is completely unknown
# known_count: the number of sites
#	       where the return value is at least partly known
# unknown_vote: keeps track of whether or not return value should be ignored
class FunctionCalls:
	# callee_segment: the first call site to add
	# path: the first path to add
	# bin_limit: bin_limit
	# low_ratio: low_ratio
	# high_ratio: high_ratio
	def __init__(self, callee_segment, path, bin_limit, \
		     low_ratio, high_ratio):
		self.name = callee_segment.function
		self.branch_stat = initialize_stat(callee_segment.value, True)
		self.callee_type = callee_segment.value.type_marker
		self.rangify = self.callee_type == INT_TYPE_START
		self.site_paths = {}

		self.bin_limit = bin_limit
		self.low_ratio = low_ratio
		self.high_ratio = high_ratio

		self.vote_points = None
		self.exit_votes = None
		self.threshold_infallible = False
		self.threshold_votes = None
		self.unknown_count = 0
		self.known_count = 0
		self.unknown_vote = ExtremeVote(False, high_ratio)

		self.add(callee_segment, path)
	# Add call site information from a callee segment.
	# callee_segment: the first call site to add
	# path: the first path to add
	def add(self, callee_segment, path):
		site_key = callee_segment.location

		these_site_paths = None
		if (self.site_paths.has_key(site_key)):
			these_site_paths = self.site_paths[site_key]
		else:
			these_site_paths = []
			self.site_paths[site_key] = these_site_paths
		these_site_paths.append((callee_segment, path))

		value = \
		callee_segment.value \
			      .clone_new_data([callee_segment.follower_edge])
		self.branch_stat.update(value)

		if (path.caller.value.type_marker == VOID_TYPE_START):
			return

		if (path.caller.value.is_unknown()):
			self.unknown_count += 1
			self.unknown_vote.tally(True, 1)
		else:
			self.known_count += 1
			self.unknown_vote.tally(False, 1)
	# Based on the number of unknown return values,
	# the return value is unchecked.
	# returns true iff there are significantly more unknown return values
	#	  than known ones
	def too_many_unknown(self):
		return self.unknown_vote.vote() == True
	# Get a list of this program's pairs of call sites
	# and the list of paths that run through them.
	# returns the site-paths pairs of the dictionary
	#	  mapping call sites to the paths that go through them
	def get_site_paths(self):
		return self.site_paths.items()
	# Generate a string representation of the values.
	# returns a string representing value statistics
	def values_str(self):
		value_branch_lengths = ""
		for (key, branches) in self.branch_stat:
			value_branch_lengths += to_label(key)
			value_branch_lengths += ": "
			value_branch_lengths += counts_to_stats_string(branches)
			value_branch_lengths += "\n"
		return value_branch_lengths
	def __str__(self):
		return "%s():\n%s\n"%(self.name, self.values_str())
	# Generate the normalized statistics of the constraints.
	# returns the constraint path counts, but normalized.
	def gen_normalized(self):
		return self.branch_stat.gen_normalized()
	# Check if there are too many bins.
	# returns true iff the bin count is over the limit
	def check_bins(self, bin_set, total_count):
		too_many = len(bin_set) > self.bin_limit
		return too_many
	# Vote based on the statistics of the paths.
	def tally_threshold(self):
		bins = set()
		# Vote based on path counts and path length,
		# which should be low
		least_count_vote = ExtremeVote(True, self.low_ratio, 2, \
					       allow_tie = self.rangify, \
					       only_threshold = self.rangify)
		shortest_path_vote = ExtremeVote(True, self.low_ratio, 2, \
						 allow_tie = self.rangify, \
					         only_threshold = self.rangify)
		index = 0
		for (key, point) in self.vote_points:
			bins.add(to_label(key))
			if (point.count > 0):
				least_count_vote.tally(index, point.count)
			shortest_path_vote.tally(index, point.length)
			index += 1
		if (self.check_bins(bins, self.branch_stat.get_total_count())):
			self.threshold_infallible = True
			return

		# First try path count, then try path length.
		least_count_votes = least_count_vote.vote()
		if (not least_count_votes is None):
			self.threshold_votes = least_count_votes
			return
		shortest_path_votes = shortest_path_vote.vote()
		if (not shortest_path_votes is None):
			self.threshold_votes = shortest_path_votes
			return

	# Perform complete vote for the program.
	def generate_votes(self):
		need_any_count = True
		self.vote_points = []
		most_exit_vote = ExtremeVote(False, self.high_ratio, \
					     allow_tie = self.rangify, \
					     only_threshold = self.rangify)
		# Process constraints to vote on them.
		index = 0
		for (key, followers) in self.branch_stat:
			need_any_count = False
			original_count = len(followers)
			if (is_undefined(self.callee_type, key)):
				continue

			exit_count = 0
			path_lengths = []
			for follower in followers:
				if (follower.path.is_error_exit):
					exit_count += 1
				path_lengths.append(follower.count)

			count = original_count - exit_count
			if (exit_count > 0):
				most_exit_vote.tally(index, exit_count)
			if (original_count > 0):
				(_, _, median_length, _) = \
				counts_to_stats(path_lengths)
				point = VotePoint(count, median_length)
				self.vote_points.append((key, point))
			index += 1
		if (need_any_count):
			throw_error("Passed empty vote statistic")

		# Vote based on error exits.
		self.exit_votes = most_exit_vote.vote()

		# Vote based on path statistics.
		self.tally_threshold()
		if (not self.threshold_votes is None):
			for index in self.threshold_votes:
				self.vote_points[index][1].choose_threshold()

	# Generate string representation of vote.
	# returns string representation of vote
	def vote_str(self):
		points_strs = map(lambda (key, point): \
				  VOTE_STAT_PREFIX + VOTE_POINT_MARKER + \
				  "%s%s%s"%(to_label(key), VOTE_FUNC_DELIM, \
					    point), \
				  self.vote_points)
		points_str = "\n".join(points_strs)
		return VOTE_STAT_PREFIX + FUNCTION_VOTE_MARKER + \
		       self.name  + FUNC_TYPE_DELIM + self.callee_type + \
		       "\n" + points_str

	# Cast the vote for this program using the first method that has a vote.
	# vote_holder: the object in which to cast the vote
	# votes: the constraints to vote for
	# infallible: does the program consider the function infallible?
	def _cast_vote(self, vote_holder, votes, infallible = None):
		if (infallible is None):
			infallible = votes is None
		total_count = self.branch_stat.get_total_count()
		if (infallible or votes is None):
			# Vote that the function is infallible.
			vote_holder.record_vote(None, 1.0, total_count)
		else:
			# Vote for the specific constraints.
			key_votes = []
			for index in votes:
				key_votes.append(self.vote_points[index][0])
			if (self.rangify):
				error_range = RangeList(key_votes, False)
				vote_holder.record_vote(error_range, 1.0, \
							total_count)
			else:
				vote_holder.record_votes(key_votes, \
							 total_count)
	# Cast the vote for this program.
	# vote_holder: the object in which to cast the vote
	def cast_vote(self, vote_holder):
		# Count the function as infallible because there are too many
		# different constraints.
		if (False and self.too_many_unknown()):
			total_count = self.branch_stat.get_total_count()
			vote_holder.record_vote(None, 1.0, total_count)
		# Try to vote based on error exits.
		if (not self.exit_votes is None):
			self._cast_vote(vote_holder, self.exit_votes, False)
		# Try to vote based on path statistics.
		else:
			self._cast_vote(vote_holder, self.threshold_votes, \
					self.threshold_infallible)

# Generate a function to initialize a FunctionCalls classes.
# bin_limit: the maximum number of different constraints
# low_ratio: the number of standard deviations that a low value should be
#	     below the average
# high_ratio: the number of standard deviations that a high value should be
#	      above the average
# returns a function to generate a FunctionCalls class,
#	  given a callee segment and the containing path
def gen_function_call_stats_generator(bin_limit, low_ratio, high_ratio):
	return lambda callee, path : \
	       FunctionCalls(callee, path, bin_limit, low_ratio, high_ratio)

# the prefix of the checker output lines we want to read
AUTO_EPEX_START = "AutoEPEx: "

# marks the beginning of a new file
NEW_FILE_MARKER = "NEW FILE"

# the maximum number of distinct constraints
BIN_LIMIT = 6.0

# the high and low threshold ratios
THRESHOLD_RATIO = 1.0
# the voting ratio by which the winner must lead
VOTE_RATIO = 1.0

# the main parser for the checker output
# bin_limit: the maximum number of different constraints
# low_ratio: the number of standard deviations that a low value should be
#	     below the average
# high_ratio: the number of standard deviations that a high value should be
#	      above the average
# seen: the seen paths in the current file
# functions: the statistics organized by function
# not_wrapped: call sites where we know the return value is not wrapped
# maybe_wrapped: call sites for which we have not found cases where
#		 the return value is not wrapped
# 
class AutoEPExParser(OutputParser):
	# output_handle: the output stream
	# input_handle: the input stream
	# bin_limit: bin_limit
	# low_ratio: low_ratio
	# high_ratio: high_ratio
	def __init__(self, output_handle, input_handle = stdin, \
		     bin_limit = BIN_LIMIT, low_ratio = THRESHOLD_RATIO, \
		     high_ratio = THRESHOLD_RATIO):
		OutputParser.__init__(self, AUTO_EPEX_START, \
				      output_handle, input_handle)
		self.bin_limit = bin_limit
		self.low_ratio = low_ratio
		self.high_ratio = high_ratio

		self.seen = {}
		self.functions = {}
		self.not_wrapped = set()
		self.maybe_wrapped = {}
	# Add a call site.
	# callee: the call site
	# path: the path containing the call site
	def add_callee(self, callee, path):
		function_name = callee.function
		callee_type = callee.value.type_marker
		key = (function_name, callee_type)
		# Add the call site to the function if it already exists.
		# Otherwise, create the function data object.
		if (self.functions.has_key(key)):
			self.functions[key].add(callee, path)
		else:
			self.functions[key] = \
			FunctionCalls(callee, path, self.bin_limit, \
				      self.low_ratio, self.high_ratio)
	# When we know a call site's return value
	# is not simply wrapped by the caller,
	# record all the previous instances of the site to the statistics.
	# site_key: the key for the site to record as not wrapped
	def add_unwrapped(self, site_key):
		if (self.maybe_wrapped.has_key(site_key)):
			sites = self.maybe_wrapped[site_key]

			for (callee, path) in sites:
				self.add_callee(callee, path)

			del self.maybe_wrapped[site_key]
	# Handle a single call site segment in a path.
	# callee: the call site segment
	# path: the path containing the segment
	def handle_callee(self, callee, path):
		# Ignore empty segments (this should not occur).
		if (not callee.have_data):
			return
		site_key = callee.get_key()
		should_add = None

		# Check and update if the site is wrapped.
		if (site_key in self.not_wrapped):
			should_add = True
		elif (not path.caller.value.same_assignments(callee.value)):
			self.not_wrapped.add(site_key)
			should_add = True
		else:
			should_add = False

		# If we already know that the site is not wrapped,
		# record it in the statistics.
		if (should_add):
			self.add_unwrapped(site_key)
			self.add_callee(callee, path)
		else:
			maybe_entry = (callee, path)
			if (self.maybe_wrapped.has_key(site_key)):
				self.maybe_wrapped[site_key].append(maybe_entry)
			else:
				self.maybe_wrapped[site_key] = [maybe_entry]
	# Get a list of all programs' pairs of call sites
	# and the list of paths that run through them.
	# returns the site-paths pairs of the dictionary
	#	  mapping call sites to the paths that go through them
	def get_site_paths(self):
		site_paths = []
		for (key, function_data) in self.functions.items():
			site_paths.append((key, function_data.get_site_paths()))
		return site_paths
	# Handle a line, which could indicate a new file, or contain a path.
	# line: the line
	# returns the path if the line contains one
	def handle_line(self, line):
		# Reset the wrapping data upon a new file.
		if (line.rstrip() == NEW_FILE_MARKER):
			self.not_wrapped = set()
			self.maybe_wrapped = {}
			return None
		pre_path = PreCallPath(line)
		path_key = pre_path.get_key()
		if (self.seen.has_key(path_key)):
			return None

		self.seen[path_key] = 1
		path = CallPath(pre_path)

		for callee in path.callees:
			self.handle_callee(callee, path)

		return str(path) + "\n"
	# Generate votes and output a program summary.
	def finish(self):
		function_summary = ""
		for (name, function) in sort_by_key(self.functions):
			function.generate_votes()
			function_summary += function.vote_str() + "\n"
		callsite_summary = ""

		return "Function information:\n" + function_summary + \
		       "Per call-site profiles:\n" + callsite_summary

# the inferred error specification
# errors: lookup table for the vote results for the error specification
# checkers: lookup table for the values of the error specification,
#	    used for checking overlaps
class ErrorSpec:
	def __init__(self):
		self.errors = {}
		self.checkers = {}
	# Generate the key to access the function error specification.
	# function: the function name
	# return_type: the return type of the function
	# returns the key that identifies the function and its return type
	def _to_key(self, function, return_type):
		return (function, return_type)
	# Add an entry if there is not already one for the function.
	# function: the function name
	# return_type: the return type of the function
	# error_result: contains the vote result
	def add(self, function, return_type, error_result):
		key = self._to_key(function, return_type)
		if (not self.errors.has_key(key)):
			self.errors[key] = (function, error_result)
			checker_str = str(error_result)
			# Add the checker value, if it exists.
			if (len(checker_str) > 0):
				self.checkers[key] = \
				reparse_value(return_type, checker_str)
	# Check if the function's error specification
	# at least partly covers another label.
	# key: the key for the error specification
	# other_label: the value to check for coverage
	# returns true iff the error specification overlaps with the value
	def covers(self, key, other_label):
		if (self.checkers.has_key(key)):
			return self.checkers[key].overlaps(other_label)
		else:
			return False
	# Get the error specification for a function.
	# function: the function name
	# return_type: the return type of the function
	# returns the function's error vote result if it exists, None otherwise
	def get_spec(self, function, return_type):
		key = self._to_key(function, return_type)
		if (self.errors.has_key(key)):
			return self.errors[key][1]
		else:
			return None
	def __str__(self):
		# Generate the error specification file.
		sorted_pairs = sort_by_key(self.errors)
		to_return = ""
		for ((function, return_type), (function, value)) in \
		     sorted_pairs:
			if (value is None or value.choose_infallible()):
				to_return += "%s%s %s %s"%(ERROR_SPEC_PREFIX,
							   function, \
							   return_type, \
							   INFALLIBLE_MARKER)
			elif (value.have_valid_result()):
				to_return += "%s%s %s %s"%(ERROR_SPEC_PREFIX,
							   function, \
							   return_type, \
							   value)
			else:
				continue
			to_return += "\n"
		return to_return

# delimiter between multiple error specification ranges
ERRORS_DELIM = ","

# result of voting on error specification between programs
# votes: the per-program vote
# is_infallible: is the function infallible?
# n_infallibles: number of votes for infallibility
# changed: do the votes need to be recounted?
# winners: the winning error specification constraints
class VoteResult:
	# threshold_ratio: the threshold ratio for the winning votes
	# as_list: if voting on integer ranges,
	#	   this value is not None, and determines if the ranges
	#	   will contain a lists as their values
	def __init__(self, threshold_ratio, as_list = None):
		self.votes = ExtremeVote(False, threshold_ratio, \
					 as_list = as_list)
		self.is_infallible = False
		self.n_infallibles = 0
		self.changed = True
		self.winners = None
	# Count an infallible vote. This function can be overridden.
	# decision: the voted constraint
	# increment: the vote weight
	def _count_vote(self, decision, increment):
		self.votes.tally(decision, increment)
		self.changed = True
	# Count a vote.
	# decision: the voted constraint
	# increment: the vote weight
	def count_vote(self, decision, increment):
		if (increment == 0):
			return
		if (decision is None):
			self.n_infallibles += increment
		else:
			self._count_vote(decision, increment)
	# Perform any type-specific preprocessing.
	def preprocess_winners(self):
		pass
	# Perform any type-specific postprocessing.
	def postprocess_winners(self):
		pass
	# Calculate the winners.
	# returns the winning error constraints
	def get_winners(self):
		self.preprocess_winners()
		self.winners = None
		if (self.votes.top_strength is None):
			pass
		elif (self.n_infallibles > self.votes.top_strength):
			self.is_infallible = True
		else:
			self.winners = self.votes.vote()
		self.changed = False
		self.postprocess_winners()
		return self.winners
	# Get a string representation of the winners.
	# returns a string representation of the winning result
	def get_winner_strs(self):
		return (map(str, self.winners))
	# Check if there is a valid error constraint.
	# returns true iff there exist valid error constraints
	def have_valid_result(self):
		if (self.changed):
			self.get_winners()
		return (not self.winners is None) and len(self.winners) > 0
	# Check if the function is voted as infallible.
	# returns true iff the is_infallible field is set
	def choose_infallible(self):
		return self.is_infallible
	def __str__(self):
		if (self.changed):
			self.get_winners()
		if (not self.have_valid_result()):
			return ""

		winner_strs = []
		if (not self.is_infallible):
			winner_strs = self.get_winner_strs()
		return ERRORS_DELIM.join(winner_strs)

# integer-specific voting results
# range_votes: the votes for range nodes
class RangeVoteResult(VoteResult):
	# threshold_ratio: the threshold ratio for the winning votes
	# as_list: determines if the ranges
	#	   will contain a lists as their values
	def __init__(self, threshold_ratio, as_list = False):
		VoteResult.__init__(self, threshold_ratio, as_list)
		self.range_votes = RangeList([], as_list)
	def _count_vote(self, decision, increment):
		self.range_votes \
		    .add(decision.clone_new_value(increment))
	# Tally the range nodes.
	def preprocess_winners(self):
		for (range_node, range_count) in self.range_votes:
			if (range_count > 0):
				self.votes.tally(range_node, range_count)
	# Combine contiguous winning ranges.
	def postprocess_winners(self):
		old_winners = self.winners
		if (old_winners is None):
			return
		smoothened_winners = map(lambda r: generate_smooth(r.ranges), \
					 old_winners)
		self.winners = smoothened_winners
	# Get the short version of the winning ranges' strings.
	# returns the short string version of the winning ranges
	def get_winner_strs(self):
		return map(lambda w: w.short_str(), self.winners)

# Initialize the vote result object based on type.
# stat_type: the return type
# threshold_ratio: the threshold ratio for winning votes
# returns RangeVoteResult for integers, and VoteResult for the rest
def init_vote_result(stat_type, threshold_ratio):
	if (stat_type == INT_TYPE_START):
		return RangeVoteResult(threshold_ratio)
	else:
		return VoteResult(threshold_ratio)

# the inter-program vote holder
# function_name: the name of the function
# votes: the per-program votes
# counts: the number of appearances of the function per program
# stat_type: the return type
# rangify: if the type is an integer, the constraints must be ranges
# as_list: False for integers, None otherwise. Used for VoteResult
# changed: do we need to recount the votes?
# total_strength: the total number of appearances of the function
# bin_limit: the maximum number of different constraints
# low_ratio: the number of standard deviations that a low value should be
#	     below the average
# high_ratio: the number of standard deviations that a high value should be
#	      above the average
# vote_ratio: the threshold ratio for the winning votes
class Vote:
	def __init__(self, function_name, stat_type, \
		     bin_limit, low_ratio, high_ratio, vote_ratio):
		self.function_name = function_name
		self.votes = {}
		self.counts = []
		self.stat_type = stat_type
		rangify = stat_type == INT_TYPE_START
		self.rangify = rangify
		self.as_list = None
		if (rangify):
			self.as_list = False
		self.changed = True
		self.result = None
		self.total_strength = 0
		self.bin_limit = bin_limit
		self.low_ratio = low_ratio
		self.high_ratio = high_ratio
		self.vote_ratio = vote_ratio
	# Record a single constraint vote.
	# key: the constraint
	# share: the weight to add
	# strength: the number of appearances of the function in the program
	def record_vote(self, key, share, strength):
		self.total_strength += strength
		vote = (share, strength)
		if (self.votes.has_key(key)):
			self.votes[key].append(vote)
		else:
			self.votes[key] = [vote]
		self.counts.append(strength)
	# Record a set of constraint votes.
	# votes: the constraints
	# strength: the number of appearances of the function in the program
	def record_votes(self, votes, strength):
		for vote in votes:
			self.record_vote(vote, 1.0 / len(votes), \
					 strength)
	# Check if there are too many bins.
	# returns true iff the bin count is over the limit
	def check_bins(self, bin_set, total_count):
		too_many = len(bin_set) > self.bin_limit
		return too_many
	# Decide on the error specification.
	def decide(self):
		self.changed = False
		if (len(self.votes) == 0):
			return
		stats = counts_to_stats(self.counts)
		if (stats is None):
			throw_error("No votes")
		# For the program to vote,
		# require the number of appearances of the function
		# to be above the lower quartile, or 2,
		# whichever is larger
		(_, threshold, _, _) = stats
		if (threshold <= 1.0):
			threshold = 2.0
		self.result = init_vote_result(self.stat_type, self.vote_ratio)
		bins = set()
		# For each vote,
		# only count programs with enough function appearances
		# towards the vote.
		for (key, votes) in self.votes.items():
			if (not key is None):
				bins.add(to_label(key))
			n_votes = 0
			for (share, strength) in votes:
				if (strength >= threshold):
					n_votes += share
			self.result.count_vote(key, n_votes)
		# Check if there are too many bins.
		if (self.check_bins(bins, self.total_strength)):
			self.result.is_infallible = True
			return
	# Add the result to the error specification.
	# spec the output specification
	def add_to_spec(self, spec):
		if (self.changed):
			self.decide()
		if (len(self.votes) > 0 and self.result.have_valid_result()):
			spec.add(self.function_name, self.stat_type, \
				 self.result)

# the prefix for lines predicting whether a path is an error path or not
PREDICTION_PREFIX = "Prediction: "

# csv row for predicting whether or not
# a constraint overlaps with the error range
# function: the function name
# return_type: the return type of the function
# constraint: the constraint for which to make the prediction
# count: the number of paths following this constraint
# prediction: the prediction about
#	      whether this constraint overlaps with the error range
class PredictionRow:
	# function: function
	# return_type: return_type
	# constraint: constraint
	# count: count
	# prediction: prediction
	def __init__(self, function, return_type, constraint, count, \
		     prediction):
		self.function = function
		self.return_type = return_type
		self.constraint = constraint
		self.count = count
		self.prediction = prediction
	# Return the key for this function.
	# returns the key identifying the function and its return type
	def get_key(self):
		return (self.function, self.return_type)

# combined information about parsed file data
# functions: per-function statistics
# unnormalized: unnormalized function data
# function_unknowns: number of unknown return values per function appearance
# function_knowns: number of known return values per function appearance
# votes: the vote holders for each function
# bin_limit: the maximum number of different constraints
# low_ratio: the number of standard deviations that a low value should be
#	     below the average
# high_ratio: the number of standard deviations that a high value should be
#	      above the average
# vote_ratio: the threshold ratio for the winning votes
# error_specs: the generated error specification
# prediction_rows: prediction about the constraints
class AutoEPExSum:
	# bin_limit: bin_limit
	# low_ratio: low_ratio
	# high_ratio: high_ratio
	# vote_ratio: vote_ratio
	def __init__(self, bin_limit = BIN_LIMIT, low_ratio = THRESHOLD_RATIO, \
		     high_ratio = THRESHOLD_RATIO, vote_ratio = VOTE_RATIO):
		self.functions = {}
		self.unnormalized = {}
		self.function_unknowns = {}
		self.function_knowns = {}
		self.votes = {}
		self.bin_limit = bin_limit
		self.low_ratio = low_ratio
		self.high_ratio = high_ratio
		self.vote_ratio = vote_ratio
		self.error_specs = None
		self.prediction_rows = []
	# Add the data for a program,
	# and calculate and record its votes and normalized path counts.
	# parsed: the parsed program data
	def add(self, parsed):
		# Get data per function.
		for (key, data) in parsed.functions.items():
			function_name = key[0]
			stat = data.branch_stat
			normalized_data = stat.gen_normalized()
			unnormalized_data = stat.gen_unnormalized()
			total_count = stat.get_total_count()
			vote_holder = None
			unknown_count = data.unknown_count
			known_count = data.known_count
			if (self.functions.has_key(key)):
				self.functions[key] += normalized_data
				self.unnormalized[key] += unnormalized_data
				self.function_unknowns[key] += unknown_count
				self.function_knowns[key] += known_count
				vote_holder = self.votes[key]
			else:
				self.functions[key] = normalized_data
				self.unnormalized[key] = unnormalized_data
				self.function_unknowns[key] = unknown_count
				self.function_knowns[key] = known_count
				vote_holder = Vote(function_name, \
						   stat.type_marker, \
						   self.bin_limit, \
						   self.low_ratio, \
						   self.high_ratio, \
						   self.vote_ratio)
				self.votes[key] = vote_holder
			data.cast_vote(vote_holder)
	# Choose a function's error specification
	# by using the normalized path count.
	# function: the function name
	# type_marker: the function's return type
	# normalized_stat: the normalized statistics for the function
	# unknown_count: the number of unknown return values
	# known_count: the number of known return values
	# error_specs: the output error specifications
	def choose_by_normalized(self, function, type_marker, normalized_stat, \
				 unknown_count, known_count, error_specs):
		# Check if the function should even be fallible.
		unknown_vote = ExtremeVote(False, self.high_ratio)
		for _ in range(unknown_count):
			unknown_vote.tally(True, 1)
		for _ in range(known_count):
			unknown_vote.tally(False, 1)
		if (False and unknown_vote.vote() == True):
			error_specs.add(function, type_marker, None)
			return

		# Don't give list weights for ranges.
		as_list = None
		type_marker = normalized_stat.type_marker
		if (type_marker == INT_TYPE_START):
			as_list = False

		# Combine the normalized votes.
		function_vote = ExtremeVote(True, self.low_ratio, 2, \
					    as_list)
		for (key, ratio) in normalized_stat:
			if (not is_undefined(type_marker, key)):
				function_vote.tally(key, ratio)

		if (function_vote.get_n_distinct_votes() > self.bin_limit):
			return

		# Add the result, if there is one.
		results = function_vote.vote()
		if (not results is None):
			result_vote = init_vote_result(type_marker, \
						       self.high_ratio)
			for result in results:
				result_vote.count_vote(result, 1)
			error_specs.add(function, type_marker, result_vote)
	# Generate the error specifications.
	def fill_error_specs(self):
		# Generate the error specifications using choose_by_normalized.
		self.error_specs = ErrorSpec()
		for (key, ratios) in self.functions.items():
			function, type_marker = key
			unknown_count = self.function_unknowns[key]
			known_count = self.function_knowns[key]
			self.choose_by_normalized(function, type_marker, \
						  ratios, unknown_count, \
						  known_count, self.error_specs)
		# Generate any remaining error specifications
		# by voting per program.
		for vote_value in self.votes.values():
			vote_value.add_to_spec(self.error_specs)
	def __str__(self):
		self.fill_error_specs()
		sorted_pairs = sort_by_key(self.functions)
		sorted_string = ""

		for ((function, site), value) in sorted_pairs:
			sorted_string += "%s:\n%s\n\n"%(function, value)

		classification_str = ""
		for (key, stats) in self.unnormalized.items():
			(function, return_type) = key
			for (label, count) in stats:
				if is_undefined(return_type, label):
					continue
				prediction = self.error_specs.covers(key, label)
				prediction_row = \
				PredictionRow(function, return_type, label, \
					      count, prediction)
				self.prediction_rows.append(prediction_row)
				classification_str += \
				PREDICTION_PREFIX + \
				"%s,%s,%s,%s\n"%(function, label, prediction, \
						 count)

		return "Normalized sums:\n" + sorted_string + \
		       "\nfunction,constraint,prediction,count\n" + \
		       classification_str + \
		       "\nReturn error specifications:\n" + \
		       str(self.error_specs)

if __name__ == "__main__":
	OUTPUT_I = 1
	INPUT_I = OUTPUT_I + 1

	if (len(argv) <= OUTPUT_I):
		throw_error("Please enter the output file")

	output_name = argv[OUTPUT_I]
	output_file = open(output_name, "w")
	if (output_file is None):
		throw_error("Could not open %s for output file"%output_file)

	if (len(argv) > INPUT_I):
		input_name = argv[INPUT_I]
		input_file = open(input_name, "r")
		if (input_file is None):
			output_file.close()
			throw_error("Could not open " + input_file + \
				    " for input file")
	else:
		input_file = stdin

	parser = AutoEPExParser(output_file, input_file)
	parser.read_lines()
	output_file.close()
	if (input_file != stdin):
		input_file.close()
