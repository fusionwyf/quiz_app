# 内置示例题库（spec P3 首次引导）：一键导入即可体验全部题型与判分规则。
# 数据内嵌为 Python 常量，避免 PyInstaller 打包资源文件的额外配置。
from sqlmodel import Session, select

from api.models import Question, QuestionBank

SAMPLE_BANK_NAME = "示例题库"

# (type, content, options, answer, blank_answer, score)
_SAMPLE_QUESTIONS = [
    (
        "single",
        "刷题助手中的“已掌握”是什么意思？",
        {
            "A": "把错题移出错题本",
            "B": "删除这道题目",
            "C": "把题目加入收藏",
            "D": "修改题目答案",
        },
        ["A"],
        None,
        1.0,
    ),
    (
        "single",
        "填空题答案写「TCP|传输控制协议」表示什么？",
        {
            "A": "答案只能是 TCP",
            "B": "两个备选写法任答其一即算对",
            "C": "必须两个都写才算对",
            "D": "这是一道多选题",
        },
        ["B"],
        None,
        1.0,
    ),
    (
        "multi",
        "以下哪些属于有效的备考习惯？（多选）",
        {
            "A": "错题及时重做",
            "B": "只看答案不动手",
            "C": "定期复习错题本",
            "D": "考前突击刷完所有题",
        },
        ["A", "C"],
        None,
        2.0,
    ),
    (
        "judge",
        "连续答对同一道错题若干次后，它会自动移出错题本。",
        None,
        ["对"],
        None,
        1.0,
    ),
    (
        "judge",
        "删除题库后，库内题目与相关错题、答题记录仍然保留。",
        None,
        ["错"],
        None,
        1.0,
    ),
    (
        "blank",
        "HTTP 的中文全称是超文本____协议。（提示：传输 或 传送 都算对）",
        None,
        ["传输|传送"],
        ["传输|传送"],
        1.0,
    ),
    (
        "blank",
        "IPv4 地址由____组十进制数构成，每组取值范围是 0～____。",
        None,
        ["4", "255"],
        ["4|四", "255"],
        2.0,
    ),
    (
        "blank",
        "数据库事务的 ACID 特性指原子性、____、隔离性和持久性。",
        None,
        ["一致性|一致性（Consistency）"],
        ["一致性|consistency|Consistency"],
        1.0,
    ),
]


def import_sample_bank(session: Session) -> QuestionBank:
    """创建示例题库并写入示例题目；同名已存在时抛 ValueError（路由转 409）"""
    exists = session.exec(
        select(QuestionBank).where(QuestionBank.name == SAMPLE_BANK_NAME)
    ).first()
    if exists:
        raise ValueError(f"题库名称已存在：{SAMPLE_BANK_NAME}")

    bank = QuestionBank(name=SAMPLE_BANK_NAME)
    session.add(bank)
    session.commit()
    session.refresh(bank)

    for qtype, content, options, answer, blank_answer, score in _SAMPLE_QUESTIONS:
        session.add(
            Question(
                bank_id=bank.id,
                type=qtype,
                content=content,
                options=options,
                answer=answer,
                blank_answer=blank_answer,
                score=score,
            )
        )
    session.commit()
    session.refresh(bank)  # 第二次 commit 过期属性，序列化前恢复
    return bank
