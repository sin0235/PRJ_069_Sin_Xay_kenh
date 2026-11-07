import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {mkdtemp, mkdir, readFile, writeFile, access, rm, unlink} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {boxesOverlap, eventFrame, eventProgress, progressAtFrame, secondsToFrame, valueAtProgress, wrapText} from '../engines/remotion/src/chuyen_dong.mjs';

function selfCheck() {
  assert.equal(boxesOverlap({x: 0, y: 0, width: 10, height: 10}, {x: 5, y: 5, width: 10, height: 10}), true);
  assert.equal(boxesOverlap({x: 0, y: 0, width: 10, height: 10}, {x: 10, y: 0, width: 10, height: 10}), false);
  assert.equal(boxesOverlap({x: 0, y: 0, width: 10, height: 10}, undefined), false);
  assert.equal(secondsToFrame(1.25, 30), 38);
  assert.equal(secondsToFrame(-0.2, 30), 0);
  assert.throws(() => secondsToFrame(Number.NaN, 30), /số hữu hạn/);
  assert.equal(progressAtFrame(20, 10, 10), 1);
  assert.equal(progressAtFrame(5, 10, 20), 0);
  assert.equal(eventFrame({c0: 0.5}, 'c0', 30), 15);
  assert.equal(eventFrame({c0: 10}, 'c0', 30, 30), 29);
  assert.equal(eventFrame({}, 'c0', 30), null);
  assert.equal(eventProgress(15, {c0: 0.5}, 'c0', 30, 30, 10), 0);
  assert.equal(valueAtProgress('36', 0.5), '18');
  assert.equal(valueAtProgress('36', 1), '36');
  assert.equal(valueAtProgress('5 phút', 0.5), '5 phút');
  assert.equal(valueAtProgress('92%', 0.5), '92%');
  assert.equal(valueAtProgress('1,200', 0.5), '1,200');
  assert.equal(valueAtProgress('3.5', 0.5), '1.8');
  assert.equal(valueAtProgress('-2,50', 0.5), '-1,25');
  assert.equal(valueAtProgress('+4.00', 0.25), '+1.00');
  assert.equal(valueAtProgress('3.5', 1), '3.5');
  assert.throws(() => valueAtProgress('36', Infinity), /hữu hạn/);
  assert.deepEqual(wrapText('ABCDEFGH', 3), ['ABC', 'DEF', 'GH']);
  assert.deepEqual(wrapText('a\u0301b\u0301', 1), ['a\u0301', 'b\u0301']);
  assert.throws(() => wrapText('test', 0), /số nguyên dương/);
}

const apiRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const remotionRoot = path.join(apiRoot, 'engines', 'remotion');
const evidenceRoot = path.join(apiRoot, '08_kiem_thu', 'bang_chung', 'nang_cap_hoat_hoa_20261104');
const assetPaths = [
  path.join(remotionRoot, 'public', 'phong_chu', 'be_vietnam_pro_dam.ttf'),
  path.join(remotionRoot, 'public', 'thuong_hieu', 'logo_ngang_mau.png'),
];
let temporaryBundle = null;
let temporaryBundleParent = null;

function parseArguments(args) {
  const result = {};
  for (let index = 0; index < args.length; index++) {
    const key = args[index];
    if (key === '--self-check') result.selfCheck = true;
    else if (key === '--spot-check') result.spotCheck = true;
    else if (['--props', '--ra', '--frames'].includes(key) && args[index + 1]) result[key.slice(2)] = args[++index];
    else throw new Error(`Tham số không hợp lệ: ${key}`);
  }
  return result;
}

function inside(parent, child) {
  const relative = path.relative(parent, child);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex');
}

function eventKeys(diagram) {
  if (diagram.kind === 'CHECKLIST') return [...diagram.steps.map((_, index) => `c${index}`), ...(diagram.stamp ? ['stamp'] : [])];
  if (diagram.kind === 'KPI_CARDS') return diagram.cards.map((_, index) => `k${index}`);
  return ['before', 'after', 'delta'];
}

