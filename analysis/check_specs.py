# basic application of the error specifications that looks for
# unchecked function return values
from auto_epex_parser import AutoEPExParser, ErrorSpec, ERROR_SPEC_PREFIX
from ranges import OUT_RANGE_DELIM, RangeNode
from vote import add_polar_vote, init_polar_vote
from time import time

from parser_utils import OutputParser
from value_parser import VOID_TYPE_START, BOOL_TYPE_START, PTR_TYPE_START, \
			 INT_TYPE_START
from value_stats import to_label, COVER_OVER, COVER_EXACT, COVER_UNDER, \
			initialize_raw_stat, to_label

from error_handler import add_line, clear_history, throw_error
from spec import FullErrorSpec
from print_sorted_keys import sort_by_key

from sys import argv
from data_utilities import add_to_dict, do_to_dict
from file_utilities import get_extensionless_name, get_dir

from math import sqrt

# general delimiter
DELIM = " "

# parses the error specification
# spec: the parsed error specification
class ErrorSpecParser(OutputParser):
	# input_handle: the input reading stream
	def __init__(self, input_handle):
		OutputParser.__init__(self, ERROR_SPEC_PREFIX, \
				      None, input_handle)
		self.spec = ErrorSpec()
	# Parse an error range specification
	# range_string: the string representing an integer range
	# return the range represented by the string
	def parse_range(self, range_string):
		(least_str, most_str) = range_string.split(OUT_RANGE_DELIM)
		return RangeNode(int(least_str), int(most_str))
	# Read as specification line.
	# line: the line representing a specification
	# returns None
	def handle_line(self, line):
		(function, return_type, error_result_str) = line.split(DELIM)
		error_result = None
		if (return_type == INT_TYPE_START):
			error_result = self.parse_range(error_result_str)
		else:
			error_result = error_result_str
		self.spec.add(function, return_type, error_result)
		return None
	# Fetch a specification.
	# function: the name of the function
	# return_type: the return type of the function
	def get_spec(self, function, return_type):
		return self.spec.get_spec(function, return_type)

# organizes bug reports by caller
# caller: the caller function
# report_str: the report string
# n_bugs: number of bugs found
# can_try: the report still has not been generated
# reports: the site reports
class CallerReport:
	# caller: caller
	# site_reports: the initial list of site reports
	def __init__(self, caller, site_reports):
		self.caller = caller
		self.report_str = None
		self.n_bugs = 0
		self.can_try = True
		self.reports = {}
		for site_report in site_reports:
			self.add_site_report(site_report)
	# Add one site report.
	# site_report: the site report to add
	def add_site_report(self, site_report):
		self.reports[site_report.site] = site_report
	# Combine two caller reports, using the caller of this object.
	# other: the other caller report for the sum
	def __add__(self, other):
		total = CallerReport(self.caller, self.reports.values())
		for site_report in other.reports.values():
			total.add_site_report(site_report)
		return total
	# Assuming we still don't have a report, create one.
	# threshold_ratio: the checking threshold ratio
	# min_sites: the minimum number of sites to reject the bugs
	# check_counts: the votes on whether or not
	#		the function should not be checked
	# returns the report string and bug count
	def try_report(self, threshold_ratio, min_sites, check_counts):
		reports = ""
		bug_count = 0
		for (site, site_report) in sort_by_key(self.reports):
			site_report_str = site_report.report()
			# Only record if there is a possible report.
			if (not site_report_str is None):
				callee = site_report.function
				report_line = \
				"\t%s->%s(): %s\n"%(site, callee, \
						    site_report_str)
				# Immediately count certain reports.
				if (site_report.sure):
					reports += report_line
					bug_count += 1
				# Determine if unchecked bug should be counted.
				elif (site_report.unchecked):
					unchecked_votes = check_counts[callee]
					reject = unchecked_votes.\
						 choose(threshold_ratio, \
							min_sites)
					if (not reject):
						reports += report_line
						bug_count += 1

		return reports, bug_count
	# Generate or fetch the bug report.
	# threshold_ratio: the checking threshold ratio
	# min_sites: the minimum number of sites to reject the bugs
	# check_counts: the votes on whether or not
	#		the function should not be checked
	# returns the report string and bug count
	def report(self, threshold_ratio, min_sites, check_counts):
		if (self.report_str is None and self.can_try):
			self.can_try = False

			(self.report_str, self.bug_count) = \
			self.try_report(threshold_ratio, min_sites, \
					check_counts)
		return self.report_str, self.bug_count
	# Get the number of site reports.
	# returns the number of site reports, even if they won't be shown
	def __len__(self):
		return len(self.reports)

