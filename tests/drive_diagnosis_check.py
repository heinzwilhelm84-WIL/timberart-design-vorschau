"""Offline, read-only diagnosis contracts. No live Drive or GitHub requests."""
import contextlib
import copy
import io
import os
import pathlib
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tests')]
import drive_sync as sync
import sync_motifs as images
from drive_sync_check import fixture, snapshot, write, folder, image, blob


class DiagnosisChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)/'repo'
        self.api = fixture(self.root)
        sync.synchronize(self.root, self.api, True)
        self.api.downloads = []

    def diagnose(self):
        before = snapshot(self.root)
        with patch.object(self.api, 'download', side_effect=AssertionError('No media download')), \
             patch.object(images, 'atomic_write', side_effect=AssertionError('No repository writes')):
            result = sync.diagnose_metadata(self.root, self.api)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(self.api.downloads, [])
        for value in ['Alt.png', 'legacy-fixed', 'TimberArt_Designs', 'PRIVATE', 'ya29.', 'md5Checksum', 'folderIds']:
            self.assertNotIn(value, result)
        return result

    def test_unchanged_is_zero_and_read_only(self):
        result = self.diagnose()
        self.assertIn('Metadatenprojektion: 0', result)
        self.assertIn('nicht sichtbare bestehende Motive: 0', result)
        self.assertIn('Bildverifikation (nicht ausgefuehrt): 0', result)

    def test_each_metadata_change_identifies_fixed_field_label(self):
        original = copy.deepcopy(self.api.tree['a'][0])
        for key, value, label in [
            ('name', 'PRIVATE customer.png', 'Quelldateiname'),
            ('modifiedTime', 'PRIVATE timestamp', 'Aenderungszeit'),
            ('version', 'PRIVATE version', 'Dateiversion'),
            ('size', '99', 'Dateigroesse'),
            ('md5Checksum', '0'*32, 'Inhaltspruefsumme'),
        ]:
            with self.subTest(key=key):
                self.api.tree['a'][0] = {**original, key:value}
                result = self.diagnose()
                self.assertIn(label + ': 1', result)
                self.assertIn('Metadatenprojektion: 1', result)
                self.assertIn('nur Metadatenabweichung: ' + ('0' if key=='md5Checksum' else '1'), result)
                self.assertIn('Bildverifikation (nicht ausgefuehrt): ' + ('1' if key=='md5Checksum' else '0'), result)

    def test_one_new_and_one_withheld_is_explained_without_importing_new_image(self):
        self.api.tree['a'][0]['version'] = '2'
        data = blob('blue')
        self.api.tree['a'].append(image('PRIVATE-new-id', 'PRIVATE new.png', data))
        self.api.payloads['PRIVATE-new-id'] = data
        result = self.diagnose()
        self.assertIn('Durch Metadaten oder Sichtbarkeit erklaerte Rueckhaltungen: 1', result)
        self.assertIn('nur Metadatenabweichung: 1', result)
        self.assertIn('Dateiversion: 1', result)
        self.assertIn('Bildverifikation (nicht ausgefuehrt): 0', result)
        # Confirm the existing importer reaches the same explanation on this fixture.
        imported = sync.synchronize(self.root, self.api, True)
        self.assertEqual(imported['metadataOnlyImages'], ['old'])
        self.assertEqual(imported['newImages'], ['PRIVATE-new-id'])
        self.assertEqual(self.api.downloads, ['PRIVATE-new-id'])

    def test_missing_is_not_claimed_deleted(self):
        self.api.tree['a'] = []
        result = self.diagnose()
        self.assertIn('nicht sichtbare bestehende Motive: 1', result)
        self.assertIn('beweist keine Loeschung', result)
        self.assertIn('Metadatenprojektion: 0', result)

    def test_folder_rename_and_move_keep_existing_ids_and_categories(self):
        self.api.tree['root'][0]['name'] = 'PRIVATE renamed'
        result = self.diagnose()
        self.assertIn('Kategorien mit abweichenden Metadaten: 1', result)
        self.assertIn('Metadatenprojektion: 0', result)
        self.api.tree['root'].append(folder('new-parent', 'PRIVATE parent'))
        self.api.tree['new-parent'] = [self.api.tree['root'].pop(0)]
        result = self.diagnose()
        self.assertIn('Kategorien mit abweichenden Metadaten: 1', result)
        self.assertIn('Metadatenprojektion: 0', result)

    def test_motif_move_reports_assignment_and_source_folder(self):
        self.api.tree['root'].append(folder('new', 'PRIVATE new category'))
        self.api.tree['new'] = [self.api.tree['a'].pop(0)]
        result = self.diagnose()
        self.assertIn('Direkter Quellordner: 1', result)
        self.assertIn('Kategoriezuordnung: 1', result)

    def test_stale_saved_fingerprint_is_distinguished_from_changed_drive_data(self):
        manifest = images.read_json(self.root/'data/motifs-manifest.json')
        manifest['motifs'][0]['sourceFingerprint'] = 'PRIVATE stale'
        write(self.root, 'data/motifs-manifest.json', manifest)
        result = self.diagnose()
        self.assertIn('Gespeicherter Quell-Fingerprint inkonsistent: 1', result)
        self.assertIn('Dateiversion: 0', result)
        self.assertIn('Inhaltspruefsumme: 0', result)

    def test_legacy_record_and_generator_mismatch_remain_explicitly_unverified(self):
        manifest = images.read_json(self.root/'data/motifs-manifest.json')
        entry = manifest['motifs'][0]
        entry.pop('originalFingerprint')
        entry['generator'] = {**entry['generator'], 'pillow':'older'}
        entry['syncVersion'] = 0
        write(self.root, 'data/motifs-manifest.json', manifest)
        result = self.diagnose()
        self.assertIn('Bildverifikation (nicht ausgefuehrt): 1', result)
        self.assertIn('Vorschaugenerator: 1', result)
        self.assertIn('Importversion: 1', result)

    def test_saved_exclusions_continue_to_apply(self):
        self.api.tree['root'][1]['name'] = 'PRIVATE formerly excluded'
        self.diagnose()
        self.assertNotIn('logos', self.api.reads)
        self.assertNotIn('fonts', self.api.reads)

    def cli(self, extra=()):
        report = pathlib.Path(self.temp.name)/'summary.md'
        args = ['sync', '--repo', str(self.root), '--diagnose-metadata', '--report', str(report), *extra]
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', args), patch.object(sync, 'DriveAPI', return_value=self.api), \
             patch.object(sync, 'synchronize', side_effect=AssertionError('No import')), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = sync.main()
        return status, report, out.getvalue(), err.getvalue()

    def test_cli_emits_only_aggregate_report_outside_repository(self):
        before = snapshot(self.root)
        status, report, out, err = self.cli()
        self.assertEqual(status, 0)
        self.assertIn('Metadaten-Diagnose', report.read_text())
        self.assertNotIn('Alt', out+err+report.read_text())
        self.assertEqual(snapshot(self.root), before)

    def test_failures_do_not_disclose_api_errors_or_write_reports(self):
        for exception in (sync.SyncError('PRIVATE file-id name token'), sync.MappingError()):
            with self.subTest(exception=type(exception).__name__):
                self.api.tree['a'] = exception
                before = snapshot(self.root)
                status, report, out, err = self.cli()
                self.assertEqual(status, 1)
                self.assertFalse(report.exists())
                self.assertNotIn('PRIVATE', out+err)
                self.assertEqual(snapshot(self.root), before)

    def test_cli_forbids_import_binding_overrides_and_repository_reports(self):
        for extra in [['--additions-evidence', '/tmp/not-created-evidence.json'],
                      ['--category-bindings', '/tmp/not-read-bindings.json'],
                      ['--report', str(self.root/'not-created.md')]]:
            status, report, _, _ = self.cli(extra)
            self.assertEqual(status, 1)
            self.assertFalse(report.exists())
        with patch.object(sys, 'argv', ['sync', '--diagnose-metadata', '--apply', '--report', '/tmp/unused']), \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            sync.main()

    def test_unknown_source_keys_never_become_report_labels(self):
        manifest = images.read_json(self.root/'data/motifs-manifest.json')
        manifest['motifs'][0]['source']['PRIVATE-field'] = 'PRIVATE value'
        write(self.root, 'data/motifs-manifest.json', manifest)
        status, report, out, err = self.cli()
        self.assertEqual(status, 1)
        self.assertFalse(report.exists())
        self.assertNotIn('PRIVATE', out+err)


