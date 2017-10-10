#!/usr/bin/python
import csv
import random
import json
import datetime
import dateutil.parser
from dateutil.relativedelta import relativedelta

NUM_MONTHS_NEW_EMPLOYEE = 6

# survey: https://docs.google.com/forms/d/1rHJ1DOLj1tv3eqayjpmR20N8lq87UAI1dCYmv9jUl5E/edit
COL_EMAIL = 1
COL_CITY = 2
COL_WANT_TO_BE_MENTEE = 5
COL_COMMIT_TO_BE_MENTEE = 6
COL_WANT_SKILLS = 7
COL_MOST_WANTED_SKILL = 8
COL_WANT_TO_BE_MENTOR = 9
COL_CAN_MENTOR_SKILLS = 10

def filter_city(persons, city):
    return [p for p in persons if p.city == city]

def filter_titles(persons):
    return [p for p in persons
               if p.title in ('SWE', 'Director, Engineering', 'Data Scientist', 'Engineering Manager')]

def filter_out_new_employees(persons):
    return [p for p in persons if not p.is_new_employee]

def filter_mentors(people):
    """Accepts a list of all people who filled out form.
      Returns a list of potential mentors after filtering
        out those who don't want to or don't have skills to.
    """
    # TODO: write more of this (like filter out non-complete forms)
    people = [p for p in people
              if p.row[COL_WANT_TO_BE_MENTOR] == 'Yes']
    mentors = [Mentor(p) for p in people]
    mentors = filter_titles(mentors)
    mentors = filter_out_new_employees(mentors)
    mentors = filter_city(mentors, 'Seattle')
    return mentors

def filter_mentees(people):
    """Accepts a list of all people who filled out form.
      Returns a list of potential mentees after filtering
        out those who don't say yes to the level of work.
    """
    # TODO: write more of this (like filter out non-complete forms)
    people = [p for p in people
              if p.row[COL_WANT_TO_BE_MENTEE] == 'Yes']
    #people = [p for p in people
    #          if p.row[COL_COMMIT_TO_BE_MENTEE] == 'YES'] # double willing 

    mentees = [Mentee(p) for p in people]
    mentees = filter_titles(mentees)
    mentees = filter_out_new_employees(mentees)
    mentees = filter_city(mentees, 'Seattle')
    return mentees


def make_match(mentor, mentees):
    """Accepts a mentor, and a list of possible matches.
       Returns a 2-tuple of 
           1. the match (3-tuple of mentor, mentee, skills list) and
           2. the mentees who were not matched.
    """
    #TODO: this is greedy; can we optimize an objective function instead?
    #TODO: use more logic: e.g. increase cross-org matches
    for i, mentee in enumerate(mentees):
        if mentor.is_skills_match_with(mentee):
            match = (mentor, mentee, mentor.skills_to_mentor(mentee))
            remaining_mentees = [m for m in mentees if m != mentee]
            return (match, remaining_mentees)
    else:
        return (None, mentees)


class Person(object):
    def __init__(self, row, family=None):
        self._row = row
        self._family = family

    @property
    def email(self):
        return self._row[1]

    @property
    def row(self):
        return self._row

    @property
    def city(self):
        return self._row[2]

    @property
    def title(self):
        return self.family.get('title', 'Not in family')

    @property
    def time_at_lyft(self):
        start_date = dateutil.parser.parse(self.family.get('start_date', '')).replace(tzinfo=None)
        rd = dateutil.relativedelta.relativedelta(datetime.datetime.now(), start_date)
        return rd

    @property
    def is_new_employee(self):
        rd = self.time_at_lyft
        return rd.years == 0 and rd.months < NUM_MONTHS_NEW_EMPLOYEE

    @property
    def time_at_lyft_str(self):
        rd = self.time_at_lyft
        return "%d years, %d months" % (rd.years, rd.months)

    @property
    def family(self):
        return self._family if self._family else {}

    def _parse_skills_str_in_row(self, col_index):
        skills = set(self.row[col_index].split(';'))
        if '' in skills:
          skills.remove('')
        return skills

    def __str__(self):
        return '{0} ({1}, {3}, {2})'.format(self.email, self.title, self.time_at_lyft_str, self.is_new_employee)

    def __repr__(self):
        return self.__str__()


class Mentor(Person):
    def __init__(self, person):
        Person.__init__(self, person.row, person.family)

    def is_skills_match_with(self, mentee):
        # TODO: add in most-wanted skill logic from mentee when we have that data
        if len(self.skills_to_mentor(mentee)) > 0:
            return True

    def skills_to_mentor(self, mentee):
        return self.mentorable_skills().intersection(mentee.mentee_skills_interests())

    def mentorable_skills(self):
        skills = self._parse_skills_str_in_row(COL_CAN_MENTOR_SKILLS)
        # TODO: cross-ref with 5's on skills self assessment
        return skills


class Mentee(Person):
    def __init__(self, person):
        Person.__init__(self, person.row, person.family)

    def mentee_skills_interests(self):
        skills = self._parse_skills_str_in_row(COL_WANT_SKILLS)
        return skills


def read_emails(filename):
    with open(filename, 'r') as f:
        return [line.strip(' \r\n') for line in f.readlines()]


def select(persons, emails):
    selected = []
    nonselected = []
    emails = set(emails)
    for p in persons:
        if p.email in emails:
            selected.append(p)
        else:
            nonselected.append(p)
    return nonselected + list(reversed(selected))


def read_family(filename):
    family = {}
    with open(filename, 'r') as f:
        for line in f:
            p = json.loads(line)
            family[p['email'].lower()] = p
    return family


if __name__ == '__main__':
    family = read_family('all.txt')

    headers = []
    output = []
    with open('data.csv', 'rb') as csvfile:
        data = csv.reader(csvfile)
        output = [row for row in data]
        headers, data = output[0], output[1:]
        people = [Person(row, family=family.get(row[1])) for row in data]

    mentors, mentees = filter_mentors(people), filter_mentees(people)

    random.shuffle(mentors)
    random.shuffle(mentees)

    selected_mentors = read_emails('mentors.txt')
    selected_mentees = read_emails('mentees.txt')
    mentors = select(mentors, selected_mentors)
    mentees = select(mentees, selected_mentees)

    matches = []
    while len(mentors) > 0:
        mentor_to_match = mentors.pop()
        match, mentees = make_match(mentor_to_match, mentees)
        if match is not None:
            matches.append(match)
        else:
            print 'No mentees found for %s' % mentor_to_match

    for m in matches:
        print m

