"""Real HTTP regressions for per-device roles, restore transactions and streams."""
import base64
import concurrent.futures
import copy
import http.client
import json
import threading
import time
import unittest
from unittest.mock import patch
import test_runtime as runtime


class RemoteTests(unittest.TestCase):
    setUpClass = classmethod(runtime.RuntimeTests.setUpClass.__func__)
    tearDownClass = classmethod(runtime.RuntimeTests.tearDownClass.__func__)
    request = runtime.RuntimeTests.request

    def pair(self, role='controller', name='Phone'):
        invitation = self.request('/api/remote/invite', {'role': role, 'name': name})[1]['invite']
        code, data, headers = self.request('/api/remote/session', {}, phone=True, headers={'X-P2000-Admin-Token': invitation['token']})
        self.assertEqual(code, 200)
        return {'Cookie': headers['Set-Cookie'].split(';', 1)[0]}, data['id'], invitation

    def insert(self, mid, published='2026-09-12T10:00:00+00:00', **values):
        with self.state.connect() as con:
            columns = {row[1]: row for row in con.execute('PRAGMA table_info(messages)')}
            row = {name: '' for name, meta in columns.items() if meta[3]}
            row.update(id=mid,published=published,title='P 1 BR woning Teststraat Tilburg',city='Tilburg',service='brandweer',priority='P1',units_json='[]',categories_json='[]',scale_score=0,parser_confidence=0,parser_notes_json='[]',**values)
            con.execute(f'INSERT OR REPLACE INTO messages({",".join(row)}) VALUES({",".join("?" for _ in row)})', list(row.values()))

    def test_invitation_one_use_expiring_and_no_shared_token(self):
        headers, key, invite = self.pair()
        self.assertEqual(self.request('/api/remote/session', {}, phone=True, headers={'X-P2000-Admin-Token': invite['token']})[0],401)
        self.assertEqual(self.request('/api/remote/status', phone=True, headers={'X-P2000-Admin-Token': invite['token']})[0],401)
        row=self.request('/api/remote/invite', {})[1]['invite']
        access=self.module._REMOTE_ACCESS
        access.invites[access.digest(row['token'])]['expires_at']=time.time()-1
        self.assertEqual(self.request('/api/remote/session', {},phone=True,headers={'X-P2000-Admin-Token':row['token']})[0],401)

    def test_concurrent_pairing_consumes_invite_once(self):
        invitation=self.module._REMOTE_ACCESS.invite('Concurrent')
        def pair(_):return self.request('/api/remote/session',{},phone=True,headers={'X-P2000-Admin-Token':invitation['token']})[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool: statuses=list(pool.map(pair,range(5)))
        self.assertEqual(statuses.count(200),1);self.assertEqual(statuses.count(401),4)

    def test_viewer_read_allowlist_and_all_mutations_denied(self):
        headers,_,_=self.pair('viewer')
        for path in ['/api/remote/status','/api/remote/archive','/api/remote/info']:
            self.assertEqual(self.request(path,phone=True,headers=headers)[0],200,path)
        for path in ['/api/settings','/api/remote/history','/api/remote/devices','/api/stream','/api/update/github/settings']:
            self.assertEqual(self.request(path,phone=True,headers=headers)[0],403,path)
        for path in ['/api/settings','/api/quick-action','/api/remote/profile','/api/client-health','/api/remote/receipt','/api/remote/invite','/api/background/upload']:
            self.assertEqual(self.request(path,{},phone=True,headers=headers)[0],403,path)

    def test_revocation_leaves_other_devices_working_and_persists_hash_only(self):
        a,aid,invite=self.pair(name='A');b,_,_=self.pair(name='B')
        self.assertEqual(self.request('/api/remote/revoke',{'id':aid})[0],200)
        self.assertEqual(self.request('/api/remote/status',phone=True,headers=a)[0],401)
        self.assertEqual(self.request('/api/remote/status',phone=True,headers=b)[0],200)
        stored=self.module._REMOTE_ACCESS.path.read_text()
        self.assertNotIn(invite['token'],stored);self.assertNotIn(b['Cookie'].split('=',1)[1],stored)
        refreshed=type(self.module._REMOTE_ACCESS)(self.module._REMOTE_ACCESS.path.parent/'admin-token.txt')
        self.assertNotIn(aid,refreshed.devices)

    def test_logout_revokes_server_session(self):
        headers,_,_=self.pair()
        self.assertEqual(self.request('/api/remote/logout',{},phone=True,headers=headers)[0],200)
        self.assertEqual(self.request('/api/remote/status',phone=True,headers=headers)[0],401)

    def test_controller_cannot_administer_other_devices(self):
        headers,_,_=self.pair()
        for path,payload in [('/api/remote/devices',None),('/api/remote/invite',{}),('/api/remote/revoke',{'id':'x'})]:
            self.assertEqual(self.request(path,payload,phone=True,headers=headers)[0],403)

    def test_profile_roundtrip_preserves_filters_and_original_volume(self):
        original=copy.deepcopy(self.state.get_display_settings())
        try:
            self.state.save_display_settings({'activeProfile':'normal','masterVolume':37,'cities':['Tilburg'],'services':['brandweer'],'nightMode':False})
            result=self.request('/api/remote/profile',{'id':'night'})[1]['settings']
            self.assertEqual(result['masterVolume'],25);self.assertEqual(result['cities'],['Tilburg'])
            result=self.request('/api/remote/profile',{'id':'exercise'})[1]['settings']
            self.assertTrue(result['exerciseMode']);self.assertFalse(result['nightMode'])
            result=self.request('/api/remote/profile',{'id':'urgent'})[1]['settings'];self.assertTrue(result['urgentOnly']);self.assertFalse(result['exerciseMode'])
            result=self.request('/api/remote/profile',{'id':'normal'})[1]['settings']
            self.assertEqual(result['masterVolume'],37);self.assertFalse(result['nightMode']);self.assertEqual(result['services'],['brandweer'])
        finally:self.state.save_display_settings(original,replace=True)

    def test_restore_removes_new_keys_and_survives_a_new_dashboard(self):
        original=copy.deepcopy(self.state.get_display_settings())
        point=self.request('/api/remote/checkpoint',{'description':'Before theme'})[1]['id']
        self.state.save_display_settings({'backgroundColor':'#abcdef','masterVolume':17})
        preview=self.request('/api/remote/restore-preview?id='+point)[1]['preview']
        self.assertTrue(any(x['key']=='backgroundColor' for x in preview['changes']))
        result=self.request('/api/remote/restore',{'id':point,'expected':preview['expected']})
        self.assertEqual(result[0],200);self.assertEqual(self.state.get_display_settings(),original)
        dashboard=type(self.state.dashboard)(self.state,self.module.DATA_DIR)
        self.assertTrue(any(x['id']==point for x in dashboard.history_view()))

    def test_restore_rejects_changes_after_preview_and_never_writes(self):
        point=self.request('/api/remote/checkpoint',{})[1]['id']
        preview=self.request('/api/remote/restore-preview?id='+point)[1]['preview']
        self.state.save_display_settings({'masterVolume':19})
        self.assertEqual(self.request('/api/remote/restore',{'id':point,'expected':preview['expected']})[0],400)
        self.assertEqual(self.state.get_display_settings()['masterVolume'],19)

    def test_failed_checkpoint_prevents_setting_change(self):
        original=self.state.get_display_settings()
        with patch.object(self.state.dashboard,'checkpoint',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.state.save_display_settings({'name':'Must not save'})
        self.assertEqual(self.state.get_display_settings(),original)

    def test_history_and_metrics_remain_bounded(self):
        dash=self.state.dashboard
        for number in range(45):dash.checkpoint('Test',{'name':str(number)})
        self.assertEqual(len(dash.history),40)
        for number in range(1000):dash.measure('bounded',number)
        self.assertEqual(dash.metrics()['stages']['bounded']['samples'],240)
        for _ in range(365):dash.sample(force=True)
        self.assertEqual(len(dash.samples),360)

    def test_archive_date_filters_and_stable_cursor(self):
        with self.state.connect() as con:con.execute('DELETE FROM messages')
        for i in range(61):self.insert(f'archive-{i:03}')
        self.insert('old','2020-01-01T00:00:00+00:00')
        first=self.request('/api/remote/archive?city=tilburg&service=brandweer&since=2026-09-12T00:00:00Z&until=2026-09-13T00:00:00Z')[1]
        self.assertEqual(len(first['messages']),50);self.assertTrue(first['next_cursor'])
        second=self.request('/api/remote/archive?since=2026-09-12T00:00:00Z&cursor='+first['next_cursor'])[1]
        self.assertEqual(len(second['messages']),11)
        self.assertFalse(set(x['id'] for x in first['messages'])&set(x['id'] for x in second['messages']))
        self.assertIsNone(second['next_cursor'])
        self.assertEqual(self.request('/api/remote/archive?until=garbage')[0],400)
        self.assertEqual(self.request('/api/remote/archive?cursor=%25%25%25')[0],400)

    def test_archive_pin_replay_and_unpin_produce_screen_commands(self):
        self.insert('pin-source')
        for action in ['pin','replay','unpin']:
            code,data,_=self.request('/api/remote/message-action',{'id':'pin-source','action':action})
            self.assertEqual(code,200)
            cmd=self.state.display_command_batch(data['command_seq']-1)['commands'][0]
            self.assertEqual(cmd['action'],action);self.assertEqual(cmd['speak'],action=='replay')
        self.assertEqual(self.request('/api/remote/message-action',{'id':'missing','action':'pin'})[0],400)

    def test_receipts_validate_target_and_do_not_regress(self):
        self.state.record_display_client('screen-a',{})
        self.state.record_display_client('screen-b',{})
        _,seq=self.state.publish_display_command({'type':'remote-message','target_client_id':'screen-a','action':'pin'})
        row={'seq':seq,'client_id':'screen-b','status':'completed'}
        self.assertEqual(self.request('/api/remote/receipt',row)[0],400)
        row.update(client_id='screen-a',status='completed',detail='Getoond')
        self.assertEqual(self.request('/api/remote/receipt',row)[0],200)
        row['status']='received';self.request('/api/remote/receipt',row)
        self.assertEqual(self.state.dashboard.receipts[str(seq)]['results']['screen-a']['status'],'completed')

    def test_preview_requires_known_screen_and_valid_jpeg(self):
        self.state.record_display_client('preview-screen',{})
        self.assertEqual(self.request('/api/remote/preview',{'client_id':'preview-screen','image':'data:image/svg+xml,evil'})[0],400)
        image='data:image/jpeg;base64,'+base64.b64encode(b'\xff\xd8\xff\xe0fake\xff\xd9').decode()
        self.assertEqual(self.request('/api/remote/preview',{'client_id':'missing','image':image})[0],400)
        self.assertEqual(self.request('/api/remote/preview',{'client_id':'preview-screen','image':image,'message':'Archived'})[0],200)
        self.assertEqual(self.request('/api/remote/preview?client_id=preview-screen')[1]['preview']['image'],image)
        self.assertNotIn('image',self.request('/api/remote/status')[1]['screens']['preview-screen'])

    def test_remote_stream_updates_without_counting_as_screen_and_revokes(self):
        headers,key,_=self.pair('viewer')
        initial=self.state.subscriber_count()
        conn=http.client.HTTPConnection('127.0.0.1',self.servers[1].server_port,timeout=5)
        conn.request('GET','/api/remote/events',headers=headers);response=conn.getresponse()
        try:
            self.assertEqual(response.status,200)
            line=response.fp.readline().decode();self.assertTrue(line.startswith('data: '));response.fp.readline()
            self.assertEqual(self.state.subscriber_count(),initial)
            self.module._REMOTE_ACCESS.revoke(key);self.state.dashboard.notify()
            event=response.fp.readline().decode();self.assertEqual(event.strip(),'event: revoked')
        finally:conn.close()

    def test_real_pipeline_metrics_are_recorded(self):
        poller=self.module.FeedPoller(self.state)
        poller.parse_feed(b'<rss><channel></channel></rss>','https://example.test/rss')
        self.assertGreater(self.state.dashboard.metrics()['stages']['parse']['samples'],0)

    def test_host_playback_uses_process_completion_and_detects_cancel(self):
        process=runtime.SimpleNamespace(poll=lambda:None)
        tracker=self.module.HOST_PLAYBACK
        token=tracker.add(process)
        self.assertEqual(self.request('/api/tts/play-status?token='+token)[1]['status'],'playing')
        process.poll=lambda:1
        self.assertFalse(self.request('/api/tts/play-status?token='+token)[1]['ok'])
        process.poll=lambda:0
        self.assertEqual(self.request('/api/tts/play-status?token='+token)[1]['status'],'completed')
        tracker.cancel(process)
        self.assertEqual(self.request('/api/tts/play-status?token='+token)[1]['status'],'cancelled')

    def test_windows_pcm_volume_preserves_zero_and_half_gain(self):
        import io, struct, wave
        output=io.BytesIO()
        with wave.open(output,'wb') as writer:
            writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(22050)
            writer.writeframes(struct.pack('<hhhh',10000,-10000,32767,-32768))
        for volume,expected in [(0,(0,0,0,0)),(50,(5000,-5000,16384,-16384))]:
            scaled=self.module.attenuate_wav(output.getvalue(),volume)
            with wave.open(io.BytesIO(scaled),'rb') as reader:
                self.assertEqual(struct.unpack('<hhhh',reader.readframes(4)),expected)
                self.assertEqual(reader.getframerate(),22050)

    def test_archive_map_looks_up_only_the_requested_incident(self):
        self.insert('map-only')
        with patch.object(self.state,'geocode_incident',return_value={'lat':51.5,'lon':5}) as geocode:
            result=self.request('/api/remote/map?id=map-only')
        self.assertEqual(result[0],200);self.assertEqual(result[1]['map']['lat'],51.5)
        geocode.assert_called_once()


    def test_windows_player_passes_paths_as_literal_file_parameters(self):
        m=self.module
        fake_os=runtime.SimpleNamespace(name='nt',path=runtime.os.path)
        with patch.object(m,'os',fake_os),patch.object(m.shutil,'which',return_value='powershell.exe'):
            player,argv=m.detect_local_audio_player(50, 'C:/My folder/dispatch.wav')
        self.assertEqual(player,'windows-soundplayer')
        self.assertIn('-File',argv)
        self.assertNotIn('-Command',argv)
        self.assertEqual(argv[-1],'-AudioPath')
        self.assertTrue(runtime.Path(argv[argv.index('-File')+1]).is_file())

    def test_stop_during_host_render_cancels_before_process_launch(self):
        m=self.module
        def render(*args,**kwargs):
            self.assertFalse(kwargs['attention'])
            m.stop_host_tts()
            return b'a'*200,'audio/mpeg','test'
        fake_os=runtime.SimpleNamespace(name='nt',path=runtime.os.path,replace=runtime.os.replace)
        with patch.object(m,'os',fake_os),patch.object(m,'_TTS_PLAYER_PROCESS',None),patch.object(m,'generate_dispatch_audio',side_effect=render),patch.object(m,'detect_local_audio_player',return_value=('test',['test-player'])),patch.object(m.subprocess,'Popen') as launch:
            result=m.play_dispatch_tts_on_host('Stop while rendering',attention=False)
            self.assertTrue(result['cancelled'])
            launch.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
