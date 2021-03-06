# Gather all the randomly-named log files that APEx output.
from os import path, listdir, sep, remove
from sys import argv

# The suffix of the randomly-named log files generated by the checker.
SUFFIX = ".ae.log"

# Recursively read and combine all the log files.
# current_dir:		the current working directory
# suffix:		the suffix of the log files to gather
# remove_after_read:	should the log file be removed after reading?
# returns		concatenation of all the log file contents
def gather_output(current_dir, suffix, remove_after_read = False):
	suffix_len = len(suffix)
	gathered = []
	current_dir += sep
	for file_name in listdir(current_dir):
		file_path = current_dir + file_name
		# recursive case
		if (path.isdir(file_path)):
			gathered += gather_output(file_path, suffix,
						  remove_after_read)
		# Read the file, if it has the correct suffix.
		if (file_name.endswith(suffix)):
			log_file = open(file_path, "r")
			log_text = log_file.read()
			log_file.close()
			if (len(log_text) > 0):
				gathered += [file_path + "\n" + log_text]
			if (remove_after_read):
				remove(file_path)
	return gathered

# Consolidate all log files into a single one, and delete the read files.
# out_path:	the path to the output file
# root_dir:	the root of the directory tree containing the log files
# suffix:	the suffix of the log files to gather
def merge_output(out_path, root_dir, suffix):
	gathered = gather_output(root_dir, suffix, True)
	combo_file = open(out_path, "w")
	for file_entry in gathered:
		combo_file.write(file_entry + "\n")
	combo_file.close()

if __name__ == "__main__":
	OUT_I = 1
	DIR_I = OUT_I + 1
	MIN_N_ARGS = DIR_I + 1

	if (len(argv) < MIN_N_ARGS):
		print "Usage %s [output file] [input directory]"%(argv[0])
		exit(-1)

	merge_output(argv[OUT_I], argv[DIR_I], SUFFIX)
