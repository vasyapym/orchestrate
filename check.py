#!/usr/bin/env python3
"""usage: check.py brief <brief.md> [--round <dir>] | reply <file> | decl [root] [--no-machine]
exit 0 ok / 1 refused or incomplete (FAIL lines name the check and the path) / 2 broken
"""
import glob,hashlib,json,os,re,shlex,sys
from pathlib import Path
SLOT,OC="<N\u2013M>","## Output contract"
MARK,PH=re.compile(r"^=== (begin|end) (.+) ===$"),re.compile(r"<[^>\n]{1,80}>")
UNSET="<OPENCODE_SESSION_ID unset \u2014 ask the orchestrator>"
USAGE="usage: check.py brief <brief.md> [--round <dir>] | reply <file> | decl [root] [--no-machine]"
PARTS="core briefs reply roster jobs skeleton".split()
def die(msg):
 sys.stderr.write("check.py: %s\n"%msg);sys.exit(2)
def split(text):
 return [l[:-1] if l[-1:]=="\r" else l for l in text.split("\n")]
def head(lines):
 return lines[:next((i for i,l in enumerate(lines) if l.startswith("## ")),len(lines))]
def check(lines,sk,spec):
 p=[l for l in head(sk) if l.startswith("There's a")]
 if not sk[0] or len(p)!=1 or p[0].count(SLOT)!=1:die("broken skeleton: need line 1 and one 'There's a' paragraph with one %s"%SLOT)
 l,r=p[0].split(SLOT)
 rx=re.compile(re.escape(l)+r"(\d+(?:\s*\u2013\s*\d+)?)"+re.escape(r))
 miss,h=[],head(lines)
 if sk[0] not in h:miss+=[(1,"opener missing from the head")]
 w=[m[1] for m in map(rx.fullmatch,h) if m]
 win=w[0] if w else ""
 if not w:miss+=[(2,"time paragraph missing from the head")]
 oc=[i for i,l in enumerate(lines) if l.startswith(OC)]
 c,t,st,req,mm=lines[oc[-1]+1:] if oc else [],[],[],[],None
 for l in c:
  m=MARK.match(l)
  if m:
   if l in req and not mm:mm="a marker line is not unique"
   req.append(l)
   if m[1]=="begin":st.append(m[2])
   elif st and st[-1]==m[2]:st.pop()
   elif not mm:mm="an end without its begin before it"
  if m or not st:t.append(l)
 if st and not mm:mm="a begin without its end after it"
 a=[i for i,l in enumerate(lines[:oc[-1]]) if l.startswith("## Context and code")] if oc else []
 live=lines[:a[0]]+t if a else lines
 hit=[i for i,l in enumerate(live,1) if PH.search(l)]
 if hit:miss+=[(3,"placeholder left in live text (line %d)"%hit[0])]
 stem=Path(spec).stem
 ok,phrase=re.fullmatch(r"\d+-.*\S.*",stem),"reply "+stem
 if not ok:miss+=[(4,"stem is not <n>-<slug>")]
 if not oc:miss+=[(n,"no %r heading"%OC) for n in (4,5,6,7)]
 else:
  text="\n".join(c)
  if ok and phrase not in text:miss+=[(4,"phrase %r missing from the contract"%phrase)]
  if win and win not in text:miss+=[(5,"digits %r missing from the contract"%win)]
  if mm:miss+=[(6,mm)]
  if not re.search(r"\bCOMPLETE\b",text):miss+=[(7,"terminal line missing from the contract")]
 if miss:
  print("\n".join("FAIL %d %s: %s"%(n,spec,why) for n,why in miss));sys.exit(1)
 return win,req
def brief(rest):
 rd=None
 if "--round" in rest:
  i=rest.index("--round")
  rd,rest=rest[i+1],rest[:i]+rest[i+2:]
 if len(rest)!=1:die(USAGE)
 path,skill=Path(rest[0]),Path(__file__).resolve().parent
 raw=path.read_bytes()
 sk=split((skill/"declarations/brief-skeleton.md").read_text(encoding="utf-8"))
 win,req=check(split(raw.decode("utf-8")),sk,rest[0])
 out=(Path(rd) if rd else path.parent)/"replies"
 p=out/(path.name+".profile.json")
 d={"version":1,"required_lines":req,"terminal_line":"COMPLETE"}
 if p.exists():
  try:old=json.loads(p.read_bytes())
  except (OSError,ValueError):old=None
  if not isinstance(old,dict) or {k:v for k,v in old.items() if k!="since"}!=d:die("profile conflict at %s; never rewritten"%p)
 else:
  out.mkdir(parents=True,exist_ok=True)
  with open(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),"wb") as f:f.write((json.dumps(d,indent=2,sort_keys=True)+"\n").encode())
 ab=os.path.abspath
 h=shlex.join(["python3",str(skill/"extract-reply.py"),"reply "+path.stem,ab(p),"--session",os.environ.get("OPENCODE_SESSION_ID") or UNSET,"--since",str(int(p.stat().st_mtime)),"--out",ab(out/path.name)])
 return "VERDICT: brief ok %s %d window %s\nHARVEST: %s"%(rest[0],len(raw),win,h),0
