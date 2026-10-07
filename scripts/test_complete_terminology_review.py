import copy,json,unittest
from pathlib import Path
from complete_terminology_review import resolve,substitute,ALIASES,repair_structure
from audit_sst_terminology import matcher
from patch_engine import check_translation

class CompleteReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terms=json.loads((Path(__file__).resolve().parents[1]/'translation-review/terminology-followup/glossary-extensions.json').read_text(encoding='utf-8'))['terms']
        for t in cls.terms:t['known_variants']+=ALIASES.get(t['english'],[])
        cls.pattern,cls.aliases=matcher(cls.terms)
    def apply(self,en,ko,field='FULL',record='NPC_'):
        return resolve(en,ko,{'field':field,'record':record},self.terms,self.pattern,self.aliases)[0]
    def test_open_is_activation_only(self):
        self.assertEqual(self.apply('Open','오픈','ATTX'),'열기')
        self.assertEqual(self.apply('BARC Speeder (open)','BARC 스피더(오픈형)','FULL','FURN'),'BARC 스피더(오픈형)')
    def test_tokens_are_preserved(self):
        self.assertEqual(self.apply('<Alias=Droids[0]> attack','<Alias=Droids[0]> 공격'),'<Alias=Droids[0]> 공격')
    def test_attached_grammar_and_canonical_prefix(self):
        self.assertEqual(substitute('블래스터든 블래스터일 뿐.',{'블래스터':'블라스터'}),'블라스터든 블라스터일 뿐.')
        self.assertEqual(substitute('보나갈 III',{'보나가':'보나갈'}),'보나갈 III')
    def test_currency_and_metaphor_kept(self):
        self.assertEqual(self.apply('For that many credits, I could hire two of you.','그 가격이면 두 명을 고용할 수 있습니다.'),'그 가격이면 두 명을 고용할 수 있습니다.')
        self.assertEqual(self.apply('Growth is launching it into hyperdrive.','성장에 과부하를 건다.'),'성장에 과부하를 건다.')
    def test_source_guard_prevents_rewriting_good_translation(self):
        ko='여기서 태어났죠. 나르 샤다가 제 고향이에요.'
        self.assertEqual(self.apply("I was born here. Nar Shaddaa's my home.",ko),ko)
    def test_global_id_is_not_interchangeable(self):
        en='[Extort <Global=SFBGS003_NPCDemandMoney_Small> Credits] Pay.'
        ko='[<Global=SFBGS003_NPCDemandMoney_Large> 크레딧 갈취] 내놔.'
        fixed=repair_structure(en,ko);check_translation(en,fixed)
        self.assertIn('Money_Small>',fixed)
    def test_missing_paragraph_is_not_hidden_with_blank_padding(self):
        with self.assertRaises(ValueError):repair_structure('One.\n\nTwo.','하나.')
    def test_planet_number_follows_english(self):
        self.assertEqual(self.apply('Lantana VII','란타나 VIII','FULL','WRLD'),'란타나 VII')
    def test_existing_context_decision_returns_text(self):
        self.assertEqual(self.apply('Mandalorian Loyalist','만달로어 충성파'),'만달로리안 충성파')
    def test_both_factions_keep_their_identity(self):
        en='The Shadow Collective has taken vital Imperial data.'
        ko='섀도우 콜렉티브가 제국군의 중요 데이터를 탈취했다.'
        self.assertEqual(self.apply(en,ko),ko)
        self.assertEqual(self.apply('Imperial Army vs Shadow Collective','제국군 대 섀도우 콜렉티브'),'제국군 대 섀도우 콜렉티브')
    def test_multiple_planets_do_not_collapse(self):
        ko='코러산트와 지오노시스, 나르 샤다.'
        self.assertEqual(self.apply('CORUSCANT, GEONOSIS, Nar Shaddaa',ko),ko)

if __name__=='__main__':unittest.main()
