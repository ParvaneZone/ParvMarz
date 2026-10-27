import base64, json
from urllib.parse import unquote, parse_qs

def parse_link(link:str)->dict|None:
 link=link.strip()
 if '://' not in link: return None
 scheme,rest=link.split('://',1); scheme=scheme.lower()
 if scheme not in {'vmess','vless','trojan','ss','hysteria2','hy2'}: return None
 fragment=''; query=''
 if '#' in rest: rest,fragment=rest.split('#',1); fragment=unquote(fragment)
 if '?' in rest: rest,query=rest.split('?',1)
 params={k:v[0] for k,v in parse_qs(query,keep_blank_values=True).items()}
 if scheme=='vmess':
  try:
   data=json.loads(base64.b64decode(rest+'='*(-len(rest)%4)))
   return {'type':'vmess','server':data.get('add',''),'port':int(data.get('port',0)),'uuid':data.get('id',''),'name':fragment or data.get('ps','vmess'),'tls':str(data.get('tls','')).lower()=='tls','network':data.get('net','tcp'),'sni':data.get('sni',''),'path':data.get('path',''),'host':data.get('host',''),'raw':link}
  except Exception:return None
 if scheme=='ss':
  endpoint=rest.split('@')[-1]
  try: host,port=endpoint.rsplit(':',1); return {'type':'ss','server':host.strip('[]'),'port':int(port),'name':fragment or 'ss','raw':link}
  except Exception:return None
 try:
  userinfo,hostpart=(rest.rsplit('@',1) if '@' in rest else ('',rest))
  hostpart=hostpart.strip('[]'); host,port=hostpart.rsplit(':',1)
  return {'type':{'hy2':'hysteria2'}.get(scheme,scheme),'server':host,'port':int(port),'uuid':unquote(userinfo),'name':fragment or f'{scheme}-{host}','tls':params.get('security','') in {'tls','reality'} or scheme in {'trojan','hysteria2','hy2'},'security':params.get('security',''),'network':params.get('type','tcp'),'sni':params.get('sni',params.get('peer','')),'fp':params.get('fp',''),'pbk':params.get('pbk',''),'sid':params.get('sid',''),'flow':params.get('flow',''),'path':params.get('path',''),'host_header':params.get('host',''),'raw':link}
 except Exception:return None

def deduplicate_links(links:list[str])->list[dict]:
 result=[]; seen=set()
 for link in links:
  parsed=parse_link(link)
  if not parsed: continue
  key=(parsed.get('type'),parsed.get('server'),parsed.get('port'),parsed.get('uuid'))
  if key in seen: continue
  seen.add(key); result.append(parsed)
 return result

def to_clash(proxies:list[dict])->str:
 import yaml
 result=[]
 for p in proxies:
  kind=p['type']; item={'name':p['name'],'type':{'ss':'ss','hy2':'hysteria2'}.get(kind,kind),'server':p['server'],'port':p['port']}
  if kind in {'vless','vmess','trojan'}: item['uuid']=p.get('uuid','')
  if p.get('tls'): item['tls']=True
  if p.get('sni'): item['servername']=p['sni']
  if p.get('fp'): item['client-fingerprint']=p['fp']
  if kind=='vless' and p.get('flow'): item['flow']=p['flow']
  if p.get('network')=='ws': item['network']='ws'; item['ws-opts']={'path':p.get('path') or '/','headers':{'Host':p.get('host_header') or p.get('host','')}}
  if p.get('security')=='reality': item['reality-opts']={'public-key':p.get('pbk',''),'short-id':p.get('sid','')}
  result.append(item)
 return yaml.safe_dump({'proxies':result},allow_unicode=True,sort_keys=False)

