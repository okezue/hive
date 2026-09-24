import asyncio, json, os, re, shlex, shutil, signal, subprocess, sys, time, tomllib
from contextlib import suppress
from pathlib import Path

from .err import Bad, Err, Missing
from .prompt import brief

PRE = 'Edit|Write|MultiEdit|NotebookEdit|apply_patch|search_replace|edit_file|write_file|replace'
CL = (('SessionStart', '', 'start'), ('UserPromptSubmit', '', 'prompt'), ('PreToolUse', PRE, 'pre'), ('PostToolUse', '', 'post'),
      ('Stop', '', 'stop'), ('SessionEnd', '', 'end'))
GE = (('SessionStart', '', 'start'), ('BeforeAgent', '', 'prompt'), ('BeforeTool', 'write_file|replace', 'pre'), ('AfterTool', '', 'post'),
      ('AfterAgent', '', 'stop'), ('SessionEnd', '', 'end'))
H = {
    'claude': {'bin': 'claude', 'run': ['claude', '-p', '{prompt}', '--permission-mode', 'bypassPermissions'], 'chat': ['claude', '{prompt}'],
               'model': '--model', 'mcp': ('json', '.mcp.json', '~/.claude.json'), 'hooks': ('.claude/settings.json', '~/.claude/settings.json', CL)},
    'codex': {'bin': 'codex', 'run': ['codex', 'exec', '--dangerously-bypass-approvals-and-sandbox', '--skip-git-repo-check', '-C', '{root}', '{prompt}'],
              'chat': ['codex', '-C', '{root}', '{prompt}'], 'model': '-m', 'mcp': ('toml', '.codex/config.toml', '~/.codex/config.toml'),
              'hooks': ('.codex/hooks.json', '~/.codex/hooks.json', CL[:5])},
    'grok': {'bin': 'grok', 'run': ['grok', '--prompt-file', '{promptFile}', '--cwd', '{root}', '--permission-mode', 'bypassPermissions', '--no-auto-update'],
             'chat': ['grok', '--cwd', '{root}', '{prompt}'], 'model': '-m', 'mcp': ('toml', '.grok/config.toml', '~/.grok/config.toml'),
             'hooks': ('.grok/hooks/hive.json', '~/.grok/hooks/hive.json', CL)},
    'gemini': {'bin': 'gemini', 'run': ['gemini', '-p', '{prompt}', '--yolo', '--skip-trust'], 'chat': ['gemini', '-i', '{prompt}'], 'model': '-m',
               'mcp': ('json', '.gemini/settings.json', '~/.gemini/settings.json'), 'hooks': ('.gemini/settings.json', '~/.gemini/settings.json', GE)},
    'cursor': {'bin': 'cursor-agent', 'run': ['cursor-agent', '-p', '{prompt}', '--force', '--approve-mcps'], 'chat': ['cursor-agent', '{prompt}'],
               'model': '--model', 'mcp': ('json', '.cursor/mcp.json', '~/.cursor/mcp.json')},
    'opencode': {'bin': 'opencode', 'run': ['opencode', 'run', '{prompt}'], 'chat': ['opencode', '--prompt', '{prompt}'], 'model': '-m',
                 'mcp': ('opencode', 'opencode.json', '~/.config/opencode/opencode.json')},
}
ORDER = tuple(H)
LIST = {'cursor': ['cursor-agent', 'mcp', 'list']}
OURS = re.compile(r'''(?:^|[\s/'"])hive['"]?\s+hook\s+(?:pre|post|prompt|stop|start|end)\b|\s-m\s+hive\s+hook\s+(?:pre|post|prompt|stop|start|end)\b''')
TBL = re.compile(r'^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(?:#.*)?$')
ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')


