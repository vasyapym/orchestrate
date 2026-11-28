import hashlib,json,os,re,shlex,shutil,subprocess,sys,time
from pathlib import Path
import pytest
C=Path(__file__).resolve().parent.parent/"check.py"
S=C.parent/"declarations/brief-skeleton.md"
E="ses_check_test"
U="<OPENCODE_SESSION_ID unset — ask the orchestrator>"
P=["=== begin design ===","=== end design ==="]
W="6–10"
Q="round-1/replies/2-foo.md.profile.json"
R="\n".join(P+["COMPLETE"])
def run(t,args,session=E,mode="brief",extra=None):
 e=dict(os.environ);e.pop("OPENCODE_SESSION_ID",None)
 if session is not None:e["OPENCODE_SESSION_ID"]=session
 e.update(extra or {})
 return subprocess.run([sys.executable,str(C)]+([mode] if mode else [])+list(map(str,args)),capture_output=True,env=e,timeout=120,cwd=str(t))
def b(t,p,**kw):return run(t,[p,"--round","round-1"],**kw)
def read(p):return p.read_text(encoding="utf-8")
def put(p,s):p.write_text(s,encoding="utf-8")
def out(p):return p.stdout.decode("utf-8")
def argv(p):return shlex.split(out(p).splitlines()[1][9:])
def ok(p,prefix=""):
 assert p.returncode==0,out(p)+p.stderr.decode()
 assert out(p).startswith(prefix)
def fill(d,name="2-foo.md",marker=True):
 s=read(S)
 for x,y in [("<one or two sentences; less is better>","Shape the gate."),("<each with its path or source>","- DECISION-2 §C"),("<...>","- none"),("<files whole or in generous excerpts>","- declarations/brief-skeleton.md"),("<what to return, in what order>","the design"),("<LINES>","350"),("<N–M>",W),("`reply <n>-<slug>`","`reply %s`"%Path(name).stem),("=== begin <name> ===",P[0]),("<the artifact, ONE <BREAK>-joined line>","the artifact, one line"),("=== end <name> ===",P[1])]:
  assert x in s
  s=s.replace(x,y)
 if not marker:s="\n".join(l for l in s.split("\n") if l not in P and not l.startswith("the artifact, one line"))
 p=d/name;put(p,s);return p
@pytest.fixture
def t(tmp_path):return tmp_path
@pytest.fixture
def good(t):return fill(t)
def test_pass(t,good):
 p=b(t,good);ok(p);l=out(p).splitlines()
 assert len(l)==2 and l[1].startswith("HARVEST: ")
 assert l[0]=="VERDICT: brief ok %s %d window %s"%(good,good.stat().st_size,W)
 v=argv(p);q=t/Q;d=t/"round-1/replies"
 assert v[:6]==["python3",str(C.parent/"extract-reply.py"),"reply 2-foo",str(q),"--session",E]
 assert v[6]=="--since" and v[8]=="--out" and v[9]==str(d/"2-foo.md")
 assert abs(int(v[7])-time.time())<120
 assert json.loads(read(q))=={"version":1,"required_lines":P,"terminal_line":"COMPLETE"}
 assert q.stat().st_mode&0o777==0o600
def test_shell(t):
 p=fill(t,"2-fo$(reboot)o.md");d=t/"TD rounds/spares guard round"
 x=run(t,[p,"--round",d]);ok(x);v=argv(x);s=p.stem
 assert v[2]=="reply "+s
 assert v[3]==str(d/"replies"/(s+".md.profile.json"))
 assert v[9]==str(d/"replies"/(s+".md"))
 assert list(t.glob("round-*"))==[]
def test_session(t,good):
 p=b(t,good,session=None);ok(p)
 assert argv(p)[4:6]==["--session",U]
def test_rerun(t,good):
 q=t/Q;p=b(t,good);ok(p)
 since=argv(p)[7];before=(q.stat().st_mtime_ns,q.read_bytes())
 time.sleep(1.1)
 p=b(t,good);ok(p)
 assert argv(p)[7]==since
 assert (q.stat().st_mtime_ns,q.read_bytes())==before
 assert int(q.stat().st_mtime)==int(since)
@pytest.mark.parametrize("crlf",[False,True])
def test_variants(t,crlf):
 p=fill(t,"3-crlf.md" if crlf else "2-foo.md",marker=crlf)
 if crlf:p.write_bytes(p.read_bytes().replace(b"\n",b"\r\n"))
 raw=p.read_bytes();x=b(t,p);ok(x)
 assert p.read_bytes()==raw
 if crlf:assert out(x).splitlines()[0]=="VERDICT: brief ok %s %d window %s"%(p,p.stat().st_size,W)
 else:
  d=json.loads(read(t/Q))
  assert d["required_lines"]==[] and d["terminal_line"]=="COMPLETE"
@pytest.mark.parametrize("n,count,change",[(1,1,lambda s:s.replace("no agentic operations","no agent-ic operations")),(2,2,lambda s:s.replace(W,"<N–M>",1)),(3,1,lambda s:s+"\npull the roster from <project> first.\n"),(5,1,lambda s:s.replace("hard stop at %s minutes"%W,"hard stop at 99 minutes")),(6,1,lambda s:s.replace(P[1]+"\n","")),(7,1,lambda s:s.replace("COMPLETE","DONE"))])
def test_refusal(t,good,n,count,change):
 put(good,change(read(good)));p=b(t,good)
 assert p.returncode==1
 assert out(p).startswith("FAIL %d %s:"%(n,good))
 assert out(p).count("\n")==count
