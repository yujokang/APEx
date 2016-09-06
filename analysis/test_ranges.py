from ranges import RangeNode, RangeList

BIG_SINGLE = RangeList([RangeNode(-1024, 1024)])
SMALL_SINGLE = RangeList([RangeNode(0, 32)])

ABOVE_SMALL_SINGLE = RangeList([RangeNode(33, 34), RangeNode(36, 38)])
ABOVE_RESULT = RangeList([RangeNode(0, 32), RangeNode(33, 34), \
			  RangeNode(36, 38)])

BELOW_SMALL_SINGLE = RangeList([RangeNode(-5, -3), RangeNode(-2, -1)])
BELOW_RESULT = RangeList([RangeNode(-5, -3), RangeNode(-2, -1), \
			  RangeNode(0, 32)])

WITHIN_BIG = RangeList([RangeNode(-25, -5), RangeNode(-4, -2), \
			RangeNode(2, 4), RangeNode(5, 25)])
WITHIN_BIG_RESULT = RangeList([RangeNode(-1024, -26), RangeNode(-25, -5, 2), \
			       RangeNode(-4, -2, 2), RangeNode(-1, 1), \
			       RangeNode(2, 4, 2), RangeNode(5, 25, 2), \
			       RangeNode(26, 1024)])

AROUND_SMALL_SINGLE = RangeList([RangeNode(-5, -3), RangeNode(35, 50)])
AROUND_RESULT = RangeList([RangeNode(-5, -3), RangeNode(0, 32), \
			   RangeNode(35, 50)])

TOUCH_SMALL_SINGLE_BELOW = RangeList([RangeNode(-5, 3), RangeNode(35, 50)])
TOUCH_BELOW_RESULT = RangeList([RangeNode(-5, -1), RangeNode(0, 3, 2), \
				RangeNode(4, 32), RangeNode(35, 50)])

TOUCH_SMALL_SINGLE_ABOVE = RangeList([RangeNode(-5, -3), RangeNode(30, 50)])
TOUCH_ABOVE_RESULT = RangeList([RangeNode(-5, -3), RangeNode(0, 29), \
				RangeNode(30, 32, 2), RangeNode(33, 50)])

TOUCH_SMALL_SINGLE_BOTH = RangeList([RangeNode(-5, 3), RangeNode(30, 50)])
TOUCH_BOTH_RESULT = RangeList([RangeNode(-5, -1), RangeNode(0, 3, 2), \
			       RangeNode(4, 29), RangeNode(30, 32, 2), \
			       RangeNode(33, 50)])

SMALL_SINGLE_ON_TOP = RangeList([RangeNode(-36, -6), RangeNode(-5, 3)])
ON_TOP_RESULT = RangeList([RangeNode(-36, -6), RangeNode(-5, -1), \
			   RangeNode(0, 3, 2), RangeNode(4, 32)])

SMALL_SINGLE_ON_BOTTOM = RangeList([RangeNode(30, 50), RangeNode(52, 100)])
ON_BOTTOM_RESULT = RangeList([RangeNode(0, 29), RangeNode(30, 32, 2), \
			      RangeNode(33, 50), RangeNode(52, 100)])

SMALL_SINGLE_SUBSUME_TOP = RangeList([RangeNode(-36, -6), RangeNode(1, 3)])
SUBSUME_TOP_RESULT = RangeList([RangeNode(-36, -6), RangeNode(0, 0), \
				RangeNode(1, 3, 2), RangeNode(4, 32)])

SMALL_SINGLE_SUBSUME_BOTTOM = RangeList([RangeNode(1, 20), RangeNode(52, 100)])
SUBSUME_BOTTOM_RESULT = RangeList([RangeNode(0, 0), RangeNode(1, 20, 2), \
				   RangeNode(21, 32), RangeNode(52, 100)])

ZERO = RangeList([RangeNode(0, 0)])
NON_ZERO = RangeList([RangeNode(-2147483648, -1), RangeNode(1, 2147483647)])
ZERO_RESULT = RangeList([RangeNode(-2147483648, -1), RangeNode(0, 0), \
			 RangeNode(1, 2147483647)])

EMPTY = RangeList([])

ARBITRARY = RangeList([RangeNode(0, 0), RangeNode(1, 20), \
		       RangeNode(21, 32), RangeNode(52, 100)])

def compare_results(expected, real):
	expected_ranges = expected.clone_flat()
	real_ranges = real.clone_flat()

	n_expected_ranges = len(expected_ranges.ranges)
	n_real_ranges = len(real_ranges.ranges)
	if (n_expected_ranges != n_real_ranges):
		print "Expected %d ranges, but have %d"%(n_expected_ranges, \
							 n_real_ranges)
		return False

	for range_i in range(n_expected_ranges):
		expected_range = expected_ranges.ranges[range_i]
		real_range = real_ranges.ranges[range_i]
		if (expected_range.count != real_range.count):
			print "Range %d has a count mismatch: "%range_i + \
			      "expected %d, but got %d"%(expected_range.count, \
							 real_range.count)
		if (expected_range.least != real_range.least):
			print "Range %d has "%range_i + \
			      "a lower bound mismatch: " + \
			      "expected %d, but got %d"%(expected_range.least, \
							 real_range.least)
		if (expected_range.most != real_range.most):
			print "Range %d has "%range_i + \
			      "an upper bound mismatch: " + \
			      "expected %d, but got %d"%(expected_range.most, \
							 real_range.most)
			return False

	return True