def profile(n, cfg=None, run=False):
    p = dict(H.get(n, {})) | {k: v for k, v in ((cfg.harness if cfg else {}) or {}).get(n, {}).items()}
    if not p.get('run') and not p.get('chat'):
        raise Missing(f'unknown harness {n!r}', f"known: {', '.join(ORDER)}; define others under [harness.{n}] in .hive/config.toml")
    if run and not p.get('run'): raise Bad(f'harness {n} has no headless command', f'add run = [...] under [harness.{n}] in .hive/config.toml')
    p.setdefault('bin', (p.get('run') or p['chat'])[0])
    return p


def found(cfg=None): return [n for n in (*ORDER, *((cfg.harness if cfg else {}) or {})) if shutil.which(profile(n, cfg)['bin'])]


def exe():
    here = Path(sys.executable).parent
    for w in (sys.argv[0], shutil.which('hive')):
        if w and os.path.basename(w) == 'hive' and Path(w).resolve().parent in (here, here.resolve()): return [os.path.abspath(w)]
    return [sys.executable, '-m', 'hive']


def server(scope, root): return exe() + ['mcp'] + (['--dir', str(root)] if scope == 'project' else [])


def extra(): return {'HIVE_HOME': str(Path(h).expanduser().resolve())} if (h := os.environ.get('HIVE_HOME')) and Path(h).expanduser().resolve() != Path('~/.hive').expanduser().resolve() else {}


def hookCmd(ev, fmt='claude'):
    e, hm = [f'{k}={v}' for k, v in extra().items()], extra().get('HIVE_HOME') or str(Path('~/.hive').expanduser())
    run = shlex.join((['env', *e] if e else []) + exe() + ['hook', ev] + (['--format', fmt] if fmt != 'claude' else []))
    return f'[ -n "${{HIVE_AGENT:-}}${{HIVE_AGENT_TOKEN:-}}" ] || [ -e {shlex.quote(str(Path(hm).expanduser()/"bound"))} ] || exit 0; exec {run}'


def where(f, root): return Path(f).expanduser() if f.startswith('~') else Path(root)/f


def tv(v):
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, int | float): return str(v)
    if isinstance(v, list): return '[' + ', '.join(map(tv, v)) + ']'
    if isinstance(v, dict): return '{ ' + ', '.join(f"{k if re.fullmatch(r'[A-Za-z0-9_-]+', k) else json.dumps(k)} = {tv(x)}" for k, x in v.items()) + ' }'
    return json.dumps(str(v), ensure_ascii=False)


def tkey(t): return tuple(a if a or b else c.strip() for a, b, c in re.findall(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'|([^.]+)', t)) if t else ()


def tomlPut(text, table, kv=None):
    out, pend, skip, want = [], [], False, tuple(table.split('.'))
    for ln in text.splitlines(keepends=True):
        if m := TBL.match(ln):
            k = tkey(m[1])
            now_ = k[:len(want)] == want
            if skip and not now_:
                i = len(pend)
                while i and (not pend[i-1].strip() or pend[i-1].lstrip().startswith('#')): i -= 1
                out += pend[i:]
            skip, pend = now_, []
        (pend if skip else out).append(ln)
    if skip:
        i = len(pend)
        while i and (not pend[i-1].strip() or pend[i-1].lstrip().startswith('#')): i -= 1
        out += pend[i:]
    s = ''.join(out).rstrip('\n')
    add = f'[{table}]\n' + ''.join(f'{k} = {tv(v)}\n' for k, v in kv.items()) if kv else ''
    return (s + '\n\n' + add if s and add else s + '\n' if s else add)


def readJ(p):
    if not p.exists() or not p.read_text().strip(): return {}
    try: d = json.loads(p.read_text())
    except ValueError as e: raise Err(f'{p} is not plain JSON ({e})', 'fix it or add the entry by hand; Hive will not overwrite it') from None
    if not isinstance(d, dict): raise Err(f'{p} does not hold a JSON object')
    return d


def readT(p):
    try: return tomllib.loads(p.read_text()) if p.exists() else {}
    except tomllib.TOMLDecodeError as e: raise Err(f'{p} is not valid TOML ({e})', 'fix it first; Hive will not overwrite it') from None


