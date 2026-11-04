"""Thu nhỏ đầu vào video lớn bằng stream copy; giữ nguyên gói hình và đồng bộ mốc tiếng."""
import copy
import json
import shutil
import subprocess
from pathlib import Path

MIN_WINDOW_BYTES = 512 * 1024**2


def _goi_hinh(path, start):
    result = subprocess.run(['ffprobe', '-v', 'error', '-read_intervals', f'{start:.9f}%+0.05',
        '-select_streams', 'v:0', '-show_packets', '-show_data_hash', 'sha256',
        '-show_entries', 'packet=pts_time,data_hash,flags', '-of', 'json', str(path)],
        check=True, capture_output=True, text=True, timeout=60)
    return json.loads(result.stdout)['packets'][0]


def chuan_bi_cua_so(arguments, inputs, scratch):
    arguments, inputs = copy.deepcopy(arguments), list(inputs)
    timeline = arguments['timeline']
    timeline = timeline.get('value', timeline)
    paths = arguments['asset_paths']
    proof = []

    def nodes(value):
        if isinstance(value, dict):
            yield value
            for item in value.values():
                yield from nodes(item)
        elif isinstance(value, list):
            for item in value:
                yield from nodes(item)

    for index, source in enumerate(inputs):
        source = Path(source)
        if source.stat().st_size < MIN_WINDOW_BYTES or source.suffix.lower() not in {'.mp4', '.mov', '.mkv', '.m4v'}:
            continue
        ids = {asset for asset, path in paths.items() if path == {'remote_input': index}}
        references = []
        for node in nodes(timeline):
            duration = int(node.get('duration_ms') or 0)
            if duration <= 0:
                continue
            if node.get('asset_id') in ids:
                start = int(node.get('trim_in_ms') or 0)
                end = int(node.get('trim_out_ms') or 0)
                end = end if end > start else start + duration
                node['trim_in_ms'], node['trim_out_ms'] = start, end
                references += [(node, 'trim_in_ms', start, end), (node, 'trim_out_ms', start, end)]
            if node.get('audio_asset_id', node.get('asset_id')) in ids:
                start = int(node.get('audio_trim_in_ms', node.get('trim_in_ms', 0)))
                node['audio_trim_in_ms'] = start
                references.append((node, 'audio_trim_in_ms', start, start + duration))
        if not references:
            continue
        start, end = min(item[2] for item in references), max(item[3] for item in references)
        if start < 0 or end <= start:
            raise ValueError('SOURCE_WINDOW_RANGE_INVALID')
        packet = _goi_hinh(source, start / 1000)
        keyframe = float(packet['pts_time'])
        if 'K' not in packet['flags'] or keyframe > start / 1000 + 0.05:
            raise ValueError('SOURCE_WINDOW_KEYFRAME_INVALID')
        if shutil.disk_usage(scratch).free < 2 * 1024**3:
            raise RuntimeError('SOURCE_WINDOW_DISK_FULL')
        suffix = source.suffix.lower() if source.suffix.lower() in {'.mov', '.mkv'} else '.mp4'
        target = Path(scratch) / f'nguon_{index}{suffix}'
        # Stream copy không giải mã/tái mã hóa; chỉ chuyển các gói trong cửa sổ cần dựng.
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{keyframe:.9f}', '-i', str(source),
            '-t', f'{end / 1000 - keyframe + 0.25:.9f}', '-map', '0:v:0', '-map', '0:a:0?',
            '-c', 'copy', '-avoid_negative_ts', 'make_zero', str(target)],
            check=True, capture_output=True, timeout=300)
        copied = _goi_hinh(target, 0)
        if packet['data_hash'] != copied['data_hash']:
            raise ValueError('SOURCE_WINDOW_PACKET_MISMATCH')
        offset = round((keyframe - float(copied['pts_time'])) * 1000)
        for node, key, _, _ in references:
            node[key] -= offset
            if node[key] < 0:
                raise ValueError('SOURCE_WINDOW_NEGATIVE_TRIM')
        inputs[index] = target
        proof.append({'input_index': index, 'asset_ids': sorted(ids), 'start_ms': start, 'end_ms': end,
            'offset_ms': offset, 'original_bytes': source.stat().st_size,
            'window_bytes': target.stat().st_size, 'packet_hash_verified': True})
    return arguments, inputs, proof