def test_rename(t,good):
 p=good.with_name("3-bar.md");good.rename(p);x=b(t,p);s=out(x)
 assert x.returncode==1
 assert s.startswith("FAIL 4 %s:"%p) and "reply 3-bar" in s and s.count("\n")==1
def test_dispatch(t):
 assert run(t,[],mode=None).returncode==2
 assert run(t,["reply","x"],mode=None).returncode==2
@pytest.mark.parametrize("body,need,n,end",[(R,P,2,"ok"),(R+"\n \t\n",P,2,"ok"),(R.replace("\n","\r\n")+"\r\n",P,2,"ok"),("COMPLETE",[],0,"ok"),(" ".join(P+["COMPLETE"]),P,0,"missing"),(P[0]+"\nCOMPLETE",P,1,"ok"),(P[0]+"\n"+P[0]+"\nCOMPLETE",P,1,"ok"),("\n".join(P),P,2,"missing"),(R+"\nlate",P,2,"missing"),("\n".join(" "+s for s in P)+"\nCOMPLETE",P,0,"ok"),("\n".join(s+" " for s in P)+"\nCOMPLETE",P,0,"ok"),(R+" ",P,2,"missing"),(R+"\r",P,2,"missing")]+[(R.replace("\n",s),P,0,"missing") for s in ["\r","\v","\f","\x85","\u2028","\u2029"]])
def test_reply(t,body,need,n,end):
 p=t/"reply with space.md";raw=body.encode();p.write_bytes(raw)
 q=Path(str(p)+".profile.json")
 put(q,json.dumps({"version":1,"required_lines":need,"terminal_line":"COMPLETE"}))
 before=(p.read_bytes(),p.stat().st_mtime_ns)
 x=run(t,[p],mode="reply");v=[l for l in out(x).splitlines() if l.startswith("RECEIPT: ")][-1].split(" ",2)
 assert x.returncode==int(n!=len(need) or end!="ok")
 assert out(x).startswith("RECEIPT: ") and v[1] and not any(c.isspace() for c in v[1])
 assert v[2]==f"{p} {len(raw)} {hashlib.sha256(raw).hexdigest()} lines {n}/{len(need)} terminal {end}"
 assert (p.read_bytes(),p.stat().st_mtime_ns)==before
@pytest.mark.parametrize("profile",[None,b"{"])
def test_reply_profile_error(t,profile):
 p=t/"reply.md";p.write_bytes(R.encode());q=Path(str(p)+".profile.json")
 if profile is not None:q.write_bytes(profile)
 before=(p.read_bytes(),p.stat().st_mtime_ns)
 x=run(t,[p],mode="reply")
 assert x.returncode==2 and str(q) in out(x)+x.stderr.decode()
 assert (p.read_bytes(),p.stat().st_mtime_ns)==before
@pytest.fixture
def tree(t):
 return Path(shutil.copytree(C.parent,t/"tree",symlinks=True,ignore=shutil.ignore_patterns(".git","node_modules",".venv","__pycache__",".pytest_cache")))
def test_decl_tree(t):
 ok(run(t,[C.parent],mode="decl"),"DECL: ok ")
@pytest.mark.parametrize("case",["map","cat","skeleton","duplicate","absent","size","part","config"])
def test_decl(t,tree,case):
 r=tree;c=next(r.rglob("core.md"));sk=r/"declarations/brief-skeleton.md"
 args=[r,"--no-machine"];extra={};x=run(t,args,mode="decl");ok(x,"DECL: ok ")
 w=out(x).split();total=int(w[2])
 assert w[3::2]==["core","briefs","reply","roster","jobs","skeleton"]
 assert total==sum(map(int,w[4::2]))
 assert int(w[4])==c.stat().st_size and int(w[-1])==sk.stat().st_size
 code=1
 if case in ("map","cat"):
  p=c
  if case=="map":
   tok=re.search(r"~/[^\s`]+\.md",read(c)).group(0);put(c,read(c).replace(tok,tok.replace(".md",".mX",1),1))
  else:
   p,region=next((p,l) for p in r.rglob("*.md") if "commands" in p.parts for l in read(p).splitlines() if "!" in l and "cat " in l);put(p,read(p).replace(region,region.replace(".md",".mX",1),1))
 elif case=="skeleton":put(sk,read(sk).replace("\n"," \n",1))
 elif case in ("duplicate","absent"):
  p,block=next((p,s) for p in (r/"declarations").glob("*.md") for s in read(p).split("\n\n") if "There's a" in s)
  if case=="duplicate":put(r/"declarations/duplicate.md",block+"\n")
  else:put(p,read(p).replace("There's a","There is a"))
 elif case=="size":
  sk.write_bytes(sk.read_bytes()+b"\n"*(20000-total))
  x=run(t,args,mode="decl");ok(x,"DECL: ok ")
  assert int(out(x).split()[2])==20000
  sk.write_bytes(sk.read_bytes()+b"\n")
 elif case=="part":sk.unlink();code=2
 else:
  h=t/"home";h.mkdir();args=[r]
  extra={"HOME":str(h),"XDG_CONFIG_HOME":str(h/".config")}
  ok(run(t,[r,"--no-machine"],mode="decl",extra=extra),"DECL: ok ")
 x=run(t,args,mode="decl",extra=extra);s=out(x)+x.stderr.decode()
 assert x.returncode==code
 if code==2:assert str(sk) in s
 else:
  assert s and all(re.match(r"FAIL \S+ .+",l) for l in s.splitlines())
  assert re.search(r"/|\.md\b",s)

