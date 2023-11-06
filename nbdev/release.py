# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/api/18_release.ipynb.

# %% auto 0
__all__ = ['GH_HOST', 'Release', 'changelog', 'release_git', 'release_gh', 'pypi_json', 'latest_pypi', 'pypi_details',
           'conda_output_path', 'write_conda_meta', 'write_requirements', 'anaconda_upload', 'release_conda',
           'chk_conda_rel', 'release_pypi', 'release_both', 'bump_version', 'nbdev_bump_version']

# %% ../nbs/api/18_release.ipynb 14
from fastcore.all import *
from ghapi.core import *

from datetime import datetime
import shutil,subprocess

from .doclinks import *

# %% ../nbs/api/18_release.ipynb 16
GH_HOST = "https://api.github.com"

# %% ../nbs/api/18_release.ipynb 17
def _find_config(cfg_name="settings.ini"):
    cfg_path = Path().absolute()
    while cfg_path != cfg_path.parent and not (cfg_path/cfg_name).exists(): cfg_path = cfg_path.parent
    return Config(cfg_path, cfg_name)

# %% ../nbs/api/18_release.ipynb 18
def _issue_txt(issue):
    res = '- {} ([#{}]({}))'.format(issue.title.strip(), issue.number, issue.html_url)
    if hasattr(issue, 'pull_request'): res += ', thanks to [@{}]({})'.format(issue.user.login, issue.user.html_url)
    res += '\n'
    if not issue.body: return res
    return res + f"  - {issue.body.strip()}\n"

def _issues_txt(iss, label):
    if not iss: return ''
    res = f"### {label}\n\n"
    return res + '\n'.join(map(_issue_txt, iss))

def _load_json(cfg, k):
    try: return json.loads(cfg[k])
    except json.JSONDecodeError as e: raise Exception(f"Key: `{k}` in .ini file is not a valid JSON string: {e}")

# %% ../nbs/api/18_release.ipynb 20
class Release:
    def __init__(self, owner=None, repo=None, token=None, **groups):
        "Create CHANGELOG.md from GitHub issues"
        self.cfg = _find_config()
        self.changefile = self.cfg.config_path/'CHANGELOG.md'
        if not groups:
            default_groups=dict(breaking="Breaking Changes", enhancement="New Features", bug="Bugs Squashed")
            groups=_load_json(self.cfg, 'label_groups') if 'label_groups' in self.cfg else default_groups
        os.chdir(self.cfg.config_path)
        owner,repo = owner or self.cfg.user, repo or self.cfg.repo
        token = ifnone(token, os.getenv('NBDEV_TOKEN',None))
        if not token and Path('token').exists(): token = Path('token').read_text().strip()
        token = ifnone(token, os.getenv('GITHUB_TOKEN',None))
        if not token: raise Exception('Failed to find token')
        self.gh = GhApi(owner, repo, token)
        self.groups = groups

    def _issues(self, label):
        return self.gh.issues.list_for_repo(state='closed', sort='created', filter='all', since=self.commit_date, labels=label)
    def _issue_groups(self): return parallel(self._issues, self.groups.keys(), progress=False)

# %% ../nbs/api/18_release.ipynb 22
@patch
def changelog(self:Release,
              debug=False): # Just print the latest changes, instead of updating file
    "Create the CHANGELOG.md file, or return the proposed text if `debug` is `True`"
    if not self.changefile.exists(): self.changefile.write_text("# Release notes\n\n<!-- do not remove -->\n")
    marker = '<!-- do not remove -->\n'
    try: self.commit_date = self.gh.repos.get_latest_release().published_at
    except HTTP404NotFoundError: self.commit_date = '2000-01-01T00:00:004Z'
    res = f"\n## {self.cfg.version}\n"
    issues = self._issue_groups()
    res += '\n'.join(_issues_txt(*o) for o in zip(issues, self.groups.values()))
    if debug: return res
    res = self.changefile.read_text().replace(marker, marker+res+"\n")
    shutil.copy(self.changefile, self.changefile.with_suffix(".bak"))
    self.changefile.write_text(res)
    run(f'git add {self.changefile}')

