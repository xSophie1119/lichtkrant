"""Controller-only studio routes. Preview and playback never publish display commands."""
import copy
import sys
import time
import sqlite3
from dataclasses import asdict, fields
from monitor_studio import correction, apply_corrections, validate


def handle(handler,path,payload=None,query=None):
    runtime=sys.modules[handler.state.__class__.__module__]
    studio=handler.state.studio
    key=path.rsplit('/',1)[-1];qs=query or {};value=lambda k,d='':qs.get(k,[d])[0]
    try:
        if payload is None:
            if key=='config':return handler.send_json({'ok':True,**studio.snapshot()})
            if key=='records':
                records=studio.list_records(value('before',0),value('q'),value('since',0),value('until',4102444800))
                for row in records:row.pop('design',None)
                return handler.send_json({'ok':True,'records':records,'error':studio.error})
            if key=='recordings':return handler.send_json({'ok':True,'recordings':studio.recordings(value('id'))})
            if key=='examples':return handler.send_json({'ok':True,'tests':run_examples(handler.state,runtime)})
        elif key=='config':
            current=studio.snapshot();config=copy.deepcopy(payload.get('config'))
            if not isinstance(config,dict):raise ValueError('Ongeldige instellingen')
            config['corrections']=current['config']['corrections']
            result=studio.save(config,payload.get('revision'))
            handler.state.broadcast({'type':'studio','design':result})
            return handler.send_json({'ok':True,**result})
        elif key=='validate':return handler.send_json({'ok':True,'config':validate(payload.get('config'))})
        elif key=='decision':
            client=str(payload.get('client_id',''))
            if not any(c['client_id']==client and c['online'] for c in handler.state.display_clients_view()):raise ValueError('Onbekend scherm')
            studio.decision(payload);return handler.send_json({'ok':True})
        elif key=='parse':
            raw=str(payload.get('raw',''))[:1200]
            message=runtime.parse_raw_p2000_line(handler.state,raw,[])
            message['title']=raw
            result=correct_message(handler.state,message,runtime)
            result['incident']=runtime.incident_type_label(raw,'')
            with handler.state.vehicle_catalog_lock:
                result['vehicle_labels']=[vehicle_label(handler.state.vehicle_catalog.get(runtime.normalize_vehicle_digits(u),{}),u) for u in result.get('units',[])]
            return handler.send_json({'ok':True,'message':result})
        elif key in {'correction-preview','correction-save','correction-delete'}:
            current=studio.snapshot();conf=current['config']
            if key=='correction-delete':
                conf['corrections']=[x for x in conf['corrections'] if x['id']!=str(payload.get('id',''))]
            else:
                c=correction(payload.get('correction',{}))
                existing=[x for x in conf['corrections'] if x['id']!=c['id']]
                proposed=[c]+existing
                raw=str(payload.get('raw',''))[:1200]
                parsed=runtime.parse_raw_p2000_line(handler.state,raw,[]);parsed['title']=raw
                after=correct_message(handler.state,parsed,runtime,proposed)
                records=studio.list_records(limit=100)
                changes=[]
                for row in records:
                    before=correct_message(handler.state,row['message'],runtime,existing);new=correct_message(handler.state,row['message'],runtime,proposed)
                    diff={k:{'before':before.get(k),'after':new.get(k)} for k in c['changes'] if before.get(k)!=new.get(k)}
                    if diff:changes.append(dict(id=row['mid'],raw=row['message'].get('title',''),diff=diff))
                if key=='correction-preview':return handler.send_json({'ok':True,'correction':c,'before':parsed,'after':after,'affected':changes,'checked':len(records),'revision':current['revision']})
                if payload.get('preview_revision')!=current['revision']:raise ValueError('Bekijk eerst een actuele voorvertoning van de correctie')
                if after.get('studio_correction')!=c['id']:raise ValueError('Correctie past niet op het testvoorbeeld')
                conf['corrections']=proposed
                example=dict(raw=raw,expected={k:after.get(k) for k in c['changes']},correction=c['id'],at=time.time())
            result=studio.save(conf,payload.get('revision'),example if key=='correction-save' else None)
            handler.state.broadcast({'type':'studio','design':result})
            return handler.send_json({'ok':True,**result})
        elif key=='capture':
            return handler.send_json({'ok':True,'recording':studio.capture(payload.get('name',''),payload.get('since',0),payload.get('until',time.time()+1))})
        return handler.send_json({'ok':False,'error':'Onbekende studiofunctie'},404)
    except (ValueError,TypeError,KeyError,OverflowError) as exc:return handler.send_json({'ok':False,'error':str(exc)},400)
    except (OSError,sqlite3.Error):return handler.send_json({'ok':False,'error':'Opslaan of lezen mislukt; controleer schijfruimte en rechten'},503)


def vehicle_label(meta,fallback):
    return ' '.join(str(x).strip() for x in [meta.get('function_name') or meta.get('label') or fallback,meta.get('station_name') or meta.get('station') or ''] if x)


def run_examples(state,runtime):
    conf=state.studio.snapshot()['config'];tests=[]
    for case in conf['examples']:
        base=runtime.parse_raw_p2000_line(state,case['raw'],[]);base['title']=case['raw']
        actual=correct_message(state,base,runtime,conf['corrections'])
        tests.append(dict(raw=case['raw'],correction=case['correction'],passed=all(actual.get(k)==v for k,v in case['expected'].items()),expected=case['expected'],actual={k:actual.get(k) for k in case['expected']},parser_already_correct=all(base.get(k)==v for k,v in case['expected'].items())))
    return tests


def correct_message(state,message,runtime,corrections=None):
    corrections=state.studio.snapshot()['config']['corrections'] if corrections is None else corrections
    out=apply_corrections(message,corrections)
    if out.get('studio_correction'):
        out['units']=runtime.enforce_unit_discipline(out.get('service',''),out.get('priority',''),out.get('city',''),out.get('title') or out.get('raw',''),out.get('summary',''),out.get('units',[]))
        out['incident_key']=runtime.incident_key(out.get('service',''),out.get('city',''),out.get('location',''),out.get('title') or out.get('raw',''))
        rule=next(c for c in corrections if c['id']==out['studio_correction'])
        out['parser_notes']=(out.get('parser_notes') or [])+['Lokale correctie: '+out['studio_correction']]
        if 'units' in rule['changes']:out['parser_notes'].append('Lokale voertuigcorrectie')
        out.update(runtime.parser_text_diagnostics(out.get('title') or out.get('raw',''),out,state))
    return out


def process_feed(state,messages,runtime):
    corrected=[];originals=[];names={f.name for f in fields(runtime.Message)}
    conf=state.studio.snapshot()['config']['corrections']
    for message in messages:
        original=asdict(message);out=correct_message(state,original,runtime,conf)
        corrected.append(runtime.Message(**{k:v for k,v in out.items() if k in names}))
        original['corrected']={k:out.get(k) for k in names};originals.append(original)
    by_id={m.id:m for m in corrected}
    state.studio.record(originals,lambda row:runtime.config_allows_message(state.config,by_id[row['id']]),state.get_display_settings())
    return corrected
