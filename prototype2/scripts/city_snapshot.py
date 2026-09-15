"""Read-only TourAPI import and explicit allowlist for the feedback beta."""
import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from shutil import copyfile

P2 = Path(__file__).resolve().parents[1]
SOURCE = Path('/Users/lyuhoyun/Library/CloudStorage/GoogleDrive-hoyun0131.pro@gmail.com/My Drive/projects/pixel_city/tourapi/20260915T001245036104+0900')
RUN = P2 / 'eval/vworld/landmark_link/runs/20260915T130211965290Z'
DEST = P2 / 'assets/city_pilot'

class Plain(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.skip += 1
        if tag in ('br', 'p', 'li'): self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.skip = max(0, self.skip - 1)
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)

def plain(value, limit=2200):
    p = Plain(); p.feed(str(value or ''))
    return ' '.join(''.join(p.parts).split())[:limit]

def read(path): return json.loads(path.read_text())
def write(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def build(source=SOURCE, dest=DEST):
    dest.mkdir(parents=True, exist_ok=True)
    meta = read(source / 'manifest.json')
    if meta['status'] != 'complete': raise ValueError('Incomplete source collection')
    places = []
    for row in read(source / 'places.json'):
        common = (row.get('common') or [{}])[0]
        data = {**row['listing'], **common}
        cid = str(row['contentid'])
        places.append({'id': cid, 'name': plain(data.get('title'), 160),
            'address': plain(data.get('addr1'), 300), 'type': str(data.get('contenttypeid', '')),
            'overview': plain(data.get('overview')), 'modifiedAt': data.get('modifiedtime', ''),
            'collectedAt': meta['collected_at'], 'source': '한국관광공사 TourAPI',
            'sourceUrl': 'https://www.data.go.kr/data/15101578/openapi.do',
            'contentId': cid, 'imageLicense': data.get('cpyrhtDivCd', ''),
            'coordinates': [float(data['mapx']), float(data['mapy'])] if data.get('mapx') and data.get('mapy') else None})
    landmarks = []
    for i, row in enumerate(read(source / 'landmarks.json')):
        landmarks.append({'id': 'landmark-' + str(i), 'name': row['name'], 'status': row['status'],
            'placeId': row.get('matched_contentid'), 'parentPlaceId': row.get('parent_contentid'),
            'note': row['review_note'], 'mapSpotId': 'jongno-tower' if row['name'] == '종로타워' else None})
    write(dest / 'places.json', {'version': 1, 'collectedAt': meta['collected_at'], 'places': places, 'landmarks': landmarks})
    files = ['before.png', 'final.png', 'sprite.png', 'hit.png', 'traveler.png', 'car_se.png', 'car_nw.png']
    for file in files: copyfile(RUN / file, dest / file)
    overlay = read(RUN / 'overlay.json'); overlay.pop('sunset', None)
    overlay['landmarks'] = [overlay.pop('landmark')]
    write(dest / 'overlay.json', overlay)
    manifest = read(RUN / 'manifest.json')
    manifest.update(kind='city-pilot', run_id='city-beta-20260916', asset_sha256={f: sha(dest / f) for f in files})
    scene = manifest['scenes']['jongno-link']; scene['variants'].pop('source')
    scene['label'] = '종로 픽셀 산책'; scene['review'] = 'AI 재해석 지도 · 실제 길찾기 아님 · 보신각 독립 외관은 가림으로 보류'
    manifest['overlay_sha256']['jongno-link'] = sha(dest / 'overlay.json')
    write(dest / 'manifest.json', manifest)
    write(dest / 'build.json', {'sourceRun': RUN.name, 'inputManifestSha256': sha(RUN / 'manifest.json'),
        'tourRun': source.name, 'sourceFiles': {f: sha(source / f) for f in ['manifest.json', 'places.json', 'landmarks.json']},
        'places': len(places), 'landmarks': len(landmarks), 'imageCalls': 0,
        'publicRightsApproved': False, 'excluded': ['raw captures', 'reference images', 'prompts', 'logs', 'local paths', 'TourAPI photos']})
    return {'places': len(places), 'landmarks': len(landmarks), 'output': str(dest)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--source', type=Path, default=SOURCE); parser.add_argument('--dest', type=Path, default=DEST)
    args = parser.parse_args(); print(json.dumps(build(args.source, args.dest), ensure_ascii=False))
