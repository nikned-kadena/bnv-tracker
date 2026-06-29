import { useState, useEffect, useMemo, useRef } from "react";

const REPO = "https://raw.githubusercontent.com/nikned-kadena/bnv-tracker/main/data";

const SOURCES = {
  halo: {
    key:   "halo",
    label: "Halo Oglasi",
    files: { prodaja: "latest_prodaja.json", renta: "latest_renta.json" },
    agMode: "slug",   // agencija je slug → mapping
  },
  nrs: {
    key:   "nrs",
    label: "Nekretnine.rs",
    files: { prodaja: "latest_nrs_prodaja.json", renta: "latest_nrs_renta.json" },
    agMode: "name",   // agencija je već puno ime
  },
};

const STR_ORDER  = ["1.0","1.5","2.0","2.5","3.0","3.5","4.0","5.0"];
const STR_LABEL  = {"1.0":"Garsonjera/Studio","1.5":"Jednoiposoban","2.0":"Dvosoban","2.5":"Dvoiposoban","3.0":"Trosoban","3.5":"Troiposoban","4.0":"Četvorosoban","5.0":"Petosoban+"};
const STR_COLOR  = {"1.0":"#10B981","1.5":"#EC4899","2.0":"#F59E0B","2.5":"#8B5CF6","3.0":"#22C55E","3.5":"#06B6D4","4.0":"#F97316","5.0":"#EF4444"};
const PERIODS    = [{k:7,l:"7d"},{k:30,l:"30d"},{k:90,l:"90d"},{k:365,l:"1g"}];

const C = {
  navy:"#1B2A4A", navyL:"#243659", bg:"#F0F2F5", white:"#FFFFFF",
  text:"#111827", textS:"#6B7280", textXS:"#9CA3AF", border:"#E5E7EB",
  green:"#10B981", red:"#EF4444", blue:"#3B82F6",
  shadow:"0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04)",
  shadowM:"0 4px 12px rgba(0,0,0,.08), 0 2px 4px rgba(0,0,0,.04)",
};

const fmt       = n => n==null?"–":new Intl.NumberFormat("sr-RS").format(Math.round(n));
const fmtK      = n => n==null?"–":n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?(n/1e3).toFixed(0)+"k":String(Math.round(n));
const fmtKRenta = n => n==null?"–":n>=1e6?(n/1e6).toFixed(1)+"M":new Intl.NumberFormat("sr-RS").format(Math.round(n));
const fmtPct    = n => n==null?"–":(n>=0?"+":"")+n.toFixed(2)+"%";
const pctColor  = n => n==null?C.textS:n>0?C.green:n<0?C.red:C.textS;

function Spark({ data, color=C.blue, height=80 }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!data||data.length<2||!ref.current) return;
    const canvas=ref.current, dpr=window.devicePixelRatio||1;
    const W=canvas.offsetWidth*dpr, H=height*dpr;
    canvas.width=W; canvas.height=H;
    const ctx=canvas.getContext("2d"), P=12*dpr;
    const vals=data.map(d=>d.count||d);
    const mn=Math.min(...vals)*0.97, mx=Math.max(...vals)*1.03, rng=mx-mn||1;
    const x=i=>P+(i/(vals.length-1))*(W-2*P);
    const y=v=>P+(H-2*P)-((v-mn)/rng)*(H-2*P);
    ctx.clearRect(0,0,W,H);
    const grad=ctx.createLinearGradient(0,0,0,H);
    grad.addColorStop(0,color+"30"); grad.addColorStop(1,color+"00");
    ctx.beginPath();
    vals.forEach((v,i)=>i===0?ctx.moveTo(x(i),y(v)):ctx.lineTo(x(i),y(v)));
    ctx.lineTo(x(vals.length-1),H); ctx.lineTo(x(0),H); ctx.closePath();
    ctx.fillStyle=grad; ctx.fill();
    ctx.beginPath(); ctx.strokeStyle=color; ctx.lineWidth=2*dpr;
    ctx.lineJoin="round"; ctx.lineCap="round";
    vals.forEach((v,i)=>i===0?ctx.moveTo(x(i),y(v)):ctx.lineTo(x(i),y(v)));
    ctx.stroke();
    const lx=x(vals.length-1),ly=y(vals[vals.length-1]);
    ctx.beginPath(); ctx.arc(lx,ly,3.5*dpr,0,Math.PI*2);
    ctx.fillStyle=color; ctx.fill();
  },[data,color,height]);
  return <canvas ref={ref} style={{width:"100%",height,display:"block"}}/>;
}

function KPI({ label, value, sub, valueColor }) {
  return (
    <div style={{background:C.white,borderRadius:12,padding:"20px 24px",boxShadow:C.shadow}}>
      <div style={{fontSize:11,fontWeight:600,color:C.textS,textTransform:"uppercase",letterSpacing:.6,marginBottom:8}}>{label}</div>
      <div style={{fontSize:28,fontWeight:700,color:valueColor||C.text,lineHeight:1,marginBottom:6}}>{value}</div>
      {sub&&<div style={{fontSize:12,color:C.textS}}>{sub}</div>}
    </div>
  );
}

function Pill({ label, active, onClick, color }) {
  return (
    <button onClick={onClick} style={{
      padding:"6px 14px",borderRadius:20,fontSize:13,fontWeight:active?600:400,
      border:active?"none":`1px solid ${C.border}`,
      background:active?(color||C.navy):C.white,
      color:active?C.white:C.textS,
      cursor:"pointer",transition:"all .15s",whiteSpace:"nowrap",
    }}>{label}</button>
  );
}