def to_singbox(proxies:list[dict])->str:
 out=[]
 for p in proxies:
  kind=p['type']
  if kind not in {'vless','vmess','trojan','shadowsocks','ss','hysteria2'}: continue
  item={'type':{'ss':'shadowsocks'}.get(kind,kind),'tag':p['name'],'server':p['server'],'server_port':p['port']}
  if kind in {'vless','vmess','trojan'}: item['uuid']=p.get('uuid','')
  if p.get('tls'):
   tls={'enabled':True}
   if p.get('sni'): tls['server_name']=p['sni']
   if p.get('fp'): tls['utls']={'enabled':True,'fingerprint':p['fp']}
   if p.get('security')=='reality': tls['reality']={'enabled':True,'public_key':p.get('pbk',''),'short_id':p.get('sid','')}
   item['tls']=tls
  if p.get('network')=='ws': item['transport']={'type':'ws','path':p.get('path') or '/','headers':({'Host':p.get('host_header')} if p.get('host_header') else {})}
  out.append(item)
 return json.dumps({'outbounds':out},ensure_ascii=False,separators=(',',':'))

def to_v2ray_json(proxies:list[dict])->str:
 out=[]
 for p in proxies:
  kind=p['type']; server={'address':p['server'],'port':p['port']}
  if kind=='vless':
   out.append({'tag':p['name'],'protocol':'vless','settings':{'vnext':[{'address':p['server'],'port':p['port'],'users':[{'id':p.get('uuid',''),'encryption':'none','flow':p.get('flow','')}]}]},'streamSettings':_stream(p)})
  elif kind=='vmess':
   out.append({'tag':p['name'],'protocol':'vmess','settings':{'vnext':[{'address':p['server'],'port':p['port'],'users':[{'id':p.get('uuid',''),'alterId':0,'security':'auto'}]}]},'streamSettings':_stream(p)})
  elif kind=='trojan':
   out.append({'tag':p['name'],'protocol':'trojan','settings':{'servers':[{'address':p['server'],'port':p['port'],'password':p.get('uuid','')}]},'streamSettings':_stream(p)})
  elif kind=='ss':
   out.append({'tag':p['name'],'protocol':'shadowsocks','settings':{'servers':[server]}})
 return json.dumps({'log':{'loglevel':'warning'},'outbounds':out},ensure_ascii=False,separators=(',',':'))

def _stream(p:dict)->dict:
 stream={'network':p.get('network') or 'tcp','security':'tls' if p.get('tls') else 'none'}
 if p.get('tls'): stream['tlsSettings']={'serverName':p.get('sni') or p['server'],'fingerprint':p.get('fp') or 'chrome'}
 if p.get('network')=='ws': stream['wsSettings']={'path':p.get('path') or '/','headers':({'Host':p.get('host_header')} if p.get('host_header') else {})}
 if p.get('security')=='reality': stream['security']='reality'; stream['realitySettings']={'serverName':p.get('sni') or p['server'],'fingerprint':p.get('fp') or 'chrome','publicKey':p.get('pbk',''),'shortId':p.get('sid','')}
 return stream


def rename_link(link:str,name:str)->str:
 from urllib.parse import quote
 scheme=link.split('://',1)[0].lower()
 if scheme=='vmess':
  try:
   rest=link.split('://',1)[1]; data=json.loads(base64.b64decode(rest+'='*(-len(rest)%4))); data['ps']=name
   return 'vmess://'+base64.b64encode(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()).decode()
  except Exception: return link
 return link.split('#',1)[0]+'#'+quote(name)

def apply_aliases(links:list[str],inbounds:list[tuple],aliases:dict)->list[str]:
 """inbounds: (tag,protocol,network,security) of one panel; aliases: tag->display name.
 A link is renamed only when it maps to exactly one aliased inbound (by tag in its name, else by protocol/network/security)."""
 if not aliases: return links
 out=[]
 for link in links:
  p=parse_link(link)
  if not p: out.append(link); continue
  name=p.get('name','')
  hit=[t for t,*_ in inbounds if t in aliases and t and t in name]
  if len(hit)!=1:
   sig=(p['type'],p.get('network') or 'tcp',p.get('security') or ('tls' if p.get('tls') else 'none'))
   cand=[t for t,pr,nw,sc in inbounds if ((pr or '').lower(),nw or 'tcp',sc or 'none')==sig]
   hit=cand if len(cand)==1 and cand[0] in aliases else []
  out.append(rename_link(link,aliases[hit[0]]) if len(hit)==1 else link)
 return out
