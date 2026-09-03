"""국가유산청 개방 사진 -> 랜드마크 픽셀 스프라이트.

국가유산청 Open API는 **인증키가 필요 없다** (HTTPS 필수).
사진을 축소하고 팔레트로 양자화하면 픽셀 스프라이트가 된다.

발견: 확산 모델이 필요 없다. 3/4 부감으로 찍힌 사진이 실제로 있어
시점 변환도 불필요하다. 자세한 경위는 docs/WORKLOG.md 참조.

    python landmark.py 근정전            # 후보 목록 + 컨택트시트
    python landmark.py 근정전 --pick 10  # 10번 사진으로 스프라이트 생성
"""
import io, json, os, re, ssl, sys, urllib.request

API = "https://www.khs.go.kr/cha"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE          # 국가유산청 인증서 체인이 불완전하다

# 대상 전각. ccbaKdcd=종목(11 국보), ccbaCtcd=시도(11 서울), ccbaAsno=지정번호
LANDMARKS = {
    "근정전":   ("11", "0002230000000", "11", "경복궁 근정전"),
    "경회루":   ("11", "0002240000000", "11", "경복궁 경회루"),
    "인정전":   ("11", "0002250000000", "11", "창덕궁 인정전"),
    "명정전":   ("11", "0002260000000", "11", "창경궁 명정전"),
    "종묘정전": ("11", "0002270000000", "11", "종묘 정전"),
    "숭례문":   ("11", "0000010000000", "11", "서울 숭례문"),
}
# 세부 사진 — 외관 스프라이트에 쓸 수 없다
DETAIL = ("내부", "천장", "현판", "옥좌", "가구", "쌍용", "어좌", "공포", "막새", "잡상",
          "초석", "문양", "해태", "동물상", "측우대", "누기")
# ponytail: imageNuri 코드 A/B/C/D가 공공누리 몇 유형인지 공식 문서에 없다.
# A가 제1유형(출처표시)이라는 가정으로 A만 쓴다. 국가유산청 042-481-4715 확인 필요.
SAFE_NURI = ("A",)


def _get(url):
    return urllib.request.urlopen(url, timeout=30, context=CTX).read()


def images(key):
    """전각의 외관 사진 후보 [(설명, url)]. 세부 사진과 비안전 라이선스는 뺀다."""
    kd, asno, ct, _ = LANDMARKS[key]
    x = _get(f"{API}/SearchImageOpenapi.do?ccbaKdcd={kd}&ccbaAsno={asno}&ccbaCtcd={ct}") \
        .decode("utf-8", "replace")
    nuri = re.findall(r"<imageNuri>(.*?)</imageNuri>", x)
    urls = re.findall(r"<imageUrl>(.*?)</imageUrl>", x)
    desc = [re.sub(r"</?!\[CDATA\[|\]\]>", "", d).strip()
            for d in re.findall(r"<ccimDesc>(.*?)</ccimDesc>", x, re.S)]
    return [(d, u.replace("http://", "https://"))
            for nu, u, d in zip(nuri, urls, desc)
            if nu in SAFE_NURI and not any(k in d for k in DETAIL)]


def cut_sky(im):
    """하늘 제거. 위 가장자리에서 흘러들어오는 하늘색 영역만 지운다.

    단순 색 임계값으로 지우면 단청의 청색까지 날아가므로 연결성을 본다.
    """
    import numpy as np
    a = np.asarray(im.convert("RGB")).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    sky = (b > r + 10) & (b > 85) & (g > 75)
    h, w = sky.shape
    out = np.zeros_like(sky)
    stack = [(0, c) for c in range(w) if sky[0, c]]           # 위 가장자리에서 시작
    while stack:                                              # ponytail: 파이썬 flood fill.
        y, xq = stack.pop()                                   # 사진 한 장이라 성능은 무관하다
        if y < 0 or y >= h or xq < 0 or xq >= w or out[y, xq] or not sky[y, xq]:
            continue
        out[y, xq] = True
        stack += [(y + 1, xq), (y - 1, xq), (y, xq + 1), (y, xq - 1)]
    from PIL import Image
    rgba = np.dstack([np.asarray(im.convert("RGB")),
                      np.where(out, 0, 255).astype(np.uint8)])
    cut = Image.fromarray(rgba, "RGBA")
    return cut.crop(cut.getchannel("A").getbbox())


def palette_img(style_path=None):
    from PIL import Image
    p = style_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.json")
    C = json.load(open(p, encoding="utf-8"))["colors"]
    pal = [C["ground"], [255, 255, 255]]
    for t in (C["palace"], C["hanok"]):
        pal += t
    pal += [[214, 210, 200], [176, 170, 158], [128, 122, 110], [92, 88, 80],   # 석재
            [118, 122, 128], [86, 92, 100], [58, 64, 72],                      # 기와
            [186, 98, 76], [140, 64, 52], [92, 46, 38],                        # 단청 적
            [96, 128, 112], [62, 90, 80],                                      # 단청 녹
            [196, 168, 96], [120, 96, 56]]                                     # 단청 황·목재
    flat = [v for c in pal for v in c]
    flat += [0] * (768 - len(flat))
    im = Image.new("P", (1, 1))
    im.putpalette(flat)
    return im


def sprite(im, width=112):
    """RGBA 이미지를 픽셀 스프라이트로. 디더링은 쓰지 않는다 — 노이즈만 생긴다."""
    import numpy as np
    from PIL import Image
    small = im.resize((width, max(1, round(width * im.height / im.width))), Image.LANCZOS)
    a = np.asarray(small)
    mask = a[..., 3] > 128
    q = Image.fromarray(a[..., :3]).quantize(palette=palette_img(),
                                             dither=Image.Dither.NONE).convert("RGB")
    return Image.fromarray(np.dstack([np.asarray(q),
                                      np.where(mask, 255, 0).astype(np.uint8)]), "RGBA")


def _selfcheck():
    from PIL import Image
    import numpy as np
    # 위쪽 절반이 하늘색, 아래 절반이 붉은 벽인 그림 -> 하늘만 지워야 한다
    a = np.zeros((20, 10, 3), np.uint8)
    a[:10] = (120, 150, 220); a[10:] = (180, 60, 40)
    cut = cut_sky(Image.fromarray(a))
    assert cut.size == (10, 10), cut.size
    assert np.asarray(cut)[..., 3].min() == 255
    sp = sprite(cut, 8)
    assert sp.size[0] == 8 and sp.mode == "RGBA"
    assert set(LANDMARKS) >= {"근정전", "경회루", "숭례문"}
    print("landmark selfcheck ok")


if __name__ == "__main__":
    _selfcheck()
    if len(sys.argv) < 2:
        print(__doc__); raise SystemExit
    key = sys.argv[1]
    cands = images(key)
    print(f"{LANDMARKS[key][3]} — 외관 후보 {len(cands)}장")
    for i, (d, _) in enumerate(cands):
        print(f"  {i:2d}. {d}")
    if "--pick" in sys.argv:
        from PIL import Image
        i = int(sys.argv[sys.argv.index("--pick") + 1])
        d, u = cands[i]
        src = Image.open(io.BytesIO(_get(u)))
        out = sprite(cut_sky(src))
        f = f"sprite_{key}.png"
        out.save(f)
        print(f"\n[{i}] {d}\n  원본 {src.size} -> 스프라이트 {out.size} -> {f}")
