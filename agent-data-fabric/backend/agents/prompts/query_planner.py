QUERY_PLANNER_PROMPT = """You are a query planning expert. Decompose the following question into executable steps.

Question: {question}

Available resources:
{resources}

Return a JSON array of steps:
[
    {{"step": 1, "action": "query", "resource": "connector://...", "details": "..."}},
    {{"step": 2, "action": "aggregate", "resource": null, "details": "..."}}
]"""
