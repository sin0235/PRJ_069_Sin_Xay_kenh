"""Chạy lô Auto Edit đã đóng băng; mặc định chỉ kiểm tra, --duyet mới gửi tác vụ."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid


def doc_goi(path):
    encoded=path.read_bytes()
    digest=hashlib.sha256(encoded).hexdigest()
    expected=path.with_suffix('.sha256').read_text(encoding='ascii').strip()
    if digest!=expected:
        raise ValueError('Bản chuẩn bị đã thay đổi sau khi đóng băng')
    bundle=json.loads(encoded)
    if bundle.get('state')!='AWAITING_APPROVAL' or len(bundle.get('plan',{}).get('clips',[]))!=8:
        raise ValueError('Chưa có đủ tám nội dung sẵn sàng duyệt')
    if not bundle.get('visual_briefs') or not bundle.get('words'):
        raise ValueError('Thiếu storyboard hoặc mốc phụ đề')
    return bundle,digest


def cho_canh_clip(clip_id, briefs, jobs, read_states, *, sleep=time.sleep):
    indices={i for i,brief in enumerate(briefs) if brief['target_clip_id']==clip_id}
    ids=[item['job_id'] for item in jobs if item['index'] in indices]
    if not ids or len(ids)!=len(indices):
        raise ValueError('Thiếu tác vụ cảnh của nội dung '+clip_id)
    deadline=time.monotonic()+24*3600
    while time.monotonic()<deadline:
        states=read_states(ids)
        if len(states)==len(ids) and all(s=='SUCCEEDED' for s in states):return
        if any(s in {'FAILED','CANCELLED','NEEDS_RECONCILIATION','BLOCKED_LOGIN','BLOCKED_SETUP',
                     'BLOCKED_QUOTA','BLOCKED_FLOW_LOGIN','BLOCKED_FLOW_QUOTA'} for s in states):
            raise RuntimeError('Một cảnh cần đối soát; giữ receipt, không tạo lại Flow bằng khóa mới')
        sleep(15)
    raise TimeoutError('Giữ nguyên receipt để tiếp tục kiểm tra, không gửi lại')


def clip_san_sang(clips, briefs, jobs, read_states, completed):
    for clip in clips:
        if any(video['clip_id']==clip['clip_id'] for video in completed):continue
        indices={i for i,brief in enumerate(briefs) if brief['target_clip_id']==clip['clip_id']}
        ids=[job['job_id'] for job in jobs if job['index'] in indices]
        if not ids or len(ids)!=len(indices):raise ValueError('Thiếu tác vụ cảnh')
        if all(s=='SUCCEEDED' for s in read_states(ids)):return clip
    return None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=Path(__file__).parent/'runtime/goi_duyet_8_video_20261104.json')
    parser.add_argument('--duyet',action='store_true',help='Chỉ dùng sau khi người dùng đã duyệt chạy cả lô')
    args=parser.parse_args(argv)
    bundle,digest=doc_goi(args.bundle)
    print(json.dumps({'clips':8,'visuals':len(bundle['visual_briefs']),
        'flow':sum(b['renderer']=='FLOW' for b in bundle['visual_briefs']),
        'approved':args.duyet,'bundle_sha256':digest}),flush=True)
    if not args.duyet:
        return

    import os
    import sys
    from dotenv import load_dotenv
    import httpx
    root=Path(__file__).resolve().parents[2]
    load_dotenv(Path(__file__).with_name('.env.dev'),override=True)
    sys.path[:0]=[str(root/'sin_content_api'),str(root)]
    if os.getenv('REMOTE_COMPUTE_MODE')!='github':
        raise ValueError('Phần nặng phải chạy trên GitHub Actions')
    from src.database import SessionLocal
    from src.models.entities import AIGenerationJob,MediaAsset
    from src.modules.media_queue.service import authorized_worker_tenant,enqueue_media_job
    from src.modules.flow_sessions.service import resolve_profile
    from src.modules.media_studio.security import MEDIA_ROOT_DIR,hash_file
    from src.modules.dieu_phoi_dung.dung_video_dai import TaoKeHoachDungVideo
    from baha_auth.src.database import SessionLocal as AuthSession
    from baha_auth.src.models.entities import GlobalUser
    from src.modules.auth.router import _create_jwt
    TaoKeHoachDungVideo.model_validate(bundle['plan'])
    workspace=os.environ['SIN_WORKSPACE_ID']
    with AuthSession() as db:
        uid=db.query(GlobalUser).filter(GlobalUser.email==os.environ['AUTH_OWNER_EMAIL']).one().id
    receipt=args.bundle.with_name('tien_trinh_lo_8_video_da_duyet.json')
    state=json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else {
        'bundle_sha256':digest,'approval_received':True,'jobs':[]}
    if state['bundle_sha256']!=digest:
        raise ValueError('Lượt đang chạy thuộc bản chuẩn bị khác')
    def save():
        staging=receipt.with_suffix('.json.part')
        staging.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');staging.replace(receipt)
    with authorized_worker_tenant(workspace,uid,action='ai_job.create'):
        with SessionLocal() as db:
            source=db.get(MediaAsset,bundle['source_asset_id'])
            if (not source or source.workspace_id!=workspace or source.project_id!=bundle['project_id']
                    or source.source_product!='UPLOAD' or source.parent_asset_id or source.sha256!=bundle['source_sha256']):
                raise ValueError('Nguồn gốc hoặc phạm vi dự án đã thay đổi')
            source_path=(MEDIA_ROOT_DIR/source.storage_key).resolve()
            if not source_path.is_relative_to(MEDIA_ROOT_DIR.resolve()) or hash_file(source_path)!=(source.sha256,source.byte_size):
                raise ValueError('Hash nguồn gốc không còn khớp')
            profile_id=bundle['flow_profile_id']
            if any(b['renderer']=='FLOW' for b in bundle['visual_briefs']):
                profile=resolve_profile(db,workspace,profile_id)
                if profile.google_flow_state!='READY':
                    raise ValueError('Hồ sơ Flow chưa sẵn sàng; chưa gửi cả lô')
            save()
            for index,brief in enumerate(bundle['visual_briefs']):
                if any(j['index']==index for j in state['jobs']):continue
                if brief['renderer']=='FLOW':
                    operation,backend,mode,model,credits='generate_video_scene','GOOGLE_FLOW','FLOW_BROWSER_PILOT','google-flow','GOOGLE_FLOW_PRO'
                    profile=profile_id;prompt=brief['prompt']
                    params={'aspect_ratio':'9:16','remove_watermark':True,'include_audio':False,'target_clip_id':brief['target_clip_id']}
                else:
                    operation,backend,mode,model,credits='render_auto_edit_diagram','BAHA_AUTO_EDIT','INTERNAL_RENDERER','hyperframes','BAHA_AUTO_EDIT'
                    profile=None;prompt=f"{brief['scene']}. {brief['action']}"
                    params={'target_clip_id':brief['target_clip_id'],'duration_seconds':brief['duration_seconds'],
                        'target_start_word_id':brief['start_word_id'],'target_end_word_id':brief['end_word_id'],
                        'narration':brief['narration'],'narration_word_times':brief['word_times'],
                        'transparent_background':brief['ui_scene']['layout']!='CHECKLIST','diagram_revision':4,
                        'ui_scene':brief['ui_scene'],'style_snapshot':brief['style_snapshot'],
                        'style_snapshot_hash':brief['style_snapshot_hash']}
                child=enqueue_media_job(db,workspace_id=workspace,user_id=uid,provider='MEDIA_VIDEO',
                    operation=operation,backend_provider=backend,provider_mode=mode,model_id=model,
                    prompt_text=prompt,parameters=params,idempotency_key=f'lo8-{digest[:24]}-{index}',
                    project_id=bundle['project_id'],profile_id=profile,credits_source=credits)
                state['jobs'].append({'index':index,'job_id':child.id,'renderer':brief['renderer']});save()
    def read_states(ids):
        with SessionLocal() as db:
            return [db.get(AIGenerationJob,ident).state for ident in ids]
    token=_create_jwt(uid,workspace)
    with httpx.Client(base_url='http://127.0.0.1:8001',headers={'Authorization':'Bearer '+token},timeout=90) as client:
        state.setdefault('parent_job_ids',{})
        state.setdefault('videos',[])
        origin=os.environ['REMOTE_PUBLIC_ORIGIN'].rstrip('/')
        # Xuất độc lập để giữ các MP4 đã xong khi một nội dung phía sau gặp lỗi.
        deadline_ready=time.monotonic()+24*3600
        while len(state['videos'])<8:
            clip=clip_san_sang(bundle['plan']['clips'],bundle['visual_briefs'],state['jobs'],read_states,state['videos'])
            if clip is None:
                if time.monotonic()>deadline_ready:raise TimeoutError('Chưa có nội dung đủ cảnh; giữ nguyên receipt')
                time.sleep(15)
                continue
            clip_id=clip['clip_id']
            if any(video['clip_id']==clip_id for video in state['videos']):continue
            cho_canh_clip(clip_id,bundle['visual_briefs'],state['jobs'],read_states)
            indices=[i for i,b in enumerate(bundle['visual_briefs']) if b['target_clip_id']==clip_id]
            manifest={key:bundle[key] for key in ('source_asset_id','source_sha256',
                'removed_pause_intervals','pause_candidates','waveform_peaks')}
            manifest.update(plan={'clips':[clip]},
                words=[w for w in bundle['words'] if clip['start_ms']<=w['start_ms'] and w['end_ms']<=clip['end_ms']],
                visual_briefs=[bundle['visual_briefs'][i] for i in indices],
                visual_generation=[next(j for j in state['jobs'] if j['index']==i) for i in indices])
            manifest_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'lo8-'+digest+'-'+clip_id))
            encoded=json.dumps(manifest,ensure_ascii=False,separators=(',',':')).encode('utf-8')
            with authorized_worker_tenant(workspace,uid,action='media.upload'):
                with SessionLocal() as db:
                    path=MEDIA_ROOT_DIR/'workspaces'/workspace/'media'/f'bien_ban_lo_8_{manifest_id}.json'
                    if path.exists():
                        if path.read_bytes()!=encoded:raise ValueError('Biên bản cùng ID nhưng khác nội dung')
                    else:path.write_bytes(encoded)
                    if db.get(MediaAsset,manifest_id) is None:
                        db.add(MediaAsset(id=manifest_id,workspace_id=workspace,project_id=bundle['project_id'],
                            parent_asset_id=bundle['source_asset_id'],storage_key=path.relative_to(MEDIA_ROOT_DIR).as_posix(),
                            sha256=hashlib.sha256(encoded).hexdigest(),byte_size=len(encoded),mime_detected='application/json',
                            source_product='AUTO_EDIT',original_filename=path.name,created_by=uid))
                        db.commit()
            if clip_id not in state['parent_job_ids']:
                response=client.post(f"/v1/media/projects/{bundle['project_id']}/dung/tu-dong-dung-video-dai",
                    json={'source_asset_id':bundle['source_asset_id'],'manifest_asset_id':manifest_id,
                          'idempotency_key':'lo8-final-'+digest[:24]+'-'+clip_id})
                response.raise_for_status();state['parent_job_ids'][clip_id]=response.json()['job_id'];save()
            deadline=time.monotonic()+24*3600
            while time.monotonic()<deadline:
                response=client.get('/v1/ai-jobs/'+state['parent_job_ids'][clip_id]);response.raise_for_status();job=response.json()
                if job['state']=='SUCCEEDED':break
                if job['state'] in {'FAILED','CANCELLED','NEEDS_RECONCILIATION'}:raise RuntimeError(str(job.get('error_code')))
                time.sleep(15)
            else:raise TimeoutError('Tác vụ còn chờ, tiếp tục bằng receipt hiện có')
            videos=[]
            for asset_id in job['output_asset_ids']:
                response=client.get('/v1/media/assets/'+asset_id);response.raise_for_status();asset=response.json()
                if asset['mime_detected']!='video/mp4':continue
                for byte_range in ('bytes=0-1023','bytes=-1024'):
                    part=client.get('/v1/media/assets/'+asset_id+'/download',headers={'Range':byte_range})
                    if part.status_code!=206:raise RuntimeError('Video chưa tải được bằng Range')
                videos.append({'clip_id':clip_id,'asset_id':asset_id,
                    'url':origin+'/auto-edit?project_id='+bundle['project_id']+'&asset_id='+asset_id})
            if len(videos)!=1:raise RuntimeError('Chưa có đúng một MP4 cho nội dung '+clip_id)
            state['videos'].extend(videos);save()
            print(json.dumps({'completed':clip_id,'url':videos[0]['url']},ensure_ascii=False),flush=True)
        if len(state['videos'])!=8:raise RuntimeError('Chưa đủ tám MP4 kết quả')
        state.update(state='SUCCEEDED');save()
        print(json.dumps({'videos':state['videos']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
