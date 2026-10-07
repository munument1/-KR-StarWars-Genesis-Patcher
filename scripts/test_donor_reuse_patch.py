import unittest
from build_donor_reuse_patch import adapted_translation, repair_particle

class AdaptationTests(unittest.TestCase):
    def test_subject_particle(self):
        self.assertEqual(adapted_translation('UC is here.','UC는 여기 있다.','Empire is here.')[0],'제국은 여기 있다.')
    def test_remove_old_house_descriptor(self):
        self.assertEqual(adapted_translation("A Va'ruun delicacy.",'바룬 가문의 진미.', 'A Sith delicacy.')[0],'시스의 진미.')
    def test_instrumental_rieul(self):
        self.assertEqual(repair_particle('서울','으로'),'로')
        self.assertEqual(repair_particle('제국','로'),'으로')
        self.assertEqual(repair_particle('스파이스','으로'),'로')
    def test_alphanumeric_name_pronunciation(self):
        self.assertEqual(adapted_translation('Vasco is here.','바스코가 여기 있다.','ND-5 is here.')[0],'ND-5가 여기 있다.')
    def test_preserve_existing_words(self):
        self.assertEqual(adapted_translation('Hello.','안녕하십니까.','Hello.')[0],'안녕하십니까.')
    def test_hold_other_changes_and_compounds(self):
        self.assertIsNone(adapted_translation('Mars is here.','마스터가 여기 있다.','Geonosis is here.')[0])
        self.assertIsNone(adapted_translation('UC is here.','UC는 여기 있다.','Empire left.')[0])
    def test_noun_particle_inside_word_not_repaired(self):
        self.assertIsNone(adapted_translation('Mars is here.','마스이야기다.','Geonosis is here.')[0])
    def test_missing_controls_not_repaired(self):
        self.assertIsNone(adapted_translation('Press [Accept] in Neon.','네온에서 누르세요.','Press [Accept] in Nar Shaddaa.')[0])

if __name__=='__main__':unittest.main()
