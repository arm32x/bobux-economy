import random
import re


def fill(template: str, templates: dict[str, list[str]]):
    while "[" in template and "]" in template:
        start, end = template.index("["), template.index("]")
        key = template[(start + 1):end]
        template = template[:start] + random.choice(templates[key]) + template[(end + 1):]
    return re.sub(" +", " ", template).strip()
