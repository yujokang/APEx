# a simple script for running multiple analyses of AutoEPExParser,
# and combining them into AutoEPExSum, and generating an error specification
from auto_epex_parser import AutoEPExParser, AutoEPExSum, ErrorSpec
from time import time

from sys import argv, path
from file_utilities import get_extensionless_name, get_dir

# Run analyses on all the files, and generate a summary.
# out_name: path to the output file, which will contain the error specification
# in_paths: the paths to the input log files to read
# low_ratio: the number of standard deviations that a low value should be
#	     below the average
# high_ratio: the number of standard deviations that a high value should be
#	      above the average
# vote_ratio: the threshold ratio for the winning votes
# returns the AutoEPExSum of the parsed data
def run_analyses(out_name, in_paths, low_ratio, high_ratio, vote_ratio):
	parse_sum = AutoEPExSum(low_ratio = low_ratio, \
				high_ratio = high_ratio, \
				vote_ratio = vote_ratio)
	out_dir = get_dir(out_name)
	# Parse each file.
	for in_name in in_paths:
		start = time()
		# Generate the output file for the log file.
		extensionless = out_dir + get_extensionless_name(in_name)
		post_out_name = extensionless + ".ae.analysis"

		input_file = open(in_name, "r")
		if (input_file is None):
			print "Could not open %s for input file"%input_file
			output_file.close()
			exit(-1)

		post_output_file = open(post_out_name, "w")
		if (post_output_file is None):
			print "Could not open " + \
			      "%s for AutoEPEx output"%post_out_name
			output_file.close()
			exit(-1)

		print "Analyzing " + in_name

		print "Postconditions"
		# Parse the log file.
		post_parser = AutoEPExParser(post_output_file, input_file)
		post_parser.read_lines()
		post_output_file.close()
		input_file.close()
		# Add the parsed data to the sum.
		parse_sum.add(post_parser)
		end = time()
		print "Program Elapsed Time: %f"%(end - start)

	out_file = open(out_name, "w")
	overall_start = time()
	# Generate the summary.
	out_file.write(str(parse_sum))
	overall_end = time()
	out_file.close()
	print "Overall Elapsed Time: %f"%(overall_end - overall_start)
	return parse_sum

DEFAULT_RATIO = 1.0

if __name__ == "__main__":
	SUM_OUT_I = 1
	IN_START = SUM_OUT_I + 1

	if (len(argv) <= IN_START):
		print "Please enter summary output file and input files"
		exit(-1)

	out_name = argv[SUM_OUT_I]
	run_analyses(out_name, argv[IN_START :], DEFAULT_RATIO, DEFAULT_RATIO, \
		     DEFAULT_RATIO)
