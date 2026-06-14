"""Article route handlers.

All routes that live under ``/articles`` are defined here in a single
``router`` so that the wiring in ``app.api.routes.api`` stays trivial.

Responsibilities kept in this module:
  * HTTP concerns only (status codes, request parsing, error responses).
  * Delegation to :mod:`app.services.articles` for anything that involves
    business rules or response assembly.
  * Delegation to :class:`~app.db.repositories.articles.ArticlesRepository`
    for direct DB access where no extra logic is needed (create / update /
    delete, retrieve-by-slug).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from starlette import status

from app.api.dependencies.articles import (
    check_article_modification_permissions,
    get_article_by_slug_from_path,
    get_articles_filters,
)
from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.database import get_repository
from app.db.repositories.articles import ArticlesRepository
from app.models.domain.articles import Article
from app.models.domain.users import User
from app.models.schemas.articles import (
    DEFAULT_ARTICLES_LIMIT,
    DEFAULT_ARTICLES_OFFSET,
    ArticleInCreate,
    ArticleInResponse,
    ArticleInUpdate,
    ArticlesFilters,
    ListOfArticlesInResponse,
)
from app.resources import strings
from app.services.articles import (
    ArticleAlreadyFavoritedError,
    ArticleNotFavoritedError,
    check_article_exists,
    create_article_response,
    get_articles_list,
    get_slug_for_article,
    get_user_feed,
    toggle_favorite,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# List & Feed  (read-only collection endpoints)
# ---------------------------------------------------------------------------


@router.get("", response_model=ListOfArticlesInResponse, name="articles:list-articles")
async def list_articles(
    articles_filters: ArticlesFilters = Depends(get_articles_filters),
    user: Optional[User] = Depends(get_current_user_authorizer(required=False)),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ListOfArticlesInResponse:
    return await get_articles_list(articles_repo, articles_filters, user)


@router.get(
    "/feed",
    response_model=ListOfArticlesInResponse,
    name="articles:get-user-feed-articles",
)
async def get_articles_for_user_feed(
    limit: int = Query(DEFAULT_ARTICLES_LIMIT, ge=1),
    offset: int = Query(DEFAULT_ARTICLES_OFFSET, ge=0),
    user: User = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ListOfArticlesInResponse:
    return await get_user_feed(articles_repo, user, limit, offset)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ArticleInResponse,
    name="articles:create-article",
)
async def create_new_article(
    article_create: ArticleInCreate = Body(..., embed=True, alias="article"),
    user: User = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticleInResponse:
    slug = get_slug_for_article(article_create.title)
    if await check_article_exists(articles_repo, slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strings.ARTICLE_ALREADY_EXISTS,
        )

    article = await articles_repo.create_article(
        slug=slug,
        title=article_create.title,
        description=article_create.description,
        body=article_create.body,
        author=user,
        tags=article_create.tags,
    )
    return create_article_response(article)


@router.get("/{slug}", response_model=ArticleInResponse, name="articles:get-article")
async def retrieve_article_by_slug(
    article: Article = Depends(get_article_by_slug_from_path),
) -> ArticleInResponse:
    return create_article_response(article)


@router.put(
    "/{slug}",
    response_model=ArticleInResponse,
    name="articles:update-article",
    dependencies=[Depends(check_article_modification_permissions)],
)
async def update_article_by_slug(
    article_update: ArticleInUpdate = Body(..., embed=True, alias="article"),
    current_article: Article = Depends(get_article_by_slug_from_path),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticleInResponse:
    slug = get_slug_for_article(article_update.title) if article_update.title else None
    article = await articles_repo.update_article(
        article=current_article,
        slug=slug,
        **article_update.dict(),
    )
    return create_article_response(article)


@router.delete(
    "/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="articles:delete-article",
    dependencies=[Depends(check_article_modification_permissions)],
    response_class=Response,
)
async def delete_article_by_slug(
    article: Article = Depends(get_article_by_slug_from_path),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> None:
    await articles_repo.delete_article(article=article)


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------


@router.post(
    "/{slug}/favorite",
    response_model=ArticleInResponse,
    name="articles:mark-article-favorite",
)
async def mark_article_as_favorite(
    article: Article = Depends(get_article_by_slug_from_path),
    user: User = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticleInResponse:
    try:
        updated = await toggle_favorite(
            articles_repo, article, user, favorite=True,
        )
    except ArticleAlreadyFavoritedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strings.ARTICLE_IS_ALREADY_FAVORITED,
        )
    return create_article_response(updated)


@router.delete(
    "/{slug}/favorite",
    response_model=ArticleInResponse,
    name="articles:unmark-article-favorite",
)
async def remove_article_from_favorites(
    article: Article = Depends(get_article_by_slug_from_path),
    user: User = Depends(get_current_user_authorizer()),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
) -> ArticleInResponse:
    try:
        updated = await toggle_favorite(
            articles_repo, article, user, favorite=False,
        )
    except ArticleNotFavoritedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strings.ARTICLE_IS_NOT_FAVORITED,
        )
    return create_article_response(updated)
