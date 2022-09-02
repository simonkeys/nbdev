# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/09_API/16_serve.ipynb.

# %% auto 0
__all__ = ['proc_nbs']

# %% ../nbs/09_API/16_serve.ipynb 2
import ast
from shutil import rmtree,copy2

from fastcore.utils import *
from fastcore.parallel import parallel
from fastcore.script import call_parse
from fastcore.meta import delegates

from .config import get_config
from .doclinks import nbglob_cli,nbglob
from .processors import FilterDefaults
import nbdev.serve_drv

# %% ../nbs/09_API/16_serve.ipynb 4
def _is_qpy(path:Path):
    "Is `path` a py script starting with frontmatter?"
    path = Path(path)
    if not path.suffix=='.py': return
    p = ast.parse(path.read_text())
#     try: p = ast.parse(path.read_text())
#     except: return
    if not p.body: return
    a = p.body[0]
    if isinstance(a, ast.Expr) and isinstance(a.value, ast.Constant):
        v = a.value.value.strip()
        vl = v.splitlines()
        if vl[0]=='---' and vl[-1]=='---': return v

def _exec_py(fname):
    "Exec a python script and warn on error"
    try: subprocess.check_output('python ' + fname, shell=True)
    except subprocess.CalledProcessError as cpe: warn(str(cpe))

# %% ../nbs/09_API/16_serve.ipynb 5
@call_parse
@delegates(nbglob)
def proc_nbs(
    path:str='', # Path to notebooks
    n_workers:int=defaults.cpus,  # Number of workers
    force:bool=False,  # Ignore cache and build all
    file_glob:str='', # Only include files matching glob
    **kwargs):
    "Process notebooks in `path` for docs rendering"
    from multiprocessing.forkserver import set_forkserver_preload
    set_forkserver_preload(['io', 'contextlib', 'execnb.nbio'])

    cfg = get_config()
    cache = cfg.config_path/'_proc'
    if not path: path = cfg.nbs_path
    files = nbglob(path, func=Path, file_glob=file_glob, **kwargs)
    if (path/'_quarto.yml').exists(): files.append(path/'_quarto.yml')

    # If settings.ini or filter script newer than cache folder modified, delete cache
    chk_mtime = max(cfg.config_file.stat().st_mtime, Path(__file__).stat().st_mtime)
    cache.mkdir(parents=True, exist_ok=True)
    cache_mtime = cache.stat().st_mtime
    if force or (cache.exists and cache_mtime<chk_mtime): rmtree(cache)

    def _doproc(o):
        src,dst=o
        return not dst.exists() or src.stat().st_mtime>max(cache_mtime, dst.stat().st_mtime)
    def _src_dst(o):
        dst = cache/o.relative_to(path)
        if o.suffix=='.py': dst = dst.with_suffix('.qmd')
        return o,dst

    files = files.map(_src_dst).filter(_doproc)
    execs = []
    for s,d in files:
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.suffix=='.ipynb': execs.append((s,d,FilterDefaults))
        else:
            md = _is_qpy(s)
            if md: execs.append((s,d,md))
            else: copy2(s,d)

    kw = {} if IN_NOTEBOOK else {'method':'forkserver' if os.name=='posix' else 'spawn'}
    parallel(nbdev.serve_drv.main, execs, n_workers=n_workers, pause=0.01, **kw)
    cache.touch()
    return cache