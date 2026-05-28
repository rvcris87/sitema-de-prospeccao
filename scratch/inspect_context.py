with open("ddg_test.html", "r", encoding="utf-8") as f:
    html = f.read()

# Print 100 characters around each occurrence of result__a
import re
for m in re.finditer(r'result__a', html):
    start = max(0, m.start() - 50)
    end = min(len(html), m.end() + 100)
    print("MATCH:", repr(html[start:end]))
    print("-" * 40)
