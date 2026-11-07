export function secondsToFrame(seconds, fps = 30) {
  if (!Number.isFinite(seconds) || !Number.isFinite(fps) || fps <= 0) throw new TypeError('Thời gian và fps phải là số hữu hạn dương.');
  return Math.max(0, Math.floor(seconds * fps + 0.5));
}

export function progressAtFrame(frame, start, end) {
  if (![frame, start, end].every(Number.isFinite)) throw new TypeError('Mốc khung hình phải là số hữu hạn.');
  if (end <= start) return frame >= end ? 1 : 0;
  return Math.min(1, Math.max(0, (frame - start) / (end - start)));
}

export function eventFrame(events, key, fps = 30, durationInFrames = Infinity) {
  const seconds = events?.[key];
  if (!Number.isFinite(seconds)) return null;
  const lastFrame = Number.isFinite(durationInFrames) ? Math.max(0, durationInFrames - 1) : Infinity;
  return Math.min(lastFrame, secondsToFrame(seconds, fps));
}

export function eventProgress(frame, events, key, fps, durationInFrames, revealFrames = 10) {
  const start = eventFrame(events, key, fps, durationInFrames);
  if (start === null) return 0;
  return progressAtFrame(frame, start, start + Math.max(1, revealFrames));
}

export function valueAtProgress(value, progress) {
  const text = String(value ?? '');
  if (!Number.isFinite(progress)) throw new TypeError('Tiến độ phải là số hữu hạn.');
  const match = text.match(/^[+-]?\d+(?:([.,])(\d+))?$/);
  if (!match || progress >= 1) return text;
  // shortcut: ba chữ số có thể là nhóm nghìn; mở rộng khi schema tách số và định dạng.
  if (match[2]?.length === 3) return text;
  const number = Number(text.replace(',', '.'));
  if (!Number.isFinite(number)) return text;
  const decimals = (text.split(/[.,]/)[1] || '').length;
  const current = number * Math.min(1, Math.max(0, progress));
  return `${text[0] === '+' ? '+' : ''}${current.toFixed(decimals).replace('.', match[1] || '.')}`;
}

export function boxesOverlap(a, b) {
  return Boolean(a && b && a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y);
}

export function wrapText(value, maxChars) {
  if (!Number.isInteger(maxChars) || maxChars < 1) throw new TypeError('Độ dài dòng phải là số nguyên dương.');
  const words = String(value ?? '').trim().split(/\s+/).filter(Boolean);
  const segmenter = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter('vi', {granularity: 'grapheme'}) : null;
  const lines = [];
  let line = '';
  for (const word of words) {
    const graphemes = segmenter ? [...segmenter.segment(word)].map(({segment}) => segment) : Array.from(word);
    const parts = [];
    let part = '';
    for (const grapheme of graphemes) {
      if (part && [...part].length + [...grapheme].length > maxChars) { parts.push(part); part = ''; }
      part += grapheme;
    }
    if (part) parts.push(part);
    for (let index = 0; index < parts.length; index++) {
      const candidate = `${line}${index === 0 && line ? ' ' : ''}${parts[index]}`;
      if (line && [...candidate].length > maxChars) { lines.push(line); line = parts[index]; }
      else line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
}

