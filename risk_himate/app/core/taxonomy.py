"""Static taxonomy and scoring metadata."""

from __future__ import annotations

RISK_TAXONOMY: dict[str, dict[str, object]] = {
    "algorithm_safety": {
        "label": "算法安全风险",
        "subtypes": ["算法歧视", "算法黑箱", "算法滥用"],
        "legal_basis": ["《互联网信息服务算法推荐管理规定》"],
        "weight": 1.0,
        "keywords": ["算法推荐", "智能推荐", "推荐系统", "歧视", "黑箱", "不可解释", "可解释性", "模型滥用", "自动决策"],
    },
    "data_compliance": {
        "label": "数据合规风险",
        "subtypes": ["数据采集合规", "数据存储安全", "跨境数据传输", "隐私保护"],
        "legal_basis": ["《个人信息保护法》", "《数据安全法》"],
        "weight": 1.2,
        "keywords": ["个人信息", "隐私", "出境", "跨境", "境外", "境外云平台", "数据安全", "数据存储", "用户数据", "行为数据"],
    },
    "tech_ethics": {
        "label": "科技伦理风险",
        "subtypes": ["透明度不足", "公平性问题", "人工干预机制缺失"],
        "legal_basis": ["《新一代人工智能伦理规范》"],
        "weight": 0.9,
        "keywords": ["伦理", "透明度", "公平性", "人工干预", "问责", "可解释"],
    },
    "ip_risk": {
        "label": "知识产权风险",
        "subtypes": ["专利侵权", "技术泄露", "软著/商标风险"],
        "legal_basis": ["《专利法》", "《商标法》", "《著作权法》"],
        "weight": 1.0,
        "keywords": ["专利", "侵权", "技术泄露", "商业秘密", "商标", "软著", "知识产权"],
    },
    "geopolitical": {
        "label": "地缘博弈风险",
        "subtypes": ["出海合规壁垒", "技术封锁风险", "数据主权风险"],
        "legal_basis": ["出口管制相关政策", "境外监管要求"],
        "weight": 0.8,
        "keywords": ["出海", "海外客户", "制裁", "出口管制", "实体清单", "海外合规", "数据主权", "境外监管"],
    },
}

RISK_LABEL_TO_CODE = {
    metadata["label"]: code for code, metadata in RISK_TAXONOMY.items()
}
