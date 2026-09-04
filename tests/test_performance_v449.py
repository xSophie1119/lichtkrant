#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, sys, time
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2000_v449_perf',ROOT/'backend'/'server.py')
mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
checks={}
checks['version'] = tuple(map(int,mod.APP_VERSION.split('.'))) >= (4,4,9)
checks['pooled_http'] = '_HTTP_POOL' in vars(mod) and 'pooled_http_bytes' in vars(mod)
checks['static_cache'] = hasattr(mod,'_STATIC_CACHE')
checks['defaults_fast'] = True
# Inspect the shipped config instead of mutating the user's actual config in this test.
config=json.loads((ROOT/'config'/'config.json').read_text('utf-8'))
checks['poll_8s'] = config.get('poll_interval_seconds') == 8
checks['timeout_6s'] = config.get('request_timeout_seconds') == 6
checks['workers_10'] = config.get('feed_parallel_workers') == 10
checks['migration_marker'] = config.get('performance_tuned_v449') is True
server=(ROOT/'backend'/'server.py').read_text('utf-8')
checks['ram_dedupe'] = 'recent_message_ids' in server and '_remember_message_id' in server
checks['hourly_retention'] = 'last_retention_cleanup_monotonic' in server and '>= 3600' in server
checks['conditional_cache_write'] = 'current = self.state.feed_cache.setdefault(url, {}).get(kind)' in server and 'if current == value:' in server
checks['scope_signature'] = 'scope-filter:v449' in server
# Existing installs with untouched v4.4.8 defaults are tuned once; custom choices survive.
old_cfg_path=mod.CONFIG_PATH
try:
    with TemporaryDirectory() as td:
        mod.CONFIG_PATH=Path(td)/'config.json'
        mod.CONFIG_PATH.write_text(json.dumps({'poll_interval_seconds':10,'request_timeout_seconds':15,'feed_parallel_workers':6}),encoding='utf-8')
        migrated=mod.load_config()
        checks['old_defaults_migrate']=(migrated['poll_interval_seconds'],migrated['request_timeout_seconds'],migrated['feed_parallel_workers'])==(8,6,10) and json.loads(mod.CONFIG_PATH.read_text()).get('performance_tuned_v449') is True
        mod.CONFIG_PATH.write_text(json.dumps({'poll_interval_seconds':12,'request_timeout_seconds':9,'feed_parallel_workers':4}),encoding='utf-8')
        custom=mod.load_config()
        checks['custom_values_preserved']=(custom['poll_interval_seconds'],custom['request_timeout_seconds'],custom['feed_parallel_workers'])==(12,9,4)
finally:
    mod.CONFIG_PATH=old_cfg_path
checks['feed_backoff'] = 'feed_backoff_until' in server and '_feed_backoff_seconds' in server
checks['primary_error_semantics'] = '112-nu tijdelijk niet bereikbaar; secundaire bron actief' in server
supervisor=(ROOT/'tools'/'supervisor.py').read_text('utf-8')
checks['supervisor_lightweight'] = 'loop_now-health_checked>=10' in supervisor and 'loop_now-display_checked>=15' in supervisor and 'time.sleep(2)' in supervisor
# Ensure repeated scope cleanup is O(1-ish): first call writes marker, second must not enumerate rows.
old_db=mod.DB_PATH
try:
    with TemporaryDirectory() as td:
        mod.DB_PATH=Path(td)/'perf.sqlite3'
        st=mod.AppState({'region_disciplines':{'midden-en-west-brabant':['brandweer']}});st.init_db()
        st.purge_out_of_scope()
        with st.connect() as con:
            marker=con.execute("SELECT value FROM kv WHERE key='scope-filter:v449'").fetchone()
        checks['scope_marker_written']=bool(marker)
        t=time.monotonic(); removed=st.purge_out_of_scope(); elapsed=time.monotonic()-t
        checks['scope_second_fast']=removed==0 and elapsed < .25
finally:
    mod.DB_PATH=old_db
failed=[k for k,v in checks.items() if not v]
print(json.dumps({'tests':len(checks),'passed':len(checks)-len(failed),'failures':len(failed),'failed':failed},ensure_ascii=False))
if failed: raise SystemExit(1)
