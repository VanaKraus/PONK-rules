# this file contains the definitions for a certain class of rules
# they all inherit from a superclass, which in turn inherits from Rule
# the superclass overloads Rule's background_color and foreground_color fields

from document_applicables.rules import Rule
from document_applicables.rules.util import Color

class RuleClass(Rule): # <- name it whatever you like :)
    foreground_color = Color(123, 0, 255)
    background_color = Color(0, 42, 69)

class SomeActualRule(RuleClass):
    pass