_backed = set()


def save(p, text, backup=False, dry=False):
    p = p.resolve() if p.is_symlink() else p
    old = p.read_text() if p.exists() else None
    if old == text: return None
    if dry: return 'would write'
    p.parent.mkdir(parents=True, exist_ok=True)
    if backup and old is not None and p not in _backed:
        shutil.copy2(p, p.with_name(f"{p.name}.bak-{time.strftime('%Y%m%d%H%M%S')}-{os.getpid()}"))
        _backed.add(p)
    tmp = p.with_name(f'.{p.name}.hive-{os.getpid()}')
    tmp.write_text(text)
    with suppress(OSError): os.chmod(tmp, p.stat().st_mode & 0o7777 if old is not None else 0o644)
    os.replace(tmp, p)
    return 'updated' if old is not None else 'created'


def entry(n, scope, root):
    cmd, e = server(scope, root), extra()
    if H[n]['mcp'][0] == 'opencode': return {'type': 'local', 'command': cmd, 'enabled': True} | ({'environment': e} if e else {})
    return {'command': cmd[0], 'args': cmd[1:]} | ({'env': e} if e else {}) | ({'timeout': 1000000} if n == 'gemini' else {})


def mcpFile(n, scope, root): return where(H[n]['mcp'][1 if scope == 'project' else 2], root)


def mcpKey(n): return 'mcp' if H[n]['mcp'][0] == 'opencode' else 'mcpServers'


def putMcp(n, scope, root, on=True, dry=False):
    p, kind, out = mcpFile(n, scope, root), H[n]['mcp'][0], []
    if kind == 'toml':
        cmd = server(scope, root)
        kv = {'command': cmd[0], 'args': cmd[1:], 'startup_timeout_sec': 60} | ({'tool_timeout_sec': 1000} if n == 'codex' else {}) | \
            ({'env': e} if (e := extra()) else {})
        was = readT(p)
        text = tomlPut(p.read_text() if p.exists() else '', 'mcp_servers.hive', kv if on else None)
        try: now_ = tomllib.loads(text)
        except tomllib.TOMLDecodeError: now_ = None
        strip = lambda d: {k: ({x: y for x, y in v.items() if x != 'hive'} if k == 'mcp_servers' else v) for k, v in d.items()} if d is not None else None
        drop = lambda d: {k: v for k, v in d.items() if k != 'mcp_servers' or v} if d is not None else None
        if now_ is None or (now_.get('mcp_servers', {}).get('hive') != kv if on else 'hive' in now_.get('mcp_servers', {})) or drop(strip(now_)) != drop(strip(was)):
            raise Err(f'could not update {p} safely', 'edit the [mcp_servers.hive] table by hand')
    else:
        d, k = readJ(p), mcpKey(n)
        if d.get(k) is None: d.pop(k, None)
        elif not isinstance(d[k], dict): raise Err(f'{k} in {p} is not a JSON object', 'fix it first; Hive will not overwrite it')
        if on: d.setdefault(k, {})['hive'] = entry(n, scope, root)
        elif 'hive' in d.get(k, {}): del d[k]['hive']
        text = json.dumps(d, indent=2, ensure_ascii=False) + '\n'
    if r := save(p, text, scope == 'user', dry): out.append((p, r))
    if n == 'claude' and scope == 'project':
        s = where('.claude/settings.local.json', root)
        d = readJ(s)
        ok = [x for x in d.get('enabledMcpjsonServers', []) if x != 'hive'] + (['hive'] if on else [])
        if ok or 'enabledMcpjsonServers' in d: d['enabledMcpjsonServers'] = ok
        if r := save(s, json.dumps(d, indent=2) + '\n', False, dry): out.append((s, r))
    return out


