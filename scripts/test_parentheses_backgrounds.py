import unittest
from review_parentheses_backgrounds import clean_glosses,resolve

class ReviewTests(unittest.TestCase):
    def test_both_directions(self):
        self.assertEqual(clean_glosses('시스(Sith), NCI(신경 제어 인터페이스)'), '시스, 신경 제어 인터페이스')
    def test_meaningful_parentheses(self):
        for value in ('보호막 (AI)','아르곤 (Ar)','24시간 (UT)','상자 (LED 조명)','BARC - 1인승 (오픈형)','요약 (계속 증가 중)','기관실 (부상자 3명)','킬로그램 (kg)'):
            self.assertEqual(clean_glosses(value),value)
    def test_protected_markup(self):
        value='<image name="한글(Sith)" caption="시스(Sith)"><Alias=Key>(으)로 이동 [Jump]'
        self.assertEqual(clean_glosses(value),value)
    def test_wordplay(self):
        value='감독하고(SUPERVISE), 제공하고(PROVIDE), 반복(REPEAT)합니다. 글럽 런치(Glob Lunch).'
        self.assertEqual(clean_glosses(value),value)
    def test_only_background(self):
        source='An elected voice in a fractured era, you use leverage.';ko='협정을 성사시킨다.'
        self.assertEqual(resolve(source,ko,{'record':'INFO','field':'NAM1','form_id':'0022EC7B'})[0],ko)
        self.assertTrue(resolve(source,ko,{'record':'PERK','field':'DESC','form_id':'0022EC7B'})[0].endswith('성사시킵니다.'))
        self.assertEqual(resolve('Other background description',ko,{'record':'PERK','field':'DESC','form_id':'0022EC7B'})[0],ko)

if __name__=='__main__':unittest.main()
