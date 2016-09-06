from sys import stdin

from error_handler import clear_history, add_line

class OutputParser:
	def __init__(self, prefix, output_handle, input_handle = stdin):
		self.prefix = prefix
		self.prefix_len = len(prefix)
		self.output_handle = output_handle
		self.input_handle = input_handle
		clear_history()
	def handle_line(self, line):
		return None
	def finish(self):
		return None
	def write(self, string):
		if (not self.output_handle is None):
			self.output_handle.write(string)
	def read_lines(self):
		n_lines = 0
		for line in self.input_handle:
			n_lines += 1
			if (len(line) < self.prefix_len or \
			     line[ : self.prefix_len] != self.prefix):
				continue
			line = line[self.prefix_len : -1]
			add_line(n_lines)
			add_line(line)
			line_result = self.handle_line(line)
			if (line_result != None):
				self.write(line_result + "\n")
			clear_history()
		final = self.finish()
		if (final != None):
			self.write(final)
