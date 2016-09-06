# voting utilities for inferring error specifications
# and deciding on reporting
from value_parser import INT_TYPE_START, is_undefined

from math import sqrt
from sys import stdin, argv, path
from data_utilities import counts_to_stats

from ranges import RangeList

# vote for the element(s) with the largest or smallest strength
# inverted: this class technically votes for the greatest strength,
#	    but it can choose the smallest strength by inverting the strengths
# total_strength: the running total of the strengths,
#		  used for calculating the mean and standard deviation
# total_strength_square: the running total of the squares of the strengths,
#		  used for calculating the standard deviation
# threshold_ratio: the number of standard deviations above the mean
#		   by which the winning votes must win to be counted
# min_votes: the minimum number of votes
# tallies: the votes. Each element is a distinct vote
# strengths: the strength of each vote
# rangify: are the votes range nodes?
# as_list: if this is not None, the votes are range nodes,
#	   and this boolean determines if the resulting range is weighted
#	   as a list
# top_strength: the maximum strength
# allow_tie: allow multiple votes to tie. Ignored for ranges
# only_threshold: the winning nodes only have to pass the threshold,
#		  and don't need the maximum strength
class ExtremeVote:
	def __init__(self, inverted, threshold_ratio, \
		     min_votes = 1, as_list = None, allow_tie = False, \
		     only_threshold = None):
		self.inverted = inverted
		self.total_strength = 0.0
		self.total_strength_square = 0.0
		self.count = 0
		self.threshold_ratio = threshold_ratio
		self.min_votes = min_votes
		self.tallies = []
		self.strengths = []
		self.rangify = not as_list is None
		self.as_list = as_list
		self.top_strength = None
		self.allow_tie = allow_tie
		if (only_threshold is None):
			self.only_threshold = self.rangify
		else:
			self.only_threshold = only_threshold
	# Get the number of votes.
	# return the vote count
	def get_n_distinct_votes(self):
		return self.count
	# Tally a vote.
	# vote: the element to vote for. Cannot be repeated.
	# strength: the strength of the vote
	def tally(self, vote, strength):
		self.count += 1
		used_strength = None
		# Invert if we are really looking for low values.
		if (self.inverted):
			used_strength = -1 * strength
		else:
			used_strength = strength
		self.tallies.append((vote, used_strength))
		# Count the strength towards the aggregates.
		self.strengths.append(used_strength)
		self.total_strength += used_strength
		self.total_strength_square += used_strength ** 2
		# Check if the strength beats the top one.
		if (self.top_strength is None or \
		    used_strength > self.top_strength):
			self.top_strength = used_strength
	# Choose the winning votes.
	# returns a list of the winning votes, or None
	def _vote(self):
		# Bail if there are not enough votes.
		if (self.count < self.min_votes):
			return None
		# Pick the single winner.
		if (self.count == 1):
			return [self.tallies[0][0]]

		# Calculate the standard deviation of all data points.
		rest_count = float(self.count - 1.0)
		average_strength = float(self.total_strength) / \
				   float(self.count)
		variance_numerator = self.total_strength_square - \
				     average_strength * \
				     self.total_strength
		if (variance_numerator < 0):
			# this only occurs due to round-off errors
			variance_numerator = 0.0
		whole_stdev = sqrt(variance_numerator / rest_count)

		# Look for functions to count as winners.
		choices = []
		# Allow multiple votes if ties are allowed,
		# or ranges are used.
		allow_multiple = (self.allow_tie or self.rangify)
		for (vote, strength) in self.tallies:
			# Calculate the threshold.
			# If possible, calculate and use the standard deviation
			# of the other votes.
			rest_total_strength = self.total_strength - \
					      strength
			rest_average_strength = float(rest_total_strength) / \
						float(rest_count)
			stdev = None
			if (rest_count > 1.0):
				rest_total_strength_square = \
				self.total_strength_square - strength ** 2
				variance_numerator = \
				rest_total_strength_square - \
				rest_average_strength * rest_total_strength
				if (variance_numerator < 0):
					# this only occurs due to
					# round-off errors
					variance_numerator = 0.0
				stdev = sqrt(variance_numerator / \
					     (rest_count - 1))
			else:
				stdev = whole_stdev
			stdev = whole_stdev

			difference = self.threshold_ratio * stdev
			vote_threshold = rest_average_strength + difference
			# Determine if we should count the vote as a winner.
			if (strength >= vote_threshold and \
			    (self.only_threshold or \
			     strength == self.top_strength)):
				choices.append(vote)

		# Check that the number of votes is not too much.
		n_choices = len(choices)
		if (n_choices == 0 or n_choices == len(self.tallies) or \
		    (not allow_multiple and n_choices > 1)):
			return None

		return choices

	# Pick the winners in the desired form.
	# returns the list of winning votes,
	#	  converting range nodes into one range if needed.
	def vote(self):
		choices = self._vote()
		if (choices is None):
			return None
		elif (self.rangify):
			combined_range = RangeList(choices, self.as_list)
			return [combined_range]
		else:
			return choices

# vote for two values, eg. not check or check
# true_count: votes for the first element,
#	      which must clear the threshold to be chosen
# false_count: votes for the second element, which is chosen by default
class PolarVote():
	def __init__(self):
		self.true_count = 0
		self.false_count = 0
	# Add a vote.
	# vote: vote for the first element, or not
	def add(self, vote):
		if (vote):
			self.true_count += 1
		else:
			self.false_count += 1
	# Choose the vote.
	# threshold_ration: the threshold to choose the first element
	# min_true: the minimum number of votes to choose the first element
	def choose(self, threshold_ratio, min_true = 0):
		# Too few votes.
		if (self.true_count < min_true):
			return False
		# No false votes.
		if (self.false_count == 0):
			return True

		# Calculate the threshold.
		total = self.true_count + self.false_count
		var_numerator = float(self.true_count * self.false_count)
		stdev = sqrt(var_numerator / float(total * (total - 1)))
		threshold = self.false_count + threshold_ratio * stdev
		# Choose the first element iff the threshold is cleared.
		return self.true_count > threshold
	# Combine the true and false votes.
	# other: the other set of votes in the sum
	# returns the element-wise sum of the two sets of votes
	def __add__(self, other):
		added = PolarVote()
		added.true_count = self.true_count + other.true_count
		added.false_count = self.false_count + other.false_count
		return added

# Add a vote.
# This function is used as the increase function in data_utilities.do_to_dict.
# polar_vote: the set of votes to add to
# vote: the vote to cast
# returns: polar_vote, with the added vote
def add_polar_vote(polar_vote, vote):
	polar_vote.add(vote)
	return polar_vote

# Initialize a PolarVote with an initial vote.
# This function is used as the init function in data_utilities.do_to_dict.
# first_vote: the first vote to cast
# returns: a new PolarVote object, with first_vote cast
def init_polar_vote(first_vote):
	polar_vote = PolarVote()
	return add_polar_vote(polar_vote, first_vote)
