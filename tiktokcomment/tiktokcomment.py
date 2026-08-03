import re
import jmespath

from typing import Any, Dict, Iterator
from requests import Session, Response
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util import Retry
from loguru import logger
from typing import Optional
from datetime import datetime
from tiktokcomment.typing import Comments, Comment

_VIDEO_ID_RE = re.compile(r'/video/(\d+)')

_DEFAULT_HEADERS: Dict[str, str] = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    )
}


def extract_aweme_id(
    link: str,
    session: Optional[Session] = None
) -> Optional[str]:
    """Resolve a tiktok video id from a raw id, a full video url or a short share link."""
    link = (link or '').strip()
    if not link:
        return None

    if link.isdigit():
        return link

    if match := _VIDEO_ID_RE.search(link):
        return match.group(1)

    if link.startswith('http'):
        try:
            response: Response = (session or Session()).get(
                link,
                headers=_DEFAULT_HEADERS,
                allow_redirects=True,
                timeout=10
            )
            if match := _VIDEO_ID_RE.search(response.url):
                return match.group(1)
        except RequestException as e:
            logger.warning('failed to resolve short link %s: %s' % (link, e))

    return None


class TiktokComment:
    BASE_URL: str = 'https://www.tiktok.com'
    API_URL: str = '%s/api' % BASE_URL

    def __init__(
        self: 'TiktokComment'
    ) -> None:
        self.__session: Session = Session()
        self.__session.headers.update(_DEFAULT_HEADERS)

        retry: Retry = Retry(
            total=3,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter: HTTPAdapter = HTTPAdapter(max_retries=retry)
        self.__session.mount('https://', adapter)
        self.__session.mount('http://', adapter)

    def __parse_comment(
        self: 'TiktokComment',
        data: Dict[str, Any]
    ) -> Comment:
        data: Dict[str, Any] = jmespath.search(
            """
            {
                comment_id: cid,
                username: user.unique_id,
                nickname: user.nickname,
                comment: text,
                create_time: create_time,
                avatar: user.avatar_thumb.url_list[0],
                total_reply: reply_comment_total,
                like_count: digg_count
            }
            """ ,
            data
        )
    
        comment: Comment = Comment(
            **data,
            replies=list(
                self.get_all_replies(data.get('comment_id'))
            ) if data.get('total_reply') else []
        )

        logger.info('%s - %s : %s' % (
                comment.create_time,
                comment.username, 
                comment.comment
            )
        )

        return comment

    def get_all_replies(
        self: 'TiktokComment',
        comment_id: str
    ) -> Iterator[Comment]:
        page: int = 1
        while True:
            if(
                not (replies := self.get_replies(
                    comment_id=comment_id,
                    page=page
                ))
            ): break
            for reply in replies:
                yield reply
            
            page += 1

    def get_replies(
        self: 'TiktokComment',
        comment_id: str,
        size: Optional[int] = 50,
        page: Optional[int] = 1
    ):
        response: Response = self.__session.get(
            '%s/comment/list/reply/' % self.API_URL,
            params={
                'aid': 1988,
                'comment_id': comment_id,
                'item_id': self.aweme_id,
                'count': size,
                'cursor': (page - 1) * size
            }
        )

        return [
            self.__parse_comment(
                comment
            ) for comment in (self.__parse_response(response).get('comments') or [])
        ]

    def __parse_response(
        self: 'TiktokComment',
        response: Response
    ) -> Dict[str, Any]:
        try:
            payload: Dict[str, Any] = response.json()
        except ValueError as e:
            raise RuntimeError(
                'unexpected response from tiktok (status %s): %s' % (response.status_code, e)
            )

        if not isinstance(payload, dict) or 'comments' not in payload:
            raise RuntimeError(
                'tiktok did not return comments, video may be private, deleted or the id is invalid'
            )

        return payload
    
    def get_all_comments(
        self: 'TiktokComment',
        aweme_id: str
    ) -> Comments:
        page: int = 1
        data: Comments = self.get_comments(
            aweme_id=aweme_id,
            page=page
        )
        while data.has_more:
            page += 1
            comments: Comments = self.get_comments(
                aweme_id=aweme_id,
                page=page
            )
            data.comments.extend(comments.comments)
            if not comments.has_more:
                break

        return data

    def get_comments(
        self: 'TiktokComment',
        aweme_id: str,
        size: Optional[int] = 50,
        page: Optional[int] = 1
    ) -> Comments:
        self.aweme_id: str = aweme_id

        response: Response = self.__session.get(
            '%s/comment/list/' % self.API_URL,
            params={
                'aid': 1988,
                'aweme_id': aweme_id,
                'count': size,
                'cursor': (page - 1) * size
            }
        )

        data: Dict[str, Any] = jmespath.search(
            """
            {
                caption: comments[0].share_info.title,
                video_url: comments[0].share_info.url,
                comments: comments,
                has_more: has_more
            }
            """,
            self.__parse_response(response)
        )

        return Comments(
            comments=[
                self.__parse_comment(
                    comment
                ) for comment in (data.pop('comments') or [])
            ],
            **data,
        )
    
    def __call__(
        self: 'TiktokComment',
        aweme_id: str
    ) -> Comments:
        return self.get_all_comments(
            aweme_id=aweme_id
        )
