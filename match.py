#!/usr/bin/env python
import csv
import sys
import random
import json
import datetime

from scipy import spatial
import dateutil.parser
from dateutil.relativedelta import relativedelta

NUM_MONTHS_NEW_EMPLOYEE = 6

# survey: https://docs.google.com/forms/d/1rHJ1DOLj1tv3eqayjpmR20N8lq87UAI1dCYmv9jUl5E/edit
COL_EMAIL = 1
COL_CITY = 2
COL_YEARS = 3
COL_WANT_TO_BE_MENTEE = 6
COL_COMMIT_TO_BE_MENTEE = 7
COL_WANT_SKILLS = 8
COL_MOST_WANTED_SKILL = 9
COL_WANT_TO_BE_MENTOR = 10
COL_CAN_MENTOR_SKILLS = 11


def filter_city(persons, city):
    # hack for people who didn't update survey, assume SF
    return [p for p in persons if p.office == city]


def filter_office(persons, office):
    return [p for p in persons if p.office == office]


def filter_titles(persons):
    return [p for p in persons
            if p.title in ('SWE', 'Director, Engineering', 'Data Scientist', 'Engineering Manager')]


def filter_out_new_employees(persons):
    return [p for p in persons if not p.is_new_employee]


def filter_mentors(rows, orgchart, city):
    """Accepts a list of all people who filled out form.
      Returns a list of potential mentors after filtering
        out those who don't want to or don't have skills to.
    """
    # TODO: write more of this (like filter out non-complete forms)
    mentor_rows = [row for row in rows
                   if row[COL_WANT_TO_BE_MENTOR] == 'Yes']
    mentors = [Mentor(mentor_row, orgchart) for mentor_row in mentor_rows]
    mentors = filter_titles(mentors)
    mentors = filter_out_new_employees(mentors)
    mentors = filter_city(mentors, city)
    return mentors


def filter_mentees(rows, orgchart, city):
    """Accepts a list of all people who filled out form.
      Returns a list of potential mentees after filtering
        out those who don't say yes to the level of work.
    """
    # TODO: write more of this (like filter out non-complete forms)
    mentee_rows = [row for row in rows
                   if row[COL_WANT_TO_BE_MENTEE] == 'Yes']
    mentees = [Mentee(mentee_row, orgchart) for mentee_row in mentee_rows]
    mentees = filter_titles(mentees)
    mentees = filter_out_new_employees(mentees)
    mentees = filter_city(mentees, city)
    return mentees


def make_match(mentor, mentee):
    match = (mentor, mentee,
             ' | '.join(mentor.skills_to_mentor(mentee)),
             mentor.manager_delta(mentee),
             mentor.cosine_similarity_skills_match_with(mentee))
    return match


def match_algorithm(mentor, mentees):
    """Accepts a mentor, and a list of possible matches.
       Returns a 2-tuple of
           1. the match (3-tuple of mentor, mentee, skills list) and
           2. the mentees who were not matched.
    """
    # TODO: this is greedy; can we optimize an objective function instead?
    # TODO: use more logic: e.g. increase cross-org matches
    for i, mentee in enumerate(mentees):
        if mentor.is_skills_match_with(mentee) and mentor.manager_delta(mentee) > 2:
            match = make_match(mentor, mentee)
            remaining_mentees = [m for m in mentees if m != mentee]
            return (match, remaining_mentees)
    else:
        return (None, mentees)


class Person(object):
    skills = []

    def __init__(self, row, orgchart=None):
        self._row = row
        self._managers = []
        if orgchart:
            self._json = orgchart.get_by_email(row[COL_EMAIL])

            json = self._json
            while json and 'manager' in json:
                json = orgchart.get_by_id(json['manager'])
                self._managers.append(json)

    def manager_delta(self, other):
        my_managers = set([m['email'] for m in self.managers])
        other_managers = set([m['email'] for m in other.managers])
        if self.email in other_managers or other.email in my_managers:
            return 0
        else:
            return len(my_managers.symmetric_difference(other_managers))

    @property
    def email(self):
        return self._row[1]

    @property
    def row(self):
        return self._row

    @property
    def city(self):
        """Self reported city in the survey"""
        return self._row[2]

    @property
    def office(self):
        """Office in TOM"""
        o = self.json.get('office', '')
        if o == '56c9058543dd7515dcaf17a7':
            return 'Seattle'
        elif o == '5801363843dd750335385593':
            return 'SF'
        elif o == '59a7731643dd75614c9998db':
            return 'Palo Alto'
        else:
            return ''

    @property
    def title(self):
        return self.json.get('title', 'Not in orgchart')

    @property
    def managers(self):
        return self._managers

    @property
    def manager_email(self):
        return self._managers[0]['email']

    @property
    def time_at_lyft(self):
        start_date = dateutil.parser.parse(self.json.get('start_date', '')).replace(tzinfo=None)
        rd = relativedelta(datetime.datetime.now(), start_date)
        return rd

    @property
    def is_new_employee(self):
        rd = self.time_at_lyft
        return rd.years == 0 and rd.months < NUM_MONTHS_NEW_EMPLOYEE

    @property
    def time_at_lyft_str(self):
        rd = self.time_at_lyft
        return "%dy %dm" % (rd.years, rd.months)

    def skills_interests(self):
        skills = self._parse_skills_str_in_row(COL_WANT_SKILLS)
        return skills

    @property
    def json(self):
        return self._json if self._json else {}

    def _parse_skills_str_in_row(self, col_index):
        skills = set(self.row[col_index].split(';'))
        if '' in skills:
            skills.remove('')
        return skills

    def __str__(self):
        return '{0}, ({1} | {2}), {3}'.format(self.email, self.title, self.time_at_lyft_str, self.manager_email)

    def __repr__(self):
        return self.__str__()

    @classmethod
    def _vectorize_skills(cls, skills_to_vectorize):
        return [(1 if s in skills_to_vectorize else 0) for s in cls.skills]


