import unittest
from audit_sst_terminology import glossary,matcher,inspect,proposal
from pathlib import Path

class TerminologyTests(unittest.TestCase):
    def setUp(self):
        self.terms=glossary(Path(__file__).resolve().parents[1]/'translation-review/GLOSSARY.md')
        self.pattern,self.aliases=matcher(self.terms)
    def adapt(self,en,ko,field='FULL'):
        _,issues=inspect(en,ko,self.pattern,self.aliases)
        return proposal(en,ko,issues,self.terms,{'field':field})
    def test_plural_and_particle(self):
        self.assertEqual(self.adapt('Lightsabers are here.','라이트세이버는 여기 있다.')[0],'광선검은 여기 있다.')
        self.assertEqual(self.adapt('Damage from lightsabers.','라이트세이버로부터 받는 피해.')[0],'광선검으로부터 받는 피해.')
        self.assertEqual(self.adapt('Blasters are illegal.','블래스터들은 불법이다.')[0],'블라스터들은 불법이다.')
    def test_contextual_money_and_common_word(self):
        self.assertIsNone(self.adapt('Take your credits.','보상을 챙겨라.')[0])
        self.assertFalse(inspect('Citizen vigilance.','시민의 경계심.',self.pattern,self.aliases)[1])
    def test_prefix_is_not_variant(self):
        self.assertFalse(inspect('Bonagal','보나갈',self.pattern,self.aliases)[1])
        self.assertEqual(self.adapt('Bonagal III','보나가르 III')[0],'보나갈 III')
    def test_ambiguous_short_name_only_in_label(self):
        self.assertIsNone(self.adapt('Go to Jum.','줌에는 조사할 점이 있다.')[0])
        self.assertEqual(self.adapt('Jum I','점 I')[0],'줌 I')
    def test_tags_and_structure(self):
        self.assertIsNone(self.adapt('Lightsaber <Alias=Name>','라이트세이버')[0])
        self.assertIsNone(self.adapt('Lightsaber <Alias=Name>','<Alias=라이트세이버>')[0])
    def test_provisional_names_held(self):
        self.assertIsNone(self.adapt('Janese','자니스')[0])

if __name__=='__main__':unittest.main()
