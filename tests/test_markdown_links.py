"""Local Markdown file links must resolve; historical measurements stay untouched."""
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote


def test_tracked_markdown_file_links_resolve(repo_root):
    paths=subprocess.check_output(['git','ls-files','*.md'],cwd=repo_root,text=True).splitlines()
    broken=[]
    for name in paths:
        path=repo_root/name
        for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',path.read_text()):
            target=unquote(link.split('#')[0].strip('<>'))
            if not target or '://' in target or target.startswith(('mailto:','/')):
                continue
            if not (path.parent/target).exists():
                broken.append(f'{name}: {target}')
    assert not broken, '\n'.join(broken)