def reply(rest):
 if len(rest)!=1:die(USAGE)
 p=Path(rest[0]);q=Path(str(p)+".profile.json")
 try:
  d=json.loads(q.read_bytes())
  assert type(d["version"]) is int and d["version"]==1
  req,terminal=d["required_lines"],d["terminal_line"]
  assert isinstance(req,list) and all(isinstance(x,str) for x in req)
  assert isinstance(terminal,str)
 except Exception:die("profile %s"%q)
 try:
  raw=p.read_bytes()
  lines=raw.decode("utf-8").replace("\r\n","\n").split("\n")
 except Exception:die("reply %s"%p)
 n=sum(x in lines for x in req)
 for x in req:
  if x not in lines:print("FAIL required %s"%p)
 while lines and not lines[-1].strip():lines.pop()
 ok=bool(lines) and lines[-1]==terminal
 if not ok:print("FAIL terminal %s"%p)
 good=n==len(req) and ok
 return "RECEIPT: %s %s %d %s lines %d/%d terminal %s"%("complete" if good else "partial",p,len(raw),hashlib.sha256(raw).hexdigest(),n,len(req),"ok" if ok else "missing"),int(not good)
def decl(rest):
 args=[x for x in rest if x!="--no-machine"]
 if len(args)>1 or any(x.startswith("-") for x in args):die(USAGE)
 root=Path(args[0]).resolve() if args else Path(__file__).resolve().parent
 if not root.is_dir():die("root %s"%root)
 dec=root/"declarations"
 fs=[dec/(("brief-skeleton" if x=="skeleton" else x)+".md") for x in PARTS]
 data=[p.read_bytes() for p in fs]
 ns=[p.stat().st_size for p in fs]
 miss=[]
 def fail(check,path):miss.append("FAIL %s %s"%(check,path))
 core=data[0].decode("utf-8")
 sk=split(data[-1].decode("utf-8"))
 for t in re.findall(r"(?<!\S)(?:~/|/)[^\s`]+",core):
  t=t.rstrip(".,;:)]\u2014")
  if "<" in t or "$" in t:continue
  if (t.startswith("~") or t.count("/")>=2) and not os.path.exists(os.path.expanduser(t)):fail("path",t)
 skill=split((root/"SKILL.md").read_bytes().decode("utf-8"))
 chat=[l[2:] if l.startswith("> ") else l for l in skill]
 opener=next((l for l in chat if l.startswith("Answer as a chat model \u2014 no agentic operations")),None)
 if opener is None or sk[0]!=opener:fail("opener",fs[-1])
 paras=[l for l in head(sk) if l.startswith("There's a "+SLOT+"-minute")]
 if len(paras)!=1:fail("paragraph",fs[-1])
 else:
  homes=[p for p in dec.rglob("*.md") if p.is_file() and paras[0] in split(p.read_bytes().decode("utf-8"))]
  if len(homes)!=1:fail("paragraph",dec)
 cmd=root/"commands"
 paths=sorted(cmd.glob("*.md"))
 if not cmd.is_dir() or not paths:fail("directive",cmd)
 for p in paths:
  for line in split(p.read_bytes().decode("utf-8")):
   s=line.lstrip()
   if not s.startswith("!`"):continue
   for span in re.findall(r"`([^`]*)`",line):
    for t in re.findall(r"(?:^|\s)cat\s+([^\s`]+)",span):
     if "<" in t or "$" in t:continue
     seg=os.path.expanduser(t).split("/")
     rel=next(("/".join(seg[seg.index(x):]) for x in ("declarations","commands") if x in seg),None)
     if rel is None:continue
     target=str(root/rel)
     if not (glob.glob(target) if any(c in rel for c in "*?[") else os.path.exists(target)):fail("path",target)
 if "--no-machine" not in rest:
  p=Path("~/.config/orchestrate/declarations.md").expanduser()
  if p.is_symlink():good=os.path.realpath(p)==os.path.realpath(fs[0])
  else:good=p.is_file() and p.read_bytes()==data[0]
  if not good:fail("config-root",p)
 total=sum(ns)
 if total>20000:fail("size",dec)
 if miss:return "\n".join(miss),1
 return "DECL: ok %d %s"%(total," ".join("%s %d"%x for x in zip(PARTS,ns))),0
def main(argv):
 if not argv or argv[0] not in ("brief","reply","decl"):die(USAGE)
 try:text,code=globals()[argv[0]](argv[1:])
 except Exception as exc:die("%s: %s"%(type(exc).__name__,exc))
 print(text)
 return code
if __name__=="__main__":
 sys.exit(main(sys.argv[1:]))

