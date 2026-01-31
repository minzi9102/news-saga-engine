# config.py

BASE_URL_TEMPLATE = "http://tv.cctv.com/lm/xwlb/day/{date_str}.shtml"

SELECTORS = {
    # [修正] 列表页: 改为提取 title 属性
    "daily_list_schema": {
        "name": "CCTV News List",
        "baseSelector": "li",
        "fields": [
            {
                "name": "title", 
                "selector": "a:first-child", 
                "type": "attribute",  # 修正：提取属性
                "attribute": "title"  # 修正：属性名为 title
            },
            {
                "name": "url", 
                "selector": "a:first-child", 
                "type": "attribute", 
                "attribute": "href"
            }
        ]
    },
    # [新增] 摘要页: 对应 N8N 节点 149c26a6
    # 这里的 selector 非常长，为了稳健性，我保留了 N8N 的逻辑但稍微简化
    "abstract_schema": {
        "name": "News Abstract",
        "baseSelector": "body",
        "fields": [
            {
                "name": "raw_content",
                "selector": "#page_body .video18847 .playingCon .nrjianjie_shadow ul li:first-child p",
                "type": "text"
            }
        ]
    },
    # [新增] 详情页: 对应 N8N 节点 43dd14e5
    "news_detail_schema": {
        "name": "News Detail",
        "baseSelector": "body",
        "fields": [
            {
                "name": "title",
                "selector": ".tit", # 简化选择器
                "type": "text"
            },
            {
                "name": "content",
                "selector": "#content_area",
                "type": "text"
            }
        ]
    }
}