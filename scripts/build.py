"""Stage and validate an entire static build; failures preserve the last build."""
from pathlib import Path
from hashlib import sha256
import json
import os
import shutil
import tempfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from marketbudget.config import ROOT
from marketbudget.releases import load_release,validate_snapshot

def build(root=ROOT,destination=None):
    destination=destination or root/'dist'
    state,manifest,release=load_release(root)
    with tempfile.TemporaryDirectory(dir=root.parent,prefix='.marketbudget-build-') as temporary:
        stage=Path(temporary)/'dist'
        shutil.copytree(root/'web',stage)
        (stage/'data').mkdir(exist_ok=True)
        for name in ('snapshot.json','evaluation.json','corrections.json'):
            shutil.copy2(release/name,stage/'data'/name)
        research=root/'reports/research/latest.json'
        if research.exists():
            value=json.loads(research.read_text())
            if value.get('status')!='research_only':raise ValueError('Research outputs must remain research_only')
            shutil.copy2(research,stage/'data/research.json')
        else:(stage/'data/research.json').write_text(json.dumps({'status':'not_run'}))
        (stage/'runtime.json').write_text(json.dumps({'storage':'browser','release_id':manifest['release_id'],'snapshot_sha256':manifest['files']['snapshot.json']},indent=2))
        shutil.copy2(root/'README.md',stage/'project-guide.md')
        if (destination/'downloads').exists():shutil.copytree(destination/'downloads',stage/'downloads')
        validate_snapshot(json.loads((stage/'data/snapshot.json').read_text()))
        if sha256((stage/'data/snapshot.json').read_bytes()).hexdigest()!=manifest['files']['snapshot.json']:raise ValueError('Build snapshot integrity mismatch')
        for name in ('index.html','app.js','math.mjs','storage.mjs','vendor/decimal.mjs'):
            if not (stage/name).is_file():raise ValueError(f'Missing application asset: {name}')
        backup=Path(temporary)/'previous'
        if destination.exists():os.replace(destination,backup)
        try:os.replace(stage,destination)
        except BaseException:
            if backup.exists():os.replace(backup,destination)
            raise
    print(f"Built {destination} from {manifest['release_id']}")

if __name__=='__main__':build()