function BuildingFilter({ buildings, selected, onToggle, onClear }) {
  const [open, setOpen] = useState(false);
  const count = selected.length;
  return (
    <div style={{marginBottom:10}}>
      <div style={{display:"flex",alignItems:"center",gap:8,flexWrap:"wrap"}}>
        <button onClick={()=>setOpen(o=>!o)} style={{
          display:"flex",alignItems:"center",gap:6,padding:"6px 14px",borderRadius:20,
          fontSize:13,fontWeight:600,border:"none",background:C.navy,color:C.white,
          cursor:"pointer",whiteSpace:"nowrap",
        }}>
          Zgrade
          {count>0&&<span style={{background:"rgba(255,255,255,.25)",borderRadius:20,padding:"1px 7px",fontSize:11}}>{count}</span>}
          <span style={{fontSize:10,transform:open?"rotate(180deg)":"rotate(0deg)",display:"inline-block"}}>▼</span>
        </button>
        {selected.map(z=>(
          <div key={z} style={{display:"flex",alignItems:"center",gap:4,padding:"5px 10px 5px 14px",borderRadius:20,fontSize:12,fontWeight:600,background:C.navy+"15",color:C.navy,border:`1px solid ${C.navy}40`}}>
            {z.replace("BW ","")}
            <button onClick={()=>onToggle(z)} style={{background:"none",border:"none",cursor:"pointer",color:C.navy,fontSize:14,lineHeight:1,padding:"0 2px"}}>×</button>
          </div>
        ))}
        {count===0&&!open&&<span style={{fontSize:12,color:C.textS}}>{buildings.length} zgrada</span>}
        {count>0&&<button onClick={onClear} style={{fontSize:12,color:C.textS,background:"none",border:"none",cursor:"pointer",padding:"4px 8px"}}>Obriši sve ×</button>}
      </div>
      {open&&(
        <div style={{marginTop:10,padding:"12px 14px",background:C.white,borderRadius:12,boxShadow:C.shadowM,display:"flex",gap:6,flexWrap:"wrap"}}>
          <Pill label="Sve zgrade" active={count===0} onClick={()=>{onClear();setOpen(false);}}/>
          {buildings.map(z=>(
            <Pill key={z} label={z.replace("BW ","")} active={selected.includes(z)} onClick={()=>onToggle(z)}/>
          ))}
        </div>
      )}
    </div>
  );
}

function SortTH({ label, sortKey:k, activeSortKey, sortDir, onSort, width, align="left" }) {
  const isActive=activeSortKey===k;
  const [hover,setHover]=useState(false);
  return (
    <th onClick={k?()=>onSort(k):undefined}
      onMouseEnter={()=>k&&setHover(true)} onMouseLeave={()=>setHover(false)}
      style={{width,textAlign:align,padding:"12px 20px",fontSize:11,fontWeight:700,
        color:isActive?C.navy:hover?C.navy:C.textS,
        background:hover&&k?"#F3F4F6":"transparent",
        cursor:k?"pointer":"default",userSelect:"none",
        letterSpacing:.4,textTransform:"uppercase"}}>
      {label}{k&&<span style={{marginLeft:4,fontSize:10,color:isActive?C.blue:C.textXS}}>{isActive?(sortDir===1?"↑":"↓"):"↕"}</span>}
    </th>
  );
}

function RangeBar({ min, max, globalMax, color }) {
  const left=Math.round((min||0)/globalMax*100);
  const width=Math.max(Math.round(((max||0)-(min||0))/globalMax*100),1);
  return (
    <div style={{height:4,background:"#F3F4F6",borderRadius:2,position:"relative",overflow:"hidden",margin:"6px 0"}}>
      <div style={{position:"absolute",left:left+"%",width:width+"%",height:"100%",background:color,borderRadius:2}}/>
    </div>
  );
}

