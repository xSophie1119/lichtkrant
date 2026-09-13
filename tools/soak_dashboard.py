#!/usr/bin/env python3
"""Exercise isolated real HTTP status streams and screen heartbeats for a duration.

No production settings, feeds, audio or screens are touched. Uses the regression
fixture to copy the checkout, then measures the actual backend process in this run.
"""
import argparse
import http.client
import json
import statistics
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tests'))
from test_runtime import RuntimeTests


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=120)
    parser.add_argument('--clients',type=int,default=3)
    args=parser.parse_args()
    if not 10<=args.seconds<=86400 or not 1<=args.clients<=10: parser.error('Gebruik 10–86400 seconden en 1–10 cliënten')
    RuntimeTests.setUpClass();test=RuntimeTests();state=test.state
    state.dashboard.start_sampler()
    stop=threading.Event();errors=[];latencies=[];stream_counts=[0]*args.clients
    started=time.monotonic()
    def stream(index):
        con=http.client.HTTPConnection('127.0.0.1',test.servers[1].server_port,timeout=15)
        try:
            con.request('GET','/api/remote/events',headers=test.auth_headers);response=con.getresponse()
            if response.status!=200: raise RuntimeError('Stream HTTP '+str(response.status))
            while not stop.is_set():
                line=response.fp.readline()
                if not line:break
                if line.startswith(b'data: '):json.loads(line[6:]);stream_counts[index]+=1
        except Exception as exc:
            if not stop.is_set():errors.append(str(exc))
        finally:con.close()
    workers=[threading.Thread(target=stream,args=(i,),daemon=True) for i in range(args.clients)]
    for worker in workers:worker.start()
    try:
        next_report=started+30
        while time.monotonic()-started<args.seconds:
            tick=time.perf_counter()
            code,_,_=test.request('/api/client-health',{'client_id':'soak-screen','render_p95_ms':2.5,'audio_unlocked':True})
            code2,data,_=test.request('/api/remote/status',phone=True,token=True)
            if code!=200 or code2!=200:errors.append(f'HTTP {code}/{code2}')
            latencies.append((time.perf_counter()-tick)*1000)
            if state.subscriber_count()!=0:errors.append('Phone counted as display subscriber')
            if time.monotonic()>=next_report:
                print(f'{int(time.monotonic()-started)}s: {sum(stream_counts)} statusupdates, {len(errors)} fouten',flush=True);next_report+=30
            stop.wait(.25)
        state.dashboard.sample(force=True)
        samples=list(state.dashboard.samples);rss=[x['rss_bytes'] for x in samples if x['rss_bytes'] is not None]
        report={'seconds':round(time.monotonic()-started,1),'stream_clients':args.clients,'stream_updates':stream_counts,'http_cycles':len(latencies),'http_pair_p95_ms':round(sorted(latencies)[min(len(latencies)-1,int(len(latencies)*.95))],2),'cpu_mean_percent':round(statistics.mean(x['cpu_percent'] for x in samples),2),'rss_first_bytes':rss[0] if rss else None,'rss_last_bytes':rss[-1] if rss else None,'samples':samples,'errors':errors}
        print(json.dumps(report,indent=2),flush=True)
    finally:
        stop.set();state.stop_event.set();state.dashboard.notify()
        for worker in workers:worker.join(timeout=3)
        RuntimeTests.tearDownClass()
    return bool(errors)


if __name__=='__main__':raise SystemExit(main())
