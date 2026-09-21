"""Offline road review: immutable evidence sheets and uncertainty-aware measurements.

Annotations are an operator's visible-road observations, never an automatic
segmentation or geographic certification. No network calls or release approval.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def classify_distance(distance, uncertainty, limit=4):
    if not all(math.isfinite(v) and v >= 0 for v in (distance, uncertainty, limit)):
        raise ValueError('Invalid measurement')
    if distance + uncertainty <= limit:
        return 'pass'
    if distance - uncertainty > limit:
        return 'needs_repair'
    return 'inconclusive'


def measure(control):
    if control.get('output') is None or control.get('source') is None:
        return dict(control, status='inconclusive', reason='Correspondence not visible')
    a, b = np.asarray(control['source'], float), np.asarray(control['output'], float)
    if a.shape != (2,) or b.shape != (2,) or not np.isfinite([a, b]).all():
        raise ValueError('Invalid control coordinates')
    delta = b - a
    if control['kind'] == 'edge':
        n = np.asarray(control['normal'], float)
        if n.shape != (2,) or not np.isfinite(n).all() or np.linalg.norm(n) == 0:
            raise ValueError('Invalid edge normal')
        distance = abs(float(np.dot(delta, n / np.linalg.norm(n))))
    elif control['kind'] == 'corner':
        distance = float(np.linalg.norm(delta))
    else:
        raise ValueError('Unknown control kind')
    uncertainty = control['uncertainty_px']
    return dict(control, distance_px=distance,
                status=classify_distance(distance, uncertainty))


def inventory():
    items = []
    for r in range(4):
        for c in range(5):
            x, y = (c+1)*768, r*768
            items.append({'id': f'v{r}_{c}', 'kind': 'seam', 'rotate': True,
                          'box': [x-128, y, x+128, y+768]})
    for r in range(3):
        for c in range(6):
            x, y = c*768, (r+1)*768
            items.append({'id': f'h{r}_{c}', 'kind': 'seam', 'rotate': False,
                          'box': [x, y-128, x+768, y+128]})
    for r in range(3):
        for c in range(5):
            x, y = (c+1)*768, (r+1)*768
            items.append({'id': f'j{r}_{c}', 'kind': 'junction', 'rotate': False,
                          'box': [x-128, y-128, x+128, y+128]})
    return items


def corridor_checks(records, mask, rect, allowance=2):
    """Classify centers only inside a hand-reviewed corridor's x interval.

    Dilate/erode the traced corridor to keep boundary readings inconclusive.
    This is final-art containment, not source alignment or full sprite collision.
    """
    if mask.mode != 'L' or mask.size != (rect[2]-rect[0], rect[3]-rect[1]):
        raise ValueError('Corridor mask size/mode mismatch')
    if type(allowance) is not int or allowance < 0 or allowance > 4:
        raise ValueError('Invalid boundary allowance')
    inner = np.asarray(mask.filter(ImageFilter.MinFilter(2*allowance+1))) > 127
    outer = np.asarray(mask.filter(ImageFilter.MaxFilter(2*allowance+1))) > 127
    result = []
    for item in records:
        x, y = item['xy']
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('Nonfinite vehicle center')
        if not rect[0]+allowance <= x < rect[2]-allowance:
            status = 'outside_review_scope'
        else:
            ix, iy = math.floor(x-rect[0]), math.floor(y-rect[1])
            if not 0 <= iy < mask.height or not outer[iy, ix]:
                status = 'outside_road'
            elif inner[iy, ix]:
                status = 'inside_road'
            else:
                status = 'boundary_uncertain'
        result.append(dict(item, road_status=status))
    return {'counts': {s: sum(r['road_status'] == s for r in result) for s in
                       ('inside_road', 'outside_road', 'boundary_uncertain', 'outside_review_scope')},
            'records': result}


def atlas(source, final, items, dest, name, per_page=4):
    for start in range(0, len(items), per_page):
        page = Image.new('RGB', (1536, 280*min(per_page, len(items)-start)), '#202020')
        draw = ImageDraw.Draw(page)
        for row, item in enumerate(items[start:start+per_page]):
            for col, (label, im) in enumerate([('SOURCE', source), ('FINAL', final)]):
                crop = im.crop(item['box'])
                if item.get('rotate'):
                    crop = crop.transpose(Image.Transpose.ROTATE_90)
                page.paste(crop, (col*768, row*280+24))
                draw.text((col*768+4, row*280+4), f"{item['id']} {label} {item['box']}" +
                          (' rotated90' if item.get('rotate') else ''), fill='white')
        page.save(dest/f'{name}_{start//per_page:02d}.png')


def prepare(source, final, dest):
    if dest.exists():
        raise ValueError('Use a new review directory')
    a, b = Image.open(source).convert('RGB'), Image.open(final).convert('RGB')
    if a.size != (4608, 3072) or b.size != a.size:
        raise ValueError('Dense image size changed')
    dest.mkdir(parents=True)
    items = inventory()
    write(dest/'inputs.json', {'source': str(source.resolve()), 'source_sha256': sha(source),
                             'final': str(final.resolve()), 'final_sha256': sha(final)})
    write(dest/'inventory.json', items)
    atlas(a, b, items[:38], dest, 'seams')
    atlas(a, b, items[38:], dest, 'junctions')
    for r in range(4):
        page = Image.new('RGB', (768, 6*408), '#202020')
        draw = ImageDraw.Draw(page)
        for c in range(6):
            box = [c*768, r*768, (c+1)*768, (r+1)*768]
            for col, im in enumerate([a, b]):
                page.paste(im.crop(box).resize((384, 384), Image.Resampling.NEAREST),
                           (col*384, c*408+24))
                draw.text((col*384+4, c*408+4), f'{r}_{c} overview 50%', fill='white')
        page.save(dest/f'tiles_{r}.png')
    overview = b.resize((1536, 1024), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(overview)
    for x in range(768, 4608, 768):
        draw.line((x//3, 0, x//3, 1024), fill='magenta')
    for y in range(768, 3072, 768):
        draw.line((0, y//3, 1536, y//3), fill='magenta')
    for r in range(4):
        for c in range(6):
            draw.text((c*256+5, r*256+5), f'{r}_{c}', fill='white', stroke_width=2, stroke_fill='black')
    overview.save(dest/'overview_grid.png')


def review(dest, annotations):
    inputs = read(dest/'inputs.json')
    for key in ('source', 'final'):
        if sha(Path(inputs[key])) != inputs[key+'_sha256']:
            raise ValueError('Frozen image changed')
    data = read(annotations)
    if data['inputs'] != inputs:
        raise ValueError('Annotations refer to different images')
    frozen = dest/'source_controls_frozen.json'
    if frozen.exists():
        expected_controls = read(frozen)
        actual_controls = [{k: v for k, v in c.items() if k != 'output'} for c in data['controls']]
        if (expected_controls['source_sha256'] != inputs['source_sha256'] or
                expected_controls['controls'] != actual_controls):
            raise ValueError('Frozen source controls changed')
    expected = {i['id'] for i in inventory()}
    if set(data['regions']) != expected:
        raise ValueError('Incomplete seam/junction inventory')
    allowed = {'visible_road', 'no_visible_road', 'occluded_or_ambiguous'}
    for entry in data['regions'].values():
        if entry['visibility'] not in allowed or not entry['note']:
            raise ValueError('Missing region evidence')
    controls = [measure(c) for c in data['controls']]
    report = {'inputs': inputs, 'annotation_sha256': sha(annotations),
              'regions': data['regions'], 'controls': controls,
              'width_reviews': data.get('width_reviews', []),
              'counts': {s: sum(c['status'] == s for c in controls)
                         for s in ('pass', 'needs_repair', 'inconclusive')},
              'limit_native_px': 4, 'all_roads_passed': False,
              'geometryPassed': False, 'public_release_accepted': False,
              'note': 'Only explicitly annotated visible correspondences are measured. '
                      'Overview inspection is not a 4px certificate for entire regions.'}
    write(dest/'road_review.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['prepare', 'review'])
    p.add_argument('--source', type=Path)
    p.add_argument('--final', type=Path)
    p.add_argument('--dest', type=Path, required=True)
    p.add_argument('--annotations', type=Path)
    args = p.parse_args()
    if args.mode == 'prepare':
        if not args.source or not args.final:
            p.error('prepare requires --source and --final')
        prepare(args.source, args.final, args.dest)
    else:
        if not args.annotations:
            p.error('review requires --annotations')
        print(json.dumps(review(args.dest, args.annotations), ensure_ascii=False))
