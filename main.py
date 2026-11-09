import os
import json
import time
import click

from datetime import datetime, timezone
from typing import Iterable, List, Optional

from loguru import logger

from tiktokcomment import TiktokComment, extract_aweme_id
from tiktokcomment.profile_discovery import (
    ProfileVideoDiscoverer,
    download_video,
    extract_profile_username,
)
from tiktokcomment.typing import Comments, Comment

__title__ = 'TikTok Comment Scrapper'
__version__ = '2.1.0'

DEFAULT_LINKS_FILE = 'links.txt'
DEFAULT_PROFILES_FILE = 'profiles.txt'


def resolve_output_dir(output: str) -> str:
    output_dir: str = output.rstrip("/\\")
    return output_dir or "data"


def count_comments(comments: Iterable[Comment]) -> int:
    total: int = 0
    for comment in comments:
        total += 1
        total += count_comments(comment.replies)
    return total


def read_links(links_file: str) -> List[str]:
    links: List[str] = []
    with open(links_file, 'r', encoding='utf-8') as f:
        for line in f:
            line: str = line.strip()
            if not line or line.startswith('#'):
                continue
            links.append(line)
    return links


def save_comments(comments: Comments, aweme_id: str, output_dir: str) -> str:
    output_dir = resolve_output_dir(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    final_path: str = os.path.join(output_dir, f"{aweme_id}.json")

    payload = {
        'aweme_id': aweme_id,
        'scraped_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total_comments': len(comments.comments),
        'total_comments_with_replies': count_comments(comments.comments),
        **comments.dict,
    }

    with open(final_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)

    return final_path


def save_profile_manifest(
    profile_url: str,
    video_urls: List[str],
    output_dir: str,
) -> str:
    username = extract_profile_username(profile_url)
    if not username:
        raise ValueError('invalid TikTok profile url: %s' % profile_url)
    profile_dir = os.path.join(resolve_output_dir(output_dir), 'profiles', username)
    os.makedirs(profile_dir, exist_ok=True)
    path = os.path.join(profile_dir, '_profile.json')
    payload = {
        'username': username,
        'profile_url': 'https://www.tiktok.com/@%s' % username,
        'discovered_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'video_count': len(video_urls),
        'video_urls': video_urls,
    }
    with open(path, 'w', encoding='utf-8') as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=4)
    return path


def scrape_one(
    tiktok: TiktokComment,
    raw_link: str,
    output_dir: str,
    overwrite: bool
) -> None:
    aweme_id: Optional[str] = extract_aweme_id(raw_link)
    if not aweme_id:
        logger.warning('could not extract a video id from "%s", skipping' % raw_link)
        return

    final_path: str = os.path.join(resolve_output_dir(output_dir), f"{aweme_id}.json")
    if not overwrite and os.path.exists(final_path):
        logger.info('skip %s, already collected at %s' % (aweme_id, final_path))
        return

    logger.info('start scrap comments %s' % aweme_id)
    try:
        comments: Comments = tiktok(aweme_id=aweme_id)
    except Exception as e:
        logger.error('failed to scrap %s: %s' % (aweme_id, e))
        return

    saved_path: str = save_comments(comments, aweme_id, output_dir)
    logger.info('save comments %s on %s' % (aweme_id, saved_path))


