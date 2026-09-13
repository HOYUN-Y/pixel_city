"""개발용 정적 서버. `python3 -m http.server`와 같되 **캐시 재검증을 강제한다.**

`http.server`는 캐시 헤더를 전혀 보내지 않아 크롬이 휴리스틱 캐싱을 한다.
그래서 `app.js`를 고쳐도 페이지가 옛 코드를 계속 쓰고, `export.py`를 돌려도
옛 `city.json`을 계속 쓴다 — 실제로 이 프로젝트에서 반복해 겪었다.
강력 새로고침이나 `?v=N`으로 매번 우회하는 대신 여기서 끝낸다
(`index.html`의 `<script src="app.js">`에는 버전이 없어 `?v=N`이 애초에 안 통한다).

`no-cache`는 캐시를 버리는 게 아니라 **매번 재검증**하게 한다. 안 바뀐 파일은
304로 돌아와 비용이 거의 없다.

    python3 serve.py [포트]      # 기본 8765
"""
import functools, http.server, socketserver, sys


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):          # 404만 찍는다. 200 로그는 시끄럽다
        if not str(args[1] if len(args) > 1 else "").startswith("2"):
            super().log_message(fmt, *args)


def main(port=8765):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as srv:
        print(f"http://127.0.0.1:{port}/   (Cache-Control: no-cache)")
        srv.serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
