"""Stage an allowlisted Vercel project. No upload; require explicit rights evidence."""
import argparse
import json
import re
from pathlib import Path
from shutil import copyfile
from city_snapshot import P2, DEST, sha, write

WEB = ['beta-app.js', 'city.js', 'rain.js', 'map.js', 'lab.js', 'lab-core.js',
       'lab-size.js', 'living.js', 'living-core.js', 'sunset.js', 'style.css',
       'fonts/neodgm.woff2', 'fonts/PretendardVariable.woff2', 'fonts/LICENSE.txt', 'fonts/README.md']
ASSETS = ['manifest.json', 'overlay.json', 'places.json', 'before.png', 'final.png',
          'sprite.png', 'hit.png', 'traveler.png', 'car_se.png', 'car_nw.png']

def stage(dest, approval=None):
    if dest.exists(): raise ValueError('Use a new empty release path; existing releases are immutable')
    dest.mkdir(parents=True)
    def copy(src, relative):
        target=dest / relative; target.parent.mkdir(parents=True,exist_ok=True);copyfile(src,target)
    for file in WEB: copy(P2 / 'web/pilot' / file, 'public/' + file)
    for file in ASSETS: copy(DEST / file, 'public/assets/city_pilot/' + file)
    # Backend data is included explicitly in the function bundle, never the raw collection.
    copy(DEST / 'places.json', 'assets/city_pilot/places.json')
    for file in ['server/guide.mjs','server/budget.mjs','api/guide.mjs']: copy(P2 / file,file)
    html=(P2 / 'web/pilot/index.html').read_text().replace('src="app.js"','src="beta-app.js"').replace('<body>','<body data-city-base="./assets/city_pilot/">')
    html=re.sub(r'  <details id="inspection">.*?</details>\n','',html,flags=re.S)
    html=re.sub(r'  <div id="route-bar".*?</dialog>\n','',html,flags=re.S)
    (dest / 'public/index.html').write_text(html)
    approved=False
    if approval:
        record=json.loads(approval.read_text())
        approved=record.get('approved') is True and record.get('finalSha256')==sha(DEST/'final.png') and bool(record.get('evidence'))
        if not approved: raise ValueError('Rights approval does not match this image')
    write(dest / 'package.json', {'private':True,'type':'module','scripts':{'build':'node check-release.mjs'},'engines':{'node':'24.x'}})
    write(dest / 'release-rights.json',{'approved':approved})
    (dest / 'check-release.mjs').write_text("import {readFileSync} from 'node:fs';\nif(JSON.parse(readFileSync('release-rights.json')).approved!==true)throw Error('Public image rights approval required. Do not deploy this candidate.');\n")
    write(dest / 'vercel.json', {'framework':None,'buildCommand':'npm run build','outputDirectory':'public',
        'functions':{'api/guide.mjs':{'maxDuration':35,'includeFiles':'assets/city_pilot/places.json'}},
        'headers':[{'source':'/(.*)','headers':[{'key':'X-Content-Type-Options','value':'nosniff'},{'key':'Referrer-Policy','value':'strict-origin-when-cross-origin'},{'key':'X-Frame-Options','value':'DENY'}]}]})
    (dest / '.vercelignore').write_text('.env*\n.vercel\nnode_modules\n')
    files={str(p.relative_to(dest)):sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}
    write(dest / 'release-manifest.json',{'files':files,'publicRightsApproved':approved,'guideEnabledByDefault':False})
    print(json.dumps({'staged':str(dest),'files':len(files),'publicRightsApproved':approved}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dest',type=Path,required=True);p.add_argument('--rights-approval',type=Path);a=p.parse_args();stage(a.dest,a.rights_approval)