def putHooks(n, scope, root, on=True, dry=False):
    if 'hooks' not in H[n]: return []
    proj, user, evs = H[n]['hooks']
    p, fmt = where(proj if scope == 'project' else user, root), 'gemini' if evs is GE else 'claude'
    d = readJ(p)
    hs = d.get('hooks') if isinstance(d.get('hooks'), dict) else {}
    for ev in list(hs):
        gs = [g | {'hooks': [x for x in g.get('hooks', []) if not OURS.search(str(x.get('command', '')))]} for g in hs[ev] if isinstance(g, dict)]
        hs[ev] = [g for g in gs if g['hooks']]
        if not hs[ev]: del hs[ev]
    for ev, m, k in evs if on else ():
        t = (60 if k == 'stop' else 30) * (1000 if fmt == 'gemini' else 1)
        hs.setdefault(ev, []).append(({'matcher': m} if m else {}) | {'hooks': [{'type': 'command', 'command': hookCmd(k, fmt), 'timeout': t}]})
    if hs: d['hooks'] = hs
    else: d.pop('hooks', None)
    if not d and n == 'grok':
        if not p.exists(): return []
        if not dry: p.unlink()
        return [(p, 'would remove' if dry else 'removed')]
    return [(p, r)] if (r := save(p, json.dumps(d, indent=2, ensure_ascii=False) + '\n', scope == 'user' and n != 'grok', dry)) else []


def install(n, scope='user', root='.', hooks=True, dry=False):
    if n not in H: raise Missing(f'unknown harness {n!r}', f"known: {', '.join(ORDER)}")
    if scope not in ('user', 'project'): raise Bad('scope is user or project')
    return putMcp(n, scope, root, True, dry) + (putHooks(n, scope, root, True, dry) if hooks else [])


def uninstall(n, scope='user', root='.', dry=False):
    if n not in H: raise Missing(f'unknown harness {n!r}', f"known: {', '.join(ORDER)}")
    return putMcp(n, scope, root, False, dry) + putHooks(n, scope, root, False, dry)


def norm(v):
    if not isinstance(v, dict) or v.get('enabled') is False or v.get('disabled') is True: return None
    if u := v.get('url') or v.get('httpUrl') or v.get('serverUrl'):
        return {'url': u} | ({'headers': dict(x)} if (x := v.get('headers') or v.get('http_headers')) else {})
    c, args, e = v.get('command'), list(v.get('args') or []), v.get('env') or v.get('environment') or {}
    if isinstance(c, list): c, args = (c[0] if c else None), c[1:] + args
    return {'command': c, 'args': args} | ({'env': dict(e)} if e else {}) | ({'cwd': v['cwd']} if v.get('cwd') else {}) if c else None


def servers(n, root, scope=None):
    out = {}
    for sc in ('user', 'project') if scope is None else (scope,):
        if not (p := mcpFile(n, sc, root)).exists(): continue
        d = readT(p) if H[n]['mcp'][0] == 'toml' else readJ(p)
        got = dict((d.get('mcp_servers') if H[n]['mcp'][0] == 'toml' else d.get(mcpKey(n))) or {})
        if n == 'claude' and sc == 'user': got |= d.get('projects', {}).get(str(Path(root).resolve()), {}).get('mcpServers') or {}
        out |= {k: x for k, v in got.items() if (x := norm(v))}
    return out


def installed(n, root):
    for sc in ('project', 'user'):
        if sc == 'project' and mcpFile(n, 'project', root).resolve() == mcpFile(n, 'user', root).resolve(): continue
        with suppress(Err, OSError):
            if 'hive' in servers(n, root, sc): return sc
    return ''


def hooked(n, root):
    if 'hooks' not in H[n]: return ''
    for sc in ('project', 'user'):
        if sc == 'project' and where(H[n]['hooks'][0], root).resolve() == where(H[n]['hooks'][1], root).resolve(): continue
        with suppress(Err, OSError):
            if OURS.search(json.dumps(readJ(where(H[n]['hooks'][0 if sc == 'project' else 1], root)).get('hooks', {}))): return sc
    return ''


