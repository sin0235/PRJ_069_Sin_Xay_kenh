"""Thao tác media cố định; không nhận lệnh shell hoặc mã thực thi từ task spec."""
from pathlib import Path
import shutil
from .client import offload


@offload('decode', 'QC')
def verify_decode(path: Path):
    from src.media_process import run_media_command
    result = run_media_command(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'],
                               capture_output=True, text=True, timeout=3600)
    return {'decode_ok': result.returncode == 0}


@offload('extract_frame', 'EXTRACT_AUDIO', output='output_path')
def extract_frame(source_path: Path, output_path: Path):
    from src.media_process import run_media_command
    result = run_media_command(['ffmpeg', '-y', '-sseof', '-0.15', '-i', str(source_path), '-frames:v', '1', str(output_path)],
                               capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('VIDEO_REFERENCE_FRAME_FAILED')
    return {'byte_size': output_path.stat().st_size}


@offload('extract_audio', 'EXTRACT_AUDIO', output='output_path')
def extract_audio(source_path: Path, output_path: Path, start_ms: int = 0, duration_ms: int | None = None):
    from src.media_process import run_media_command
    command = ['ffmpeg', '-y']
    if start_ms:
        command += ['-ss', str(start_ms / 1000)]
    if duration_ms is not None:
        command += ['-t', str(duration_ms / 1000)]
    command += ['-i', str(source_path), '-vn', '-ac', '1', '-ar', '16000', str(output_path)]
    result = run_media_command(command, capture_output=True, text=True, timeout=3600)
    if result.returncode or not output_path.is_file():
        raise RuntimeError('VIDEO_AUDIO_EXTRACTION_FAILED')
    return {'byte_size': output_path.stat().st_size}


@offload('normalize_flow', 'PREPARE_FLOW_ASSET', output='output_path')
def normalize_flow(source_path: Path, output_path: Path, width: int, height: int, include_audio: bool = True):
    from src.media_process import run_media_command
    if (width, height) not in {(1080, 1920), (1920, 1080)}:
        raise ValueError('FLOW_ASPECT_RATIO_UNSUPPORTED')
    audio_options = ['-c:a', 'aac', '-b:a', '192k'] if include_audio else ['-an']
    result = run_media_command(['ffmpeg', '-y', '-i', str(source_path), '-vf',
        f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=0.1',
        '-t', '10', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', *audio_options, str(output_path)],
        capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('FLOW_VIDEO_NORMALIZATION_FAILED')
    return {'byte_size': output_path.stat().st_size}


def decode_arguments(value, inputs):
    if isinstance(value, dict):
        if set(value) == {'remote_input'}:
            index = value['remote_input']
            if not isinstance(index, int) or not 0 <= index < len(inputs):
                raise ValueError('REMOTE_INPUT_INVALID')
            return inputs[index]
        if set(value) == {'remote_model', 'value'}:
            from src.modules.tao_video_noi_dung.planner import UiScene, Storyboard
            from src.schemas.contracts import TimelineDocument
            models = {'UiScene': UiScene, 'Storyboard': Storyboard, 'TimelineDocument': TimelineDocument}
            if value['remote_model'] not in models:
                raise ValueError('REMOTE_MODEL_UNSUPPORTED')
            return models[value['remote_model']].model_validate(value['value'])
        return {key: decode_arguments(item, inputs) for key, item in value.items()}
    if isinstance(value, list):
        return [decode_arguments(item, inputs) for item in value]
    return value


def execute_stage(spec, inputs, output):
    from src.modules.media_studio.video_processor import video_processor
    from src.modules.media_studio.audio_processor import audio_processor
    from src.modules.tao_video_noi_dung.render_engines import render_scene
    from src.modules.tao_video_noi_dung.runner import _render_with_hyperframes, _add_brand_end_card, _probe_shot_with_qc
    from src.modules.dieu_phoi_dung.dung_video_dai import _kiem_tra_khung_den
    from src.modules.tao_video_noi_dung.vietsub import transcribe_words, transcribe_vietnamese
    registry = {
        'measure_loudness': ('QC', audio_processor.measure_loudness, None),
        'audio_qc': ('QC', audio_processor.verify_audio_qc, None),
        'normalize_audio': ('RENDER_FINAL', audio_processor.normalize_loudness, 'output_path'),
        'duck_audio': ('RENDER_FINAL', audio_processor.apply_auto_ducking, 'output_path'),
        'trim_audio': ('RENDER_FINAL', audio_processor.trim_and_fade, 'output_path'),
        'decode': ('QC', verify_decode, None),
        'extract_frame': ('EXTRACT_AUDIO', extract_frame, 'output_path'),
        'extract_audio': ('EXTRACT_AUDIO', extract_audio, 'output_path'),
        'normalize_flow': ('PREPARE_FLOW_ASSET', normalize_flow, 'output_path'),
        'transcribe_words': ('TRANSCRIBE', transcribe_words, None),
        'transcribe_cues': ('TRANSCRIBE', transcribe_vietnamese, None),
        'render_scene': ('RENDER_VISUAL', render_scene, 'out_path'),
        'render_timeline': ('RENDER_FINAL', video_processor.render_timeline_document, 'output_path'),
        'render_project': ('RENDER_FINAL', _render_with_hyperframes, 'output_path'),
        'brand_end': ('RENDER_FINAL', _add_brand_end_card, 'video_path'),
        'probe_qc': ('QC', _probe_shot_with_qc, None),
        'black_frames': ('QC', _kiem_tra_khung_den, None),
        'remove_watermark': ('PREPARE_FLOW_ASSET', video_processor.remove_veo_watermark, 'output_video_path'),
        'expand_canvas': ('PREPARE_FLOW_ASSET', video_processor.expand_16_9_to_9_16, 'output_video_path'),
    }
    operation = spec['parameters']['operation']
    arguments = decode_arguments(spec['parameters']['arguments'], inputs)
    if operation == 'tts' and spec['stage'] == 'TTS':
        from src.modules.tao_video_noi_dung.tts_provider import tts_provider_manager
        import soundfile as sf
        audio, rate = tts_provider_manager.synthesize(**arguments)
        sf.write(output, audio, rate, subtype='FLOAT', format='WAV')
        return {'sample_rate': rate}
    if operation not in registry or registry[operation][0] != spec['stage']:
        raise ValueError('REMOTE_OPERATION_UNSUPPORTED')
    _, function, output_name = registry[operation]
    if operation == 'render_timeline':
        paths = arguments.pop('asset_paths')
        arguments['asset_path_resolver'] = lambda asset_id: paths[asset_id]
    if operation == 'brand_end':
        shutil.copyfile(arguments['video_path'], output)
    if output_name:
        arguments[output_name] = output
    return function(**arguments)