# %% ../nbs/api/18_release.ipynb 24
@patch
def release(self:Release):
    "Tag and create a release in GitHub for the current version"
    ver = self.cfg.version
    notes = self.latest_notes()
    self.gh.create_release(ver, branch=self.cfg.branch, body=notes)
    return ver

# %% ../nbs/api/18_release.ipynb 26
@patch
def latest_notes(self:Release):
    "Latest CHANGELOG entry"
    if not self.changefile.exists(): return ''
    its = re.split(r'^## ', self.changefile.read_text(), flags=re.MULTILINE)
    if not len(its)>0: return ''
    return '\n'.join(its[1].splitlines()[1:]).strip()

# %% ../nbs/api/18_release.ipynb 29
@call_parse
def changelog(
    debug:store_true=False,  # Print info to be added to CHANGELOG, instead of updating file
    repo:str=None,  # repo to use instead of `lib_name` from `settings.ini`
):
    "Create a CHANGELOG.md file from closed and labeled GitHub issues"
    res = Release(repo=repo).changelog(debug=debug)
    if debug: print(res)

# %% ../nbs/api/18_release.ipynb 30
@call_parse
def release_git(
    token:str=None  # Optional GitHub token (otherwise `token` file is used)
):
    "Tag and create a release in GitHub for the current version"
    ver = Release(token=token).release()
    print(f"Released {ver}")

# %% ../nbs/api/18_release.ipynb 31
@call_parse
def release_gh(
    token:str=None  # Optional GitHub token (otherwise `token` file is used)
):
    "Calls `nbdev_changelog`, lets you edit the result, then pushes to git and calls `nbdev_release_git`"
    cfg = _find_config()
    Release().changelog()
    subprocess.run([os.environ.get('EDITOR','nano'), cfg.config_path/'CHANGELOG.md'])
    if not input("Make release now? (y/n) ").lower().startswith('y'): sys.exit(1)
    run('git commit -am release')
    run('git push')
    ver = Release(token=token).release()
    print(f"Released {ver}")

# %% ../nbs/api/18_release.ipynb 33
from fastcore.all import *
from .config import *
from .cli import *

import yaml,subprocess,glob,platform
from os import system
try: from packaging.version import parse
except ImportError: from pip._vendor.packaging.version import parse

_PYPI_URL = 'https://pypi.org/pypi/'

# %% ../nbs/api/18_release.ipynb 34
def pypi_json(s):
    "Dictionary decoded JSON for PYPI path `s`"
    return urljson(f'{_PYPI_URL}{s}/json')

# %% ../nbs/api/18_release.ipynb 35
def latest_pypi(name):
    "Latest version of `name` on pypi"
    return max(parse(r) for r,o in pypi_json(name)['releases'].items()
               if not parse(r).is_prerelease and not nested_idx(o, 0, 'yanked'))

# %% ../nbs/api/18_release.ipynb 36
def pypi_details(name):
    "Version, URL, and SHA256 for `name` from pypi"
    ver = str(latest_pypi(name))
    pypi = pypi_json(f'{name}/{ver}')
    rel = [o for o in pypi['urls'] if o['packagetype']=='sdist'][0]
    return ver,rel['url'],rel['digests']['sha256']

# %% ../nbs/api/18_release.ipynb 37
import shlex
from subprocess import Popen, PIPE, CalledProcessError

def _run(cmd):
    res = ""
    with Popen(shlex.split(cmd), stdout=PIPE, bufsize=1, text=True, encoding="utf-8") as p:
        for line in p.stdout:
            print(line, end='')
            res += line

    if p.returncode != 0: raise CalledProcessError(p.returncode, p.args)
    return res

# %% ../nbs/api/18_release.ipynb 38
def conda_output_path(name, build='build'):
    "Output path for conda build"
    return run(f'conda {build} --output {name}').strip().replace('\\', '/')