async def shake(sp, root):
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters
    env = {k: v for k, v in os.environ.items() if not k.startswith('HIVE_')} | {k: str(v) for k, v in sp.get('env', {}).items()}
    async with Client(StdioServerParameters(command=sp['command'], args=sp.get('args', []), env=env, cwd=str(root))) as c:
        return [t.name for t in (await c.list_tools()).tools]


TRUST = {'grok': 'this folder is not trusted, so grok skips its project MCP servers and hooks: run /hooks-trust in grok here, or install for your user',
         'codex': 'this project is not trusted, so codex skips its .codex folder: trust it when codex asks, or install for your user',
         'gemini': 'gemini turns off every MCP server, even user ones, in folders it does not trust: trust this folder when gemini asks '
                   '(headless agents Hive starts pass --skip-trust for their session)'}


def trusted(n, root, scope='project'):
    r = Path(root).resolve()
    if n == 'gemini':
        with suppress(Exception):
            if readJ(Path('~/.gemini/settings.json').expanduser()).get('security', {}).get('folderTrust', {}).get('enabled') is False: return True
        with suppress(Exception):
            fs = readJ(Path(os.environ.get('GEMINI_CLI_TRUSTED_FOLDERS_PATH') or '~/.gemini/trustedFolders.json').expanduser())
            ok = {Path(k).resolve() if v == 'TRUST_FOLDER' else Path(k).resolve().parent: v for k, v in fs.items() if v in ('TRUST_FOLDER', 'TRUST_PARENT')}
            return any(r == k or k in r.parents for k in ok)
        return False
    if scope != 'project': return True
    if n == 'grok':
        if os.environ.get('GROK_FOLDER_TRUST', '').lower() in ('0', 'false', 'off', 'no'): return True
        with suppress(Exception):
            if readT(Path('~/.grok/config.toml').expanduser()).get('folder_trust', {}).get('enabled') is False: return True
        with suppress(Exception):
            fs = tomllib.loads(Path('~/.grok/trusted_folders.toml').expanduser().read_text()).get('folders', {})
            return any(v.get('trusted') and (r == Path(k) or Path(k) in r.parents) for k, v in fs.items())
        return False
    if n == 'codex':
        with suppress(Exception):
            ps = tomllib.loads(Path('~/.codex/config.toml').expanduser().read_text()).get('projects', {})
            return any(v.get('trust_level') == 'trusted' and (r == Path(k) or Path(k) in r.parents) for k, v in ps.items())
        return False
    return True


def doctor(n, root, native=True):
    out, sc = {'harness': n, 'bin': shutil.which(H[n]['bin']) or ''}, installed(n, root)
    out |= {'installed': sc or 'no', 'hooks': hooked(n, root) or ('no' if 'hooks' in H[n] else 'not supported')}
    if not sc: return out | {'ok': False, 'fix': f'hive install {n}'}
    sp = servers(n, root, sc)['hive']
    out['config'] = str(mcpFile(n, sc, root))
    try:
        ts = asyncio.run(asyncio.wait_for(shake(sp, root), 90))
        out['server'] = f'answers with {len(ts)} tools' if 'join' in ts and 'me' in ts else f'unexpected tools: {ts[:5]}'
    except BaseException as e:
        out['server'] = f'failed: {type(e).__name__}: {e}'[:300]
    ok = out['server'].startswith('answers')
    if n in TRUST and not trusted(n, root, sc):
        out['trust'], ok = TRUST[n], False
    if n == 'claude' and sc == 'project': out['note'] = 'claude asks once to approve project servers; .claude/settings.local.json pre-approves hive'
    if native and out['bin']:
        try:
            r = subprocess.run([out['bin'], *(LIST.get(n, [n, 'mcp', 'list'])[1:])], cwd=root, capture_output=True, text=True, timeout=120,
                               env={**os.environ, 'NO_COLOR': '1', 'FORCE_COLOR': '0'}, stdin=subprocess.DEVNULL)
            lines = [ANSI.sub('', x).strip() for x in (r.stdout + '\n' + r.stderr).splitlines()]
            hit = next((x for x in lines if re.search(r'(^|[^\w-])hive([^\w-]|$)', x)), None)
            out['native'] = hit or f'hive not listed by {n} mcp list (exit {r.returncode})'
            if not hit or re.search(r'fail|error|✗|✘|disconnect|disabled|timed? ?out', hit, re.I): ok = False
        except (OSError, subprocess.SubprocessError) as e: out['native'] = f'{n} mcp list failed: {e}'[:300]
    return out | {'ok': ok}


