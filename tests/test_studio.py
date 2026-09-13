"""Studio HTTP/persistence regressions; never touch installation data or speakers."""
import copy
import time
import unittest
from unittest.mock import patch
import test_runtime as runtime


class StudioTests(unittest.TestCase):
    setUpClass=classmethod(runtime.RuntimeTests.setUpClass.__func__)
    tearDownClass=classmethod(runtime.RuntimeTests.tearDownClass.__func__)
    request=runtime.RuntimeTests.request

    def setUp(self):
        from monitor_studio import defaults
        snap=self.state.studio.snapshot()
        self.state.studio.save(defaults(),snap['revision'])
        with self.state.studio.connect() as con:
            con.execute('DELETE FROM records');con.execute('DELETE FROM decisions');con.execute('DELETE FROM recordings');con.execute('DELETE FROM designs')
        self.state.studio.seen.clear()

    def get_config(self):return self.request('/api/remote/studio/config')[1]
    def post(self,key,payload):return self.request('/api/remote/studio/'+key,payload)
    def seed(self,n=1):
        rows=[dict(id='studio-'+str(i),title='P 1 BR Woning Teststraat Tilburg 20-9432',published='2026-09-13T10:00:00+00:00',city='Tilburg',location='Teststraat',service='brandweer',units=['20-9432']) for i in range(n)]
        self.state.studio.record(rows,lambda m:True,{'name':'Test'})
        return rows

    def test_config_atomic_conflict_and_disk_failure(self):
        d=self.get_config();d['config']['enabled']=True
        self.assertEqual(self.post('config',d)[0],200)
        self.assertEqual(self.post('config',d)[0],400)
        import monitor_studio
        before=self.get_config();new=copy.deepcopy(before);new['config']['enabled']=False
        with patch.object(monitor_studio,'atomic_json',side_effect=OSError('full')):
            self.assertEqual(self.post('config',new)[0],503)
        self.assertEqual(self.get_config(),before)

    def test_invalid_geometry_and_bad_rule_references_rejected(self):
        d=self.get_config();d['config']['zones']=[dict(id='z',name='Test',points=[[51,5],[51,5],[51,5]])]
        self.assertEqual(self.post('config',d)[0],400)
        d['config']['zones']=[dict(id='z',name='Test',points=[[51,5],[52,5],[52,6]])]
        d['config']['rules']=[dict(id='r',name='Test',when={'zone':'missing'},action='hide')]
        self.assertEqual(self.post('config',d)[0],400)
        d['config']['rules'][0]['when']={'zone':'z','min_scale':60}
        self.assertEqual(self.post('config',d)[0],200)

    def test_layout_bounds_and_unknown_template_tokens(self):
        d=self.get_config();d['config']['layout']['scenes']['single'][0]['x']=99
        self.assertEqual(self.post('config',d)[0],400)
        d=self.get_config();d['config']['speech']['template']='{secret}'
        self.assertEqual(self.post('config',d)[0],400)

    def test_viewer_cannot_read_or_modify_studio(self):
        invitation=self.module._REMOTE_ACCESS.invite('Viewer','viewer')
        _,_,h=self.request('/api/remote/session',{},phone=True,headers={'X-P2000-Admin-Token':invitation['token']})
        headers={'Cookie':h['Set-Cookie'].split(';')[0]}
        for key in ['config','records','recordings','examples']:
            self.assertEqual(self.request('/api/remote/studio/'+key,phone=True,headers=headers)[0],403)
            self.assertEqual(self.request('/api/remote/studio/'+key,{},phone=True,headers=headers)[0],403)

    def test_feed_records_rejected_messages_and_applies_correction_before_scope(self):
        raw='P 1 BR Woning Teststraat Tilburg 20-9432'
        d=self.get_config();c=dict(id='fix',mode='exact',match=raw,changes={'city':'Riel'})
        preview=self.post('correction-preview',dict(raw=raw,correction=c))[1]
        self.assertEqual(self.post('correction-save',dict(raw=raw,correction=c,revision=d['revision'],preview_revision=preview['revision']))[0],200)
        xml=f'<rss><channel><item><title>{raw}</title><guid>unique</guid><pubDate>Sun, 13 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>'.encode()
        seen=[]
        def scope(_cfg,message):seen.append(message.city);return False
        with patch.object(self.module,'config_allows_message',side_effect=scope):
            result=self.module.FeedPoller(self.state)._process_payload('https://112-nu.nl/brandweer/rss',xml,{})
        rows=self.state.studio.list_records()
        self.assertEqual(len(rows),1);self.assertFalse(rows[0]['scope'])
        self.assertEqual(rows[0]['message']['corrected']['city'],'Riel');self.assertIn('Riel',seen)
        self.assertEqual(result[2],0)

    def test_correction_preview_is_read_only_and_reports_broad_impact(self):
        self.seed(3);before=self.get_config()
        c=dict(id='broad',mode='contains',match='Teststraat Tilburg',changes={'location':'Andere straat'})
        p=self.post('correction-preview',dict(raw='P 1 BR Woning Teststraat Tilburg 20-9432',correction=c))[1]
        self.assertEqual(len(p['affected']),3);self.assertEqual(self.get_config(),before)
        self.assertEqual(self.post('correction-save',dict(raw='x',correction=c,revision=before['revision'],preview_revision=-1))[0],400)

    def test_corrections_create_persistent_regression_cases(self):
        raw='P 1 BR Woning Teststraat Tilburg 20-9432';d=self.get_config()
        c=dict(id='example',mode='exact',match=raw,changes={'city':'Testdorp'})
        self.assertEqual(self.post('correction-save',dict(raw=raw,correction=c,revision=d['revision'],preview_revision=d['revision']))[0],200)
        tests=self.request('/api/remote/studio/examples')[1]['tests'];self.assertTrue(tests[-1]['passed'])
        from monitor_studio import Studio
        reopened=Studio(self.module.DATA_DIR);self.assertEqual(reopened.snapshot(),self.state.studio.snapshot())
        self.post('correction-delete',dict(id='example',revision=self.get_config()['revision']))
        tests=self.request('/api/remote/studio/examples')[1]['tests'];self.assertFalse(tests[-1]['passed'])

    def test_normal_design_save_cannot_replace_corrections(self):
        d=self.get_config();d['config']['corrections']=[dict(id='bad',mode='contains',match='Teststraat',changes={'city':'Changed'})]
        result=self.post('config',d)[1];self.assertEqual(result['config']['corrections'],[])

    def test_recording_snapshot_is_immutable_and_has_no_display_side_effects(self):
        self.seed(3);seq=self.state.display_command_seq
        self.assertEqual(self.post('capture',dict(name='Avond',since=0,until=time.time()+1))[0],200)
        saved=self.state.studio.recordings()[0];captured=self.state.studio.recordings(saved['id'])
        d=self.get_config();d['config']['enabled']=True;self.post('config',d)
        self.assertEqual(captured,self.state.studio.recordings(saved['id']))
        self.assertFalse(captured['designs'][captured['records'][0]['design_id']]['studio']['config']['enabled'])
        self.assertEqual(self.state.display_command_seq,seq)
        self.assertEqual(self.post('capture',dict(name='Bad',since=10,until=1))[0],400)

    def test_recorder_bound_and_designs_deduplicated(self):
        rows=self.seed(2100);self.assertEqual(len(self.state.studio.list_records(limit=500)),500)
        with self.state.studio.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM records').fetchone()[0],2000)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM designs').fetchone()[0],1)
        self.state.studio.record(rows,lambda m:True,{})
        with self.state.studio.connect() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM records').fetchone()[0],2000)

    def test_failing_recorder_does_not_break_feed(self):
        import sqlite3
        with patch.object(self.state.studio,'connect',side_effect=sqlite3.OperationalError('locked')):
            self.seed()
        self.assertIn('Opname opslaan mislukt',self.state.studio.error)

    def test_decision_requires_registered_screen(self):
        self.seed();payload=dict(id='studio-0',client_id='nonexistent',shown=True,reason='Rule',revision=0)
        self.assertEqual(self.post('decision',payload)[0],400)
        self.request('/api/client-health',dict(client_id='studio-screen',visibility='visible'))
        payload['client_id']='studio-screen'
        self.assertEqual(self.post('decision',payload)[0],200)
        self.assertEqual(self.state.studio.list_records()[0]['decisions'][0]['reason'],'Rule')