// ── AGENCIJE TAB ─────────────────────────────────────────────────────────────
function AgencijeTab({ mode, listings, agMapping, agMode, nrsAgMapping = {} }) {
  // Nazivi koji se ignorišu kao agencije (greške scrapera)
  const INVALID_AG = /^(agencij[ae]|mapa|logo|foto\s*\d*|nekretnine\.rs|\d+)$/i;

  const agStats = useMemo(()=>{
    const map = {};
    for (const l of listings) {
      const raw  = l.agencija;
      if (!raw) continue;
      const naziv = agMode === "slug" ? (agMapping[raw] || raw) : raw;
      // Filtriraj genericke/pogresne nazive
      if (INVALID_AG.test(naziv.trim())) continue;
      const slug  = agMode === "slug" ? raw : null;
      if (!map[naziv]) map[naziv] = { naziv, slug, count: 0, agencija_url: null };
      map[naziv].count++;
      // Sacuvaj agencija_url samo ako ima numericki ID
      if (!map[naziv].agencija_url && l.agencija_url) {
        if (/\/agencije-za-nekretnine\/\d+/.test(l.agencija_url)) {
          map[naziv].agencija_url = l.agencija_url;
        }
      }
    }
    return Object.values(map).sort((a,b)=>b.count-a.count || a.naziv.localeCompare(b.naziv));
  },[listings, agMapping, agMode]);

  const total    = listings.filter(l=>l.agencija).length;
  const totalAll = listings.length;
  const maxCount = agStats[0]?.count || 1;
  const isProdaja = mode === "prodaja";
  const accentCol = isProdaja ? C.navy : C.blue;
  const medal = i => i===0?"🥇":i===1?"🥈":i===2?"🥉":null;

  // Generiši link za agenciju zavisno od izvora
  const agLink = (a) => {
    if (agMode === "slug" && a.slug) {
      // Halo Oglasi: direktan link na stranicu agencije
      return `https://www.halooglasi.com/oglasi/${a.slug}`;
    }
    if (agMode === "name" && a.naziv) {
      // NRS: koristi ID iz mappinga ako postoji
      const agId = nrsAgMapping[a.naziv];
      if (agId) return `https://www.nekretnine.rs/agencije-za-nekretnine/${agId}/`;
    }
    return null;
  };

  return (
    <div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:12,marginBottom:24}}>
        <KPI label={`Agencija aktivnih`} value={agStats.length} sub="sa bar jednim oglasom"/>
        <KPI label="Oglasa preko agencija" value={fmt(total)} sub={`${Math.round(total/totalAll*100)||0}% od ukupnih ${totalAll}`}/>
        <KPI label="Lider tržišta" value={agStats[0]?.naziv||"–"} sub={agStats[0]?`${agStats[0].count} oglasa`:""} valueColor={accentCol}/>
        <KPI label="Top 3 udeo" value={`${Math.round((agStats.slice(0,3).reduce((s,a)=>s+a.count,0))/(total||1)*100)}%`} sub="tržišnog učešća"/>
      </div>

      <div style={{background:C.white,borderRadius:16,boxShadow:C.shadowM,overflow:"hidden",border:`1px solid ${C.border}`}}>
        <div style={{padding:"18px 24px",borderBottom:`1px solid ${C.border}`,display:"flex",alignItems:"center",justifyContent:"space-between",background:"linear-gradient(135deg,#1B2A4A 0%,#243659 100%)"}}>
          <div>
            <div style={{fontSize:15,fontWeight:700,color:"#fff",marginBottom:2}}>Rang lista agencija — {isProdaja?"Prodaja":"Izdavanje"}</div>
            <div style={{fontSize:12,color:"rgba(255,255,255,.55)"}}>{agStats.length} aktivnih agencija · sortirano po broju oglasa</div>
          </div>
          <div style={{padding:"6px 14px",borderRadius:20,fontSize:12,fontWeight:600,background:isProdaja?"rgba(255,255,255,.15)":"rgba(59,130,246,.3)",color:"#fff"}}>
            {isProdaja?"🏠 PRODAJA":"🔑 RENTA"}
          </div>
        </div>

        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
            <thead>
              <tr style={{background:"#F8FAFC",borderBottom:`2px solid ${C.border}`}}>
                <th style={{width:52,padding:"12px 16px 12px 24px",textAlign:"center",fontSize:11,fontWeight:700,color:C.textS,letterSpacing:.4,textTransform:"uppercase"}}>Rang</th>
                <th style={{padding:"12px 20px",textAlign:"left",fontSize:11,fontWeight:700,color:C.textS,letterSpacing:.4,textTransform:"uppercase"}}>Agencija</th>
                <th style={{width:120,padding:"12px 20px",textAlign:"right",fontSize:11,fontWeight:700,color:C.textS,letterSpacing:.4,textTransform:"uppercase"}}>Oglasi</th>
                <th style={{width:220,padding:"12px 24px 12px 8px",textAlign:"left",fontSize:11,fontWeight:700,color:C.textS,letterSpacing:.4,textTransform:"uppercase"}}>Tržišni udeo</th>
              </tr>
            </thead>
            <tbody>
              {agStats.map((a,i)=>{
                const pct    = Math.round(a.count/(total||1)*100*10)/10;
                const barPct = Math.round(a.count/maxCount*100);
                const isTop3 = i < 3;
                const med    = medal(i);
                const rowBg  = i===0?"linear-gradient(90deg,#1B2A4A08,transparent)":i===1?"linear-gradient(90deg,#6B728008,transparent)":i===2?"linear-gradient(90deg,#F59E0B08,transparent)":"transparent";
                const link   = agLink(a);
                return (
                  <tr key={a.naziv} style={{borderBottom:`1px solid ${C.border}`,background:rowBg,transition:"background .12s"}}
                    onMouseEnter={e=>e.currentTarget.style.background="#F0F4FF"}
                    onMouseLeave={e=>e.currentTarget.style.background=rowBg}>
                    <td style={{padding:"14px 12px 14px 24px",textAlign:"center"}}>
                      {med ? <span style={{fontSize:18}}>{med}</span>
                           : <span style={{display:"inline-block",width:28,height:28,lineHeight:"28px",borderRadius:"50%",textAlign:"center",background:C.bg,fontSize:12,fontWeight:600,color:C.textS}}>{i+1}</span>}
                    </td>
                    <td style={{padding:"14px 20px"}}>
                      <div style={{display:"flex",alignItems:"center",gap:10}}>
                        <div style={{width:36,height:36,borderRadius:10,flexShrink:0,background:isTop3?accentCol:C.bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,fontWeight:700,color:isTop3?"#fff":C.textS}}>
                          {a.naziv.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div style={{display:"flex",alignItems:"center",gap:6}}>
                            <span style={{fontWeight:isTop3?700:500,fontSize:14,color:C.text}}>{a.naziv}</span>
                            {link && (
                              <a href={link} target="_blank" rel="noreferrer"
                                title={agMode==="slug"?"Svi oglasi na Halo Oglasima":"Oglasi agencije na Nekretnine.rs"}
                                style={{display:"inline-flex",alignItems:"center",justifyContent:"center",width:20,height:20,borderRadius:6,flexShrink:0,background:C.bg,color:C.textS,fontSize:11,textDecoration:"none",border:`1px solid ${C.border}`,transition:"all .15s"}}
                                onMouseEnter={e=>{e.currentTarget.style.background=accentCol;e.currentTarget.style.color="#fff";e.currentTarget.style.borderColor=accentCol;}}
                                onMouseLeave={e=>{e.currentTarget.style.background=C.bg;e.currentTarget.style.color=C.textS;e.currentTarget.style.borderColor=C.border;}}>↗</a>
                            )}
                          </div>
                          {agMode==="slug" && a.slug && <div style={{fontSize:11,color:C.textXS,marginTop:1}}>{a.slug}</div>}
                          {agMode==="name" && <div style={{fontSize:11,color:C.textXS,marginTop:1}}>nekretnine.rs</div>}
                        </div>
                      </div>
                    </td>
                    <td style={{padding:"14px 20px",textAlign:"right"}}>
                      <span style={{display:"inline-block",padding:"4px 12px",borderRadius:20,fontSize:14,fontWeight:700,background:isTop3?accentCol+"18":C.bg,color:isTop3?accentCol:C.text}}>{a.count}</span>
                    </td>
                    <td style={{padding:"14px 24px 14px 8px"}}>
                      <div style={{display:"flex",alignItems:"center",gap:10}}>
                        <div style={{flex:1,height:6,background:"#F1F3F5",borderRadius:3,overflow:"hidden"}}>
                          <div style={{width:barPct+"%",height:"100%",borderRadius:3,background:isTop3?`linear-gradient(90deg,${accentCol},${accentCol}99)`:"#CBD5E1",transition:"width .3s ease"}}/>
                        </div>
                        <span style={{minWidth:38,fontSize:12,fontWeight:600,textAlign:"right",color:isTop3?accentCol:C.textS}}>{pct}%</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div style={{padding:"12px 24px",borderTop:`1px solid ${C.border}`,background:"#F8FAFC",fontSize:12,color:C.textXS,display:"flex",justifyContent:"space-between"}}>
          <span>{agStats.length} agencija · {total} oglasa sa poznatom agencijom</span>
          <span>{totalAll-total} oglasa bez agencije (privatni / direktni)</span>
        </div>
      </div>
    </div>
  );
}

// ── MAIN ─────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [source,  setSource]  = useState("halo");
  const [mode,    setMode]    = useState("prodaja");
  const [data,    setData]    = useState({});        // { halo_prodaja, halo_renta, nrs_prodaja, nrs_renta }
  const [agMapping, setAgMapping] = useState({});
  const [hist,    setHist]    = useState({ halo:[], nrs:[] });
  const [loading, setLoading] = useState(true);
  const [err,     setErr]     = useState(null);
  const [period,  setPeriod]  = useState(30);
  const [selStr,  setSelStr]  = useState(null);
  const [selBlds, setSelBlds] = useState([]);
  const [search,  setSearch]  = useState("");
  const [sortKey, setSortKey] = useState("zgrada");
  const [sortDir, setSortDir] = useState(1);
  const [tab,     setTab]     = useState("pregled");
  const [showNew, setShowNew] = useState(false);
  const [saleType, setSaleType] = useState("sve");   // sve | direktna | resale (samo prodaja)
  const [nrsAgMapping, setNrsAgMapping] = useState({});

  // Učitaj sve podatke jednom
  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${REPO}/latest_prodaja.json`).then(r=>r.json()).catch(()=>null),
      fetch(`${REPO}/latest_renta.json`).then(r=>r.json()).catch(()=>null),
      fetch(`${REPO}/latest_nrs_prodaja.json`).then(r=>r.json()).catch(()=>null),
      fetch(`${REPO}/latest_nrs_renta.json`).then(r=>r.json()).catch(()=>null),
      fetch(`${REPO}/history.json`).then(r=>r.json()).catch(()=>[]),
      fetch(`${REPO}/history_nrs.json`).then(r=>r.json()).catch(()=>[]),
      fetch(`${REPO}/agencije_mapping.json`).then(r=>r.json()).catch(()=>({})),
      fetch(`${REPO}/nrs_agencije_mapping.json`).then(r=>r.json()).catch(()=>({})),
    ]).then(([hp, hr, np, nr, hh, nh, m, nm])=>{
      setData({ halo_prodaja:hp, halo_renta:hr, nrs_prodaja:np, nrs_renta:nr });
      setHist({ halo: hh||[], nrs: nh||[] });
      setAgMapping(m||{});
      setNrsAgMapping(nm||{});
      setLoading(false);
    }).catch(e=>{ setErr(e.message); setLoading(false); });
  },[]);

  // Reset filtera kad se promijeni source/mode
  useEffect(()=>{ setSelBlds([]); setShowNew(false); setSelStr(null); setSearch(""); setSaleType("sve"); },[source,mode]);

  const srcCfg  = SOURCES[source];
  const dataKey = `${source}_${mode}`;
  const latest  = data[dataKey] || null;

  const listings     = useMemo(()=>latest?.listings??[],[latest]);
  const diff         = useMemo(()=>latest?.diff??{},[latest]);
  const byZgrada     = useMemo(()=>latest?.stats?.po_zgradi??{},[latest]);
  const allBuildings = useMemo(()=>Object.keys(byZgrada).sort(),[byZgrada]);

  const histData  = hist[source] || [];
  const histSlice = useMemo(()=>{
    const filtered = source === "nrs"
      ? histData.filter(h=>h.mode===mode)
      : histData;
    return filtered.slice(-period);
  },[histData, source, mode, period]);

  const priceIdx = useMemo(()=>{
    if(histData.length<2) return {dod:null,ytd:null};
    const relevant = source==="nrs" ? histData.filter(h=>h.mode===mode) : histData;
    if(relevant.length<2) return {dod:null,ytd:null};
    const last=relevant[relevant.length-1], prev=relevant[relevant.length-2];
    const ytd=relevant.find(h=>h.date?.startsWith(new Date().getFullYear()+"-01"))??relevant[0];
    const g=h=>h.avg_m2??null;
    const lv=g(last),pv=g(prev),yv=g(ytd);
    return {dod:lv&&pv?(lv-pv)/pv*100:null, ytd:lv&&yv?(lv-yv)/yv*100:null};
  },[histData,source,mode]);

  const newKeys = useMemo(()=>new Set((diff.new??[]).map(l=>l.dedup_key||l.id).filter(Boolean)),[diff]);

  // Filter tipa prodaje: direktna (cena se završava na 888) vs resale (ostalo).
  // Primenjuje se na osnovni niz pa važi za KPI, segmentaciju i listinge.
  const isDirektna = (l)=> l.cena!=null && l.cena%1000===888;
  const saleFiltered = useMemo(()=>{
    if(mode!=="prodaja" || saleType==="sve") return listings;
    if(saleType==="direktna") return listings.filter(isDirektna);
    return listings.filter(l=>!isDirektna(l));   // resale
  },[listings,mode,saleType]);

  const bldFiltered = useMemo(()=>
    selBlds.length>0 ? saleFiltered.filter(l=>selBlds.includes(l.zgrada)) : saleFiltered
  ,[saleFiltered,selBlds]);

  // Jedinstvene nekretnine (dedup po dedup_key) — za KPI i Segmentaciju.
  // Listinzi i dalje koriste pun niz (prikazuju i duplikate).
  const uniqFiltered = useMemo(()=>{
    const seen=new Set(); const out=[];
    for(const l of bldFiltered){
      const k=l.dedup_key||l.id;
      if(seen.has(k)) continue;
      seen.add(k); out.push(l);
    }
    return out;
  },[bldFiltered]);

  const segByStr = useMemo(()=>{
    const result={};
    for(const l of uniqFiltered){
      const s=l.struktura||"nepoznato";
      if(!result[s]) result[s]={label:STR_LABEL[s]||s,count:0,cene:[],cene_m2:[],m2s:[]};
      result[s].count++;
      if(l.cena)    result[s].cene.push(l.cena);
      if(l.cena_m2) result[s].cene_m2.push(l.cena_m2);
      if(l.m2)      result[s].m2s.push(l.m2);
    }
    const agg=v=>v.length?{min:Math.min(...v),max:Math.max(...v),avg:Math.round(v.reduce((a,b)=>a+b)/v.length)}:null;
    return Object.fromEntries(Object.entries(result).map(([s,v])=>[s,{...v,cena:agg(v.cene),cena_m2:agg(v.cene_m2),m2:agg(v.m2s)}]));
  },[uniqFiltered]);

  const summary = useMemo(()=>{
    const prices=uniqFiltered.filter(l=>l.cena).map(l=>l.cena);
    const m2s=uniqFiltered.filter(l=>l.cena_m2).map(l=>l.cena_m2);
    const dups=selBlds.length>0
      ? (latest?.duplicates??[]).filter(d=>bldFiltered.some(l=>l.id===d.original_id)).length
      : latest?.total_dups??0;
    return {
      cnt:uniqFiltered.length, dups,
      minC:prices.length?Math.min(...prices):null,
      maxC:prices.length?Math.max(...prices):null,
      avgM2:m2s.length?Math.round(m2s.reduce((a,b)=>a+b)/m2s.length):null,
    };
  },[uniqFiltered,bldFiltered,selBlds,latest]);

  const diffSummary = useMemo(()=>({
    newCount:     selBlds.length>0?(diff.new??[]).filter(l=>selBlds.includes(l.zgrada)).length:(diff.new?.length??0),
    removedCount: selBlds.length>0?(diff.removed??[]).filter(l=>selBlds.includes(l.zgrada)).length:(diff.removed?.length??0),
  }),[diff,selBlds]);

  const agListings = useMemo(()=>saleFiltered,[saleFiltered]);

  const filtered = useMemo(()=>{
    let d=saleFiltered;
    if(showNew)           d=d.filter(l=>newKeys.has(l.dedup_key));
    if(selStr)            d=d.filter(l=>l.struktura===selStr);
    if(selBlds.length>0)  d=d.filter(l=>selBlds.includes(l.zgrada));
    if(search)            d=d.filter(l=>(l.zgrada+(l.naslov||"")+(l.agencija||"")).toLowerCase().includes(search.toLowerCase()));
    return d.slice().sort((a,b)=>{
      const agLabel = x => srcCfg.agMode==="slug" ? (agMapping[x.agencija]||x.agencija||"") : (x.agencija||"");
      const v=x=>sortKey==="zgrada"?(x.zgrada||""):sortKey==="str"?parseFloat(x.struktura||99):sortKey==="m2"?(x.m2||0):sortKey==="cena"?(x.cena||0):sortKey==="agencija"?agLabel(x):(x.cena_m2||0);
      const va=v(a),vb=v(b);
      if(typeof va==="string") return va.localeCompare(vb)*sortDir;
      return (va-vb)*sortDir;
    });
  },[saleFiltered,showNew,newKeys,selStr,selBlds,search,sortKey,sortDir,agMapping,srcCfg]);

  const toggleSort=k=>{if(sortKey===k)setSortDir(d=>-d);else{setSortKey(k);setSortDir(1);}};
  const toggleBld=z=>setSelBlds(prev=>prev.includes(z)?prev.filter(x=>x!==z):[...prev,z]);

  const maxC  = Math.max(...STR_ORDER.map(s=>segByStr[s]?.cena?.max||0));
  const maxM2 = Math.max(...STR_ORDER.map(s=>segByStr[s]?.cena_m2?.max||0));
  const trendLast=histSlice[histSlice.length-1];
  const trendPrev=histSlice[Math.max(0,histSlice.length-2)];
  const cntDelta=trendLast&&trendPrev?trendLast.count-trendPrev.count:null;
  const scraped=latest?.scraped_at?.slice(0,10)+" "+latest?.scraped_at?.slice(11,16)+" UTC";
  const now=new Date().toLocaleDateString("sr-RS",{day:"2-digit",month:"2-digit",year:"numeric"})+" "+new Date().toLocaleTimeString("sr-RS",{hour:"2-digit",minute:"2-digit"});
  const isFiltered=selBlds.length>0 || (mode==="prodaja" && saleType!=="sve");

  if(loading) return <div style={{display:"flex",alignItems:"center",justifyContent:"center",height:"100vh",background:C.bg,fontSize:14,color:C.textS}}>Učitavanje podataka...</div>;
  if(err)     return <div style={{padding:32,background:C.bg,minHeight:"100vh",fontSize:13,color:C.red}}><strong>Greška:</strong> {err}</div>;

  return (
    <div style={{fontFamily:"-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",background:C.bg,minHeight:"100vh",fontSize:13,color:C.text}}>

      {/* Nav */}
      <div style={{background:C.navy,padding:"0 16px",display:"flex",alignItems:"center",height:52,gap:12}}>
        <div style={{display:"flex",alignItems:"center",gap:10,marginRight:"auto"}}>
          <div style={{width:28,height:28,borderRadius:6,background:"rgba(255,255,255,.15)",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <span style={{color:"#fff",fontSize:11,fontWeight:700}}>BW</span>
          </div>
          <span style={{color:"#fff",fontSize:14,fontWeight:600}}>Market Intelligence</span>
        </div>

        {/* Source switcher */}
        <div style={{display:"flex",gap:2,background:"rgba(255,255,255,.08)",borderRadius:8,padding:3}}>
          {Object.values(SOURCES).map(s=>(
            <button key={s.key} onClick={()=>setSource(s.key)} style={{
              padding:"4px 12px",fontSize:11,fontWeight:500,borderRadius:6,border:"none",cursor:"pointer",
              background:source===s.key?"rgba(255,255,255,.9)":"transparent",
              color:source===s.key?C.navy:"rgba(255,255,255,.6)",
              transition:"all .15s",whiteSpace:"nowrap",
            }}>{s.label}</button>
          ))}
        </div>

        {/* Mode switcher */}
        <div style={{display:"flex",gap:2,background:"rgba(255,255,255,.1)",borderRadius:8,padding:3}}>
          {[["prodaja","Prodaja"],["renta","Renta"]].map(([k,l])=>(
            <button key={k} onClick={()=>setMode(k)} style={{
              padding:"4px 14px",fontSize:12,fontWeight:500,borderRadius:6,border:"none",cursor:"pointer",
              background:mode===k?"#fff":"transparent",color:mode===k?C.navy:"rgba(255,255,255,.7)",
              transition:"all .15s",
            }}>{l}</button>
          ))}
        </div>

        <span style={{color:"rgba(255,255,255,.4)",fontSize:10}}>{scraped}</span>
      </div>

      {/* Source indicator bar */}
      {!latest && (
        <div style={{background:"#FEF3C7",borderBottom:"1px solid #FDE68A",padding:"8px 16px",fontSize:12,color:"#92400E",textAlign:"center"}}>
          ⚠️ Podaci za {srcCfg.label} — {mode} još nisu dostupni. Scraper će ih generisati sledećeg pokretanja.
        </div>
      )}

      <div style={{padding:"16px",maxWidth:1200,margin:"0 auto"}}>

        {/* Info bar */}
        <div style={{background:C.white,borderRadius:10,padding:"10px 16px",marginBottom:16,display:"flex",alignItems:"center",gap:12,boxShadow:C.shadow,flexWrap:"wrap"}}>
          <span style={{fontSize:11,fontWeight:600,padding:"3px 10px",borderRadius:20,background:C.navy+"12",color:C.navy}}>{srcCfg.label}</span>
          <span style={{fontSize:12,color:C.textS}}>📅 <strong style={{color:C.text}}>{scraped}</strong></span>
          <span style={{marginLeft:"auto",fontSize:12,color:C.textS}}>{now}</span>
        </div>

        {/* Tab nav */}
        <div style={{display:"flex",gap:0,borderBottom:`1px solid ${C.border}`,marginBottom:20,overflowX:"auto"}}>
          {[["pregled","Segmentacija"],["trend","Trend"],["listinzi","Listinzi"],["agencije","Agencije"]].map(([k,l])=>(
            <button key={k} onClick={()=>setTab(k)} style={{
              padding:"10px 18px",fontSize:13,fontWeight:tab===k?600:400,
              background:"transparent",border:"none",whiteSpace:"nowrap",
              borderBottom:tab===k?`2px solid ${C.navy}`:"2px solid transparent",
              color:tab===k?C.navy:C.textS,cursor:"pointer",marginBottom:-1,
            }}>
              {l}
              {k==="agencije"&&<span style={{marginLeft:6,fontSize:11,padding:"2px 7px",borderRadius:10,background:mode==="prodaja"?C.navy+"18":C.blue+"18",color:mode==="prodaja"?C.navy:C.blue,fontWeight:600}}>{mode==="prodaja"?"P":"R"}</span>}
            </button>
          ))}
        </div>

        {/* SWITCH TIP PRODAJE na Agencije tabu (samo prodaja) */}
        {tab==="agencije" && mode==="prodaja" && latest && (
          <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:14,alignItems:"center"}}>
            <span style={{fontSize:11,fontWeight:600,color:C.textS,marginRight:4}}>TIP PRODAJE</span>
            {[["sve","Sve"],["direktna","Direktna prodaja"],["resale","Resale"]].map(([k,l])=>(
              <button key={k} onClick={()=>setSaleType(k)}
                style={{fontSize:12,fontWeight:600,padding:"6px 14px",borderRadius:20,cursor:"pointer",
                  border:`1px solid ${saleType===k?C.navy:C.border}`,
                  background:saleType===k?C.navy:C.white,
                  color:saleType===k?"#fff":C.textS}}>
                {l}
              </button>
            ))}
          </div>
        )}

        {/* AGENCIJE TAB */}
        {tab==="agencije" && latest && (
          <AgencijeTab mode={mode} listings={agListings} agMapping={agMapping} agMode={srcCfg.agMode} nrsAgMapping={nrsAgMapping}/>
        )}

        {/* OSTALI TABOVI */}
        {tab!=="agencije" && latest && (<>
          <BuildingFilter buildings={allBuildings} selected={selBlds} onToggle={toggleBld} onClear={()=>setSelBlds([])}/>

          {mode==="prodaja" && (
            <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:14,alignItems:"center"}}>
              <span style={{fontSize:11,fontWeight:600,color:C.textS,marginRight:4}}>TIP PRODAJE</span>
              {[["sve","Sve"],["direktna","Direktna prodaja"],["resale","Resale"]].map(([k,l])=>(
                <button key={k} onClick={()=>setSaleType(k)}
                  style={{fontSize:12,fontWeight:600,padding:"6px 14px",borderRadius:20,cursor:"pointer",
                    border:`1px solid ${saleType===k?C.navy:C.border}`,
                    background:saleType===k?C.navy:C.white,
                    color:saleType===k?"#fff":C.textS}}>
                  {l}
                </button>
              ))}
            </div>
          )}

          <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:20}}>
            <Pill label="Sve" active={!selStr} onClick={()=>setSelStr(null)}/>
            {STR_ORDER.filter(s=>segByStr[s]).map(s=>(
              <Pill key={s} label={STR_LABEL[s]} active={selStr===s} onClick={()=>setSelStr(selStr===s?null:s)} color={STR_COLOR[s]}/>
            ))}
          </div>

          {/* KPI row */}
          <div style={{display:"grid",gridTemplateColumns:"repeat(7,1fr)",gap:12,marginBottom:20}}>
            <KPI label="Unique nekretnine" value={fmt(summary.cnt)} sub={isFiltered?`od ${latest?.total_unique} ukupno`:`${latest?.total_raw??0} oglasa, ${latest?.total_dups??0} dup.`}/>
            <KPI label="Duplikati" value={fmt(summary.dups)} sub={isFiltered?"za selektovane zgrade":"ista nkrt, više agencija"}/>
            <div onClick={()=>{setShowNew(true);setTab("listinzi");}} style={{cursor:"pointer"}}>
              <KPI label="Novi danas ↗" value={`+${diffSummary.newCount}`} sub={`−${diffSummary.removedCount} skinuto · klikni`} valueColor={C.green}/>
            </div>
            <KPI label="Cena raspon" value={summary.minC?(mode==="renta"?`${fmtKRenta(summary.minC)}–${fmtKRenta(summary.maxC)} €`:`${fmtK(summary.minC)}–${fmtK(summary.maxC)} €`):"–"}/>
            <KPI label="Prosek €/m²" value={summary.avgM2?`${fmt(summary.avgM2)} €`:"–"} sub={isFiltered?"selektovane zgrade":"sve strukture"}/>
            <KPI label="DoD" value={fmtPct(priceIdx.dod)} sub="globalni indeks" valueColor={pctColor(priceIdx.dod)}/>
            <KPI label="YTD" value={fmtPct(priceIdx.ytd)} sub="globalni indeks" valueColor={pctColor(priceIdx.ytd)}/>
          </div>

          {/* PREGLED */}
          {tab==="pregled"&&(
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(280px,1fr))",gap:16}}>
              {STR_ORDER.filter(s=>segByStr[s]&&(!selStr||selStr===s)).map(s=>{
                const v=segByStr[s], col=STR_COLOR[s];
                const c=v.cena??{}, m=v.cena_m2??{}, sz=v.m2??{};
                return (
                  <div key={s} onClick={()=>setSelStr(selStr===s?null:s)}
                    style={{background:C.white,borderRadius:12,padding:"18px 20px",boxShadow:selStr===s?`0 0 0 2px ${col}`:C.shadow,cursor:"pointer",transition:"box-shadow .15s"}}>
                    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:14}}>
                      <div style={{display:"flex",alignItems:"center",gap:8}}>
                        <div style={{width:10,height:10,borderRadius:"50%",background:col}}/>
                        <span style={{fontSize:14,fontWeight:600}}>{v.label}</span>
                      </div>
                      <span style={{fontSize:12,fontWeight:600,color:C.white,background:col,padding:"2px 10px",borderRadius:20}}>{v.count}</span>
                    </div>
                    {sz.min&&<div style={{fontSize:11,color:C.textS,marginBottom:10}}>{sz.min} – {sz.max} m²</div>}
                    <div style={{marginBottom:10}}>
                      <div style={{fontSize:11,color:C.textS,marginBottom:2}}>Cena apsolutna</div>
                      <RangeBar min={c.min} max={c.max} globalMax={maxC||1} color={col}/>
                      <div style={{display:"flex",justifyContent:"space-between",fontSize:12,fontWeight:500}}>
                        <span>{mode==="renta"?fmtKRenta(c.min):fmtK(c.min)} €</span>
                        <span>{mode==="renta"?fmtKRenta(c.max):fmtK(c.max)} €</span>
                      </div>
                    </div>
                    {mode==="prodaja"&&(
                      <div>
                        <div style={{fontSize:11,color:C.textS,marginBottom:2}}>Cena po m²</div>
                        <RangeBar min={m.min} max={m.max} globalMax={maxM2||1} color={col}/>
                        <div style={{display:"flex",justifyContent:"space-between",fontSize:12,fontWeight:500}}>
                          <span>{fmt(m.min)} €/m²</span><span>{fmt(m.max)} €/m²</span>
                        </div>
                        {m.avg&&<div style={{fontSize:11,color:C.textS,marginTop:4,textAlign:"right"}}>prosek ~{fmt(m.avg)} €/m²</div>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* TREND */}
          {tab==="trend"&&(
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
              <div style={{background:C.white,borderRadius:12,padding:"20px",boxShadow:C.shadow,gridColumn:"1/-1"}}>
                <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:16,flexWrap:"wrap",gap:8}}>
                  <div>
                    <div style={{fontSize:14,fontWeight:600,marginBottom:8}}>Broj oglasa na tržištu</div>
                    <div style={{display:"flex",gap:16,flexWrap:"wrap"}}>
                      {[{l:"Danas",v:trendLast?fmt(trendLast.count):"–",c:null},{l:"Promena 24h",v:cntDelta!=null?(cntDelta>=0?"+":"")+cntDelta:"–",c:pctColor(cntDelta)},{l:"Prosek €/m²",v:trendLast?.avg_m2?fmt(trendLast.avg_m2)+" €":"–",c:null}].map(({l,v,c})=>(
                        <div key={l} style={{fontSize:12,color:C.textS}}>
                          <div style={{fontSize:18,fontWeight:700,color:c||C.text}}>{v}</div>{l}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
                    {PERIODS.map(p=>(
                      <button key={p.k} onClick={()=>setPeriod(p.k)} style={{padding:"5px 10px",fontSize:12,borderRadius:8,border:`1px solid ${C.border}`,background:period===p.k?C.navy:C.white,color:period===p.k?C.white:C.textS,fontWeight:period===p.k?600:400,cursor:"pointer"}}>{p.l}</button>
                    ))}
                  </div>
                </div>
                {histSlice.length>=2 ? <Spark data={histSlice} color={C.blue} height={100}/> : <div style={{height:100,display:"flex",alignItems:"center",justifyContent:"center",color:C.textS,fontSize:12}}>Nema dovoljno podataka za trend.</div>}
                {histSlice.length>=2&&<div style={{display:"flex",justifyContent:"space-between",fontSize:11,color:C.textXS,marginTop:8}}><span>{histSlice[0]?.date}</span><span>{histSlice[histSlice.length-1]?.date}</span></div>}
              </div>
              {[{l:"Indeks cena DoD",v:fmtPct(priceIdx.dod),sub:"vs juče",n:priceIdx.dod},{l:"Indeks cena YTD",v:fmtPct(priceIdx.ytd),sub:"od 01.01.",n:priceIdx.ytd},{l:"Novi oglasi danas",v:`+${diff.new?.length??0}`,sub:"vs juče",n:diff.new?.length},{l:"Skinuti oglasi",v:`−${diff.removed?.length??0}`,sub:"vs juče",n:-(diff.removed?.length??0)}].map(({l,v,sub,n})=>(
                <KPI key={l} label={l} value={v} sub={sub} valueColor={pctColor(n)}/>
              ))}
              {histSlice.length>0&&(
                <div style={{background:C.white,borderRadius:12,padding:"20px",boxShadow:C.shadow,gridColumn:"1/-1"}}>
                  <div style={{fontSize:14,fontWeight:600,marginBottom:14}}>Dnevna istorija</div>
                  <div style={{overflowX:"auto"}}>
                    <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
                      <thead><tr style={{borderBottom:`1px solid ${C.border}`}}>{["Datum","Raw","Unique","Dup.","Novi","Skinuti","Avg €/m²"].map(h=><th key={h} style={{textAlign:"left",padding:"8px 10px",fontSize:11,fontWeight:600,color:C.textS}}>{h}</th>)}</tr></thead>
                      <tbody>
                        {[...histSlice].reverse().map((h,i)=>(
                          <tr key={i} style={{borderBottom:`1px solid ${C.border}`}} onMouseEnter={e=>e.currentTarget.style.background="#F9FAFB"} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
                            <td style={{padding:"9px 10px",fontWeight:600}}>{h.date}</td>
                            <td style={{padding:"9px 10px"}}>{fmt(h.total_raw)}</td>
                            <td style={{padding:"9px 10px",fontWeight:600}}>{fmt(h.total_unique)}</td>
                            <td style={{padding:"9px 10px",color:C.textS}}>{fmt(h.total_dups)}</td>
                            <td style={{padding:"9px 10px",color:C.green}}>{h.diff_new>0?`+${h.diff_new}`:"–"}</td>
                            <td style={{padding:"9px 10px",color:C.red}}>{h.diff_removed>0?`−${h.diff_removed}`:"–"}</td>
                            <td style={{padding:"9px 10px",color:C.textS}}>{h.avg_m2?fmt(h.avg_m2)+" €":"–"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* LISTINZI */}
          {tab==="listinzi"&&(
            <div style={{background:C.white,borderRadius:12,boxShadow:C.shadow,overflow:"hidden"}}>
              <div style={{padding:"12px 16px",borderBottom:`1px solid ${C.border}`,display:"flex",gap:8,alignItems:"center",flexWrap:"wrap"}}>
                <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Pretraži oglase, agenciju..."
                  style={{flex:1,minWidth:140,fontSize:13,padding:"7px 12px",border:`1px solid ${C.border}`,borderRadius:8,outline:"none"}}/>
                {showNew&&<span style={{padding:"4px 10px",borderRadius:20,background:C.green+"18",color:C.green,fontSize:12,fontWeight:600}}>🟢 Novi ({diffSummary.newCount})</span>}
                <span style={{fontSize:12,color:C.textS}}>{filtered.length} res.</span>
                {(selStr||selBlds.length>0||search||showNew)&&(
                  <button onClick={()=>{setSelStr(null);setSelBlds([]);setSearch("");setShowNew(false);}} style={{fontSize:12,padding:"6px 10px",cursor:"pointer",border:`1px solid ${C.border}`,borderRadius:8,background:C.white,color:C.textS}}>✕ Reset</button>
                )}
              </div>
              <div style={{overflowX:"auto"}}>
                <table style={{width:"100%",borderCollapse:"collapse",fontSize:13,tableLayout:"fixed"}}>
                  <thead style={{background:"#F9FAFB"}}>
                    <tr style={{borderBottom:`1px solid ${C.border}`}}>
                      <SortTH label="Zgrada"   sortKey="zgrada"   activeSortKey={sortKey} sortDir={sortDir} onSort={toggleSort} width="20%"/>
                      <SortTH label="Agencija" sortKey="agencija" activeSortKey={sortKey} sortDir={sortDir} onSort={toggleSort} width="18%"/>
                      <SortTH label="Tip"      sortKey="str"      activeSortKey={sortKey} sortDir={sortDir} onSort={toggleSort} width="13%"/>
                      <SortTH label="m²"       sortKey="m2"       activeSortKey={sortKey} sortDir={sortDir} onSort={toggleSort} width="7%"  align="right"/>
                      <SortTH label={mode==="prodaja"?"Cena":"Renta"} sortKey="cena" activeSortKey={sortKey} sortDir={sortDir} onSort={toggleSort} width="14%" align="right"/>
                      {mode==="prodaja"&&<SortTH label="€/m²" sortKey="m2p" activeSortKey={sortKey} sortDir={sortDir} onSort={toggleSort} width="10%" align="right"/>}
                      <SortTH label="Sprat" sortKey={null} activeSortKey={sortKey} sortDir={sortDir} onSort={toggleSort} width="9%"/>
                      <SortTH label="" sortKey={null} activeSortKey={sortKey} sortDir={sortDir} onSort={toggleSort} width="6%"/>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(l=>{
                      const col=STR_COLOR[l.struktura]??"#9CA3AF";
                      const lbl=STR_LABEL[l.struktura]??l.str_label??"–";
                      const isNew=newKeys.has(l.dedup_key||l.id);
                      const agNaziv = srcCfg.agMode==="slug"
                        ? (l.agencija ? (agMapping[l.agencija]||l.agencija) : null)
                        : (l.agencija||null);
                      return (
                        <tr key={l.id} style={{borderBottom:`1px solid ${C.border}`,background:isNew&&showNew?C.green+"0A":"transparent"}}
                          onMouseEnter={e=>e.currentTarget.style.background="#F9FAFB"}
                          onMouseLeave={e=>e.currentTarget.style.background=isNew&&showNew?C.green+"0A":"transparent"}>
                          <td style={{padding:"10px 16px",fontWeight:500,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                            <div style={{display:"flex",alignItems:"center",gap:7}}>
                              <div style={{width:8,height:8,borderRadius:"50%",background:col,flexShrink:0}}/>
                              <span style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{l.zgrada}</span>
                              {isNew&&showNew&&<span style={{fontSize:10,fontWeight:700,color:C.green,marginLeft:2}}>NEW</span>}
                            </div>
                          </td>
                          <td style={{padding:"10px 16px",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",fontSize:12,color:agNaziv?C.text:C.textXS}}>{agNaziv||"–"}</td>
                          <td style={{padding:"10px 16px"}}><span style={{display:"inline-block",padding:"3px 9px",borderRadius:20,fontSize:11,fontWeight:600,background:col+"18",color:col}}>{lbl}</span></td>
                          <td style={{padding:"10px 16px",color:C.textS,textAlign:"right"}}>{l.m2??"–"}</td>
                          <td style={{padding:"10px 16px",fontWeight:600,textAlign:"right"}}>
                            {l.cena?`${fmt(l.cena)} €`:<span style={{color:C.textS}}>na upit</span>}
                            {mode==="renta"&&l.cena?<span style={{fontSize:11,fontWeight:400,color:C.textS}}>/mj</span>:null}
                          </td>
                          {mode==="prodaja"&&<td style={{padding:"10px 16px",color:C.textS,textAlign:"right"}}>{l.cena_m2?fmt(l.cena_m2):"–"}</td>}
                          <td style={{padding:"10px 16px",color:C.textS,fontSize:12}}>{l.sprat||"–"}</td>
                          <td style={{padding:"10px 16px",textAlign:"right"}}><a href={l.url} target="_blank" rel="noreferrer" style={{color:C.blue,textDecoration:"none",fontSize:16}}>↗</a></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>)}

        {/* Nema podataka */}
        {tab!=="agencije" && !latest && (
          <div style={{textAlign:"center",padding:"60px 20px",color:C.textS}}>
            <div style={{fontSize:32,marginBottom:12}}>⏳</div>
            <div style={{fontSize:16,fontWeight:600,marginBottom:8}}>Podaci još nisu dostupni</div>
            <div style={{fontSize:13}}>{srcCfg.label} — {mode} · Biće dostupni posle prvog automatskog scrape-a</div>
          </div>
        )}

      </div>
    </div>
  );
}