@click.command(
    help=__title__
)
@click.version_option(
    version=__version__,
    prog_name=__title__
)
@click.option(
    "--aweme_id",
    default=None,
    help='id or url of a single tiktok video'
)
@click.option(
    "--links-file", "-l",
    default=None,
    help='txt file with one tiktok link/id per line (defaults to links.txt if present)'
)
@click.option(
    "--profiles-file", "-p",
    default=None,
    help='txt file with one TikTok profile per line (defaults to profiles.txt if present)'
)
@click.option(
    "--output", "-o",
    default='data/',
    help='directory output data'
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help='re-scrap videos that already have a saved json in the output directory'
)
@click.option(
    "--delay",
    default=1.5,
    help='seconds to wait between videos when scraping from a links file'
)
@click.option(
    "--videos-per-profile",
    default=20,
    type=click.IntRange(min=1),
    help='maximum recent videos discovered per profile'
)
@click.option(
    "--profile-scrolls",
    default=20,
    type=click.IntRange(min=1),
    help='maximum scroll rounds used to discover profile videos'
)
@click.option(
    "--profile-delay",
    default=5.0,
    type=click.FloatRange(min=0),
    help='seconds to wait between profiles'
)
@click.option(
    "--headed",
    is_flag=True,
    default=False,
    help='show Chrome during profile discovery (useful for CAPTCHA/login)'
)
@click.option(
    "--discover-only",
    is_flag=True,
    default=False,
    help='discover and save video links without collecting comments'
)
@click.option(
    "--download-videos",
    is_flag=True,
    default=False,
    help='download each discovered video and its metadata into the profile folder'
)
def main(
    aweme_id: Optional[str],
    links_file: Optional[str],
    profiles_file: Optional[str],
    output: str,
    overwrite: bool,
    delay: float,
    videos_per_profile: int,
    profile_scrolls: int,
    profile_delay: float,
    headed: bool,
    discover_only: bool,
    download_videos: bool,
):
    tiktok: TiktokComment = TiktokComment()

    if aweme_id:
        resolved_id: Optional[str] = extract_aweme_id(aweme_id)
        if not resolved_id:
            raise ValueError('invalid --aweme_id, example: --aweme_id=7418294751977327878')
        scrape_one(tiktok, resolved_id, output, overwrite=True)
        return

    if not profiles_file and not links_file and os.path.exists(DEFAULT_PROFILES_FILE):
        profiles_file = DEFAULT_PROFILES_FILE

    if profiles_file:
        profiles: List[str] = read_links(profiles_file)
        if not profiles:
            logger.warning('%s has no profiles to scrape' % profiles_file)
            return
        logger.info('found %d profile(s) in %s' % (len(profiles), profiles_file))
        with ProfileVideoDiscoverer(headless=not headed) as discoverer:
            for profile_index, profile_url in enumerate(profiles, start=1):
                username = extract_profile_username(profile_url)
                logger.info(
                    '[profile %d/%d] discovering %s'
                    % (profile_index, len(profiles), profile_url)
                )
                if not username:
                    logger.warning('invalid profile url, skipping: %s' % profile_url)
                    continue
                try:
                    video_urls = discoverer.discover(
                        profile_url,
                        max_videos=videos_per_profile,
                        max_scrolls=profile_scrolls,
                    )
                except Exception as error:
                    logger.error('failed to discover %s: %s' % (profile_url, error))
                    continue

                profile_output = os.path.join(resolve_output_dir(output), 'profiles', username)
                manifest = save_profile_manifest(profile_url, video_urls, output)
                logger.info('saved profile manifest at %s' % manifest)
                if discover_only:
                    continue
                for video_index, video_url in enumerate(video_urls, start=1):
                    logger.info(
                        '[@%s %d/%d] processing %s'
                        % (username, video_index, len(video_urls), video_url)
                    )
                    if download_videos:
                        try:
                            download_video(
                                video_url,
                                os.path.join(profile_output, 'videos'),
                                overwrite=overwrite,
                            )
                        except Exception as error:
                            logger.error('failed to download %s: %s' % (video_url, error))
                    scrape_one(tiktok, video_url, profile_output, overwrite)
                    if video_index < len(video_urls):
                        time.sleep(delay)
                if profile_index < len(profiles):
                    time.sleep(profile_delay)
        return

    if not links_file:
        links_file = DEFAULT_LINKS_FILE if os.path.exists(DEFAULT_LINKS_FILE) else None

    if not links_file:
        raise ValueError(
            'no --aweme_id given and no links file found. '
            'Pass --aweme_id=<id or url>, use --links-file=<path>, '
            'or create a "%s" with one link per line.' % DEFAULT_LINKS_FILE
        )

    links: List[str] = read_links(links_file)
    if not links:
        logger.warning('%s has no links to scrap' % links_file)
        return

    logger.info('found %d link(s) in %s' % (len(links), links_file))
    for index, raw_link in enumerate(links, start=1):
        logger.info('[%d/%d] processing %s' % (index, len(links), raw_link))
        scrape_one(tiktok, raw_link, output, overwrite)
        if index < len(links):
            time.sleep(delay)


if __name__ == '__main__':
    main()
