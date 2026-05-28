import re

with open("ddg_test.html", "r", encoding="utf-8") as f:
    html = f.read()

# Let's find result__a tags
matches = re.findall(r'(<a class="result__a"[^>]*>.*?</a>)', html, re.DOTALL)
print("Matches found:", len(matches))
for i, m in enumerate(matches[:3]):
    print(f"Match {i}:", repr(m))
