#!/usr/bin/env python
#-*- coding: utf-8 -*-
#
# Copyright 2006 Develer S.r.l. (http://www.develer.com/)
# All rights reserved.
#
# $Id$
#
# Author: Lorenzo Berni <duplo@develer.com>

from PyQt4.QtCore import QDate

DEFAULT_DAYS = (True,  True,  True,  True,  True,  True,  True)

def daterange(start_day,  end_day,  days=DEFAULT_DAYS):
    """
    Returns a QDate generator from
    *start_day* to *end_day* with one day step
    """
    current_day = start_day
    while True:
        if current_day > end_day:
            break
        tmp = current_day
        current_day = current_day.addDays(1)
        if days[tmp.dayOfWeek() - 1]:
            #TODO: Eliminare i festivi e le ferie
            yield tmp

def daysnumber(start_day,  end_day,  days=DEFAULT_DAYS):
    """
    Returns the number of working days and total days in range
    from *start_day* to *end_day*
    """
    current_day = start_day
    total = 0
    working = 0
    while True:
        if current_day > end_day:
            break
        tmp = current_day
        current_day = current_day.addDays(1)
        if days[tmp.dayOfWeek() - 1]:
            #TODO: Eliminare i festivi e le ferie
            working += 1
        total += 1
    return working,  total

def getweek(day):
    """
    Returns a QDate generator on the week of the given day
    """
    first = day.addDays(-1 * day.dayOfWeek() + 1)
    last = first.addDays(6)
    return daterange(first,  last)
