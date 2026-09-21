"""Export a reviewed dense map into bounded public tiles and cropped object assets."""
import argparse
from pathlib import Path
from shutil import copyfile
from copy import deepcopy
from PIL import Image, ImageChops
from city_snapshot import P2, DEST, read, write, sha

GATES = ('capturePassed','firstPairPassed','geometryPassed','seamsPassed','landmarksPassed')

def export(source, dest, *, review_only=False):
    d=read(source/'delivery.json')
    if (d.get('width'),d.get('height'))!=(4608,3072): raise ValueError('Dense scope changed')
    if review_only:
        if (P2/'work').resolve() not in dest.resolve().parents: raise ValueError('Review snapshots must stay in local work directory')
    elif not all(d.get('acceptance',{}).get(k) is True for k in GATES): raise ValueError('Dense release acceptance incomplete')
    if dest.exists(): raise ValueError('Use a new output directory; never overwrite a delivered snapshot')
    def src(name):
        p=(source/name).resolve()
        if source.resolve() not in p.parents or p.suffix.lower()!='.png': raise ValueError('Invalid public asset')
        return p
    background=Image.open(src(d['background'])).convert('RGB')
    if background.size!=(4608,3072): raise ValueError('Background dimensions changed')
    ids={l['id'] for l in d['landmarks']}
    if ids!={'gwanghwamun','jongno-tower','bosingak'} or len(d['landmarks'])!=3: raise ValueError('Three landmarks required')
    dest.mkdir(parents=True)
    for level in [.25,.5,1]:
        image=background if level==1 else background.resize((int(4608*level),int(3072*level)),Image.Resampling.NEAREST)
        directory=dest/'tiles'/str(level if level!=1 else 1);directory.mkdir(parents=True)
        for y in range(0,image.height,512):
            for x in range(0,image.width,512): image.crop((x,y,min(x+512,image.width),min(y+512,image.height))).save(directory/f'{x//512}_{y//512}.png')
        if level==.25:image.save(dest/'preview.png')
    landmarks=[]
    for l in d['landmarks']:
        item={k:l[k] for k in ['id','rect','anchor','occluder_id']};item.update(mode='independent',reveal_only=bool(l.get('reveal_only')))
        for kind in ['sprite','hit']:
            im=Image.open(src(l[kind]));im.load()
            if im.size!=tuple(l['rect'][2:]): raise ValueError('Cropped object dimensions mismatch')
            if kind=='sprite' and im.mode!='RGBA': raise ValueError('Real landmark alpha required')
            name=f"{l['id']}_{kind}.png";copyfile(src(l[kind]),dest/name);item[kind]=name
        landmarks.append(item)
    minimap=background.convert('RGBA')
    for item in landmarks:
        if not item['reveal_only']:
            minimap.alpha_composite(Image.open(dest/item['sprite']).convert('RGBA'),tuple(item['rect'][:2]))
    minimap.resize((1152,768),Image.Resampling.NEAREST).convert('RGB').save(dest/'minimap.png')
    reveal={k:d['reveal'][k] for k in ['targetId','rect']};reveal['geometryVerified']=False
    for kind in ['underlay','mask']:
        im=Image.open(src(d['reveal'][kind]));im.load()
        if im.size!=tuple(reveal['rect'][2:]): raise ValueError('Reveal dimensions mismatch')
        name=f'bosingak_{kind}.png';copyfile(src(d['reveal'][kind]),dest/name);reveal[kind]=name
    if d['reveal'].get('foregroundMask'):
        im=Image.open(src(d['reveal']['foregroundMask']))
        if im.mode!='L' or im.size!=tuple(reveal['rect'][2:]): raise ValueError('Invalid foreground mask')
        if ImageChops.multiply(im,ImageChops.invert(Image.open(dest/reveal['mask']).convert('L'))).getbbox(): raise ValueError('Foreground exceeds reveal mask')
        reveal['foregroundMask']='bosingak_foreground.png';copyfile(src(d['reveal']['foregroundMask']),dest/reveal['foregroundMask'])
    if d['reveal'].get('auto') is True: reveal['auto']=True
    target=next(l for l in landmarks if l['id']=='bosingak')
    tx,ty,tw,th=target['rect'];rx,ry,rw,rh=reveal['rect']
    if not (rx<=tx and ry<=ty and tx+tw<=rx+rw and ty+th<=ry+rh): raise ValueError('Bosingak crop outside reveal area')
    coverage=Image.new('L',tuple(reveal['rect'][2:]));sprite=Image.open(dest/target['sprite'])
    coverage.paste(sprite.getchannel('A'),(target['rect'][0]-reveal['rect'][0],target['rect'][1]-reveal['rect'][1]))
    mask=Image.open(dest/reveal['mask']).convert('L')
    if ImageChops.multiply(coverage,ImageChops.invert(mask)).getbbox(): raise ValueError('Bosingak sprite exceeds reveal mask')
    for f in ['traveler.png','car_se.png','car_nw.png']:copyfile(DEST/f,dest/f)
    names={'gwanghwamun':'광화문','jongno-tower':'종로타워','bosingak':'보신각'}
    traffic=deepcopy(d['traffic']);occluders=traffic.get('occluders',[]);seen=set()
    if not isinstance(occluders,list) or len(occluders)>32: raise ValueError('Invalid traffic occluders')
    for i,item in enumerate(occluders):
        rect=item.get('rect',[]);ident=item.get('id');lanes=item.get('lanes',[])
        if (not isinstance(ident,str) or not ident or ident in seen or len(rect)!=4 or
            not all(type(v) is int for v in rect) or min(rect[:2])<0 or min(rect[2:])<=0 or
            rect[0]+rect[2]>4608 or rect[1]+rect[3]>3072 or
            not isinstance(lanes,list) or not lanes or any(id not in [l['id'] for l in traffic['lanes']] for id in lanes)):
            raise ValueError('Invalid traffic occlusion placement')
        seen.add(ident)
        with Image.open(src(item['mask'])) as mask:
            if mask.mode!='L' or mask.size!=tuple(rect[2:]) or not mask.getbbox(): raise ValueError('Invalid traffic mask')
        name=f'traffic_occlusion_{i}.png';copyfile(src(item['mask']),dest/name);item['mask']=name
    overlay={'landmarks':landmarks,'spots':[{'id':l['id'],'title':names[l['id']],'xy':l['anchor']} for l in landmarks],
             'reveal':reveal,'route':d['route'],'traffic':traffic,'occluders':[]}
    write(dest/'overlay.json',overlay)
    data=read(DEST/'places.json')
    for l in data['landmarks']:
        l['mapSpotId']=next((id for id,name in names.items() if l['name']==name),None)
        if l['name']=='보신각':l['geometryStatus']='estimated'
    write(dest/'places.json',data)
    manifest={'version':1,'kind':'city-dense-pilot','run_id':d['run_id'],'testFixture':bool(d.get('testFixture')),'reviewOnly':review_only,'width':4608,'height':3072,
              'tile_size':512,'levels':[.25,.5,1],'preview':'preview.png','minimap':'minimap.png','overlay':'overlay.json','character':'traveler.png',
              'initialView':{'center':next(l['anchor'] for l in landmarks if l['id']=='gwanghwamun'),'scale':.5},
              'asset_sha256':{str(p.relative_to(dest)):sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}}
    write(dest/'manifest.json',manifest)
    write(dest/'build.json',{'acceptance':d['acceptance'],'visualAcceptance':d.get('visualAcceptance',{}),'reviewOnly':review_only,'deliverySha256':sha(source/'delivery.json'),'publicRightsApproved':False})
    return {'files':len(manifest['asset_sha256']),'manifestSha256':sha(dest/'manifest.json')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--dest',type=Path,required=True);a=p.parse_args();print(export(a.source,a.dest))
