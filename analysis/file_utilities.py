from os import sep

def get_last_sep(path):
	return path.rfind(sep)

def get_dir(path):
	last_sep = get_last_sep(path)

	if (last_sep < 0):
		return ""
	else:
		return path[ : last_sep + 1]

def get_name(path):
	last_sep = get_last_sep(path)

	if (last_sep < 0):
		return path
	else:
		return path[last_sep + 1 : ]

def get_extensionless(path):
	extension_start = path.rfind(".")
	if (extension_start < 0):
		return path
	else:
		return path[ : extension_start]

def get_extensionless_name(path):
	name = get_name(path)
	return get_extensionless(name)
