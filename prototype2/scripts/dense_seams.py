"""Deterministic native-pixel seam candidates. No network or release approval.

Source ownership is explicit; image similarity is NOT a geometry/visual gate.
The CLI starts with a single horizontal pair, then supports a gated full run.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def minimum_path(cost):
    """Top-to-bottom 8-connected path; ties prefer straight, then left.

    Infinite costs represent forbidden cuts. Never silently relax constraints.
    """
    cost = np.asarray(cost, dtype=np.float64)
    if cost.ndim != 2 or not all(cost.shape) or np.isnan(cost).any():
        raise ValueError('Expected a nonempty cost plane without NaN')
    height, width = cost.shape
    parents = np.zeros((height, width), dtype=np.int8)
    score = cost[0].copy()
    for y in range(1, height):
        choices = np.stack((score, np.r_[np.inf, score[:-1]], np.r_[score[1:], np.inf]))
        index = choices.argmin(axis=0)
        parents[y] = np.array([0, -1, 1], dtype=np.int8)[index]
        score = choices[index, np.arange(width)] + cost[y]
    if not np.isfinite(score).any():
        raise ValueError('No safe ownership path')
    path = np.empty(height, dtype=np.int32)
    path[-1] = score.argmin()
    for y in range(height-1, 0, -1):
        path[y-1] = path[y] + parents[y, path[y]]
    return path


def gradient(image):
    gray = np.asarray(image, dtype=np.float32).mean(axis=2)
    gy, gx = np.gradient(gray)
    return np.hypot(gx, gy)


def seam_mask(old, new, *, axis=1, force_old=None, force_new=None):
    """Return new-side ownership within aligned overlap, plus cut diagnostics.

    Axis 1: new to right. Axis 0: new below. Every output pixel stays at its
    existing global coordinate. No resampling or blurring.
    """
    if old.shape != new.shape or old.ndim != 3 or old.shape[2] != 3 or axis not in (0, 1):
        raise ValueError('Aligned RGB arrays and axis 0/1 required')
    a, b = (old, new) if axis == 1 else (old.transpose(1, 0, 2), new.transpose(1, 0, 2))
    h, w = a.shape[:2]
    difference = np.abs(a.astype(float)-b.astype(float)).mean(axis=2)
    # Penalize cutting high contrast roof/curb edges, rather than just matching colors.
    cost = difference + .5*np.abs(gradient(a)-gradient(b)) + .2*np.maximum(gradient(a), gradient(b))
    cost += .02*np.abs(np.arange(w)[None, :]-(w-1)/2)
    margin = min(8, (w-1)//2)
    cost[:, :margin] = np.inf
    if margin: cost[:, -margin:] = np.inf
    for forced, new_side in [(force_old, False), (force_new, True)]:
        if forced is None: continue
        if forced.shape != old.shape[:2]: raise ValueError('Ownership mask dimensions differ')
        mask = forced if axis == 1 else forced.T
        for y in range(h):
            xs = np.flatnonzero(mask[y])
            if xs.size:
                # New owns x >= cut; old owns x < cut.
                if new_side: cost[y, xs.min()+1:] = np.inf
                else: cost[y, :xs.max()+1] = np.inf
    path = minimum_path(cost)
    mask = np.arange(w)[None, :] >= path[:, None]
    report = {'path': path.tolist(), 'mean_cut_rgb_difference': float(difference[np.arange(h), path].mean()),
              'center_cut_rgb_difference': float(difference[:, w//2].mean()),
              'geometric_transform': False, 'feather_px': 0}
    return (mask if axis == 1 else mask.T), report


def bounded_repair(base, repaired, mask, *, feather=0):
    """Hard-mask accepted native edit, never trust model preservation outside it."""
    if base.shape != repaired.shape or mask.shape != base.shape[:2]:
        raise ValueError('Repair dimensions changed')
    if not mask.any() or np.count_nonzero(mask) > mask.size/4:
        raise ValueError('Repair must cover >0 and <=25% of context')
    if feather not in (0,1,2,3,4): raise ValueError('Feather must be 0..4 native pixels')
    out = base.copy()
    inside=mask.astype(bool)
    if feather:
        alpha=inside.astype(float)/feather
        eroded=Image.fromarray(inside.astype('uint8')*255)
        for _ in range(feather-1):
            eroded=eroded.filter(ImageFilter.MinFilter(3))
            alpha+=(np.asarray(eroded)>0)/feather
        out=np.rint(base*(1-alpha[:,:,None])+repaired*alpha[:,:,None]).astype('uint8')
    else: out[inside] = repaired[inside]
    return out


def inputs(source):
    report = read(source/'assembly_report.json')
    ledger = read(source/'report.json')
    result = {}
    for r in range(4):
        for c in range(6):
            name = f'background_{r}_{c}_raw.png'
            if (r,c) == (2,2): name = 'background_2_2_ground_v2.png'
            if (r,c) == (1,5):
                if not any(q['name']=='background_1_5_retry1' and q['status']=='complete' for q in ledger['requests']):
                    raise ValueError('Missing completed retry provenance')
                name = 'background_1_5_retry1_raw.png'
            im = Image.open(source/name).convert('RGB')
            if im.size != (1024,1024): raise ValueError('Native tile dimensions changed')
            offset = report['color_offsets'][f'{r}_{c}']
            result[(r,c)] = (np.rint(np.clip(np.asarray(im, dtype=float)+offset,0,255)).astype('uint8'), name)
    return result


def compose_landmarks(source, background):
    im = Image.fromarray(background).convert('RGBA')
    g = read(source/'landmark_composition_review.json')['gwanghwamun']
    layers = [{'id':'gwanghwamun','rect':g['rect'],'reveal_only':False}]
    layers += read(source/'landmark_reuse_candidates.json')['landmarks']
    for item in layers:
        if not item['reveal_only']:
            im.alpha_composite(Image.open(source/(item['id']+'_dense_sprite_candidate.png')).convert('RGBA'), tuple(item['rect'][:2]))
    return im.convert('RGB')


def pilot(source, dest):
    """Gwanghwamun 1_2 / 2_2; immutable baseline plus only the core-width overlap."""
    if dest.exists(): raise ValueError('Use a new output directory')
    tiles = inputs(source)
    a, b = tiles[(1,2)][0][768:1024,128:896], tiles[(2,2)][0][:256,128:896]
    # Global rectangle encloses the old gate roof/body plus attached wall ends.
    # Force the removal-complete 2_2 background here, never a mix of gate/no gate.
    rect = [1918,1512,2110,1632]
    forced = np.zeros(a.shape[:2], dtype=bool)
    forced[rect[1]-1408:rect[3]-1408,rect[0]-1536:rect[2]-1536] = True
    mask, report = seam_mask(a,b,axis=0,force_new=forced)
    baseline = np.asarray(Image.open(source/'dense_background_candidate.png').convert('RGB'))
    output = baseline.copy()
    output[1408:1664,1536:2304] = np.where(mask[:,:,None],b,a)
    dest.mkdir(parents=True)
    write(dest/'frozen_inputs.json', {'source':str(source.resolve()),
          'sha256':{name:sha(source/name) for name in ['dense_background_candidate.png','assembly_report.json',tiles[(1,2)][1],tiles[(2,2)][1]]},
          'scope':[1536,1408,2304,1664], 'forced_owner':{'tile':'2_2','rect':rect},
          'note':'Gate-ground ownership fixed before evaluation; no geometry acceptance implied.'})
    Image.fromarray(output).save(dest/'background.png')
    final = compose_landmarks(source, output)
    final.save(dest/'candidate.png')
    final.resize((1536,1024),Image.Resampling.NEAREST).save(dest/'preview.png')
    Image.fromarray(mask.astype('uint8')*255).save(dest/'ownership.png')
    box=(1820,1360,2220,1720)
    sheet=Image.new('RGB',(1200,390),'#222222'); d=ImageDraw.Draw(sheet)
    before=Image.open(source/'dense_full_24_candidate.png').convert('RGB')
    for i,(label,im) in enumerate([('BEFORE: 32px blend',before),('AFTER: ownership',final),('AFTER: gate hidden',Image.fromarray(output))]):
        sheet.paste(im.crop(box),(i*400,30)); d.text((i*400+6,8),label,fill='white')
    sheet.save(dest/'pilot_comparison.png')
    changed=np.any(output!=baseline,axis=2); outside=changed.copy(); outside[1408:1664,1536:2304]=False
    report.update(changed_pixels=int(changed.sum()), outside_overlap_changes=int(outside.sum()),
                  forced_owner_exact=bool(np.array_equal(output[rect[1]:rect[3],rect[0]:rect[2]],tiles[(2,2)][0][rect[1]-1408:rect[3]-1408,rect[0]-1408:rect[2]-1408])),
                  technical_passed=not outside.any(), visual_passed=False, geometry_passed=False,
                  public_release_accepted=False, paid_calls=0)
    write(dest/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='path'}))


def mosaic(tiles, *, rows, columns, core, halo, forced=None):
    """Row-major image quilting with one owner per pixel, including L overlaps.

    In the top-left intersection new ownership is the intersection of the two
    cut masks. Old pixels keep their existing owner; no four-way averaging.
    """
    size=core+2*halo
    if set(tiles)!={(r,c) for r in range(rows) for c in range(columns)}:
        raise ValueError('Complete rectangular grid required')
    height,width=rows*core,columns*core
    canvas=np.zeros((height,width,3),dtype=np.uint8)
    owner=np.full((height,width),-1,dtype=np.int16)
    coverage=np.zeros((height,width),dtype=np.uint8)
    forced=np.full_like(owner,-1) if forced is None else forced
    if forced.shape!=owner.shape: raise ValueError('Forced owner dimensions differ')
    reports=[]
    for (r,c),im in sorted(tiles.items()):
        if im.shape!=(size,size,3): raise ValueError('Tile dimensions differ')
        ident=r*columns+c
        x,y=c*core-halo,r*core-halo
        l,t,rr,bb=max(0,x),max(0,y),min(width,x+size),min(height,y+size)
        a=canvas[t:bb,l:rr]; old=owner[t:bb,l:rr]
        b=im[t-y:bb-y,l-x:rr-x]; known=old>=0
        choose=np.ones(known.shape,dtype=bool)
        force=forced[t:bb,l:rr]
        new_locked=force==ident
        old_locked=(force>=0)&(force==old)
        for axis,extent,neighbor in [(1,2*halo if c else 0,(r,c-1)),(0,2*halo if r else 0,(r-1,c))]:
            if not extent: continue
            sl=(slice(None),slice(0,extent)) if axis==1 else (slice(0,extent),slice(None))
            cut,entry=seam_mask(a[sl],b[sl],axis=axis,
                                force_old=old_locked[sl],force_new=new_locked[sl])
            choose[sl]&=cut
            entry.update(tile=[r,c],neighbor=list(neighbor),axis=axis,
                         comparison='incoming tile versus current row-major composite',
                         bounds=[l,t,rr,bb],visual_passed=False,geometry_passed=False)
            reports.append(entry)
        choose[~known]=True
        # An explicit owner is only applied where that tile is actually available.
        choose[new_locked]=True; choose[old_locked]=False
        a[choose]=b[choose]; old[choose]=ident
        coverage[t:bb,l:rr]+=1
    if (owner<0).any(): raise AssertionError('Uncovered canvas')
    if np.any((forced>=0)&(owner!=forced)): raise ValueError('Forced owner unavailable')
    return canvas,owner,coverage,reports


def full(source,dest,pilot_dir):
    review=read(pilot_dir/'review.json')
    if review.get('pilot_visual_passed') is not True or review.get('report_sha256')!=sha(pilot_dir/'report.json'):
        raise ValueError('Reviewed pilot required; no automatic visual approval')
    pinned=read(pilot_dir/'frozen_inputs.json')['sha256']
    if any(sha(source/name)!=digest for name,digest in pinned.items()):
        raise ValueError('Pilot source changed')
    if dest.exists(): raise ValueError('Use a new output directory')
    tiles=inputs(source)
    baseline=np.asarray(Image.open(source/'dense_background_candidate.png').convert('RGB'))
    forced=np.full(baseline.shape[:2],-1,dtype=np.int16)
    forced[1512:1632,1918:2110]=14
    # Gate ground and attached wall ends use the removal-complete bottom tile.
    # All constraints are stored before assembly.
    dest.mkdir(parents=True)
    write(dest/'frozen_inputs.json',{'source':str(source.resolve()),
          'sha256':{name:sha(source/name) for name in ['dense_background_candidate.png','assembly_report.json']+[v[1] for v in tiles.values()]},
          'forced_owner':[{'tile':[2,2],'rect':[1918,1512,2110,1632]}],
          'scope':'Only 256px overlap bands; color offsets fixed; no transform',
          'pilot_review_sha256':sha(pilot_dir/'review.json')})
    output,owner,coverage,reports=mosaic({k:v[0] for k,v in tiles.items()},rows=4,columns=6,core=768,halo=128,forced=forced)
    # Preserve exact baseline byte rounding outside overlap bands.
    output[coverage==1]=baseline[coverage==1]
    Image.fromarray(output).save(dest/'background.png')
    Image.fromarray(owner.astype('uint8')).save(dest/'ownership.png')
    Image.fromarray(coverage).save(dest/'coverage.png')
    final=compose_landmarks(source,output); final.save(dest/'candidate.png')
    final.resize((1536,1024),Image.Resampling.NEAREST).save(dest/'preview.png')
    before=Image.open(source/'dense_full_24_candidate.png').convert('RGB')
    seam_dir=dest/'seams'; seam_dir.mkdir()
    atlas=Image.new('RGB',(1200,1200),'#222222'); ad=ImageDraw.Draw(atlas)
    for i,entry in enumerate(reports):
        r,c=entry['tile']; axis=entry['axis']
        if axis==1: box=(c*768-128,r*768,c*768+128,(r+1)*768)
        else: box=(c*768,r*768-128,(c+1)*768,r*768+128)
        aa,bb=before.crop(box),final.crop(box)
        if axis==0: aa=aa.transpose(Image.Transpose.TRANSPOSE); bb=bb.transpose(Image.Transpose.TRANSPOSE)
        pair=Image.new('RGB',(512,792),'#222222'); pd=ImageDraw.Draw(pair)
        pair.paste(aa,(0,24)); pair.paste(bb,(256,24))
        name=f'{entry["neighbor"][0]}_{entry["neighbor"][1]}__{r}_{c}'
        pd.text((5,6),name+' / BEFORE | AFTER',fill='white'); pair.save(seam_dir/(name+'.png'))
        entry['comparison_image']='seams/'+name+'.png'
        # Contact atlas is navigation only; individual strips remain native pixels.
        thumb=pair.resize((120,186),Image.Resampling.NEAREST)
        atlas.paste(thumb,((i%10)*120,(i//10)*210+20))
        ad.text(((i%10)*120,(i//10)*210+5),name,fill='white')
    atlas.crop((0,0,1200,840)).save(dest/'seam_atlas.png')
    junctions=[]
    for r in range(1,4):
        for c in range(1,6):
            box=(c*768-128,r*768-128,c*768+128,r*768+128)
            pair=Image.new('RGB',(512,280),'#222222'); pd=ImageDraw.Draw(pair)
            pair.paste(before.crop(box),(0,24)); pair.paste(final.crop(box),(256,24))
            name=f'junction_{r}_{c}.png'; pd.text((5,5),name+' / BEFORE | AFTER',fill='white')
            pair.save(seam_dir/name)
            junctions.append({'row':r,'column':c,'comparison_image':'seams/'+name,'visual_passed':False})
    changed=np.any(output!=baseline,axis=2)
    summary={'seams':reports,'junctions':junctions,'seam_count':len(reports),'junction_count':len(junctions),
             'uncovered_pixels':int((coverage==0).sum()),'changed_pixels':int(changed.sum()),
             'outside_overlap_changes':int((changed&(coverage<2)).sum()),'geometry_warp':False,'feather_px':0,
             'forced_owner_exact':bool(np.all(owner[forced>=0]==forced[forced>=0])),
             'visual_passed':False,'geometry_passed':False,'public_release_accepted':False,'paid_calls':0}
    write(dest/'report.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('seams','junctions')}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['pilot','full'])
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--dest',type=Path,required=True)
    p.add_argument('--pilot',type=Path)
    args=p.parse_args()
    if args.command=='pilot': pilot(args.source,args.dest)
    else:
        if args.pilot is None: p.error('--pilot required')
        full(args.source,args.dest,args.pilot)
