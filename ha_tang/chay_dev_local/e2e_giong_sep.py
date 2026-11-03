"""E2E giọng nguồn: ASR/render trên Actions, LLM thật lập kế hoạch local."""
import os,sys,json
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

work=Path(__file__).with_name('runtime')/'e2e_giong_sep'
work.mkdir(exist_ok=True)
source=work.parent/'nguon_sep_120s.mp4'
token=scope.set({'workspace':os.environ['SIN_WORKSPACE_ID'],'pipeline':'AUTO_EDIT'})
try:
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
  with SessionLocal() as db:client=LLMClient.from_db(db)
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
 visual_file=work/'visuals.json'
 if not visual_file.exists():
  with SessionLocal() as db:client=LLMClient.from_db(db)
  visuals=tao_y_tuong_dien_hoa_flow([clip],words,[],client,flow_available=False)
  visual_file.write_text(json.dumps(visuals,ensure_ascii=False),encoding='utf-8')
 visuals=json.loads(visual_file.read_text(encoding='utf-8'))
 assets={'speaker':source};actions=[]
 word_map={w['id']:w for w in words}
 for index,brief in enumerate(visuals):
  if not brief.get('ui_scene'):continue
  scene=UiScene.model_validate(brief['ui_scene'])
  ratio='9:16' if scene.layout in PORTRAIT_DIAGRAM_LAYOUTS else '16:9'
  path=work/f'visual_{index}.mov'
  if not path.exists():
   print('RENDER_VISUAL',index,flush=True)
   render_scene(scene,{**brief['style_snapshot'],'render_engine':'hyperframes'},brief['duration_seconds'],ratio,path,narration=brief['narration'],word_times=brief.get('word_times'),transparent_background=True)
  asset=f'visual_{index}';assets[asset]=path
  start=word_map[brief['target_start_word_id']]['start_ms']
  end=min(clip.end_ms,start+brief['duration_seconds']*1000)
  actions.append({'clip_id':clip.clip_id,'asset_id':asset,'start_ms':start,'end_ms':end,'mode':'OVERLAY','visual_kind':'diagram','aspect_ratio':ratio,'size':'medium','position':'upper_left'})
 timeline=_tao_timeline('speaker',clip,words,visual_actions=actions)
 (work/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False),encoding='utf-8')
 output=work/'video_giong_sep.mp4'
 print('RENDER_FINAL',flush=True)
 meta=video_processor.render_timeline_document(timeline,lambda asset:assets[asset],output,caption_style='vietsub_karaoke_v2')
 qc=verify_decode(output)
 print(json.dumps({'output':str(output),'metadata':meta,'qc':qc},ensure_ascii=False),flush=True)
finally:scope.reset(token)
