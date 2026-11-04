import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from policy import check_domain

ROOT = Path(__file__).resolve().parent.parent

class PolicyTests(unittest.TestCase):
    def test_local_and_malformed_destinations_rejected(self):
        for domain in ['127.0.0.1','172.30.0.1','::1','localhost','host.docker.internal','*.com','https://example.com/x','foo.local']:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                check_domain(domain)

    def test_new_upstream_private_host_fails_build(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            shutil.copytree(ROOT/'scripts', target/'scripts')
            shutil.copytree(ROOT/'upstream', target/'upstream')
            for name in ('overlay.json','profiles.json','policy.json'):
                shutil.copy(ROOT/name,target/name)
            path=target/'upstream/gh-aw/ecosystem_domains.json'
            data=json.loads(path.read_text());data['ecosystems']['defaults'].append('new-host.internal');path.write_text(json.dumps(data))
            result=subprocess.run([sys.executable,'-B',str(target/'scripts/build.py')],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('new-host.internal',result.stderr)

    def test_candidate_never_becomes_a_generated_allow(self):
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run([sys.executable,'-B',str(ROOT/'scripts/build.py')],env={**os.environ,'SANDBOX_ALLOWLIST_OUT':temp},check=True,capture_output=True)
            candidates={e['domain'] for e in json.loads((ROOT/'overlay.json').read_text())['domains'] if e['status']=='candidate'}
            for path in Path(temp).glob('*/domains.txt'):
                self.assertFalse(candidates & set(path.read_text().splitlines()))
                self.assertNotIn('host.docker.internal',path.read_text())

if __name__=='__main__':unittest.main()