def fill(t, vals): return re.sub(r'\{(prompt|promptFile|task|agent|token|role|db|root|mcp)\}', lambda m: vals[m[1]], t)


def argv(tpl, vals):
    out = []
    for x in tpl:
        if '{prompt}' in x and not vals['prompt']:
            if out and out[-1].startswith('-'): out.pop()
            continue
        out.append(fill(x, vals))
    return out


def env(h, a, n): return {'HIVE_DB': str(h.cfg.db), 'HIVE_ROOT': str(h.root), 'HIVE_AGENT': a.name, 'HIVE_AGENT_TOKEN': a.token, 'HIVE_ROLE': a.role,
                          'HIVE_HARNESS': n}


def start(h, n, prompt='', role='implementer', name=None, task=None, headless=False, model=None, extra=(), wf=None, say=print):
    from .reg import reg
    p = profile(n, h.cfg)
    if not (b := shutil.which(p['bin'])): raise Missing(f"{p['bin']} is not installed or not on PATH")
    if headless and not (prompt or task): raise Bad('a headless agent needs a prompt or --task')
    if n in H and not installed(n, h.root):
        for f, what in install(n, 'user', h.root): say(f'{what} {f} so {n} can reach the hive')
    if task:
        d = h.op().dispatch(task, name)
        x = h.sess(d['token'])
        body = d['prompt'] + (f'\n\n{prompt}' if prompt else '')
    else:
        taken = {a.name for a in h.agents.all()}
        x = h.join(name or next(k for k in (n, *(f'{n}{i}' for i in range(2, 999))) if k not in taken), role, wf, about=f'{n} session started from the hive CLI')
        a = x.agent
        b0 = brief(a.name, a.role, h.roles.get(a.role).charter, a.token)
        body = f'{b0}\n\n{prompt}' if prompt else b0 + '\n\nThe user talks to you in this terminal; wait for their instructions.' \
            if headless or not (n in H and hooked(n, h.root)) else ''
    a = x.agent
    (d := h.cfg.dir/'run').mkdir(parents=True, exist_ok=True)
    (pf := d/f'{a.name}.prompt.md').write_text(body)
    vals = {'prompt': body, 'promptFile': str(pf), 'task': task or '', 'agent': a.name, 'token': a.token, 'role': a.role, 'db': str(h.cfg.db),
            'root': str(h.root), 'mcp': ''}
    cmd = [b, *argv((p.get('run') or p['chat']) if headless else (p.get('chat') or p['run']), vals)[1:]] + ([p.get('model', '--model'), model] if model else []) + list(extra)
    with h.db.tx() as c: h.agents.set(c, a.id, harness=n)
    say(f"{a.name} ({a.role}) joins the hive at {h.root} through {n}" + (f", working on {task}" if task else ''))
    old, proc, r = None if headless else signal.signal(signal.SIGINT, lambda *_: None), None, reg()
    try:
        proc = subprocess.Popen(cmd, cwd=h.root, env={**os.environ, **env(h, a, n)})
        if r: r.bind(proc.pid, h.cfg.db, h.root, a.name, a.token, n)
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return proc.wait()
    finally:
        if old is not None: signal.signal(signal.SIGINT, old)
        if r and proc: r.unbind(proc.pid)
        if x.agent.state != 'left': x.leave(f'{n} session ended')
