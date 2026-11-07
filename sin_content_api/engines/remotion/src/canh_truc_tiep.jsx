import React, {useEffect, useRef, useState} from 'react';
import {cancelRender, continueRender, delayRender, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {boxesOverlap, eventFrame, eventProgress, valueAtProgress, wrapText} from './chuyen_dong.mjs';

const FONT = staticFile('phong_chu/be_vietnam_pro_dam.ttf');
const LOGO = staticFile('thuong_hieu/logo_ngang_mau.png');
const COLORS = {background: '#0B0F17', surface: '#1C2A40', ink: '#F2EEE6', accent: '#D9B26A', muted: '#B9C4D4', line: '#344256'};
const SAFE = {portrait: {left: 60, right: 960, top: 150, bottom: 1600}, landscape: {left: 60, right: 1860, top: 60, bottom: 930}};

function Lines({text, x, y, width, size, color, weight = 600, anchor = 'start', qa, maxLines = 3, charRatio}) {
  const isNumeric = /^[\d\s.,+%/-]+$/.test(String(text || '').trim());
  const defaultRatio = weight >= 700 ? (isNumeric ? 0.70 : 0.58) : 0.56;
  const ratio = charRatio ?? defaultRatio;
  const maxChars = Math.max(1, Math.floor(width / (size * ratio)));
  const lines = wrapText(text, maxChars);
  return <text data-qa={qa} data-max-width={width} data-max-lines={maxLines} x={x} y={y} fill={color} fontFamily="BahaViet, sans-serif" fontSize={size} fontWeight={weight} textAnchor={anchor}>
    {lines.map((line, index) => <tspan key={`${index}-${line}`} x={x} dy={index ? size * 1.15 : 0}>{line}</tspan>)}
  </text>;
}

function useLocalAssets() {
  const [handle] = useState(() => delayRender('Nạp phông chữ tiếng Việt nội bộ'));
  const [ready, setReady] = useState(false);
  const finished = useRef(false);
  useEffect(() => {
    const finish = (error) => {
      if (finished.current) return;
      finished.current = true;
      clearTimeout(timeout);
      if (error) cancelRender(error);
      else { setReady(true); continueRender(handle); }
    };
    const timeout = setTimeout(() => finish(new Error('ASSET_LOAD_TIMEOUT: Phông chữ hoặc logo không tải kịp.')), 10000);
    const face = new FontFace('BahaViet', `url("${FONT}")`, {weight: '600'});
    const logo = new Image();
    document.fonts.add(face);
    logo.src = LOGO;
    Promise.all([face.load(), logo.decode(), document.fonts.ready])
      .then(([loaded]) => {
        if (loaded.status !== 'loaded' || !document.fonts.check('600 48px BahaViet') || !logo.naturalWidth) throw new Error('FONT_OR_LOGO_LOAD_FAILED');
        const svgLogo = document.querySelector('[data-qa="logo"]');
        if (svgLogo) svgLogo.dataset.loaded = 'true';
        finish();
      })
      .catch((error) => finish(new Error(`FONT_OR_LOGO_LOAD_FAILED: ${error?.message || 'Không tải được font hoặc logo nội bộ.'}`)));
    return () => {
      if (!finished.current) finish(new Error('ASSET_LOAD_CANCELLED: Cảnh bị hủy khi đang tải tài nguyên.'));
    };
  }, [handle]);
  return ready;
}

function CheckMark({frame, fps, event, duration}) {
  const progress = eventProgress(frame, event, 'start', fps, duration, 12);
  return <path d="M 8 25 L 20 37 L 43 10" fill="none" stroke={COLORS.accent} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" pathLength="1" strokeDasharray="1" strokeDashoffset={1 - progress} />;
}

function EventCard({children, x, y, width, height, frame, fps, at, duration, radius = 26, qa}) {
  const progress = spring({frame: Math.max(0, frame - (eventFrame(at, 'start', fps, duration) ?? 0)), fps, config: {damping: 21, stiffness: 155}});
  const start = eventFrame(at, 'start', fps, duration) ?? 0;
  return <Sequence layout="none" from={start} durationInFrames={Math.max(1, duration - start)}>
    <g data-qa={qa} transform={`translate(${x} ${y})`}>
      <g transform={`translate(0 ${interpolate(progress, [0, 1], [26, 0])})`} opacity={progress}>
        <CardSurface width={width} height={height} radius={radius} />{children}
      </g>
    </g>
  </Sequence>;
}

function CardSurface({width, height, radius = 26}) {
  return <><rect width={width} height={height} rx={radius} fill={COLORS.surface} stroke={COLORS.line} strokeWidth="2" />
    <path d={`M ${radius} 2 H ${Math.max(radius, width - radius)} Q ${width - 2} 2 ${width - 2} ${radius}`} fill="none" stroke={COLORS.accent} strokeOpacity=".7" strokeWidth="3" /></>;
}

function Header({diagram, width, landscape, simulated}) {
  const x = 100;
  const y = landscape ? 124 : 255;
  const titleWidth = width - 360;
  const simY = landscape ? 250 : 390;
  return <g>
    <image data-qa="logo" href={LOGO} onLoad={(event) => { event.currentTarget.dataset.loaded = 'true'; }} onError={(event) => { event.currentTarget.dataset.failed = 'true'; }} x={landscape ? width - 250 : 780} y={landscape ? 70 : 170} width="170" height="54" preserveAspectRatio="xMaxYMid meet" />
    <Lines qa="title" text={diagram.title} x={x} y={y} width={titleWidth} size={48} color={COLORS.ink} weight={700} maxLines={3} />
    {simulated && <g data-qa="simulated" transform={`translate(${x} ${simY})`}>
      <rect width="386" height="58" rx="29" fill="#2C2518" stroke={COLORS.accent} strokeWidth="2" />
      <text data-qa="simulated-label" data-max-width="350" data-max-lines="1" x="193" y="40" fill="#F6E2B0" fontFamily="BahaViet, sans-serif" fontSize="36" fontWeight="600" textAnchor="middle">Dữ liệu mô phỏng</text>
    </g>}
  </g>;
}

function Checklist({diagram, frame, fps, duration, landscape}) {
  const steps = diagram.steps || [];
  const cols = landscape ? Math.min(steps.length, 3) : 2;
  const rows = Math.ceil(steps.length / cols);
  const cardW = landscape ? 550 : 410;
  const cardH = landscape ? 208 : 250;
  const gapX = 28;
  const gapY = 30;
  const totalW = cols * cardW + (cols - 1) * gapX;
  const startX = (landscape ? 960 : 510) - totalW / 2;
  const startY = landscape ? 320 : 500;
  return <g>
    {steps.map((step, index) => {
      const key = `c${index}`;
      const at = {start: diagram.t?.[key] ?? 0};
      const x = startX + (index % cols) * (cardW + gapX);
      const y = startY + Math.floor(index / cols) * (cardH + gapY);
      return <EventCard key={key} qa={`item-${index}`} x={x} y={y} width={cardW} height={cardH} frame={frame} fps={fps} at={at} duration={duration}>
        <g transform="translate(34 69)"><CheckMark frame={frame} fps={fps} event={at} duration={duration} /></g>
        <Lines qa={`item-label-${index}`} text={step} x={102} y={landscape ? 112 : 94} width={cardW - 134} size={36} color={COLORS.ink} weight={600} maxLines={3} />
      </EventCard>;
    })}
    {diagram.stamp && (() => {
      const start = eventFrame(diagram.t, 'stamp', fps, duration) ?? 0;
      return <Sequence layout="none" from={start}><g data-qa="stamp" transform={`translate(${landscape ? 680 : 230} ${startY + rows * (cardH + gapY) - 8}) rotate(-3)`}>
        <rect width="560" height="76" rx="10" fill="none" stroke={COLORS.accent} strokeWidth="4" />
        <text data-qa="stamp-label" data-max-width="520" data-max-lines="1" x="280" y="52" textAnchor="middle" fill={COLORS.accent} fontFamily="BahaViet, sans-serif" fontSize="36" fontWeight="700">{diagram.stamp}</text>
      </g></Sequence>;
    })()}
  </g>;
}

function KpiCards({diagram, frame, fps, duration, landscape}) {
  const cards = diagram.cards || [];
  const cols = landscape ? Math.min(cards.length, 4) : 2;
  const rows = Math.ceil(cards.length / cols);
  const cardW = landscape ? 404 : 410;
  const cardH = 340;
  const gapX = landscape ? 30 : 28;
  const gapY = 30;
  const totalW = cols * cardW + (cols - 1) * gapX;
  const startX = (landscape ? 960 : 510) - totalW / 2;
  const startY = landscape ? 315 : 500;
  return <g>{cards.map((card, index) => {
    const key = `k${index}`;
    const start = eventFrame(diagram.t, key, fps, duration) ?? 0;
    const at = {start: diagram.t?.[key] ?? 0};
    const x = startX + index % cols * (cardW + gapX);
    const y = startY + Math.floor(index / cols) * (cardH + gapY);
    const reveal = eventProgress(frame, diagram.t, key, fps, duration, 18);
    return <EventCard key={key} qa={`card-${index}`} x={x} y={y} width={cardW} height={cardH} frame={frame} fps={fps} at={at} duration={duration}>
      <Lines qa={`card-title-${index}`} text={card.title} x={34} y={65} width={cardW - 68} size={36} color={COLORS.accent} weight={700} maxLines={2} />
      <Lines qa={`card-value-${index}`} text={valueAtProgress(card.value, reveal)} x={34} y={174} width={cardW - 68} size={52} color={COLORS.ink} weight={700} maxLines={2} />
      <Lines qa={`card-label-${index}`} text={card.label} x={34} y={260} width={cardW - 68} size={36} color={COLORS.muted} weight={500} maxLines={2} />
    </EventCard>;
  })}</g>;
}

function BeforeAfter({diagram, frame, fps, duration, landscape}) {
  const docs = diagram.docs || [];
  const gap = 30;
  const cardW = landscape ? 740 : 416;
  const cardH = landscape ? 478 : 450;
  const totalW = cardW * 2 + gap;
  const startX = (landscape ? 960 : 510) - totalW / 2;
  const y = landscape ? 314 : 500;
  return <g>
    {docs.map((doc, index) => {
      const key = index === 0 ? 'before' : 'after';
      const at = {start: diagram.t?.[key] ?? 0};
      const x = startX + index * (cardW + gap);
      const isAfter = index === 1;
      const stateColor = isAfter ? COLORS.accent : COLORS.muted;
      return <EventCard key={key} qa={`state-${key}`} x={x} y={y} width={cardW} height={cardH} frame={frame} fps={fps} at={at} duration={duration}>
        <text data-qa={`state-caption-${key}`} data-max-width={cardW - 68} data-max-lines="1" x={34} y="62" fill={stateColor} fontFamily="BahaViet, sans-serif" fontSize="36" fontWeight="700">{isAfter ? 'SAU THAY ĐỔI' : 'TRƯỚC THAY ĐỔI'}</text>
        <Lines qa={`state-title-${key}`} text={doc.title} x={34} y={126} width={cardW - 68} size={36} color={COLORS.muted} maxLines={2} />
        <Lines qa={`state-value-${key}`} text={doc.value} x={34} y={252} width={cardW - 68} size={56} color={COLORS.ink} weight={700} maxLines={2} />
        <Lines qa={`state-label-${key}`} text={doc.label} x={34} y={landscape ? 332 : 390} width={cardW - 68} size={36} color={COLORS.muted} maxLines={2} />
        {isAfter && <rect x="0" y="0" width={cardW} height="6" rx="3" fill={COLORS.accent} />}
      </EventCard>;
    })}
    {diagram.diff_label && (() => {
      const start = eventFrame(diagram.t, 'delta', fps, duration) ?? 0;
      const badgeW = Math.min(760, Math.max(380, diagram.diff_label.length * 24));
      return <Sequence layout="none" from={start}><g data-qa="delta" transform={`translate(${(landscape ? 960 : 510) - badgeW / 2} ${landscape ? 834 : 1015})`}>
        <rect width={badgeW} height="78" rx="39" fill="#2C2518" stroke={COLORS.accent} strokeWidth="2" />
        <Lines qa="delta-label" text={diagram.diff_label} x={badgeW / 2} y={52} width={badgeW - 42} size={36} color="#F6E2B0" anchor="middle" maxLines={2} />
      </g></Sequence>;
    })()}
  </g>;
}

export function CanhTrucTiep(props) {
  const assetsReady = useLocalAssets();
  const frame = useCurrentFrame();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const stageRef = useRef(null);
  const {diagram, theme = COLORS} = props;
  const landscape = width > height;
  const safe = landscape ? SAFE.landscape : SAFE.portrait;
  const camera = diagram?.camera_motion || 'AUTO';
  const intensity = camera === 'STATIC' ? 0 : camera === 'WHIP_PAN_SETTLE' ? 1.35 : 1;
  const progress = interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const zoom = 1 + 0.018 * intensity * progress;
  const drift = (camera === 'CRANE_PUSH' || camera === 'CRANE_DIVE') ? interpolate(progress, [0, 1], [18, 0]) : interpolate(progress, [0, 1], [0, -9 * intensity]);
  const centerX = width / 2;
  const centerY = height / 2;
  const layout = diagram?.kind;
  const body = layout === 'CHECKLIST'
    ? <Checklist diagram={diagram} frame={frame} fps={fps} duration={durationInFrames} landscape={landscape} />
    : layout === 'KPI_CARDS'
      ? <KpiCards diagram={diagram} frame={frame} fps={fps} duration={durationInFrames} landscape={landscape} />
      : <BeforeAfter diagram={diagram} frame={frame} fps={fps} duration={durationInFrames} landscape={landscape} />;
  useEffect(() => {
    if (!assetsReady || !stageRef.current) return;
    const stage = stageRef.current.getBoundingClientRect();
    const bounds = landscape ? SAFE.landscape : SAFE.portrait;
    const elements = [...stageRef.current.querySelectorAll('[data-qa]')].filter((node) => node.dataset.qa !== 'stage' && node.dataset.qa !== 'safe-zone' && node.dataset.qa !== 'safe-boundary');
    const errors = [];
    const items = elements.map((node) => {
      const rect = node.getBoundingClientRect();
      const box = {name: node.dataset.qa, x: rect.left - stage.left, y: rect.top - stage.top, width: rect.width, height: rect.height};
      const maxWidth = Number(node.dataset.maxWidth);
      const maxLines = Number(node.dataset.maxLines);
      if (node.tagName.toLowerCase() === 'text') {
        box.lineCount = node.querySelectorAll('tspan').length || 1;
        box.fontSize = parseFloat(getComputedStyle(node).fontSize);
        if (maxWidth && node.getBBox().width > maxWidth + 2) box.overflow = true;
        if (Number.isInteger(maxLines) && box.lineCount > maxLines) box.tooManyLines = true;
        if (box.fontSize < (node.dataset.qa === 'title' || node.dataset.qa.endsWith('-value') ? 48 : 36)) box.fontTooSmall = true;
      }
      if (box.x < bounds.left - 1 || box.x + box.width > bounds.right + 1 || box.y < bounds.top - 1 || box.y + box.height > bounds.bottom + 1) box.outsideSafeZone = true;
      if (box.overflow) errors.push(`TEXT_OVERFLOW:${box.name}`);
      if (box.tooManyLines) errors.push(`TEXT_TOO_MANY_LINES:${box.name}`);
      if (box.fontTooSmall) errors.push(`TEXT_FONT_TOO_SMALL:${box.name}`);
      if (box.outsideSafeZone) errors.push(`OUTSIDE_SAFE_ZONE:${box.name}`);
      return box;
    });
    const titleBox = items.find((box) => box.name === 'title');
    for (const name of ['simulated', 'logo']) {
      if (boxesOverlap(titleBox, items.find((box) => box.name === name))) errors.push(`HEADER_OVERLAP:${name}`);
    }
    const logo = stageRef.current.querySelector('[data-qa="logo"]');
    const faceLoaded = [...document.fonts].some((face) => face.family.replace(/["']/g, '') === 'BahaViet' && face.status === 'loaded');
    const result = {frame, width, height, fontLoaded: faceLoaded && document.fonts.check('600 48px BahaViet'), logoLoaded: logo?.dataset.loaded === 'true', logoFailed: logo?.dataset.failed === 'true', elements: items};
    if (!result.fontLoaded || !result.logoLoaded || result.logoFailed) errors.push('LOCAL_ASSET_NOT_LOADED');
    if (errors.length) cancelRender(new Error(`SCENE_GEOMETRY_INVALID:${errors.join(',')}`));
    if (props.__qa) {
      window.__BAHA_QA__ = result;
      console.log(`BAHA_QA:${JSON.stringify(result)}`);
    }
  }, [assetsReady, frame, width, height, landscape, props.__qa]);
  return <svg ref={stageRef} data-qa="stage" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={diagram?.title || 'Cảnh thông tin'} style={{display: 'block', background: theme.background || COLORS.background}}>
    <defs>
      <radialGradient id="nền-cảnh" cx="76%" cy="18%" r="82%"><stop offset="0" stopColor="#182A44"/><stop offset="1" stopColor={theme.background || COLORS.background}/></radialGradient>
      <linearGradient id="viền-thẻ" x1="0" x2="1" y1="0" y2="1"><stop stopColor={theme.accent || COLORS.accent} stopOpacity=".9"/><stop offset="1" stopColor={theme.accent || COLORS.accent} stopOpacity=".14"/></linearGradient>
    </defs>
    <rect width={width} height={height} fill="url(#nền-cảnh)" />
    <g data-qa="safe-zone" transform={`translate(${centerX + drift} ${centerY}) scale(${zoom}) translate(${-centerX} ${-centerY})`}>
      <Header diagram={diagram} width={width} landscape={landscape} simulated={diagram?.simulated !== false} />
      {body}
    </g>
    <rect data-qa="safe-boundary" x={safe.left} y={safe.top} width={safe.right - safe.left} height={safe.bottom - safe.top} fill="none" stroke="transparent" />
  </svg>;
}
