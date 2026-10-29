#!/usr/bin/env python3
"""Release helper for the Synology NAS stack: sync committed code and render the NAS-only Compose files.

The NAS copy never reads the working tree. Files are taken from a git ref (default HEAD) and only when
the tracked tree is clean, so local experiments cannot leak into the NAS or GitHub by accident.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SMB_HOST = os.environ.get("PRJ069_NAS_HOST", "bahahomes.local")
SMB_SHARE = os.environ.get("PRJ069_NAS_SHARE", "09.ai_workspace")
SMB_ROOT = os.environ.get("PRJ069_NAS_ROOT", "01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec")
SMB_CRED = os.environ.get("PRJ069_NAS_CRED", str(Path.home() / ".smbcred_nas"))
HOST_ROOT = "/volume1/" + SMB_SHARE + "/" + SMB_ROOT
STACK_DIR = "ha_tang/nas_trien_khai_sach"
APPLY_DIR = STACK_DIR + "/nas_apply"
DEPLOYED_REF = STACK_DIR + "/.deployed_ref"
PROJECT = "prj069-xaykenh-nhap"

# Mirrors the paths .dockerignore lets into the build context (plus the stack folder itself).
SYNC_PREFIXES = (
    "sin_content_api/src/", "sin_content_api/scripts/", "sin_content_api/requirements.nas.",
    "baha_auth/__init__.py", "baha_auth/src/",
    "09_kiem_thu_quyen/PERMISSION_REGISTRY.json", "09_kiem_thu_quyen/ROLE_PERMISSION_MATRIX.csv",
    "cong_cu_tu_dong/flow_bridge/", "cong_cu_tu_dong/veo_watermark_remover/",
    "ha_tang/nas_runtime/", STACK_DIR + "/", "sin_creator_os/", ".dockerignore",
)
# compose.yaml is uploaded in its rendered NAS form instead; env and secrets live only on the NAS.
SYNC_SKIP = (STACK_DIR + "/compose.yaml", STACK_DIR + "/deploy.env", STACK_DIR + "/secrets/")

APPLY_COMPOSE = """name: prj069-apply
services:
  apply:
    image: docker:24.0-cli
    restart: "no"
    network_mode: host
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - {host_root}:{host_root}:ro
      - {host_root}/{apply_dir}:/out
    environment:
      DOCKER_BUILDKIT: "0"
      COMPOSE_DOCKER_CLI_BUILD: "0"
    entrypoint: ["sh", "-c"]
    command:
      - |
        exec > /out/result.txt 2>&1
        cd {host_root}/{stack_dir}
        L="label=com.docker.compose.project={project}"
        C="docker compose -p {project} --project-directory . -f compose.yaml"
        echo "== build"; $$C build api web gateway; echo "rc=$$?"
        echo "== stop"; timeout 60 $$C stop -t 10; echo "rc=$$?"
        echo "== remove by label"
        for id in $$(docker ps -aq --filter "$$L"); do docker rm -f $$id; done
        echo "== up"; $$C up -d; echo "rc=$$?"
        echo "== after"; docker ps -a --filter "$$L" --format '{{{{.Names}}}} {{{{.Image}}}} {{{{.Status}}}}'
        echo done
