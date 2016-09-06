from sys import stderr

history = []

def clear_history():
	while (len(history) > 0):
		del history[-1]

def add_line(line):
	history.append(line)

def throw_error(msg):
	for line in history:
		stderr.write(str(line) + "\n")
	raise Exception(msg)
