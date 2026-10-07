import gzip,json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import installer_backend as backend

class InstallerTests(unittest.TestCase):
    def setUp(self):
        process_check=patch.object(backend,'check_game_closed',return_value=None);process_check.start();self.addCleanup(process_check.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.game=self.root/'Game';self.package=self.root/'package';self.stage=self.root/'stage'
        (self.game/'profiles/test').mkdir(parents=True);(self.game/'profiles/test/modlist.txt').write_text('+TestMod\n',encoding='utf-8')
        (self.package/'blobs').mkdir(parents=True)
        self.original=self.game/'mods/TestMod/original.txt';self.original.parent.mkdir(parents=True);self.original.write_bytes(b'original')
        self.new=self.game/'mods/TestMod/strings/new_en.strings'
        operations=[]
        for target,kind,old,new in [('mods/TestMod/original.txt','copy',b'original',b'patched'),('mods/TestMod/strings/new_en.strings','fallback_strings',None,b'new')]:
            blob=backend.sha(new);(self.package/'blobs'/blob).write_bytes(new)
            operations.append({'target':target,'kind':kind,'blob':blob,'input_sha256':backend.sha(old) if old else None,'output_sha256':blob})
        (self.package/'manifest.json').write_text(json.dumps({'default_profile':'test','operations':operations}),encoding='utf-8')
    def prepare(self):return backend.generate(self.game,self.package,self.stage)
    def test_apply_restore_and_repeat(self):
        self.prepare();backup=backend.apply(self.stage)
        self.assertEqual(self.original.read_bytes(),b'patched');self.assertEqual(self.new.read_bytes(),b'new')
        backend.restore(backup);self.assertEqual(self.original.read_bytes(),b'original');self.assertFalse(self.new.exists())
        backend.restore(backup);self.assertEqual(self.original.read_bytes(),b'original')
    def test_changed_after_prepare_stops_all_writes(self):
        self.prepare();self.original.write_bytes(b'user edit')
        with self.assertRaises(backend.InstallError):backend.apply(self.stage)
        self.assertFalse(self.new.exists());self.assertEqual(self.original.read_bytes(),b'user edit')
    def test_restore_refuses_to_erase_user_changes(self):
        self.prepare();backup=backend.apply(self.stage);self.original.write_bytes(b'user edit')
        with self.assertRaises(backend.InstallError):backend.restore(backup)
        self.assertTrue(self.new.exists())
    def test_partial_failure_rolls_back(self):
        self.prepare();real=backend.atomic;failed=False
        def fail_once(path,raw):
            nonlocal failed
            if Path(path)==self.new and not failed:failed=True;raise OSError('simulated failure')
            return real(path,raw)
        with patch.object(backend,'atomic',side_effect=fail_once):
            with self.assertRaises(OSError):backend.apply(self.stage)
        self.assertEqual(self.original.read_bytes(),b'original');self.assertFalse(self.new.exists())
    def test_escape_and_corrupt_payload_fail(self):
        with self.assertRaises(backend.InstallError):backend.safe(self.game,'../escape')
        with self.assertRaises(backend.InstallError):backend.generate(self.game,self.package,self.game)
        blob=next((self.package/'blobs').iterdir());blob.write_bytes(b'corrupt')
        with self.assertRaises(backend.InstallError):self.prepare()
        self.assertEqual(self.original.read_bytes(),b'original')
    def test_base_content_version_mismatch_stops_generation(self):
        steam=self.root/'Steam';(steam/'Data').mkdir(parents=True);(steam/'Data/Test.esm').write_bytes(b'new version')
        self.game.joinpath('ModOrganizer.ini').write_text('gamePath = @ByteArray('+str(steam).replace('\\','\\\\')+')\n',encoding='utf-8')
        p=self.package/'manifest.json';m=json.loads(p.read_text());m['base_content_checks']=[{'name':'Test.esm','required':True,'sha256':backend.sha(b'old version')}];p.write_text(json.dumps(m))
        with self.assertRaises(backend.InstallError):self.prepare()
        self.assertEqual(self.original.read_bytes(),b'original')
    def test_upgrade_existing_translation_and_restore(self):
        def strings(text):
            block=text.encode('utf-8')+b'\0'
            return struct.pack('<IIII',1,len(block),123,0)+block
        old=strings('기존 번역');new=strings('새 번역')
        path=self.game/'mods/TestMod/name_en.strings';path.write_bytes(old)
        raw=gzip.compress(json.dumps({'kind':'.strings','translations':[[123,['기존 번역','새 번역']]]},ensure_ascii=False).encode())
        blob=backend.sha(raw);(self.package/'blobs'/blob).write_bytes(raw)
        op={'target':'mods/TestMod/name_en.strings','kind':'text_recipe','input_sha256':backend.sha(strings('English')),'output_sha256':backend.sha(new),'blob':blob,'upgrade_from':[{'input_sha256':backend.sha(old),'blob':blob}]}
        (self.package/'manifest.json').write_text(json.dumps({'default_profile':'test','operations':[op]}))
        self.prepare();backup=backend.apply(self.stage);self.assertEqual(path.read_bytes(),new)
        backend.restore(backup);self.assertEqual(path.read_bytes(),old)
        path.write_bytes(strings('사용자 수정'))
        with self.assertRaises(backend.InstallError):self.prepare()
if __name__=='__main__':unittest.main()
