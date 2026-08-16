from typing import Optional

from pydantic import BaseModel


class QuestionDTO(BaseModel):
    """跨路由共享的题目视图（练习会话与题目 CRUD 共用）"""

    id: int
    type: str
    question: str
    options: Optional[dict[str, str]]
    score: float
