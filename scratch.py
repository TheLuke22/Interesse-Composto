import re

def fix_calcolatore():
    path = "calcolatore.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 1. Fix all E722 bare excepts: 'except:' -> 'except Exception:'
    # We look for 'except:' at the start of a line or after spaces, possibly followed by comments
    modified, count_excepts = re.subn(r'^(\s*)except\s*:(.*)$', r'\1except Exception:\2', content, flags=re.MULTILINE)
    print(f"Fixed {count_excepts} bare excepts.")

    # Let's save the modified content back
    with open(path, "w", encoding="utf-8") as f:
        f.write(modified)

if __name__ == "__main__":
    fix_calcolatore()