# Initialize a CallerReport object from a single call site's report.
# site_report: the initial site report
# returns a CallerReport object that contains site_report,
#	  and the caller is the caller of site_report
def init_caller_report(site_report):
	caller = site_report.caller
	site_reports = [site_report]
	to_return = CallerReport(caller, site_reports)
	return to_return

# Report for a call site.
# function: the callee function name
# site: the call site
# caller: the caller function
# old_report: the report to be shown, if the bug is real
# unchecked: Is the bug because the return value is unchecked?
# sure: Must the bug always be reported?
#	We might not need to report unchecked return values.
class SiteReport:
	# function: function
	# site: site
	# caller: caller
	# old_report: old_report
	# unchecked: unchecked
	def __init__(self, function, site, caller, \
		     old_report = None, unchecked = False):
		self.function = function
		self.site = site
		self.caller = caller
		self.old_report = old_report
		self.unchecked = unchecked
		self.sure = not unchecked
	# Report if the function's return values are unchecked.
	# returns the report text if the return value is unchecked,
	#	  None otherwise
	def report_unsure(self):
		if (self.unchecked):
			return self.old_report
		return None
	# Try to return a report for the function.
	# returns the report, if, according to the site,
	#	  there should be a report, None otherwise
	def report(self):
		if (self.sure):
			return self.old_report
		else:
			return self.report_unsure()

# the checking threshold
THRESHOLD_RATIO = 1.0
# the minimum number of appearances before deciding to ignore a bug
# because too many appearances do not check the return value
MIN_SITES = 2

