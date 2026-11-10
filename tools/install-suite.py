#!/usr/bin/env python3
"""Install manifest-pinned standalone Nyx releases without starting applications."""
import hashlib,json,os,platform,shutil,subprocess,sys,tarfile,tempfile,tomllib
from pathlib import Path
RAW='https://raw.githubusercontent.com/design-nexus/nyx/main'
def download(url,path):subprocess.run(['curl','--fail','--location','--retry','3','--output',str(path),url],check=True)
def main():
 with tempfile.TemporaryDirectory(prefix='nyx-install-') as tmp:
  work=Path(tmp);manifest=work/'suite.toml'
  local=Path(__file__).resolve().parents[1]/'suite.toml'
  override=os.environ.get('NYX_SUITE_MANIFEST')
  if override:shutil.copy2(override,manifest)
  elif local.exists():shutil.copy2(local,manifest)
  else:download(RAW+'/suite.toml',manifest)
  suite=tomllib.loads(manifest.read_text());apps={a['id']:a for a in suite['applications']};repos={r['id']:r for r in suite['repositories']}
  selected=[];options=[];aliases={'gallery':'photos','write':'office','sheets':'office','present':'office'}
  for arg in sys.argv[1:]:
   if arg=='--list':print('\n'.join(apps));return
   if arg in ['--help','-h']:print('Usage: nyx install APP... | all [--default] [--gear]');return
   if arg=='all':selected.extend(a for a,v in apps.items() if v.get('default',True))
   elif arg in ['--default','--gear']:options.append(arg)
   else:selected.append(aliases.get(arg,arg))
  if not selected:raise SystemExit('Choose an application or all')
  unknown=[id for id in selected if id not in apps]
  if unknown:raise SystemExit('Unknown application: '+', '.join(unknown))
  # Authentication is a shared prerequisite of the native account consumers.
  if any(apps[id].get('requires_accounts',False) for id in selected):
   selected=['accounts',*selected]
  for id in dict.fromkeys(selected):
   if id not in apps:raise SystemExit('Unknown application: '+id)
   repo=repos[apps[id]['repository']];name=id+'-x86_64.tar.gz';artifact='dist/'+name
   tag=repo.get('release_tag');expected=repo.get('artifact_sha256',{}).get(artifact)
   dest=work/id
   if not tag or not expected:
    # No release yet: the repository's own installer, at the pinned revision.
    if not repo.get('revision'):raise SystemExit(id+': no release or pinned revision in suite manifest')
    subprocess.run(['git','init','-q',str(dest)],check=True)
    subprocess.run(['git','-C',str(dest),'fetch','-q','--depth','1',repo['url'],repo['revision']],check=True)
    subprocess.run(['git','-C',str(dest),'checkout','-q','FETCH_HEAD'],check=True)
    print('Installing '+id+' from '+repo['name']+' at '+repo['revision'][:12]+' (source build)',flush=True)
    env=dict(os.environ);program=Path.home()/'.local/bin'/('nyx-'+id)
    env['NYX_SKIP_INTEGRATION']='1' if program.exists() else '0'
    subprocess.run(['bash',str(dest/repo.get('installer','install.sh')),id,*options],cwd=dest,env=env,check=True)
    continue
   needs_source=os.environ.get('NYX_BUILD')=='1' or platform.machine()!='x86_64'
   if id=='assistant' and 'cuda' in repo.get('build_features',[]) and not Path('/dev/nvidiactl').exists():needs_source=True
   if needs_source:
    subprocess.run(['git','clone','--depth','1','--branch',tag,repo['url'],str(dest)],check=True)
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=dest,text=True).strip()
    if actual!=repo.get('release_revision',repo['revision']):raise SystemExit(id+': source tag does not match supported revision')
   else:
    dest.mkdir();archive=dest/name
    print('Installing '+id+' '+tag+' from '+repo['name'],flush=True)
    download('https://github.com/design-nexus/'+repo['name']+'/releases/download/'+tag+'/'+name,archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:raise SystemExit(id+': archive checksum mismatch')
    with tarfile.open(archive) as files:files.extractall(dest,filter='data')
   env=dict(os.environ)
   if not needs_source:env.pop('CARGO_TARGET_DIR',None)
   program=Path.home()/'.local/bin'/('nyx-'+id)
   env['NYX_SKIP_INTEGRATION']='1' if program.exists() else '0'
   subprocess.run(['bash',str(dest/repo.get('installer','install.sh')),id,*options],cwd=dest,env=env,check=True)
  # Every app uses the current umbrella CLI; standalone installers cannot downgrade it.
  binary=Path.home()/'.local/bin/nyx';binary.parent.mkdir(parents=True,exist_ok=True)
  # Install icon tools and their bundled canonical assets for offline commands.
  data=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
  icon_tools=data/'nyx/icon-tools';(icon_tools/'assets').mkdir(parents=True,exist_ok=True)
  for source,target in [('tools/icons.py',icon_tools/'icons.py'),
                        ('tools/theme.py',icon_tools/'theme.py'),
                        ('assets/icons/make_icons.py',icon_tools/'assets/make_icons.py'),
                        ('assets/icons/app-glyphs.json',icon_tools/'assets/app-glyphs.json'),
                        ('assets/icons/themes.json',icon_tools/'assets/themes.json'),
                        ('assets/icons/third-party-glyphs.json',icon_tools/'assets/third-party-glyphs.json')]:
   local_source=Path(__file__).resolve().parents[1]/source
   temporary=target.with_name(target.name+'.new')
   if local_source.is_file():shutil.copy2(local_source,temporary)
   else:download(RAW+'/'+source,temporary)
   temporary.replace(target)
  temporary=binary.with_name('nyx.new')
  local_cli=Path(__file__).resolve().parents[1]/'bin/nyx'
  if local_cli.is_file():shutil.copy2(local_cli,temporary)
  else:download(RAW+'/bin/nyx',temporary)
  temporary.chmod(0o755);temporary.replace(binary)
  # nyx-actions (nyx apps, nyx APP …) from nyx-core at the suite's revision, rebuilt when it changes.
  core=repos.get('core',{});revision=core.get('actions_revision');actions=binary.with_name('nyx-actions');stamp=data/'nyx/nyx-actions.revision'
  if revision and not (actions.exists() and stamp.exists() and stamp.read_text().strip()==revision):
   if not shutil.which('cargo'):print('Warning: Rust (cargo) is missing, so nyx-actions (nyx APP …) was not built.',file=sys.stderr,flush=True)
   else:
    source=work/'nyx-core';subprocess.run(['git','init','-q',str(source)],check=True)
    subprocess.run(['git','-C',str(source),'fetch','-q','--depth','1',core['url'],revision],check=True)
    subprocess.run(['git','-C',str(source),'checkout','-q','FETCH_HEAD'],check=True)
    print('Building nyx-actions from nyx-core at '+revision[:12],flush=True)
    env=dict(os.environ);env.pop('CARGO_TARGET_DIR',None)
    subprocess.run(['cargo','build','--release','--locked','-p','nyx-actions','--features','cli'],cwd=source,env=env,check=True)
    temporary=actions.with_name('nyx-actions.new');shutil.copy2(source/'target/release/nyx-actions',temporary)
    temporary.chmod(0o755);temporary.replace(actions);stamp.parent.mkdir(parents=True,exist_ok=True);stamp.write_text(revision+'\n')
  # Recolour the icons just installed; turn on following unless it was turned off.
  follow_off=(data/'nyx/icons/follow-off').exists()
  icon_command=['follow','on'] if not follow_off else ['sync','--quiet']
  result=subprocess.run(['/usr/bin/python3',str(icon_tools/'icons.py'),*icon_command])
  if result.returncode:print('Warning: could not recolour icons for the current theme (nyx icons sync).',file=sys.stderr,flush=True)
 print('Installed without opening or restarting applications.',flush=True)
if __name__=='__main__':main()
