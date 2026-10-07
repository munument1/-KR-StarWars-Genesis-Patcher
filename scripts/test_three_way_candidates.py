"""Conservative reuse regression fixtures; run with unittest discovery or directly."""
import unittest
from build_three_way_candidates import propose

class ThreeWayTests(unittest.TestCase):
    def test_observed_uc_rename(self):
        candidate,status,_=propose('UC Prison Shuttle','UC 교도소 수송선','Imperial Prison Shuttle')
        self.assertEqual((candidate,status),('제국 교도소 수송선','term_swap_candidate'))

    def test_identity_retains_donor(self):
        self.assertEqual(propose('Hello.','안녕하세요.','Hello.')[0],'안녕하세요.')

    def test_changed_sentence_not_reused(self):
        self.assertIsNone(propose('Go to Neon.','네온으로 가라.','Leave Nar Shaddaa.')[0])

    def test_particle_remains_for_human_review(self):
        self.assertEqual(propose('Aurora is illegal.','오로라는 불법이다.','Spice is illegal.')[0],'스파이스는 불법이다.')

    def test_multiple_terms(self):
        self.assertEqual(propose('UC on Neon.','네온의 UC.','Empire on Nar Shaddaa.')[0],'나르 샤다의 제국.')

    def test_missing_and_extra_donor_terms(self):
        self.assertIsNone(propose('Go to Neon.','도시로 가라.','Go to Nar Shaddaa.')[0])
        self.assertIsNone(propose('Go to Neon.','네온에서 네온으로 가라.','Go to Nar Shaddaa.')[0])

    def test_compound_and_acronym_substrings(self):
        self.assertIsNone(propose('Mars is here.','마스터가 여기 있다.','Geonosis is here.')[0])
        self.assertIsNone(propose('UC is here.','SUC가 여기 있다.','Empire is here.')[0])

    def test_changed_tags_and_newlines(self):
        self.assertIsNone(propose('UC <Global=Money>','UC <Global=Money> 크레딧','Empire 10000')[0])
        self.assertIsNone(propose('Go to Neon.\nNow.','네온으로 가라.','Go to Nar Shaddaa.\nNow.')[0])

    def test_partial_rename_and_conflict(self):
        self.assertIsNone(propose('UC and UC.','UC와 UC.','Empire and UC.')[0])
        self.assertIsNone(propose('United Colonies and UC.','식민지 연합과 UC.','Galactic Empire and Empire.')[0])

    def test_markup_contains_translated_alias(self):
        self.assertIsNone(propose('Neon <name>','<name>네온</name>','Nar Shaddaa <name>')[0])

if __name__=='__main__':unittest.main()
