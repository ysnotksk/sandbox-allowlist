#!/usr/bin/env python3
"""Fold only clean, unlocked, attached worktrees merged into a freshly fetched base.

One task owns one checkout; its creator folds it at merge/abandonment. Squash
merges are intentionally not detected. No forced deletion, pruning or remote
branch deletion. A common-Git-directory lock serializes cooperating sweeps.
"""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys


def git(root, *args, timeout=120):
    return subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)


def value(result):
    return os.fsdecode(result.stdout).strip()


def records(root):
    result = git(root, 'worktree', 'list', '--porcelain', '-z')
    if result.returncode:
        raise RuntimeError(os.fsdecode(result.stderr).strip())
    trees, tree = [], {}
    for field in result.stdout.split(b'\0'):
        if not field:
            if tree:
                trees.append(tree)
                tree = {}
            continue
        key, _, val = field.partition(b' ')
        tree[os.fsdecode(key)] = os.fsdecode(val)
    if tree:
        trees.append(tree)
    return trees


def keep(tree, reason):
    print(f"keep  {tree['worktree']} ({reason})", flush=True)


def reason(root, tree, main, base):
    path = tree['worktree']
    if path == main:
        return 'main worktree'
    if 'locked' in tree:
        return 'locked: ' + (tree['locked'] or 'yes')
    if 'detached' in tree or not tree.get('branch', '').startswith('refs/heads/'):
        return 'detached HEAD or no local branch; human review required'
    if 'prunable' in tree or not Path(path).is_dir():
        return 'missing/unavailable checkout; human review required'
    status = git(path, 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--ignore-submodules=none')
    if status.returncode:
        return 'cannot inspect worktree status'
    if status.stdout:
        return 'uncommitted or untracked changes'
    head = git(path, 'rev-parse', 'HEAD')
    branch = git(path, 'symbolic-ref', '-q', 'HEAD')
    if head.returncode or branch.returncode or value(head) != tree.get('HEAD') or value(branch) != tree['branch']:
        return 'HEAD or branch changed during sweep'
    tip = git(root, 'rev-parse', '--verify', tree['branch'])
    if tip.returncode or value(tip) != tree['HEAD']:
        return 'branch tip changed during sweep'
    if git(root, 'merge-base', '--is-ancestor', tree['HEAD'], base).returncode:
        return f"{tree['branch'][11:]} not merged into {base} (includes squash merges)"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='origin/main', help='remote-tracking base (default origin/main)')
    parser.add_argument('--dry-run', action='store_true', help='fetch and report without removing anything')
    args = parser.parse_args()
    root_result = git(Path(__file__).resolve().parent.parent, 'rev-parse', '--show-toplevel')
    if root_result.returncode:
        print('keep  repository (cannot locate checkout)', file=sys.stderr)
        return 1
    root = value(root_result)
    initial = records(root)
    primary = initial[0]['worktree']
    common_result = git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    if common_result.returncode:
        for tree in initial:
            keep(tree, 'cannot locate common Git directory')
        return 1
    lock_path = Path(value(common_result)) / 'worktree-sweep.lock'
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            for tree in initial:
                keep(tree, 'another sweep is running')
            return 0
        # Use the stable main checkout as cwd even when invoked from a linked tree.
        root = primary
        if not Path(root).is_dir():
            for tree in initial:
                keep(tree, 'main checkout unavailable')
            return 1
        os.chdir(root)
        base = args.base.removeprefix('refs/remotes/')
        remote, sep, remote_branch = base.partition('/')
        if not sep or not remote_branch or remote.startswith('-'):
            for tree in initial:
                keep(tree, 'base must be a remote-tracking branch')
            return 1
        try:
            fetched = git(root, 'fetch', '--no-tags', remote,
                          f'+refs/heads/{remote_branch}:refs/remotes/{base}')
        except subprocess.TimeoutExpired:
            fetched = None
        if fetched is None or fetched.returncode:
            for tree in records(root):
                keep(tree, f'fresh fetch of {base} failed; no folding')
            return 1
        base_result = git(root, 'rev-parse', '--verify', f'refs/remotes/{base}^{{commit}}')
        if base_result.returncode:
            for tree in records(root):
                keep(tree, 'fetched base is not a commit')
            return 1
        base_oid = value(base_result)
        failed = False
        for tree in records(root):
            why = reason(root, tree, primary, base_oid)
            if why:
                # Keep the configured base name readable in ancestry messages.
                keep(tree, why.replace(base_oid, base))
                continue
            if args.dry_run:
                keep(tree, f'dry run: eligible to fold; merged into freshly fetched {base}')
                continue
            fresh = next((t for t in records(root) if t['worktree'] == tree['worktree']), None)
            if fresh != tree:
                keep(tree, 'worktree registration changed during sweep')
                continue
            why = reason(root, fresh, primary, base_oid)
            if why:
                keep(tree, why.replace(base_oid, base))
                continue
            removed = git(root, 'worktree', 'remove', '--', tree['worktree'])
            if removed.returncode:
                keep(tree, 'git worktree remove refused; ' + os.fsdecode(removed.stderr).strip())
                failed = True
                continue
            branch = tree['branch'][11:]
            deleted = git(root, 'branch', '-d', '--', branch)
            suffix = 'local branch deleted; remote branches kept' if deleted.returncode == 0 else 'local branch kept: git branch -d refused; remote branches kept'
            print(f"fold  {tree['worktree']} ({branch}; {suffix})", flush=True)
            failed = failed or bool(deleted.returncode)
        return int(failed)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'keep  repository (sweep stopped: {error})', file=sys.stderr)
        sys.exit(1)
