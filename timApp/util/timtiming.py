# -*- coding: utf-8 -*-
"""Functions for dealing taking time."""
import time

timing_last = time.clock()
timing_last_t = time.time()
timing_last_z = time.clock()
timing_last_t_z = time.time()
# print(timing_last, timing_last_t)


def taketime(s1="", s2="", n=0, zero= False):
    # return  # comment this to take times, uncomment for production and tests
    global timing_last
    global timing_last_t
    global timing_last_z
    global timing_last_t_z
    t22 = time.clock()
    t22t = time.time()
    if zero:
        timing_last_z = t22
        timing_last_t_z = t22t

    print("%-20s %-15s %6d - %7.4f %7.4f %7.4f %7.4f" % (s1, s2, n, (t22 - timing_last), (t22t - timing_last_t), (t22 - timing_last_z), (t22t - timing_last_t_z)))
    timing_last = t22
    timing_last_t = t22t
