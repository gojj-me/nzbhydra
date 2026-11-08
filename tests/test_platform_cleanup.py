"""Linux updater selection and managed-update guard; no network or real updates."""
from __future__ import print_function
import os,sys,unittest,new
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0]=[ROOT,ROOT+'/libs']
from bunch import Bunch
from nzbhydra import config,update,build_info


class LinuxUpdaterTests(unittest.TestCase):
    def setUp(self):
        config.settings=Bunch.fromDict(config.initialConfig)
        self.originals=(update.os.path.exists,update.GitUpdateManager,update.SourceUpdateManager,
                        update.updateManager,build_info.get_build_info)
        update.updateManager=None
        self.calls=[]
        update.GitUpdateManager=lambda:self.calls.append('git') or 'git'
        update.SourceUpdateManager=lambda:self.calls.append('source') or 'source'

    def tearDown(self):
        (update.os.path.exists,update.GitUpdateManager,update.SourceUpdateManager,
         update.updateManager,build_info.get_build_info)=self.originals

    def test_git_checkout_selects_linux_git_manager(self):
        update.os.path.exists=lambda path:path.endswith('/.git')
        self.assertEqual('git',update.getUpdateManager());self.assertEqual(['git'],self.calls)

    def test_source_archive_selects_source_manager(self):
        update.os.path.exists=lambda path:False
        self.assertEqual('source',update.getUpdateManager())

    def test_stray_windows_marker_does_not_select_retired_manager(self):
        update.os.path.exists=lambda path:path.endswith('/nzbhydra.exe')
        self.assertEqual('source',update.getUpdateManager())
        self.assertFalse(hasattr(update,'WindowsUpdateManager'))

    def test_manager_selection_remains_cached(self):
        update.os.path.exists=lambda path:False
        self.assertEqual(update.getUpdateManager(),update.getUpdateManager())
        self.assertEqual(['source'],self.calls)

    def git_manager(self,status):
        manager=new.instance(self.originals[1])
        manager._run_git=lambda path,args:(self.calls.append((path,args)) or ('synthetic',None,status))
        return manager

    def test_linux_git_path_and_global_fallback(self):
        config.settings.main.gitPath='/synthetic/git'
        update.os.path.exists=lambda path:True
        manager=self.git_manager(0)
        self.assertEqual('/synthetic/git',manager._find_working_git())
        update.os.path.exists=lambda path:False
        self.assertEqual('git',manager._find_working_git())

    def test_missing_git_does_not_probe_retired_platform_paths(self):
        config.settings.main.gitPath=None
        manager=self.git_manager(1)
        self.assertIsNone(manager._find_working_git())
        self.assertEqual([('git','version')],self.calls)

    def test_managed_build_cannot_invoke_source_overwrite_updater(self):
        build_info.get_build_info=lambda:{'source_commit':'synthetic'}
        self.assertFalse(update.update())
        self.assertEqual([],self.calls)


if __name__=='__main__':unittest.main(verbosity=2)