# %% ../nbs/api/18_release.ipynb 39
def _write_yaml(path, name, d1, d2):
    path = Path(path)
    p = path/name
    p.mkdir(exist_ok=True, parents=True)
    yaml.SafeDumper.ignore_aliases = lambda *args : True
    with (p/'meta.yaml').open('w', encoding="utf-8") as f:
        yaml.safe_dump(d1, f)
        yaml.safe_dump(d2, f)

# %% ../nbs/api/18_release.ipynb 40
def _get_conda_meta():
    cfg = get_config()
    name,ver = cfg.lib_name,cfg.version
    url = cfg.doc_host or cfg.git_url

    doc_url = (cfg.doc_host + cfg.doc_baseurl) if (cfg.doc_host and cfg.doc_baseurl) else url
    dev_url = cfg.git_url if cfg.git_url else url

    hostreqs = ['pip', 'packaging', f'python >={cfg.min_python}']
    if cfg.get('requirements'): reqs = hostreqs[-1:] + cfg.requirements.split()
    if cfg.get('conda_requirements'): reqs += cfg.conda_requirements.split()

    pypi = pypi_json(f'{name}/{ver}')
    rel = [o for o in pypi['urls'] if o['packagetype']=='sdist'][0]

    # Work around conda build bug - 'package' and 'source' must be first
    d1 = {
        'package': {'name': name, 'version': ver},
        'source': {'url':rel['url'], 'sha256':rel['digests']['sha256']}
    }

    _dir = cfg.lib_path.parent
    readme = _dir/'README.md'
    descr = readme.read_text() if readme.exists() else ''
    d2 = {
        'build': {'number': '0', 'noarch': 'python',
                  'script': '{{ PYTHON }} -m pip install . -vv'},
        'requirements': {'host':hostreqs, 'run':reqs},
        'test': {'imports': [cfg.lib_path.name]},
        'about': {
            'license': 'Apache Software',
            'license_family': 'APACHE',
            'home': dev_url, 'doc_url': doc_url, 'dev_url': dev_url,
            'summary': cfg.get('description'),
            'description': descr
        },
        'extra': {'recipe-maintainers': [cfg.get('user')]}
    }
    return name,d1,d2

# %% ../nbs/api/18_release.ipynb 41
def write_conda_meta(path='conda'):
    "Writes a `meta.yaml` file to the `conda` directory of the current directory"
    _write_yaml(path, *_get_conda_meta())

# %% ../nbs/api/18_release.ipynb 43
# This function is used as a utility for creating HF spaces.
def write_requirements(directory=None):
    "Writes a `requirements.txt` file to `directory` based on settings.ini."
    cfg = get_config()
    d = Path(directory) if directory else cfg.config_path
    req = '\n'.join([cfg.get(k, '').replace(' ', '\n') for k in ['requirements', 'pip_requirements']])
    (d/'requirements.txt').mk_write(req)

# %% ../nbs/api/18_release.ipynb 45
def anaconda_upload(name, loc=None, user=None, token=None, env_token=None):
    "Upload `name` to anaconda"
    user = f'-u {user} ' if user else ''
    if env_token: token = os.getenv(env_token)
    token = f'-t {token} ' if token else ''
    if not loc: loc = conda_output_path(name)
    if not loc: raise Exception("Failed to find output")
    return _run(f'anaconda {token} upload {user} {loc} --skip-existing')