function geometryErrors(qa) {
  const errors = [];
  if (!qa?.fontLoaded) errors.push(`FONT_NOT_LOADED frame=${qa?.frame}`);
  if (!qa?.logoLoaded || qa.logoFailed) errors.push(`LOGO_NOT_LOADED frame=${qa?.frame}`);
  for (const item of qa?.elements || []) {
    if (item.overflow) errors.push(`TEXT_OVERFLOW ${item.name} frame=${qa.frame}`);
    if (item.tooManyLines) errors.push(`TEXT_TOO_MANY_LINES ${item.name} frame=${qa.frame}`);
    if (item.outsideSafeZone) errors.push(`OUTSIDE_SAFE_ZONE ${item.name} frame=${qa.frame}`);
    if (item.fontTooSmall) errors.push(`FONT_TOO_SMALL ${item.name} frame=${qa.frame}`);
    if (item.fontSize !== undefined) {
      const minimum = item.name === 'title' || item.name.includes('value') ? 48 : 36;
      if (item.fontSize < minimum) errors.push(`FONT_TOO_SMALL ${item.name} ${item.fontSize}px frame=${qa.frame}`);
    }
  }
  return errors;
}

async function main() {
  selfCheck();
  const options = parseArguments(process.argv.slice(2));
  if (options.selfCheck) {
    process.stdout.write(`${JSON.stringify({status: 'passed', check: 'motion_helpers'})}\n`);
    return;
  }
  if (!options.props || !options.ra || !options.frames) throw new Error('Cần --props, --ra và --frames.');
  const propsPath = path.resolve(options.props);
  const outputDir = path.resolve(options.ra);
  if (!inside(apiRoot, propsPath)) throw new Error('PROPS_PATH_OUTSIDE_API');
  if (!inside(evidenceRoot, outputDir)) throw new Error('OUTPUT_PATH_OUTSIDE_EVIDENCE');
  const rawProps = await readFile(propsPath);
  const props = JSON.parse(rawProps.toString('utf8'));
  if (props.schemaVersion !== 1 || !props.diagram || !['CHECKLIST', 'KPI_CARDS', 'BEFORE_AFTER'].includes(props.diagram.kind)) throw new Error('PROPS_NATIVE_V1_INVALID');
  if (!Number.isInteger(props.durationInFrames) || props.durationInFrames < 1 || props.fps !== 30) throw new Error('PROPS_TIMING_INVALID');
  for (const file of assetPaths) await access(file);
  const requestedFrames = options.frames.split(',').map((value) => Number(value.trim()));
  if (!requestedFrames.length || requestedFrames.some((frame) => !Number.isInteger(frame) || frame < 0 || frame >= props.durationInFrames)) throw new Error('FRAMES_INVALID');
  const frames = new Set(options.spotCheck ? requestedFrames : [0, Math.floor(props.durationInFrames / 2), props.durationInFrames - 1, ...requestedFrames]);
  if (!options.spotCheck) {
    for (const key of eventKeys(props.diagram)) {
      const frame = eventFrame(props.diagram.t, key, props.fps, props.durationInFrames);
      if (frame !== null) for (const neighbor of [frame - 1, frame, frame + 1]) if (neighbor >= 0 && neighbor < props.durationInFrames) frames.add(neighbor);
    }
  }
  const orderedFrames = [...frames].sort((a, b) => a - b);
  const inputHash = sha256(rawProps);
  const files = [
    path.join(remotionRoot, 'src', 'Root.jsx'),
    path.join(remotionRoot, 'src', 'canh_truc_tiep.jsx'),
    path.join(remotionRoot, 'src', 'chuyen_dong.mjs'),
    ...assetPaths,
  ];
  const rendererRevision = sha256(await Promise.all(files.map((file) => readFile(file))).then((buffers) => Buffer.concat(buffers)));
  await mkdir(outputDir, {recursive: true});
  const bundleDir = await mkdtemp(path.join(outputDir, 'bundle_'));
  temporaryBundle = bundleDir;
  temporaryBundleParent = outputDir;
  const require = createRequire(path.join(remotionRoot, 'package.json'));
  const {bundle} = require('@remotion/bundler');
  const {openBrowser, renderStill, selectComposition} = require('@remotion/renderer');
  const serveUrl = await bundle({entryPoint: path.join(remotionRoot, 'src', 'index.js'), outDir: bundleDir, publicDir: path.join(remotionRoot, 'public'), enableCaching: false, rspack: false});
  const inputProps = {...props, __qa: true};
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  await access(chromePath);
  const browser = await openBrowser('chrome', {browserExecutable: chromePath, chromiumOptions: {headless: true}, logLevel: 'error'});
  const failures = [];
  const samples = new Map();
  let composition;
  const render = async (frame, pass) => {
    const logs = [];
    const {buffer, contentType} = await renderStill({composition, serveUrl, frame, inputProps, output: null, imageFormat: 'png', puppeteerInstance: browser, logLevel: 'error', onBrowserLog: (log) => logs.push(log.text)});
    if (contentType !== 'image/png' || !buffer) throw new Error(`FRAME_RENDER_FAILED:${frame}`);
    const markers = logs.filter((line) => line.includes('BAHA_QA:'));
    if (!markers.length) throw new Error(`FRAME_QA_NOT_CAPTURED:${frame}`);
    const qa = JSON.parse(markers.at(-1).slice(markers.at(-1).indexOf('BAHA_QA:') + 8));
    failures.push(...geometryErrors(qa));
    const hash = sha256(buffer);
    if (pass === 'forward') {
      samples.set(frame, hash);
      await writeFile(path.join(outputDir, `khung_${String(frame).padStart(5, '0')}.png`), buffer);
    } else if (samples.get(frame) !== hash) failures.push(`NONDETERMINISTIC_FRAME ${frame}`);
    return {frame, pass, sha256: hash, elements: qa.elements.length, fontLoaded: qa.fontLoaded, logoLoaded: qa.logoLoaded};
  };
  const rendered = [];
  try {
    composition = await selectComposition({serveUrl, id: 'CanhTrucTiep', inputProps, puppeteerInstance: browser, logLevel: 'error'});
    if (composition.width !== props.width || composition.height !== props.height || composition.fps !== props.fps || composition.durationInFrames !== props.durationInFrames) throw new Error('COMPOSITION_METADATA_MISMATCH');
    for (const frame of orderedFrames) rendered.push(await render(frame, 'forward'));
    if (!options.spotCheck) for (const frame of [...orderedFrames].reverse()) rendered.push(await render(frame, 'reverse'));
  } finally {
    await browser.close({silent: true});
  }
  const report = {status: failures.length ? 'failed' : 'passed', input_hash: inputHash, renderer_revision: rendererRevision, spot_check: Boolean(options.spotCheck), requested_frames: requestedFrames, checked_frames: orderedFrames, rendered, failures};
  await unlink(path.join(outputDir, 'kiem_thu_that_bai.json')).catch(() => {});
  await writeFile(path.join(outputDir, `kiem_thu_${inputHash.slice(0, 12)}.json`), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  if (temporaryBundle && path.dirname(temporaryBundle) === temporaryBundleParent && inside(outputDir, temporaryBundle)) {
    await rm(temporaryBundle, {recursive: true, force: true});
    temporaryBundle = null;
  }
  process.stdout.write(`${JSON.stringify(report)}\n`);
  if (failures.length) process.exitCode = 1;
}

main().catch((error) => {
  const report = {status: 'failed', error: error.message};
  (async () => {
    try {
      if (temporaryBundle && temporaryBundleParent && path.dirname(temporaryBundle) === temporaryBundleParent && inside(temporaryBundleParent, temporaryBundle)) await rm(temporaryBundle, {recursive: true, force: true});
      const options = parseArguments(process.argv.slice(2));
      const outputDir = options.ra && path.resolve(options.ra);
      if (outputDir && inside(evidenceRoot, outputDir)) {
        await mkdir(outputDir, {recursive: true});
        await writeFile(path.join(outputDir, 'kiem_thu_that_bai.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
      }
    } catch {}
  })().finally(() => {
  process.stderr.write(`${JSON.stringify({status: 'failed', error: error.message})}\n`);
  process.exitCode = 1;
  });
});
