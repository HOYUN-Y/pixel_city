"""Stage an allowlisted Vercel project; distinguish rights evidence from a user-directed pilot."""
import argparse
import json
import re
from pathlib import Path
from shutil import copyfile
from city_snapshot import P2, DEST, sha, write

WEB = ['beta-app.js', 'city.js', 'discovery.js', 'rain.js', 'reveal.js', 'dense-map.js', 'dense-core.js', 'tile-layer.js', 'map.js', 'lab.js', 'lab-core.js',
       'lab-size.js', 'living.js', 'living-core.js', 'sunset.js', 'style.css',
       'fonts/neodgm.woff2', 'fonts/PretendardVariable.woff2', 'fonts/LICENSE.txt', 'fonts/README.md']
ASSETS = ['manifest.json', 'overlay.json', 'places.json', 'before.png', 'final.png',
          'sprite.png', 'hit.png', 'traveler.png', 'car_se.png', 'car_nw.png']

def stage(dest, approval=None, decision=None, snapshot=DEST, local_review=False):
    if dest.exists(): raise ValueError('Use a new empty release path; existing releases are immutable')
    if local_review and (approval or decision):raise ValueError('Local-only review cannot accept deployment authorization')
    dest.mkdir(parents=True)
    def copy(src, relative):
        target=dest / relative; target.parent.mkdir(parents=True,exist_ok=True);copyfile(src,target)
    for file in WEB: copy(P2 / 'web/pilot' / file, 'public/' + file)
    manifest=json.loads((snapshot / 'manifest.json').read_text())
    dense=manifest.get('kind')=='city-dense-pilot'
    if dense:
        if manifest.get('testFixture'): raise ValueError('Diagnostic fixtures cannot be deployed')
        if manifest.get('reviewOnly') and not local_review: raise ValueError('Review-only snapshots cannot be deployed')
        from dense_snapshot import GATES
        if not local_review:
            build=json.loads((snapshot / 'build.json').read_text())
            if not all(build.get('acceptance',{}).get(k) is True for k in GATES): raise ValueError('Dense release acceptance incomplete')
        files=['manifest.json',*manifest['asset_sha256']]
        for file in files:
            if not re.fullmatch(r'[a-zA-Z0-9_./-]+',file) or '..' in file or file.startswith('/') or not (file.endswith('.png') or file in ['manifest.json','places.json','overlay.json']): raise ValueError('Non-public dense asset')
            if file!='manifest.json' and sha(snapshot/file)!=manifest['asset_sha256'][file]: raise ValueError('Dense asset changed')
            copy(snapshot / file,'public/assets/city_pilot/' + file)
    else:
        for file in ASSETS: copy(snapshot / file, 'public/assets/city_pilot/' + file)
    if not dense and json.loads((snapshot / 'overlay.json').read_text()).get('reveal'):
        for file in ['bosingak.png','bosingak_hit.png','bosingak_underlay.png','bosingak_reveal_mask.png']:
            copy(snapshot / file, 'public/assets/city_pilot/' + file)
    # Backend data is included explicitly in the function bundle, never the raw collection.
    copy(snapshot / 'places.json', 'assets/city_pilot/places.json')
    for file in ['server/guide.mjs','server/budget.mjs','api/guide.mjs']: copy(P2 / file,file)
    html=(P2 / 'web/pilot/index.html').read_text().replace('src="app.js"','src="beta-app.js"').replace('<body>','<body data-city-base="./assets/city_pilot/">')
    if manifest.get('experience')=='discovery':html=html.replace('<body data-city-base=', '<body data-city-experience="discovery" data-city-base=')
    html=re.sub(r'  <details id="inspection">.*?</details>\n','',html,flags=re.S)
    html=re.sub(r'  <div id="route-bar".*?</dialog>\n','',html,flags=re.S)
    (dest / 'public/index.html').write_text(html)
    approved=False
    digest=sha(snapshot / ('manifest.json' if dense else 'final.png'))
    hash_field='snapshotSha256' if dense else 'finalSha256'
    if approval:
        record=json.loads(approval.read_text())
        approved=record.get('approved') is True and record.get(hash_field)==digest and bool(record.get('evidence'))
        if not approved: raise ValueError('Rights approval does not match this image')
    authorized=False
    if decision:
        record=json.loads(decision.read_text())
        authorized=record.get('userAuthorized') is True and record.get('rightsVerified') is False and record.get(hash_field)==digest and bool(record.get('acknowledgement'))
        if not authorized: raise ValueError('Deployment decision does not match this candidate')
    write(dest / 'package.json', {'private':True,'type':'module','scripts':{'build':'node check-release.mjs'},'engines':{'node':'24.x'}})
    write(dest / 'release-rights.json',{'approved':approved,'userDirectedPilot':authorized,'rightsVerified':approved})
    (dest / 'check-release.mjs').write_text("import {readFileSync} from 'node:fs';\nconst r=JSON.parse(readFileSync('release-rights.json'));\nif(r.approved!==true&&r.userDirectedPilot!==true)throw Error('Public image rights approval required, or a separately recorded explicit user-directed pilot decision. Do not deploy this candidate.');\n")
    if local_review:
        (dest/'check-release.mjs').write_text("throw Error('Local-only review package: deployment is disabled regardless of rights records.');\n")
    write(dest / 'vercel.json', {'framework':None,'buildCommand':'npm run build','outputDirectory':'public',
        'functions':{'api/guide.mjs':{'maxDuration':35,'includeFiles':'assets/city_pilot/places.json'}},
        'headers':[{'source':'/(.*)','headers':[{'key':'X-Content-Type-Options','value':'nosniff'},{'key':'Referrer-Policy','value':'strict-origin-when-cross-origin'},{'key':'X-Frame-Options','value':'DENY'}]}]})
    (dest / '.vercelignore').write_text('.env*\n.vercel\nnode_modules\n')
    files={str(p.relative_to(dest)):sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}
    validate_modules(dest/'public')
    write(dest / 'release-manifest.json',{'files':files,'publicRightsApproved':approved,'userDirectedPilot':authorized,'guideEnabledByDefault':False,'localOnly':local_review})
    print(json.dumps({'staged':str(dest),'files':len(files),'publicRightsApproved':approved,'userDirectedPilot':authorized}))

def validate_modules(public):
    """Check current static/dynamic relative ES imports without executing a browser."""
    for module in public.rglob('*.js'):
        for relative in re.findall(r'''(?:from\s*|import\s*\(\s*|import\s*)['"](\.[^'"]+)['"]''',module.read_text()):
            target=(module.parent/relative).resolve()
            if not target.is_relative_to(public.resolve()) or not target.is_file():raise ValueError(f'Missing packaged module: {module.name} -> {relative}')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dest',type=Path,required=True);p.add_argument('--snapshot',type=Path,default=DEST);p.add_argument('--rights-approval',type=Path);p.add_argument('--deployment-decision',type=Path);p.add_argument('--local-review',action='store_true');a=p.parse_args();stage(a.dest,a.rights_approval,a.deployment_decision,a.snapshot,a.local_review)