# %% ../nbs/api/18_release.ipynb 47
@call_parse
def release_conda(
    path:str='conda', # Path where package will be created
    do_build:bool_arg=True,  # Run `conda build` step
    build_args:str='',  # Additional args (as str) to send to `conda build`
    skip_upload:store_true=False,  # Skip `anaconda upload` step
    mambabuild:store_true=False,  # Use `mambabuild` (requires `boa`)
    upload_user:str=None  # Optional user to upload package to
):
    "Create a `meta.yaml` file ready to be built into a package, and optionally build and upload it"
    name = get_config().lib_name
    write_conda_meta(path)
    out = f"Done. Next steps:\n```\ncd {path}\n"""
    os.chdir(path)
    build = 'mambabuild' if mambabuild else 'build'
    if not do_build: return print(f"{out}conda {build} {name}")

    for f in globtastic('out', file_glob='*.tar.bz2'): os.remove(f)
    cmd = f"conda {build} --output-folder out --no-anaconda-upload {build_args} {name}"
    print(cmd)
    res = _run(cmd)
    outs = globtastic('out', file_glob='*.tar.bz2')
    assert len(outs)==1
    loc = outs[0]
    if skip_upload: return print(loc)
    if not upload_user: upload_user = get_config().conda_user
    if not upload_user: return print("`conda_user` not in settings.ini and no `upload_user` passed. Cannot upload")
    if 'anaconda upload' not in res: return print(f"{res}\n\Failed. Check auto-upload not set in .condarc. Try `--do_build False`.")
    return anaconda_upload(name, loc)

# %% ../nbs/api/18_release.ipynb 48
def chk_conda_rel(
    nm:str,  # Package name on pypi
    apkg:str=None,  # Anaconda Package (defaults to {nm})
    channel:str='fastai',  # Anaconda Channel
    force:store_true=False  # Always return github tag
):
    "Prints GitHub tag only if a newer release exists on Pypi compared to an Anaconda Repo."
    if not apkg: apkg=nm
    condavs = L(loads(run(f'mamba repoquery search {apkg} -c {channel} --json'))['result']['pkgs'])
    condatag = condavs.attrgot('version').map(parse)
    pypitag = latest_pypi(nm)
    if force or not condatag or pypitag > max(condatag): return f'{pypitag}'

# %% ../nbs/api/18_release.ipynb 50
@call_parse
def release_pypi(
    repository:str="pypi" # Respository to upload to (defined in ~/.pypirc)
):
    "Create and upload Python package to PyPI"
    _dir = get_config().lib_path.parent
    system(f'cd {_dir}  && rm -rf dist build && python setup.py sdist bdist_wheel')
    system(f'twine upload --repository {repository} {_dir}/dist/*')

# %% ../nbs/api/18_release.ipynb 52
@call_parse
def release_both(
    path:str='conda', # Path where package will be created
    do_build:bool_arg=True,  # Run `conda build` step
    build_args:str='',  # Additional args (as str) to send to `conda build`
    skip_upload:store_true=False,  # Skip `anaconda upload` step
    mambabuild:store_true=False,  # Use `mambabuild` (requires `boa`)
    upload_user:str=None,  # Optional user to upload package to
    repository:str="pypi" # Pypi respository to upload to (defined in ~/.pypirc)
):
    "Release both conda and PyPI packages"
    release_pypi.__wrapped__(repository)
    release_conda.__wrapped__(path, do_build=do_build, build_args=build_args, skip_upload=skip_upload, mambabuild=mambabuild, upload_user=upload_user)
    nbdev_bump_version.__wrapped__()

# %% ../nbs/api/18_release.ipynb 54
def bump_version(version, part=2, unbump=False):
    version = version.split('.')
    incr = -1 if unbump else 1
    version[part] = str(int(version[part]) + incr)
    for i in range(part+1, 3): version[i] = '0'
    return '.'.join(version)

# %% ../nbs/api/18_release.ipynb 55
@call_parse
def nbdev_bump_version(
    part:int=2,  # Part of version to bump
    unbump:bool=False):  # Reduce version instead of increasing it
    "Increment version in settings.ini by one"
    cfg = get_config()
    print(f'Old version: {cfg.version}')
    cfg.d['version'] = bump_version(get_config().version, part, unbump=unbump)
    cfg.save()
    update_version()
    nbdev_export.__wrapped__()
    print(f'New version: {cfg.version}')