def overlaps_equal(list_a, list_b):
	len_a = len(list_a)
	len_b = len(list_b)
	if (len_a != len_b):
		print "Unequal lengths, %d, %d"%(len_a, len_b)
		return False

	for node_i in range(len_a):
		node_a = list_a[node_i][0]
		node_b = list_b[node_i][0]

		least_a = node_a.least
		least_b = node_b.least
		if (least_a != least_b):
			print "Unequal lower bound at %d: %d, %d"%(node_i, \
								   least_a, \
								   least_b)
			return False

		most_a = node_a.most
		most_b = node_b.most
		if (least_a != least_b):
			print "Unequal upper bound at %d: %d, %d"%(node_i, \
								   most_a, \
								   most_b)
			return False


	return True

def check_overlaps(expected_overlaps, a, b):
	n_expected_overlaps = len(expected_overlaps)

	expect_have_overlaps = n_expected_overlaps > 0
	real_have_overlaps_a = a.overlaps(b)
	real_have_overlaps_b = b.overlaps(a)
	if (real_have_overlaps_a != real_have_overlaps_b):
		print "Overlap operation not commutative"
		print real_have_overlaps_a, real_have_overlaps_b
		exit(-1)
	if (expect_have_overlaps != real_have_overlaps_a):
		if (expect_have_overlaps):
			print "Missing overlaps"
			for expected_overlap in expected_overlaps:
				print expected_overlap
		else:
			print "Unexpected overlaps"
		exit(-1)
	real_overlaps_a = a.find_overlaps(b)
	real_overlaps_b = b.find_overlaps(a)
	if (not overlaps_equal(real_overlaps_a, real_overlaps_b)):
		print "Overlaps not commutative"
		exit(-1)
	if (not overlaps_equal(expected_overlaps, real_overlaps_a)):
		print "Overlaps not commutative"
		exit(-1)

class RangeTestCase:
	def __init__(self, msg, old, new, expected):
		self.message = msg
		self.old = old
		self.new = new
		self.expected = expected
		self.overlaps = []
		for potential_overlap in self.expected.ranges:
			if (potential_overlap.count > 1):
				self.overlaps \
				    .append((potential_overlap.clone_top(), \
					     (1, 1)))
	def perform(self):
		print self.message
		print "\tBefore: %s"%(str(self.old))
		added = self.old.clone_flat().add(self.new)
		added_out = str(added)
		print "\tAfter: %s"%(added_out)
		added_back = self.new.clone_flat().add(self.old)
		if (not compare_results(added, added_back)):
			print "Result not commutative"
			print "In reverse order, got %s"%(str(added_back))
			exit(-1)
		if (not compare_results(self.expected, added)):
			print "Result not as expected"
			exit(-1)
		check_overlaps(self.overlaps, self.old, self.new)
		print "\tPassed!"

TESTS = [RangeTestCase("Adding range to ranges above it", ABOVE_SMALL_SINGLE, \
		       SMALL_SINGLE, ABOVE_RESULT), \
	 RangeTestCase("Adding range to ranges below it", BELOW_SMALL_SINGLE, \
		       SMALL_SINGLE, BELOW_RESULT), \
	 RangeTestCase("Adding large range over all small ones", WITHIN_BIG, \
		       BIG_SINGLE, WITHIN_BIG_RESULT),
	 RangeTestCase("Adding small range between ranges", \
		       AROUND_SMALL_SINGLE, SMALL_SINGLE, \
		       AROUND_RESULT), \
	 RangeTestCase("Adding small range, touching on its lower side", \
		       TOUCH_SMALL_SINGLE_BELOW, SMALL_SINGLE, \
		       TOUCH_BELOW_RESULT), \
	 RangeTestCase("Adding small range, touching on its upper range", \
		       TOUCH_SMALL_SINGLE_ABOVE, SMALL_SINGLE, \
		       TOUCH_ABOVE_RESULT), \
	 RangeTestCase("Adding small range, touching on both sides", \
		       TOUCH_SMALL_SINGLE_BOTH, SMALL_SINGLE, \
		       TOUCH_BOTH_RESULT), \
	 RangeTestCase("Adding small range, touching the top", \
		       SMALL_SINGLE_ON_TOP, SMALL_SINGLE, \
		       ON_TOP_RESULT), \
	 RangeTestCase("Adding small range, touching the bottom", \
		       SMALL_SINGLE_ON_BOTTOM, SMALL_SINGLE, \
		       ON_BOTTOM_RESULT), \
	 RangeTestCase("Adding small range, subsuming the top", \
		       SMALL_SINGLE_SUBSUME_TOP, SMALL_SINGLE, \
		       SUBSUME_TOP_RESULT), \
	 RangeTestCase("Adding small range, subsuming the bottom", \
		       SMALL_SINGLE_SUBSUME_BOTTOM, SMALL_SINGLE, \
		       SUBSUME_BOTTOM_RESULT), \
	 RangeTestCase("Adding to an empty list", EMPTY, ARBITRARY, ARBITRARY),
	 RangeTestCase("Adding zero to non-zero", NON_ZERO, ZERO, ZERO_RESULT)]

for test in TESTS:
	test.perform()