"""


def git(*args, check=True):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=check, capture_output=True, text=True).stdout


def render_nas_compose(text, tag):
    """Repo compose -> NAS compose: pin images to `tag` and drop `cpus` (the DSM kernel has no CFS)."""
    out = []
    for line in text.splitlines():
        if re.match(r"\s+cpus:", line):
            continue
        m = re.match(r"(\s+image:\s+)\$\{PRJ069_(BACKEND|WEB|GATEWAY)_IMAGE:-[^}]*\}\s*$", line)
        if m:
            line = f"{m.group(1)}prj069-nas-{m.group(2).lower()}:{tag}"
        out.append(line)
    return "\n".join(out) + "\n"


def render_apply_compose():
    return APPLY_COMPOSE.format(host_root=HOST_ROOT, apply_dir=APPLY_DIR, stack_dir=STACK_DIR, project=PROJECT)


def smb(script):
    return subprocess.run(["smbclient", "-A", SMB_CRED, f"//{SMB_HOST}/{SMB_SHARE}", "-c", script],
                          capture_output=True, text=True)


def read_deployed_ref():
    with tempfile.TemporaryDirectory() as tmp:
        r = smb(f"cd {SMB_ROOT}; get {DEPLOYED_REF} {tmp}/ref")
        p = Path(tmp) / "ref"
        return p.read_text().strip() if p.exists() else None


def changed_files(base, ref):
    """Return ({path: status}) between two refs, limited to the sync scope."""
    names = git("diff", "--name-status", "--no-renames", base, ref).splitlines()
    files = {}
    for row in names:
        status, path = row.split("\t", 1)
        if path.startswith(SYNC_PREFIXES) and not path.startswith(SYNC_SKIP):
            files[path] = status
    return files


def cmd_sync(args):
    if git("status", "--porcelain", "--untracked-files=no").strip():
        sys.exit("Tracked files have uncommitted changes; commit first. The NAS only receives committed code.")
    ref = git("rev-parse", args.ref).strip()
    base = args.base or read_deployed_ref()
    if not base:
        sys.exit(f"{DEPLOYED_REF} is missing on the NAS; pass --base <commit> for the commit the NAS already matches.")
    base = git("rev-parse", base).strip()
    files = changed_files(base, ref)
    compose = render_nas_compose(git("show", f"{ref}:{STACK_DIR}/compose.yaml"), args.tag)
    print(f"base {base[:9]} -> ref {ref[:9]}: {len(files)} file(s); images tagged {args.tag}")
    for path, status in sorted(files.items()):
        print(f"  {status} {path}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        cmds = [f"cd {SMB_ROOT}", "recurse OFF"]
        mkdirs = set()

        def stage(rel, data):
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            parts = Path(rel).parent.parts
            for i in range(1, len(parts) + 1):
                mkdirs.add("/".join(parts[:i]))
            # Files synced over SMB arrive mode 0000 unless the NAS copy is unlocked before overwrite.
            cmds.append(f'setmode "{rel}" -s -h -r')
            cmds.append(f'put "{dest}" "{rel}"')

        for path, status in sorted(files.items()):
            if status == "D":
                cmds.append(f'del "{path}"')
            else:
                stage(path, subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:{path}"],
                                           check=True, capture_output=True).stdout)
        stage(STACK_DIR + "/compose.yaml", compose.encode())
        stage(APPLY_DIR + "/compose.yaml", render_apply_compose().encode())
        (tmp / "ref").write_text(ref + "\n")
        cmds.append(f'put "{tmp / "ref"}" "{DEPLOYED_REF}"')
        script = "; ".join([cmds[0], cmds[1]] + [f'mkdir "{d}"' for d in sorted(mkdirs)] + cmds[2:])
        if args.dry_run:
            print("dry-run: nothing uploaded")
            return
        r = smb(script)
        bad = [l for l in (r.stdout + r.stderr).splitlines()
               if "NT_STATUS" in l and "OBJECT_NAME_COLLISION" not in l and "OBJECT_NAME_NOT_FOUND" not in l]
        if r.returncode or bad:
            sys.exit("Upload reported errors; .deployed_ref may be stale:\n" + "\n".join(bad[:10]))
    print(f"Uploaded. NAS is now at {ref[:9]}. Next: run the guide's build/apply step (HUONG_DAN_NAS.md).")


def cmd_render(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "compose.nas.yaml").write_text(render_nas_compose((HERE / "compose.yaml").read_text(), args.tag))
    (out / "apply.compose.yaml").write_text(render_apply_compose())
    print(f"Wrote {out}/compose.nas.yaml and {out}/apply.compose.yaml")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync", help="upload committed changes + rendered compose to the NAS")
    s.add_argument("--tag", required=True, help="image tag to pin on the NAS, e.g. 20261030a")
    s.add_argument("--ref", default="HEAD")
    s.add_argument("--base", help="commit the NAS already matches (default: read .deployed_ref from the NAS)")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_sync)
    r = sub.add_parser("render", help="write the NAS compose files locally without uploading")
    r.add_argument("--tag", required=True)
    r.add_argument("--out", default=str(HERE / "releases" / "render"))
    r.set_defaults(fn=cmd_render)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
