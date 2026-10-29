# NAS production runtime

Approved spec: conversation 2026-10-28. Implement production Docker with authenticated owner, direct creation/export (not publishing), browser login/profile switching from web, durable media queue, bounded TTS/video processes, and migration preserving NAS data.

## Constraints
- Production, TESTING=0, DEV_AUTH_BYPASS=0; never fake provider/media fallback.
- API 512 MiB + worker 3584 MiB = 4 GiB backend. Web 512 MiB separately. One heavy media task; VieNeu CPU first, Gwen explicitly unavailable until separately certified.
- Same pinned image artifacts on development host and NAS; no source mounts, reload, host browser or runtime pip installs.
- Preserve DB/media/profile/encryption keys; backup and restore before migration. No E2E seed or destructive cleanup.
- Flow owner opens authenticated remote desktop on NAS, supplies credentials/OTP manually. One lock per profile, no deleting live browser locks. Pause/resume on quota/login; reconcile uncertain sends before resubmission.
- Keep actual profile/project per attempt. Cross-account continuation uses new Flow project only for unsent shots and preserves completed assets.

## Tasks
1. Owner password auth and idempotent bootstrap, limited direct creation/export policy, same-origin FE auth.
2. Production images/Compose, model provisioning, backup/preflight/verification tools and release documentation.
3. Flow profile/session lifecycle API, remote desktop and web controls.
4. API/worker separation, durable enqueue for all media paths, fencing/recovery, bounded child-process TTS/FFmpeg, per-shot checkpoints and correct provider errors.
5. Integration tests, actual production-mode Docker boot/auth/TTS/render, resource/restart evidence, then actual NAS/real Flow acceptance when access/accounts permit.

## Acceptance
Build clean context; no sensitive files in image. Auth/tenant negative tests, no extra owner approval, real VieNeu audio with ffprobe and listening review, real Flow multi-shot video. Profile lock/login/quota/timeout/restart cases must not duplicate submissions. Recreate retains volumes. Measure one-hour workload, OOM/restart counts and responsiveness. Record NOT_VERIFIED for any live/NAS/provider condition not actually exercised. Do not call local unit evidence NAS acceptance.
