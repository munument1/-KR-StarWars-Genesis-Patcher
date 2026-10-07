import unittest
from export_terminology_ai_review import within_scope

class ScopeTests(unittest.TestCase):
    terms=[{'id':'0123456789abcdef','canonical_ko':'블라스터','known_variants':['블래스터']},
           {'id':'1123456789abcdef','canonical_ko':'광선검','known_variants':['광검']}]
    def test_spelling_and_particle(self):
        self.assertTrue(within_scope('광검을 챙겨.','광선검을 챙겨.',self.terms))
        self.assertTrue(within_scope('블래스터는 좋아.','블라스터는 좋아.',self.terms))
    def test_rewriting_ordinary_prose_is_held(self):
        self.assertFalse(within_scope('블래스터는 좋아.','블라스터는 아주 훌륭해.',self.terms))
    def test_entity_substitution_is_held(self):
        self.assertFalse(within_scope('블래스터를 챙겨.','광선검을 챙겨.',self.terms))

if __name__=='__main__':unittest.main()