class Mentor(Person):
    def __init__(self, row, orgchart=None):
        Person.__init__(self, row, orgchart=orgchart)

    def is_skills_match_with(self, mentee):
        # TODO: add in most-wanted skill logic from mentee when we have that data
        if len(self.skills_to_mentor(mentee)) > 0:
            return True

    def cosine_similarity_skills_match_with(self, mentee):
        mentor_skills = Person._vectorize_skills(self.mentorable_skills())
        mentee_skills = Person._vectorize_skills(mentee.mentee_skills_interests())
        return round(1.0 - spatial.distance.cosine(mentor_skills, mentee_skills), 2)

    def skills_to_mentor(self, mentee):
        return self.mentorable_skills().intersection(mentee.mentee_skills_interests())

    def mentorable_skills(self):
        skills = self._parse_skills_str_in_row(COL_CAN_MENTOR_SKILLS)
        # TODO: cross-ref with 5's on skills self assessment
        return skills


class Mentee(Person):
    def __init__(self, row, orgchart=None):
        Person.__init__(self, row, orgchart=orgchart)

    def mentee_skills_interests(self):
        return self.skills_interests()


class OrgChart(object):
    def __init__(self, list_of_dicts):
        self._email_index = OrgChart._index(list_of_dicts, 'email')
        self._id_index = OrgChart._index(list_of_dicts, '_id')

    def get_by_email(self, email):
        return self._email_index.get(email, None)

    def get_by_id(self, id):
        return self._id_index.get(id, None)

    @classmethod
    def _index(cls, list_of_dicts, field):
        index = {}
        for dict in list_of_dicts:
            index[dict[field]] = dict
        return index

    @classmethod
    def readfile(cls, filename):
        list_of_dicts = []
        with open(filename, 'r') as f:
            for line in f:
                p = json.loads(line)
                list_of_dicts.append(p)
        return OrgChart(list_of_dicts)


def read_emails(filename):
    with open(filename, 'r') as f:
        return [line.strip(' \r\n') for line in f.readlines()]


def sponsor(persons, emails):
    sponsored = []
    nonsponsored = []
    emails = set(emails)
    for p in persons:
        if p.email in emails:
            sponsored.append(p)
        else:
            nonsponsored.append(p)
    return sponsored + nonsponsored


def remove_person_from_list(person, list_of_people):
    return [p for p in list_of_people if p.email != person.email]


def find_all_skills(mentors, mentees):
    skills = set()
    for mentor in mentors:
        skills.update(set(mentor.mentorable_skills()))
    for mentee in mentees:
        skills.update(set(mentee.mentee_skills_interests()))
    return list(sorted(skills))


if __name__ == '__main__':
    orgchart = OrgChart.readfile('all.txt')

    city = sys.argv[1]
    if len(sys.argv) > 2:
        seed = sys.argv[2]
        random.seed(seed)

    headers = []
    rows = []
    with open('data.csv', 'rb') as csvfile:
        data = csv.reader(csvfile)
        output = [row for row in data]
        headers, rows = output[0], output[1:]

    mentors, mentees = filter_mentors(rows, orgchart, city), filter_mentees(rows, orgchart, city)

    Person.skills = find_all_skills(mentors, mentees)

    random.shuffle(mentors)
    random.shuffle(mentees)

    sponsored_mentors = read_emails('mentors.txt')
    sponsored_mentees = read_emails('mentees.txt')
    mentors = list(reversed(sponsor(mentors, sponsored_mentors)))  # pop from bottom
    mentees = sponsor(mentees, sponsored_mentees)

    """
    print 'Mentees interested in ML:'
    for m in mentees:
        if 'Machine Learning' in m.skills_interests():
            print m.email
    for m in mentors:
        if 'Machine Learning' in m.skills_interests():
            print m.email
    """


    matches = []

    # sponsored matches
    with open('matches.txt', 'r') as f:
        for line in f.readlines():
            mentor_email, mentee_email = line.strip(' \r\n').split(',')
            maybe_mentor = [m for m in mentors if m.email == mentor_email]
            if len(maybe_mentor) > 0:
                mentor = maybe_mentor[0]
                # otherwise, assume wrong city
                mentee = None
                maybe_mentee = [m for m in mentees if m.email == mentee_email]
                if len(maybe_mentee) > 0:
                    mentee = maybe_mentee[0]
                else:
                    # if a mentee was sponsored but didn't say mentee on survey
                    q = [m for m in mentors if m.email == mentee_email][0]
                    mentee = Mentee(q.row, orgchart)

                matches.append(make_match(mentor, mentee))
                mentors = remove_person_from_list(mentor, mentors)
                mentees = remove_person_from_list(mentor, mentees)
                mentees = remove_person_from_list(mentee, mentees)
                mentors = remove_person_from_list(mentee, mentors)

    while len(mentors) > 0:
        mentor_to_match = mentors.pop()
        match, mentees = match_algorithm(mentor_to_match, mentees)
        if match is not None:
            matches.append(match)
            mentees = remove_person_from_list(match[0], mentees)
        else:
            print 'No mentees found for %s' % mentor_to_match

    for m in matches:
        print str(m[0]) + ',' +  str(m[1]) + ',' +  str(m[2]) + ',' +  str(m[3]) + ',' + str(m[4])
    
    print "\n\nRemaining mentees with no mentors:"

    for m in mentees:
        print m
