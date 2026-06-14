from __future__ import annotations

from typing import List, Optional

from slugify import slugify

from app.db.errors import EntityDoesNotExist
from app.db.repositories.articles import ArticlesRepository
from app.models.domain.articles import Article
from app.models.domain.users import User
from app.models.schemas.articles import (
    ArticleForResponse,
    ArticleInResponse,
    ArticlesFilters,
    ListOfArticlesInResponse,
)


# ---------------------------------------------------------------------------
# Pure helpers (no I/O)
# ---------------------------------------------------------------------------


def get_slug_for_article(title: str) -> str:
    return slugify(title)


def check_user_can_modify_article(article: Article, user: User) -> bool:
    return article.author.username == user.username


# ---------------------------------------------------------------------------
# Async wrappers around simple repository queries
# ---------------------------------------------------------------------------


async def check_article_exists(articles_repo: ArticlesRepository, slug: str) -> bool:
    try:
        await articles_repo.get_article_by_slug(slug=slug)
    except EntityDoesNotExist:
        return False
    return True


# ---------------------------------------------------------------------------
# Response builders
#
# Centralised so route handlers never have to assemble ArticleInResponse /
# ListOfArticlesInResponse by hand.
# ---------------------------------------------------------------------------


def _to_article_for_response(article: Article) -> ArticleForResponse:
    return ArticleForResponse.from_orm(article)


def create_article_response(article: Article) -> ArticleInResponse:
    return ArticleInResponse(article=_to_article_for_response(article))


def create_articles_list_response(
    articles: List[Article],
) -> ListOfArticlesInResponse:
    return ListOfArticlesInResponse(
        articles=[_to_article_for_response(a) for a in articles],
        articles_count=len(articles),
    )


# ---------------------------------------------------------------------------
# Higher-level operations that compose repository calls
# ---------------------------------------------------------------------------


async def get_articles_list(
    articles_repo: ArticlesRepository,
    filters: ArticlesFilters,
    user: Optional[User] = None,
) -> ListOfArticlesInResponse:
    articles = await articles_repo.filter_articles(
        tag=filters.tag,
        author=filters.author,
        favorited=filters.favorited,
        limit=filters.limit,
        offset=filters.offset,
        requested_user=user,
    )
    return create_articles_list_response(articles)


async def get_user_feed(
    articles_repo: ArticlesRepository,
    user: User,
    limit: int,
    offset: int,
) -> ListOfArticlesInResponse:
    articles = await articles_repo.get_articles_for_user_feed(
        user=user,
        limit=limit,
        offset=offset,
    )
    return create_articles_list_response(articles)


# ---------------------------------------------------------------------------
# Favorite toggling
# ---------------------------------------------------------------------------


class ArticleAlreadyFavoritedError(Exception):
    """Raised when a user tries to favorite an already-favorited article."""


class ArticleNotFavoritedError(Exception):
    """Raised when a user tries to unfavorite an article that isn't favorited."""


async def toggle_favorite(
    articles_repo: ArticlesRepository,
    article: Article,
    user: User,
    *,
    favorite: bool,
) -> Article:
    """Add or remove *article* from *user*'s favorites.

    Raises ``ArticleAlreadyFavoritedError`` / ``ArticleNotFavoritedError``
    when the requested transition is invalid.  Returns an ``Article`` with
    ``favorited`` and ``favorites_count`` already updated so callers can
    wrap it straight into a response.
    """
    is_favorited = await articles_repo.is_article_favorited_by_user(
        slug=article.slug, user=user,
    )

    if favorite and is_favorited:
        raise ArticleAlreadyFavoritedError
    if not favorite and not is_favorited:
        raise ArticleNotFavoritedError

    if favorite:
        await articles_repo.add_article_into_favorites(article=article, user=user)
    else:
        await articles_repo.remove_article_from_favorites(article=article, user=user)

    return article.copy(
        update={
            "favorited": favorite,
            "favorites_count": article.favorites_count + (1 if favorite else -1),
        },
    )
