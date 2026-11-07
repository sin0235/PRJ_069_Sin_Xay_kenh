import React from 'react';
import {Composition} from 'remotion';
import {Scene} from './Scene';
import {CanhTrucTiep} from './canh_truc_tiep';

const theme = {background: '#0B0F17', surface: '#1C2A40', ink: '#F2EEE6', accent: '#D9B26A'};
const defaultNativeProps = {
  schemaVersion: 1,
  diagram: {
    kind: 'CHECKLIST', title: 'Kiểm tra trước khi triển khai', simulated: true, camera_motion: 'PARALLAX_PASS',
    steps: ['Xác thực dữ liệu đầu vào', 'Kiểm tra quyền truy cập', 'Ghi lại kết quả kiểm thử'],
    stamp: 'SẴN SÀNG', t: {c0: 0.5, c1: 2, c2: 3.5, stamp: 5},
  },
  fps: 30, durationInFrames: 240, width: 1080, height: 1920, theme,
  assets: {font: 'phong_chu/be_vietnam_pro_dam.ttf', logo: 'thuong_hieu/logo_ngang_mau.png'},
};

function calculateNativeMetadata({props}) {
  const {schemaVersion, diagram, fps, durationInFrames, width, height, theme: colors, assets} = props;
  if (schemaVersion !== 1 || fps !== 30 || !Number.isInteger(durationInFrames) || durationInFrames < 1) throw new Error('PROPS_V1_INVALID');
  if (!((width === 1080 && height === 1920) || (width === 1920 && height === 1080))) throw new Error('PROPS_SIZE_UNSUPPORTED');
  if (!diagram || typeof diagram !== 'object' || !['CHECKLIST', 'KPI_CARDS', 'BEFORE_AFTER'].includes(diagram.kind) || typeof diagram.title !== 'string' || !diagram.title.trim() || diagram.title.length > 60 || typeof diagram.simulated !== 'boolean' || !diagram.t || typeof diagram.t !== 'object' || Array.isArray(diagram.t)) throw new Error('PROPS_DIAGRAM_INVALID');
  if (Object.values(diagram.t).some((value) => !Number.isFinite(value))) throw new Error('PROPS_TIMING_INVALID');
  if (!['AUTO', 'DOLLY_ORBIT', 'TRACK_RACK', 'CRANE_PUSH', 'ARC_REVEAL', 'STATIC', 'ORBIT_ARC', 'CRANE_DIVE', 'PARALLAX_PASS', 'WHIP_PAN_SETTLE', 'DOLLY_RACK', 'DOLLY_ZOOM'].includes(diagram.camera_motion)) throw new Error('PROPS_CAMERA_INVALID');
  if (!colors || ['background', 'surface', 'ink', 'accent'].some((key) => !/^#[0-9A-Fa-f]{6}$/.test(colors[key] || ''))) throw new Error('PROPS_THEME_INVALID');
  if (assets?.font !== 'phong_chu/be_vietnam_pro_dam.ttf' || assets?.logo !== 'thuong_hieu/logo_ngang_mau.png') throw new Error('PROPS_ASSET_NOT_ALLOWLISTED');
  if (diagram.kind === 'CHECKLIST' && (!Array.isArray(diagram.steps) || diagram.steps.length < 3 || diagram.steps.length > 5 || diagram.steps.some((step) => typeof step !== 'string' || !step.trim() || step.length > 30) || diagram.steps.some((_, index) => !Number.isFinite(diagram.t[`c${index}`])) || (diagram.stamp && !Number.isFinite(diagram.t.stamp)))) throw new Error('PROPS_CHECKLIST_INVALID');
  if (diagram.kind === 'KPI_CARDS' && (!Array.isArray(diagram.cards) || diagram.cards.length < 2 || diagram.cards.length > 4 || diagram.cards.some((card, index) => !card || ['title', 'label', 'value'].some((key) => typeof card[key] !== 'string' || !card[key].trim()) || card.title.length > 28 || card.label.length > 28 || card.value.length > 14 || !Number.isFinite(diagram.t[`k${index}`])))) throw new Error('PROPS_KPI_INVALID');
  if (diagram.kind === 'BEFORE_AFTER' && (!Array.isArray(diagram.docs) || diagram.docs.length !== 2 || diagram.docs.some((doc) => !doc || ['title', 'label', 'value'].some((key) => typeof doc[key] !== 'string' || !doc[key].trim())) || !diagram.diff_label || !['before', 'after', 'delta'].every((key) => Number.isFinite(diagram.t[key])))) throw new Error('PROPS_BEFORE_AFTER_INVALID');
  return {fps, durationInFrames, width, height};
}

// Độ dài clip lấy từ props (durationInFrames) nên một bản bundle dùng cho mọi cảnh.
export const Root = () => (
  <>
  <Composition
    id="Scene"
    component={Scene}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={30}
    defaultProps={{html: '', durationInFrames: 30, width: 1920, height: 1080}}
    calculateMetadata={({props}) => ({durationInFrames: props.durationInFrames, width: props.width, height: props.height})}
  />
  <Composition
    id="CanhTrucTiep"
    component={CanhTrucTiep}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={240}
    defaultProps={defaultNativeProps}
    calculateMetadata={calculateNativeMetadata}
  />
  </>
);
