"""E2E giọng nguồn: ASR/render trên Actions, LLM thật lập kế hoạch local."""
import os,sys,json
from contextlib import ExitStack
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[2]
load_dotenv(Path(__file__).with_name('.env.dev'),override=True)
sys.path[:0]=[str(ROOT/'sin_content_api'),str(ROOT)]
from src.modules.tac_vu_tu_xa.client import scope
from src.modules.tac_vu_tu_xa.stages import extract_audio,verify_decode
from src.modules.tao_video_noi_dung.vietsub import transcribe_words
from src.modules.dieu_phoi_dung.dung_video_dai import tao_ke_hoach_dung_video,_tao_timeline
from src.modules.media_studio.video_processor import video_processor
from src.modules.llm.client import LLMClient
from src.database import SessionLocal

def llm_client():
 with SessionLocal() as db: client=LLMClient.from_db(db)
 # Phiên E2E này dùng 9Router local cùng khóa đã cấu hình; tunnel cũ đang HTTP 530.
 client.base_url='http://127.0.0.1:20128/v1'
 return client

work=Path(__file__).with_name('runtime')/'e2e_giong_sep'
work.mkdir(exist_ok=True)
source=work.parent/'nguon_sep_120s.mp4'
token=scope.set({'workspace':os.environ['SIN_WORKSPACE_ID'],'pipeline':'AUTO_EDIT'})
contexts=ExitStack()
try:
 from src.modules.flow_sessions.models import FlowProfile
 from src.modules.flow_sessions.context import profile_context
 with SessionLocal() as db:
  profiles=db.query(FlowProfile).filter(FlowProfile.workspace_id==os.environ['SIN_WORKSPACE_ID']).all()
  if len(profiles)!=1:raise RuntimeError('FLOW_PROFILE_SELECTION_REQUIRED')
  profile=profiles[0]
  contexts.enter_context(profile_context(profile.workspace_id,profile.id))
 audio=work/'nguon.wav'
 if not audio.exists():
  print('EXTRACT_AUDIO',flush=True);extract_audio(source,audio)
 words_file=work/'words.json'
 if not words_file.exists():
  print('TRANSCRIBE',flush=True)
  words=transcribe_words(audio)
  words_file.write_text(json.dumps(words,ensure_ascii=False),encoding='utf-8')
 words=json.loads(words_file.read_text(encoding='utf-8'))
 words=[{**w,'id':f'w{i:06d}'} for i,w in enumerate(words)]
 plan_file=work/'plan.json'
 if not plan_file.exists():
  print('LLM_PLAN',flush=True)
  client=llm_client()
  plan=tao_ke_hoach_dung_video(words,client,120000)
  plan_file.write_text(plan.model_dump_json(indent=2),encoding='utf-8')
 from src.modules.dieu_phoi_dung.dung_video_dai import TaoKeHoachDungVideo
 plan=TaoKeHoachDungVideo.model_validate_json(plan_file.read_text(encoding='utf-8'))
 candidates=[c for c in plan.clips if 45000<=c.end_ms-c.start_ms<=90000]
 if not candidates:raise RuntimeError('NO_COMPLETE_ONE_MINUTE_CONTENT: Không cắt ép mạch lời nói.')
 clip=min(candidates,key=lambda c:abs(c.end_ms-c.start_ms-60000))
 from src.modules.dieu_phoi_dung.dung_video_dai import tao_y_tuong_dien_hoa_flow
 from src.modules.tao_video_noi_dung.planner import UiScene,PORTRAIT_DIAGRAM_LAYOUTS
 from src.modules.tao_video_noi_dung.render_engines import render_scene
 visual_file=work/'visuals_v3.json'
 if not visual_file.exists():
  client=llm_client()
  visuals=[]
  # Lập cảnh theo từng nhịp nội dung để tránh một cảnh đơn lẻ cho cả phút.
  for part in range(4):
   start=clip.start_ms+(clip.end_ms-clip.start_ms)*part//4
   end=clip.start_ms+(clip.end_ms-clip.start_ms)*(part+1)//4
   selected=[w for w in words if start<=w['start_ms'] and w['end_ms']<=end]
   if not selected:continue
   section=clip.model_copy(update={'clip_id':f'{clip.clip_id}_beat{part}','start_ms':selected[0]['start_ms'],'end_ms':selected[-1]['end_ms']})
   planned=tao_y_tuong_dien_hoa_flow([section],selected,[],client,flow_available=True)
   for item in planned:
    item['clip_id']=clip.clip_id
    item['target_clip_id']=clip.clip_id
   visuals.extend(planned)
  visual_file.write_text(json.dumps(visuals,ensure_ascii=False),encoding='utf-8')
 visuals=json.loads(visual_file.read_text(encoding='utf-8'))
 assets={'speaker':source};actions=[];visual_candidates=[]
 word_map={w['id']:w for w in words}
 for index,brief in sorted(enumerate(visuals),key=lambda item:item[1].get('renderer')=='FLOW'):
  if brief.get('renderer')=='FLOW':
   from src.modules.media_studio.video_provider import GoogleFlowZeroCostProvider
   result_file=work/f'flow_v3_{index}.json'
   if result_file.exists():
    result=json.loads(result_file.read_text(encoding='utf-8'))
    if not Path(result['storage_path']).is_file():raise RuntimeError('FLOW_CACHED_ASSET_MISSING')
   else:
    print('GENERATE_FLOW',index,flush=True)
    result=GoogleFlowZeroCostProvider().generate(brief['prompt'],aspect_ratio='9:16',include_audio=False,remove_watermark=True,workspace_id=os.environ['SIN_WORKSPACE_ID'])
    result_file.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
   if not result.get('watermark_removed'):
    print('REMOVE_FLOW_WATERMARK',index,flush=True)
    clean_path=work/f'flow_v3_{index}_sach.mp4'
    native_path=Path(result['storage_path'])
    raw_path=native_path.with_name(native_path.name.replace('flow_native_9_16_','flow_source_9_16_'))
    if not raw_path.is_file():raise RuntimeError('FLOW_ORIGINAL_ASSET_MISSING')
    clean=video_processor.remove_veo_watermark(raw_path,clean_path,use_cpu=True,denoise_method='off')
    if clean.get('status')!='SUCCEEDED' or not clean.get('watermark_removed'):raise RuntimeError('WATERMARK_REMOVAL_FAILED')
    result={**result,'storage_path':str(clean_path),'watermark_removed':True,'sha256':clean['sha256'],'byte_size':clean['byte_size']}
    result_file.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
   asset=f'flow_{index}';assets[asset]=Path(result['storage_path'])
   visual_candidates.append({**brief,'asset_id':asset,'has_alpha':False,'aspect_ratio':'9:16','visual_kind':'flow_scene'})
   start=word_map[brief['target_start_word_id']]['start_ms']
   end=min(clip.end_ms,start+6000,word_map[brief['target_end_word_id']]['end_ms'])
   if end-start<3000:raise RuntimeError('FLOW_VISUAL_SPAN_INVALID')
   actions.append({'clip_id':clip.clip_id,'asset_id':asset,'start_ms':start,'end_ms':end,'mode':'CUTAWAY','visual_kind':'flow_scene','aspect_ratio':'9:16'})
   continue
  if not brief.get('ui_scene'):continue
  scene=UiScene.model_validate(brief['ui_scene'])
  ratio='9:16' if scene.layout in PORTRAIT_DIAGRAM_LAYOUTS else '16:9'
  path=work/f'visual_v3_{index}.mov'
  if not path.exists():
   print('RENDER_VISUAL',index,flush=True)
   render_scene(scene,{**brief['style_snapshot'],'render_engine':'hyperframes'},brief['duration_seconds'],ratio,path,narration=brief['narration'],word_times=brief.get('word_times'),transparent_background=True)
  asset=f'visual_{index}';assets[asset]=path
  visual_candidates.append({**brief,'asset_id':asset,'has_alpha':True,'aspect_ratio':ratio,'visual_kind':'diagram'})
  start=word_map[brief['target_start_word_id']]['start_ms']
  end=min(clip.end_ms,start+brief['duration_seconds']*1000)
  actions.append({'clip_id':clip.clip_id,'asset_id':asset,'start_ms':start,'end_ms':end,'mode':'OVERLAY','visual_kind':'diagram','aspect_ratio':ratio,'layout_size':'large','layout_position':'upper_left'})
 from src.modules.dieu_phoi_dung.dung_video_dai import chon_dien_hoa
 edit_file=work/'edit_v3.json'
 if edit_file.exists():
  actions=json.loads(edit_file.read_text(encoding='utf-8'))
 else:
  print('LLM_EDIT_LAYOUT',flush=True)
  actions=chon_dien_hoa([clip],words,visual_candidates,llm_client())
  edit_file.write_text(json.dumps(actions,ensure_ascii=False),encoding='utf-8')
 if len(actions)<3:raise RuntimeError('VISUAL_COVERAGE_REQUIRES_REVIEW: Không xuất bản nghiệm thu khi kế hoạch còn quá ít diễn họa.')
 timeline=_tao_timeline('speaker',clip,words,visual_actions=actions)
 # Bỏ nhãn tiêu đề hình hộp cũ; mở đầu được dựng bằng diễn họa riêng.
 timeline['captions']=[cap for cap in timeline['captions'] if cap.get('words')]
 timeline['karaoke_settings']={'font_size':70,'layout':'two_line','accent_color':'champagne','outline':True,'shadow':True,'word_pop':True}
 (work/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False),encoding='utf-8')
 if not any(a['visual_kind']=='flow_scene' for a in actions):raise RuntimeError('FLOW_VISUAL_REQUIRED_FOR_E2E')
 output=work/'video_giong_sep_v3.mp4'
 print('RENDER_FINAL',flush=True)
 meta=video_processor.render_timeline_document(timeline,lambda asset:assets[asset],output,caption_style='vietsub_karaoke_v2')
 qc=verify_decode(output)
 print(json.dumps({'output':str(output),'metadata':meta,'qc':qc},ensure_ascii=False),flush=True)
finally:
 contexts.close()
 scope.reset(token)
