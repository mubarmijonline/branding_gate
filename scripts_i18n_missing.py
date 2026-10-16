"""
Which interface strings have no Arabic yet.

Collects the English the pages show (template text, attributes, JavaScript
literals and concatenations as {0}-templates, Python error/notification
messages) and prints those missing from static/i18n/ar.js, as JSON ready to
translate and paste in. Technical strings (identifiers, console messages) show
up too; leave those out of the dictionary.

    python3 scripts_i18n_missing.py            # list missing strings
    python3 scripts_i18n_missing.py out.json   # write them to a file
"""
import html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARABIC = re.compile(r'[\u0600-\u06FF]')
LETTER = re.compile(r'[A-Za-z]')

def norm(s):
    s = html.unescape(re.sub(r'\s+', ' ', s)).strip()
    return s

def ui_like(s):
    if not s or len(s) > 220 or not LETTER.search(re.sub(r'{\d}', '', s)):
        return False
    if ARABIC.search(s):            # already bilingual or Arabic
        return False
    bare = re.sub(r'{\d}', 'X', s)
    if re.search(r'[{}<>;=\\]|\$\(|=>|function|\bvar\b|\bconst\b|\.\w+\(|^\W|https?:|/api/|\.html?$|^#|^\.', bare):
        return False
    if re.fullmatch(r'[a-z0-9_\-\.]+', s):     # identifiers, css classes, keys
        return False
    if re.fullmatch(r'[A-Z0-9_]+', s) and len(s) > 1 and '_' in s:
        return False
    if re.fullmatch(r'(fa[srb]?|fas|far|btn|col|text|mr|ml|mb|mt|d)[\w\- ]*', s):
        return False
    if re.fullmatch(r'[a-z]+[A-Z]\w*', s):            # camelCase identifier
        return False
    if re.search(r'\b[a-z]+-[a-z0-9-]+\b', s) and s == s.lower():   # css class lists
        return False
    if re.match(r'(DEBUG|Error in |Error loading|Error fetching|Error getting)\b', s) or 'loaded' in s.lower() and 'page' in s.lower():
        return False
    return True

found = {}
def add_tpl(chunk, where):
    n = [0]
    def ph(_m):
        n[0] += 1
        return '{%d}' % (n[0] - 1)
    tpl = re.sub(r'{{.*?}}', ph, chunk)
    if n[0] and re.sub(r'{\d}', '', tpl).strip(' .,:;-|·()/'):
        add(tpl, where)
    for part in re.split(r'{{.*?}}', chunk):
        add(part, where)

def add(s, where):
    s = norm(s)
    s = re.sub(r'^[\s:*·|\-–]+|[\s:*·|]+$', '', s).strip()
    if ui_like(s):
        found.setdefault(s, set()).add(where)

for path in sorted((ROOT / 'templates').glob('*.html')):
    src = path.read_text(errors='ignore')
    name = path.name
    scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', src, re.S)
    markup = re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>|<!--.*?-->', ' ', src, flags=re.S)
    markup = re.sub(r'{#.*?#}', ' ', markup, flags=re.S)
    # attributes
    for m in re.finditer(r'\b(placeholder|title|aria-label|data-original-title|alt|value|data-title|label)\s*=\s*"([^"]*)"', markup):
        if m.group(1) == 'value' and not re.search(r'type="(submit|button)"', markup[max(0, m.start()-120):m.start()]):
            continue
        for part in re.split(r'{{.*?}}|{%.*?%}', m.group(2)):
            add(part, name)
    # text nodes
    text = re.sub(r'<[^>]+>', '\n', markup)
    for chunk in text.split('\n'):
        if '{%' in chunk:
            for part in re.split(r'{%.*?%}|{%|%}', chunk):
                add_tpl(part, name)
        else:
            add_tpl(chunk, name)
    # JS string literals and template-literal text
    for js in scripts:
        js = re.sub(r'//[^\n]*', '', js)
        for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"", js):
            lit = m.group(1) if m.group(1) is not None else m.group(2)
            lit = lit.replace("\\'", "'").replace('\\"', '"')
            if '<' in lit:
                for piece in re.split(r'<[^>]*>|\$\{[^}]*\}', lit):
                    add(piece, name + ':js')
            else:
                add(lit, name + ':js')
        for line in js.split('\n'):
            if '+' not in line:
                continue
            for expr in re.findall(r"(?:(?:'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\")\s*\+\s*[^'\"+;,()]{1,60}?\s*\+\s*)+(?:'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\")", line):
                lits = re.findall(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"", expr)
                lits = [a or b for a, b in lits]
                if any('<' in l for l in lits):
                    continue
                add('{0}'.join(lits) if len(lits) == 2 else ''.join(l + ('{%d}' % i if i < len(lits) - 1 else '') for i, l in enumerate(lits)), name + ':js')
        for m in re.finditer(r'`([^`]*)`', js, re.S):
            lit = m.group(1)
            if '<' not in lit and '${' in lit:
                k = [0]
                def ph2(_m):
                    k[0] += 1
                    return '{%d}' % (k[0] - 1)
                add(re.sub(r'\$\{[^}]*\}', ph2, lit), name + ':js')
            for piece in re.split(r'<[^>]*>|\$\{[^}]*\}', m.group(1)):
                add(piece, name + ':js')

def pyph(text):
    k = [0]
    def ph(_m):
        k[0] += 1
        return '{%d}' % (k[0] - 1)
    return re.sub(r'\{[^}]*\}|%[sd]|%\.2f', ph, text)

# Python user-facing messages
py = (ROOT / 'branding_gate.py').read_text(errors='ignore')
for m in re.finditer(r"""(?:error|message|title|warning)['"]?\s*[:=]\s*f?(['"])((?:(?!\1).)+)\1""", py):
    add(pyph(m.group(2)), 'py')
for m in re.finditer(r"""notify_users?\([^,]+,\s*f?(['"])((?:(?!\1).)+)\1""", py):
    add(pyph(m.group(2)), 'py')

known = json.loads((ROOT / 'static/i18n/ar.js').read_text().split('window.BG_AR = ', 1)[1].rstrip().rstrip(';'))
folded = {k.lower() for k in known}
missing = {k: sorted(v) for k, v in sorted(found.items()) if k not in known and k.lower() not in folded}
text = json.dumps(missing, ensure_ascii=False, indent=1)
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(text)
    print(len(missing), 'missing ->', sys.argv[1])
else:
    print(text)
    print(len(missing), 'missing', file=sys.stderr)