class WorkflowChecks(unittest.TestCase):
    def test_diagnosis_is_manual_main_only_with_metadata_scope_and_no_write_paths(self):
        import yaml
        w = yaml.load((ROOT/'.github/workflows/drive-motifs-sync.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertIn('diagnose-metadata', w['on']['workflow_dispatch']['inputs']['mode']['options'])
        job = w['jobs']['diagnose-metadata']
        self.assertEqual(job['permissions'], {'contents':'read', 'id-token':'write'})
        for condition in ["github.event_name == 'workflow_dispatch'", "inputs.mode == 'diagnose-metadata'",
                          "github.ref == 'refs/heads/main'", "github.repository_id == '1425353605'"]:
            self.assertIn(condition, job['if'])
        self.assertNotIn('outputs', job)
        self.assertNotIn('needs', job)
        for step in job['steps']:
            if 'uses' in step:
                self.assertRegex(step['uses'], r'@[a-f0-9]{40}$')
            for forbidden in ['--apply', '--publish', '--seed', 'git push', 'upload-artifact', 'create-pull-request', 'pages/builds']:
                self.assertNotIn(forbidden, str(step))
        auth = next(s for s in job['steps'] if s.get('id')=='google-auth')['with']
        self.assertEqual(auth['access_token_scopes'], 'https://www.googleapis.com/auth/drive.metadata.readonly')
        self.assertEqual(auth['create_credentials_file'], 'false')
        self.assertEqual(auth['export_environment_variables'], 'false')
        checkout = job['steps'][0]['with']
        self.assertEqual(checkout['ref'], '${{ github.sha }}')
        self.assertEqual(checkout['persist-credentials'], 'false')
        self.assertTrue(any('drive_sync.py --diagnose-metadata --report' in s.get('run','') for s in job['steps']))
        for name in ('inventory', 'dry-run', 'prepare'):
            self.assertNotIn("inputs.mode == 'diagnose-metadata'", w['jobs'][name]['if'])


if __name__ == '__main__':
    with patch.object(socket, 'create_connection', side_effect=AssertionError('Offline tests must not connect')):
        unittest.main()
