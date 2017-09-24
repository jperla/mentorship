#!/usr/bin/python
import csv
import random

# survey: https://docs.google.com/forms/d/1rHJ1DOLj1tv3eqayjpmR20N8lq87UAI1dCYmv9jUl5E/edit
COL_EMAIL = 1
COL_TEAM = 2
COL_ORG = 3
COL_MANAGER_EMAIL = 4
COL_CITY = 5
COL_WANT_TO_BE_MENTEE = 8
COL_COMMIT_TO_BE_MENTEE = 9
COL_WANT_SKILLS = 10
COL_MOST_WANTED_SKILL = 11
COL_WANT_TO_BE_MENTOR = 12
COL_CAN_MENTOR_SKILLS = 13


def filter_mentors(people):
    """Accepts a list of all people who filled out form.
      Returns a list of potential mentors after filtering
        out those who don't want to or don't have skills to.
    """
    # TODO: write more of this (like filter out non-complete forms)
    people = [p for p in people
              if p.row[COL_WANT_TO_BE_MENTOR] == 'Yes']
    return [Mentor(p.row) for p in people]

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
    return [Mentee(p.row) for p in people]

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
    def __init__(self, row):
        self._row = row

    @property
    def email(self):
        return self._row[1]

    @property
    def row(self):
        return self._row

    def _parse_skills_str_in_row(self, col_index):
        skills = set(self.row[col_index].split(';'))
        if '' in skills:
          skills.remove('')
        return skills

    def __str__(self):
        return str(self.email)

    def __repr__(self):
        return self.__str__()

class Mentor(Person):
    def __init__(self, row):
        Person.__init__(self, row)

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
    def __init__(self, row):
        Person.__init__(self, row)

    def mentee_skills_interests(self):
        skills = self._parse_skills_str_in_row(COL_WANT_SKILLS)
        return skills

if __name__ == '__main__':
    headers = []
    output = []
    with open('data.csv', 'rb') as csvfile:
        data = csv.reader(csvfile)
        output = [row for row in data]
        headers, data = output[0], output[1:]
        people = [Person(row) for row in data]

    mentors, mentees = filter_mentors(people), filter_mentees(people)

    random.shuffle(mentors)
    random.shuffle(mentees)

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

