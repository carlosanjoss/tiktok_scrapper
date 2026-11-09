import os
import re
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

from loguru import logger
from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from yt_dlp import YoutubeDL


_PROFILE_RE = re.compile(r"^@([A-Za-z0-9._-]+)$")
_VIDEO_RE = re.compile(r"/(@[^/]+)/video/(\d+)", re.IGNORECASE)


def extract_profile_username(profile_url: str) -> Optional[str]:
    value = unquote((profile_url or "").strip())
    if match := _PROFILE_RE.fullmatch(value):
        return match.group(1)

    if not value.lower().startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.netloc.lower().removeprefix("www.") != "tiktok.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts or not parts[0].startswith("@"):
        return None
    username = parts[0][1:]
    return username if _PROFILE_RE.fullmatch("@" + username) else None


def canonical_video_url(value: str) -> Optional[str]:
    if not value:
        return None
    if value.startswith("/"):
        value = "https://www.tiktok.com" + value
    parsed = urlparse(value)
    match = _VIDEO_RE.search(parsed.path)
    if not match:
        return None
    return f"https://www.tiktok.com/{match.group(1)}/video/{match.group(2)}"


def download_video(video_url: str, output_dir: str, overwrite: bool = False) -> None:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with YoutubeDL(
        {
            "format": "best[ext=mp4]/best",
            "outtmpl": str(Path(output_dir) / "%(id)s.%(ext)s"),
            "writeinfojson": True,
            "overwrites": overwrite,
            "continuedl": True,
            "retries": 5,
            "socket_timeout": 60,
            "quiet": True,
            "noprogress": True,
            "no_warnings": True,
        }
    ) as ydl:
        ydl.download([video_url])


def _find_browser_executable() -> Optional[str]:
    configured = (os.getenv("BROWSER_EXECUTABLE_PATH") or "").strip()
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise RuntimeError(f"BROWSER_EXECUTABLE_PATH não existe: {path}")
        return str(path)

    candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    return next((str(path) for path in candidates if path.is_file()), None)


class ProfileVideoDiscoverer:
    def __init__(
        self,
        headless: bool = True,
        profile_dir: str = "data/browser_profile",
        page_timeout_seconds: int = 45,
        debug_dir: str = "data/debug",
    ) -> None:
        self.headless = headless
        self.profile_dir = Path(profile_dir)
        self.page_timeout_ms = page_timeout_seconds * 1000
        self.debug_dir = Path(debug_dir)
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None

    def __enter__(self):
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        return self

    def _start_browser(self) -> None:
        if self._context:
            return
        self._playwright = sync_playwright().start()
        options = {
            "headless": self.headless,
            "locale": "pt-BR",
            "viewport": {"width": 1366, "height": 900},
            "args": ["--disable-quic", "--disable-notifications"],
        }
        executable = _find_browser_executable()
        if executable:
            options["executable_path"] = executable
        self._context = self._playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            **options,
        )

    def __exit__(self, exc_type, exc, traceback):
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()

    def discover(
        self,
        profile_url: str,
        max_videos: int = 20,
        max_scrolls: int = 20,
        stable_scrolls: int = 3,
    ) -> List[str]:
        username = extract_profile_username(profile_url)
        if not username:
            raise ValueError(f"URL de perfil TikTok inválida: {profile_url}")

        canonical_profile = f"https://www.tiktok.com/@{username}"
        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                with YoutubeDL(
                    {
                        "extract_flat": True,
                        "skip_download": True,
                        "playlistend": max_videos,
                        "quiet": True,
                        "no_warnings": True,
                        "socket_timeout": 30,
                    }
                ) as ydl:
                    info = ydl.extract_info(canonical_profile, download=False)
                discovered = []
                seen = set()
                for entry in (info or {}).get("entries") or []:
                    video_url = canonical_video_url(
                        entry.get("webpage_url") or entry.get("url") or ""
                    )
                    if video_url and video_url not in seen:
                        seen.add(video_url)
                        discovered.append(video_url)
                if discovered:
                    logger.info(
                        "@%s: %d vídeo(s) descoberto(s) via yt-dlp"
                        % (username, len(discovered))
                    )
                    return discovered[:max_videos]
            except Exception as error:
                last_error = error
                logger.warning(
                    "yt-dlp falhou para @%s (tentativa %d/3): %s"
                    % (username, attempt, error)
                )
                if attempt < 3:
                    time.sleep(attempt)

        logger.warning(
            "tentativas via yt-dlp esgotadas para @%s; tentando navegador: %s"
            % (username, last_error or "nenhum vídeo retornado")
        )

        self._start_browser()
        assert self._context is not None
        page: Page = self._context.new_page()
        page.set_default_timeout(self.page_timeout_ms)
        try:
            response = page.goto(canonical_profile, wait_until="domcontentloaded")
            if response and response.status >= 400:
                raise RuntimeError(
                    f"TikTok respondeu HTTP {response.status} para {canonical_profile}"
                )
            # A grade do TikTok e renderizada de forma lazy. Bloquear imagens ou
            # encerrar cedo demais deixa apenas os placeholders no DOM.
            try:
                page.wait_for_selector(
                    'a[href*="/video/"]',
                    timeout=self.page_timeout_ms if not self.headless else 10000,
                )
            except Exception:
                page.wait_for_timeout(2500)

            discovered = []
            seen = set()
            unchanged_rounds = 0
            for _ in range(max_scrolls + 1):
                hrefs = page.locator('a[href*="/video/"]').evaluate_all(
                    "elements => elements.map(element => element.href)"
                )
                before = len(seen)
                for href in hrefs:
                    video_url = canonical_video_url(href)
                    if video_url and video_url not in seen:
                        seen.add(video_url)
                        discovered.append(video_url)
                        if max_videos > 0 and len(discovered) >= max_videos:
                            return discovered[:max_videos]

                unchanged_rounds = unchanged_rounds + 1 if len(seen) == before else 0
                if unchanged_rounds >= stable_scrolls:
                    break
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1800)

            if not discovered:
                body = page.locator("body").inner_text().lower()
                self.debug_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(self.debug_dir / f"profile_{username}.png"),
                    full_page=True,
                )
                (self.debug_dir / f"profile_{username}.html").write_text(
                    page.content(), encoding="utf-8"
                )
                if "captcha" in body or "verify" in body or "verifique" in body:
                    raise RuntimeError(
                        "TikTok solicitou verificação. Rode novamente com --headed e "
                        "conclua o CAPTCHA no navegador persistente."
                    )
                raise RuntimeError(
                    f"Nenhum vídeo público foi encontrado em @{username}. "
                    f"Página final: {page.url}. Título: {page.title()!r}. "
                    "Diagnóstico salvo em data/debug."
                )
            logger.info("@%s: %d vídeo(s) descoberto(s)" % (username, len(discovered)))
            return discovered
        finally:
            page.close()
