import unittest
from build_terminology_patch import compose
from test_patch_engine import record,field
from patch_engine import patch_plugin

class TerminologyPatchTests(unittest.TestCase):
    def test_composed_upgrades_match_clean_compressed_output(self):
        first=('MISC',1,'FULL',0);second=('MISC',2,'FULL',0)
        original=record(b'TES4',b'')+record(b'MISC',field(b'FULL',b'Lightsaber\0'),1,0x40000)+record(b'MISC',field(b'FULL',b'Blaster\0'),2,0x40000)
        v1,_=patch_plugin(original,{first:('Lightsaber','라이트세이버'),second:('Blaster','블래스터')})
        step1={first:('라이트세이버','광검')};step2={first:('광검','광선검'),second:('블래스터','블라스터')}
        combined=compose(step1,step2)
        upgraded,_=patch_plugin(v1,combined)
        clean,_=patch_plugin(original,{first:('Lightsaber','광선검'),second:('Blaster','블라스터')})
        self.assertEqual(upgraded,clean)
    def test_conflicting_upgrade_stops(self):
        key=('MISC',1,'FULL',0)
        with self.assertRaises(ValueError):compose({key:('old','before')},{key:('different','after')})
    def test_raw_source_guard_survives_composition(self):
        key=('MISC',1,'FULL',0)
        self.assertEqual(compose({key:('bad','before','abcd')},{key:('before','after')})[key],('bad','after','abcd'))

if __name__=='__main__':unittest.main()