# uses the error specifications to check for errors
# output_handle: the output file
# auto_epex_data: the parsed program path data
# specs: the error specifications
# reports: reports, organized by the caller
# threshold_ratio: the checking threshold
# min_sites: the minimum number of appearances to discard bugs
# check_counts: the votes for checking and not checking a function
class BugsChecker:
	# output_handle: output_handle
	# auto_epex_data: auto_epex_data
	# specs: specs
	# threshold_ratio: threshold_ratio
	# min_sites: min_sites
	def __init__(self, output_handle, auto_epex_data, specs, \
		     threshold_ratio = THRESHOLD_RATIO, min_sites = MIN_SITES):
		self.output_handle = output_handle
		self.auto_epex_data = auto_epex_data
		self.specs = specs
		self.reports = {}
		self.threshold_ratio = threshold_ratio
		self.min_sites = min_sites
		self.check_counts = {}
	# Write to the output file.
	# data: the data to write
	def write(self, data = ""):
		if (not data is None):
			self.output_handle.write(str(data))
	# Write a line to the output file.
	# data: the line to write
	def println(self, data = ""):
		self.write(str(data) + "\n")
	# Add a site report.
	# report: the site report to add
	def add_report(self, report):
		# We should not have reports that we must report,
		# but don't know what to report.
		if (report.old_report is None and report.sure):
			return
		to_add = init_caller_report(report)
		add_to_dict(self.reports, to_add.caller, to_add)
	# For a call site, check all the paths for bugs.
	# function: the function name
	# site: the call site
	# paths: the paths that go through the call site
	# error_spec: the error specification
	# callee_type: the return value of the callee
	# returns a SiteReport if there is a potential bug, or None
	def check_site_paths(self, function, site, paths, error_spec, \
			     callee_type):
		if (len(paths) == 0):
			return None

		caller = None
		always_wrapped = None
		sometimes_wrapped = False
		always_unchecked = True
		unchecked_paths =  []
		# Gather caller information,
		# and check if the return value is wrapped or checked.
		for (segment, path) in paths:
			value = segment.value.clone_new_data(1)
			caller = path.caller_location
			wrapped = False
			if (value.have_symbol()):
				wrapped = value.same_assignments(path.caller \
								     .value)
				if (wrapped):
					sometimes_wrapped = True
				else:
					always_wrapped = False
			if (value.is_unknown()):
				if (not wrapped):
					unchecked_paths.append(segment)
			else:
				always_unchecked = False
			path_return_type = path.caller.value.type_marker

		if (always_wrapped is None):
			always_wrapped = False
		if (not always_wrapped):
			# Count explicit checks and lack of them.
			do_to_dict(self.check_counts, function, \
				   always_unchecked, init_polar_vote, \
				   add_polar_vote)
		# Ignore if the return value is sometimes wrapped.
		if (sometimes_wrapped):
			return None
		# Report if the return value is never checked.
		if (always_unchecked):
			return SiteReport(function, site, caller, \
					  "never checked", \
					  unchecked = True)

		return None
	# Save the report, and count the number of reported bugs.
	# returns the number of reported bugs
	def check(self):
		# Gather the potential bug reports
		for ((function, callee_type), site_paths) in \
		    self.auto_epex_data.get_site_paths():
			error_spec = self.specs.get_spec(function, callee_type)
			if (error_spec is None):
				continue
			for (site, paths) in site_paths:
				report = \
				self.check_site_paths(function, site, paths, \
						      error_spec, callee_type)
				if (not report is None):
					self.add_report(report)
		n_reported = 0
		# Save and count the real bugs.
		for (caller, caller_data) in sort_by_key(self.reports):
			(caller_report, n_bugs) = \
			caller_data.report(self.threshold_ratio, \
					   self.min_sites, self.check_counts)
			if (not (caller_report is None or \
				 len(caller_report) == 0)):
				self.println("%s:\n%s"%(caller, \
							caller_report))
				n_reported += n_bugs
		self.println("Total: %d"%(n_reported))

		return n_reported

if __name__ == "__main__":
	OUT_I = 1
	SUMMARY_I = OUT_I + 1
	PROGRAMS_START = SUMMARY_I + 1
	BUGS_SUFFIX = ".bugs"

	if (len(argv) <= PROGRAMS_START):
		throw_error("Usage [output directory] " + \
			    "[error specification] [log files]")

	summary_name = argv[SUMMARY_I]
	summary_file = open(summary_name, "r")
	if (summary_file is None):
		throw_error("Could not open summary file, %s"%summary_name)

	error_spec_parser = FullErrorSpec(summary_file)
	error_spec_parser.read_lines()
	summary_file.close()

	out_dir = argv[OUT_I]
	n_reported = 0
	for log_in_name in argv[PROGRAMS_START : ]:
		start = time()
		bugs_out_name = out_dir + \
				get_extensionless_name(log_in_name) + \
				BUGS_SUFFIX

		print "Analyzing " + log_in_name
		log_in_file = open(log_in_name, "r")
		if (log_in_file is None):
			throw_error("Could not open log file, %s"%log_in_name)

		bugs_out_file = open(bugs_out_name, "w")
		if (bugs_out_file is None):
			throw_error("Could not open bugs file, " + \
				    "%s"%bugs_out_name)

		parsed_data = AutoEPExParser(None, log_in_file)
		parsed_data.read_lines()
		log_in_file.close()

		bugs_checker = BugsChecker(bugs_out_file, parsed_data, \
					   error_spec_parser)
		n_reported += bugs_checker.check()
		bugs_out_file.close()
		end = time()
		print "Elapsed time: %f"%(end - start)

	print "Reported %d bugs"%(n_reported)
