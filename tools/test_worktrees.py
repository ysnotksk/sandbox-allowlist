import fcntl, importlib.util, pathlib, shutil, subprocess, tempfile, unittest
SOURCE=pathlib.Path(__file__).parent

def run(*args,cwd=None,check=True):
    p=subprocess.run(args,cwd=cwd,text=True,capture_output=True)
    if check and p.returncode: raise AssertionError((args,p.stdout,p.stderr))
    return p

class SweepTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='sweep test ')
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name).resolve(); self.remote=self.root/'remote.git'; self.repo=self.root/'main checkout'
        run('git','init','--bare',str(self.remote)); run('git','clone',str(self.remote),str(self.repo))
        self.g('config','user.name','Test'); self.g('config','user.email','test@example.invalid'); self.g('checkout','-b','main')
        (self.repo/'seed').write_text('seed'); self.g('add','.'); self.g('commit','-m','test: seed'); self.g('push','-u','origin','main')
        tools=self.repo/'tools'; tools.mkdir()
        for name in ['worktrees.py','worktrees.sh']: shutil.copyfile(SOURCE/name,tools/name)
        self.g('add','.'); self.g('commit','-m','test: install'); self.g('push')
    def g(self,*args,cwd=None,check=True): return run('git',*args,cwd=cwd or self.repo,check=check)
    def tree(self,name,commit=False):
        path=self.root/('checkout '+name); self.g('worktree','add','-b',name,str(path))
        if commit:
            (path/'change').write_text(name); self.g('add','.',cwd=path); self.g('commit','-m','test: '+name,cwd=path)
        return path
    def sweep(self): return run('bash',str(self.repo/'tools/worktrees.sh'),check=False)
    def test_all_categories_and_repeat(self):
        folded=self.tree('merged',True); self.g('push','origin','HEAD:refs/heads/remote-kept',cwd=folded); self.g('merge','--no-ff','merged','-m','test: merge')
        dirty=self.tree('dirty'); (dirty/'seed').write_text('dirty')
        untracked=self.tree('untracked'); (untracked/'new').write_text('new')
        locked=self.tree('locked'); self.g('worktree','lock',str(locked))
        detached=self.root/'detached'; self.g('worktree','add','--detach',str(detached))
        unmerged=self.tree('unmerged',True)
        squash=self.tree('squash',True); self.g('merge','--squash','squash'); self.g('commit','-m','test: squashed'); self.g('push')
        result=self.sweep(); self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertFalse(folded.exists()); self.assertNotEqual(self.g('show-ref','--verify','refs/heads/merged',check=False).returncode,0)
        self.assertIn('refs/heads/remote-kept',self.g('ls-remote','--heads','origin').stdout)
        for path in [self.repo,dirty,untracked,locked,detached,unmerged,squash]:
            self.assertTrue(path.exists(),str(path)); self.assertIn('keep  '+str(path),result.stdout)
        self.assertIn('locked:',result.stdout); self.assertIn('detached HEAD',result.stdout); self.assertIn('includes squash merges',result.stdout)
        again=self.sweep(); self.assertEqual(again.returncode,0); self.assertNotIn('fold  ',again.stdout)
    def test_fetch_failure(self):
        path=self.tree('eligible'); self.g('remote','set-url','origin',str(self.root/'missing'))
        p=self.sweep(); self.assertNotEqual(p.returncode,0); self.assertTrue(path.exists()); self.assertIn('fresh fetch',p.stdout); self.assertNotIn('fold  ',p.stdout)
    def test_cooperative_lock(self):
        path=self.tree('eligible')
        with (self.repo/'.git/worktree-sweep.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            p=self.sweep(); self.assertEqual(p.returncode,0); self.assertTrue(path.exists()); self.assertIn('another sweep is running',p.stdout)
    def test_revalidation_rejects_changed_head(self):
        path=self.tree('changed')
        spec=importlib.util.spec_from_file_location('candidate',SOURCE/'worktrees.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        tree=next(t for t in mod.records(self.repo) if t['worktree']==str(path))
        (path/'later').write_text('later'); self.g('add','.',cwd=path); self.g('commit','-m','test: later',cwd=path)
        self.assertEqual(mod.reason(str(self.repo),tree,str(self.repo),'origin/main'),'HEAD or branch changed during sweep')

if __name__=='__main__': unittest.main(verbosity=2)
