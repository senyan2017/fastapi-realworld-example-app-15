from typing import List, Optional, Sequence

from pydantic import BaseModel, Field

from app.models.domain.articles import Article
from app.models.schemas.rwschema import RWSchema

DEFAULT_ARTICLES_LIMIT = 20
DEFAULT_ARTICLES_OFFSET = 0


class ArticleForResponse(RWSchema, Article):
    tags: List[str] = Field(..., alias="tagList")


class ArticleInResponse(RWSchema):
    article: ArticleForResponse

    @classmethod
    def from_article(cls, article: Article) -> "ArticleInResponse":
        return cls(article=ArticleForResponse.from_orm(article))


class ArticleInCreate(RWSchema):
    title: str
    description: str
    body: str
    tags: List[str] = Field([], alias="tagList")


class ArticleInUpdate(RWSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    body: Optional[str] = None


class ListOfArticlesInResponse(RWSchema):
    articles: List[ArticleForResponse]
    articles_count: int

    @classmethod
    def from_articles(
        cls,
        articles: Sequence[Article],
    ) -> "ListOfArticlesInResponse":
        return cls(
            articles=[ArticleForResponse.from_orm(article) for article in articles],
            articles_count=len(articles),
        )


class ArticlesFilters(BaseModel):
    tag: Optional[str] = None
    author: Optional[str] = None
    favorited: Optional[str] = None
    limit: int = Field(DEFAULT_ARTICLES_LIMIT, ge=1)
    offset: int = Field(DEFAULT_ARTICLES_OFFSET, ge=0)
