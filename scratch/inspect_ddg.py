import urllib.request
import urllib.parse
import re

url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote("Seu Ambrosio Barbearia Recife")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=5) as response:
    html = response.read().decode('utf-8')

# Write to file
with open("ddg_test.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Saved HTML file. Length:", len(html))
# Let's search for some patterns
print("Snippet matches count:", len(re.findall(r'result__snippet', html)))
print("result__a matches count:", len(re.findall(r'result__a', html)))
# Find result__url or similar links
urls = re.findall(r'href="([^"]*)"', html)
print("Href links count:", len(urls))
