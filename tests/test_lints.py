import glob, re
import os

print("--- Checking templates for raw Django tags in JS/CSS ---")
for path in glob.glob('templates/**/*.html', recursive=True):
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Check styles
    styles = re.findall(r'<style.*?>(.*?)</style>', html, re.DOTALL)
    for s in styles:
        if '{%' in s or '{{' in s:
            print(f'STYLE IN {path} HAS DJANGO TAGS')
            
    # Check scripts
    scripts = re.findall(r'<script.*?>\s*(.*?)\s*</script>', html, re.DOTALL)
    for s in scripts:
        lines = s.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip false positives
            if not line or line.startswith('//'): continue
            
            # Find {%...%}
            if '{%' in line:
                print(f'{os.path.basename(path)}: JS tag error [{i}]: {line}')
                
            # Find {{...}} not wrapped in quotes
            if '{{' in line:
                # Is it wrapped in quotes? "...", '...', or `...`?
                if not (('\"{{' in line or '\'{{' in line or '\`{{' in line) or ('"{{' in line) or ("'{{") in line):
                    # But if we did parseInt("{{", this is valid. Let's just do a simpler heuristic:
                    # if the sequence {{ isn't immediately preceded by a quote, warn.
                    pass
                # A better check: does the line contain {{ but no quote? This is definitely an error
                if '{{' in line and '"' not in line and "'" not in line and '`' not in line:
                    print(f'{os.path.basename(path)}: JS unquoted var [{i}]: {line}')
print("--- End Check ---")
