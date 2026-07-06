import { useState, useEffect, useMemo, useRef } from "react";

const REPO = "https://raw.githubusercontent.com/nikned-kadena/bnv-tracker/main/data";

const SOURCES = {
  halo: {
    key:   "halo",
    label: "Halo Oglasi",
    files: { prodaja: "latest_prodaja.json", renta: "latest_renta.json" },
    agMode: "slug",
  },
  nrs: {
    key:   "nrs",
    label: "Nekretnine.rs",
    files: { prodaja: "latest_nrs_prodaja.json", renta: "latest_nrs_renta.json" },
    agMode: "name",
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
const fmtK      = n => n==null?"–":n>=1e6?(n/1e6).toLocaleString("sr-RS",{maximumFractionDigits:1})+"M":n>=1e3?(n/1e3).toLocaleString("sr-RS",{maximumFractionDigits:0})+"k":String(Math.round(n));
const fmtKRenta = n => n==null?"–":n>=1e6?(n/1e6).toLocaleString("sr-RS",{maximumFractionDigits:1})+"M":new Intl.NumberFormat("sr-RS").format(Math.round(n));
const fmtDec    = (n, dec=2) => n==null?"–":n.toLocaleString("sr-RS",{minimumFractionDigits:dec,maximumFractionDigits:dec});
const fmtPct    = n => n==null?"–":(n>=0?"+":"")+fmtDec(n,2)+"%";
const pctColor  = n => n==null?C.textS:n>0?C.green:n<0?C.red:C.textS;
const BLD_COLORS = ["#EC4899","#10B981","#06B6D4","#3B82F6","#8B5CF6","#0EA5E9","#F59E0B","#EF4444","#84CC16","#14B8A6","#A855F7","#F97316","#22D3EE","#6366F1","#D946EF","#65A30D"];

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
    <div style={{background:C.white,borderRadius:12,padding:"16px 18px",boxShadow:C.shadow}}>
      <div style={{fontSize:11,fontWeight:600,color:C.textS,textTransform:"uppercase",letterSpacing:.6,marginBottom:6}}>{label}</div>
      <div style={{fontSize:24,fontWeight:700,color:valueColor||C.text,lineHeight:1,marginBottom:4}}>{value}</div>
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
        <span style={{fontSize:11,fontWeight:600,color:C.textS,textTransform:"uppercase",letterSpacing:.5,marginRight:4}}>Zgrada</span>
        <button onClick={()=>setOpen(o=>!o)} style={{
          display:"flex",alignItems:"center",gap:6,padding:"6px 14px",borderRadius:20,
          fontSize:13,fontWeight:600,border:"none",background:C.navy,color:C.white,
          cursor:"pointer",whiteSpace:"nowrap",
        }}>
          Zgrade
          {count>0&&<span style={{background:"rgba(255,255,255,.25)",borderRadius:20,padding:"1px 7px",fontSize:11}}>{count}</span>}
          <span style={{fontSize:10,transform:open?"rotate(180deg)":"rotate(0deg)",display:"inline-block",transition:"transform .2s"}}>▼</span>
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

// Kolapsibilni filter za strukturu — uvek kolapsiran (kao NB)
function StrFilter({ segByStr, selStr, setSelStr }) {
  const [open, setOpen] = useState(false);
  const available = STR_ORDER.filter(s=>segByStr[s]);
  const activeLabel = selStr ? STR_LABEL[selStr] : null;

  return (
    <div style={{marginBottom:16}}>
      <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:open?8:0}}>
        <span style={{fontSize:11,fontWeight:600,color:C.textS,textTransform:"uppercase",letterSpacing:.5,marginRight:4}}>Struktura</span>
        <button onClick={()=>setOpen(o=>!o)} style={{
          display:"flex",alignItems:"center",gap:5,
          background:selStr?STR_COLOR[selStr]:C.white,
          color:selStr?C.white:C.textS,
          border:`1px solid ${selStr?STR_COLOR[selStr]:C.border}`,
          padding:"6px 14px",borderRadius:20,fontSize:12,fontWeight:600,
          cursor:"pointer",
        }}>
          {activeLabel || "Sve strukture"}
          <span style={{fontSize:10,transform:open?"rotate(180deg)":"rotate(0deg)",display:"inline-block",transition:"transform .2s"}}>▼</span>
        </button>
        {selStr && (
          <button onClick={()=>{setSelStr(null);setOpen(false);}} style={{
            background:"transparent",border:`1px solid ${C.border}`,
            borderRadius:12,padding:"3px 8px",fontSize:11,color:C.textS,cursor:"pointer",
          }}>✕</button>
        )}
      </div>
      {open && (
        <div style={{padding:"10px 12px",background:C.white,borderRadius:12,boxShadow:C.shadowM,display:"flex",gap:6,flexWrap:"wrap"}}>
          <Pill label="Sve" active={!selStr} onClick={()=>{setSelStr(null);setOpen(false);}}/>
          {available.map(s=>(
            <Pill key={s} label={STR_LABEL[s]} active={selStr===s}
              onClick={()=>{setSelStr(selStr===s?null:s);setOpen(false);}}
              color={STR_COLOR[s]}/>
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
  const INVALID_AG = /^(agencij[ae]|mapa|logo|foto\s*\d*|nekretnine\.rs|\d+)$/i;

  const agStats = useMemo(()=>{
    const map = {};
    for (const l of listings) {
      const raw  = l.agencija;
      if (!raw) continue;
      const naziv = agMode === "slug" ? (agMapping[raw] || raw) : raw;
      if (INVALID_AG.test(naziv.trim())) continue;
      const slug  = agMode === "slug" ? raw : null;
      if (!map[naziv]) map[naziv] = { naziv, slug, count: 0, agencija_url: null };
      map[naziv].count++;
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

  const agLink = (a) => {
    if (agMode === "slug" && a.slug) return `https://www.halooglasi.com/oglasi/${a.slug}`;
    if (agMode === "name" && a.naziv) {
      if (a.agencija_url) return a.agencija_url;
      const agId = nrsAgMapping[a.naziv];
      if (agId) return `https://www.nekretnine.rs/agencije-za-nekretnine/${agId}/`;
    }
    return null;
  };

  return (
    <div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(160px,1fr))",gap:12,marginBottom:24}}>
        <KPI label="Agencija aktivnih" value={agStats.length} sub="sa bar jednim oglasom"/>
        <KPI label="Oglasa preko agencija" value={fmt(total)} sub={`${Math.round(total/totalAll*100)||0}% od ukupnih ${totalAll}`}/>
        <KPI label="Lider tržišta" value={agStats[0]?.naziv||"–"} sub={agStats[0]?`${agStats[0].count} oglasa`:""} valueColor={accentCol}/>
        <KPI label="Top 3 udeo" value={`${Math.round((agStats.slice(0,3).reduce((s,a)=>s+a.count,0))/(total||1)*100)}%`} sub="tržišnog učešća"/>
      </div>

      <div style={{background:C.white,borderRadius:16,boxShadow:C.shadowM,overflow:"hidden",border:`1px solid ${C.border}`}}>
        <div style={{padding:"18px 24px",borderBottom:`1px solid ${C.border}`,display:"flex",alignItems:"center",justifyContent:"space-between",background:"linear-gradient(135deg,#1B2A4A 0%,#243659 100%)",flexWrap:"wrap",gap:8}}>
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
                <th style={{width:100,padding:"12px 20px",textAlign:"right",fontSize:11,fontWeight:700,color:C.textS,letterSpacing:.4,textTransform:"uppercase"}}>Oglasi</th>
                <th style={{width:200,padding:"12px 24px 12px 8px",textAlign:"left",fontSize:11,fontWeight:700,color:C.textS,letterSpacing:.4,textTransform:"uppercase"}}>Tržišni udeo</th>
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
                    <td style={{padding:"12px 12px 12px 24px",textAlign:"center"}}>
                      {med ? <span style={{fontSize:18}}>{med}</span>
                           : <span style={{display:"inline-block",width:28,height:28,lineHeight:"28px",borderRadius:"50%",textAlign:"center",background:C.bg,fontSize:12,fontWeight:600,color:C.textS}}>{i+1}</span>}
                    </td>
                    <td style={{padding:"12px 20px"}}>
                      <div style={{display:"flex",alignItems:"center",gap:10}}>
                        <div style={{width:34,height:34,borderRadius:10,flexShrink:0,background:isTop3?accentCol:C.bg,display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,fontWeight:700,color:isTop3?"#fff":C.textS}}>
                          {a.naziv.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div style={{display:"flex",alignItems:"center",gap:6}}>
                            <span style={{fontWeight:isTop3?700:500,fontSize:14,color:C.text}}>{a.naziv}</span>
                            {link && (
                              <a href={link} target="_blank" rel="noreferrer"
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
                    <td style={{padding:"12px 20px",textAlign:"right"}}>
                      <span style={{display:"inline-block",padding:"4px 12px",borderRadius:20,fontSize:14,fontWeight:700,background:isTop3?accentCol+"18":C.bg,color:isTop3?accentCol:C.text}}>{a.count}</span>
                    </td>
                    <td style={{padding:"12px 24px 12px 8px"}}>
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
        <div style={{padding:"12px 24px",borderTop:`1px solid ${C.border}`,background:"#F8FAFC",fontSize:12,color:C.textXS,display:"flex",justifyContent:"space-between",flexWrap:"wrap",gap:4}}>
          <span>{agStats.length} agencija · {total} oglasa sa poznatom agencijom</span>
          <span>{totalAll-total} oglasa bez agencije</span>
        </div>
      </div>
    </div>
  );
}

// ── MAIN ─────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [source,  setSource]  = useState("halo");
  const [mode,    setMode]    = useState("prodaja");
  const [data,    setData]    = useState({});
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
  const [saleType, setSaleType] = useState("sve");
  const [bldSortKey, setBldSortKey] = useState("count");
  const [bldSortDir, setBldSortDir] = useState(-1);
  const [nrsAgMapping, setNrsAgMapping] = useState({});

  // Mobilni breakpoint
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(()=>{
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);

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

  useEffect(()=>{ setSelBlds([]); setShowNew(false); setSelStr(null); setSearch(""); setSaleType("sve"); },[source,mode]);

  const srcCfg  = SOURCES[source];
  const dataKey = `${source}_${mode}`;
  const latest  = data[dataKey] || null;

  const normZgrada = (z)=>{
    if(!z) return "Neidentifikovano";
    if(/\(/.test(z) || /neident/i.test(z)) return "Neidentifikovano";
    return z;
  };
  const listings = useMemo(()=>{
    const raw = latest?.listings??[];
    // Mode-aware sanity opseg: prodaja 1.200-25.000, renta 3-120 EUR/m2 mesecno
    const okPM2 = mode==="prodaja" ? ((p)=> p>=1200 && p<=25000) : ((p)=> p>=3 && p<=120);
    return raw.map(l=>{
      const nz=normZgrada(l.zgrada);
      let m2=l.m2, cm2=l.cena_m2, fixed=false;
      if(mode==="prodaja" && m2!=null && l.cena!=null && !okPM2(l.cena/m2)){
        for(const d of [10,100,1000]){
          if(okPM2(l.cena/(m2/d))){ m2=+(m2/d).toFixed(2); cm2=Math.round(l.cena/m2); fixed=true; break; }
        }
      }
      // Izvedi cena_m2 kad je scraper nije poslao (NRS je ne racuna,
      // Halo renta pre v4.19 takodje) - imamo cenu i m2, racun je trivijalan
      if(!cm2 && l.cena!=null && m2!=null && okPM2(l.cena/m2)){
        cm2=Math.round(l.cena/m2); fixed=true;
      }
      if(nz===l.zgrada && !fixed) return l;
      return {...l, zgrada:nz, m2, cena_m2:cm2};
    });
  },[latest,mode]);

  const diff         = useMemo(()=>latest?.diff??{},[latest]);
  const allBuildings = useMemo(()=>{
    const set=new Set(listings.map(l=>l.zgrada).filter(z=>z && z!=="Neidentifikovano"));
    return [...set].sort();
  },[listings]);

  const histData  = hist[source] || [];
  const histSlice = useMemo(()=>{
    const filtered = source === "nrs" ? histData.filter(h=>h.mode===mode) : histData;
    return filtered.slice(-period);
  },[histData, source, mode, period]);

  const newKeys = useMemo(()=>new Set((diff.new??[]).map(l=>l.dedup_key||l.id).filter(Boolean)),[diff]);

  const isDirektna = (l)=> l.cena!=null && l.cena%1000===888;
  const saleFiltered = useMemo(()=>{
    if(mode!=="prodaja" || saleType==="sve") return listings;
    if(saleType==="direktna") return listings.filter(isDirektna);
    return listings.filter(l=>!isDirektna(l));
  },[listings,mode,saleType]);

  const bldFiltered = useMemo(()=>
    selBlds.length>0 ? saleFiltered.filter(l=>selBlds.includes(l.zgrada)) : saleFiltered
  ,[saleFiltered,selBlds]);

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

  // Prosek rente po kombinaciji zgrada+struktura, iz ISTOG izvora (halo/nrs).
  // Min 2 renta oglasa po kombinaciji - jedan oglas ume da bude ekstrem.
  const rentAvgMap = useMemo(()=>{
    const rl = data[`${source}_renta`]?.listings ?? [];
    const grp = {};
    for(const l of rl){
      const z = normZgrada(l.zgrada);
      if(z==="Neidentifikovano" || !l.struktura || !l.cena) continue;
      const k = `${z}|${l.struktura}`;
      (grp[k] = grp[k] || []).push(l.cena);
    }
    const map = {};
    for(const [k,arr] of Object.entries(grp)){
      if(arr.length >= 2) map[k] = arr.reduce((a,b)=>a+b,0)/arr.length;
    }
    return map;
  },[data,source]);

  const bldRanking = useMemo(()=>{
    const seen=new Set(); const grp={};
    for(const l of saleFiltered){
      const k=l.dedup_key||l.id;
      if(seen.has(k)) continue;
      seen.add(k);
      const z=l.zgrada||"Neidentifikovano";
      if(!grp[z]) grp[z]={zgrada:z,count:0,m2s:[],yields:[]};
      grp[z].count++;
      if(l.cena_m2) grp[z].m2s.push(l.cena_m2);
      // Yield: (12 x prosecna renta iste zgrade i strukture) / trazena cena.
      // Sanity 0.5-15% odbacuje apsurdna uparivanja (los parse i sl.)
      if(mode==="prodaja" && l.cena && l.struktura){
        const avgRent = rentAvgMap[`${z}|${l.struktura}`];
        if(avgRent){
          const y = (12*avgRent)/l.cena*100;
          if(y>=0.5 && y<=15) grp[z].yields.push(y);
        }
      }
    }
    const arr=Object.values(grp).map(g=>({
      zgrada:g.zgrada, count:g.count,
      avg_m2:g.m2s.length?Math.round(g.m2s.reduce((a,b)=>a+b,0)/g.m2s.length):null,
      avg_yield:g.yields.length?g.yields.reduce((a,b)=>a+b,0)/g.yields.length:null,
    }));
    return arr.sort((a,b)=>{
      const aN=a.zgrada==="Neidentifikovano", bN=b.zgrada==="Neidentifikovano";
      if(aN!==bN) return aN?1:-1;
      return b.count-a.count;
    }).map((b,i)=>({...b, color:BLD_COLORS[i%BLD_COLORS.length]}));
  },[saleFiltered,rentAvgMap,mode]);
  const bldMaxCount = bldRanking[0]?.count || 1;
  const bldTotalUnique = bldRanking.reduce((s,b)=>s+b.count,0);

  const bldSorted = useMemo(()=>{
    const arr=[...bldRanking];
    arr.sort((a,b)=>{
      const aN=a.zgrada==="Neidentifikovano", bN=b.zgrada==="Neidentifikovano";
      if(aN!==bN) return aN?1:-1;
      if(bldSortKey==="zgrada") return a.zgrada.localeCompare(b.zgrada)*bldSortDir;
      const va = bldSortKey==="avg_m2" ? (a.avg_m2??-1) : bldSortKey==="yield" ? (a.avg_yield??-1) : a.count;
      const vb = bldSortKey==="avg_m2" ? (b.avg_m2??-1) : bldSortKey==="yield" ? (b.avg_yield??-1) : b.count;
      return (va-vb)*bldSortDir;
    });
    return arr;
  },[bldRanking,bldSortKey,bldSortDir]);

  const toggleBldSort=(k)=>{
    if(bldSortKey===k) setBldSortDir(d=>-d);
    else { setBldSortKey(k); setBldSortDir(k==="zgrada"?1:-1); }
  };
  const bldSortLabel = bldSortKey==="zgrada"?"nazivu":bldSortKey==="avg_m2"?"proseku €/m²":bldSortKey==="yield"?"yield-u":"broju oglasa";

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
  const isFiltered=selBlds.length>0 || (mode==="prodaja" && saleType!=="sve");

  if(loading) return <div style={{display:"flex",alignItems:"center",justifyContent:"center",height:"100vh",background:C.bg,fontSize:14,color:C.textS}}>Učitavanje podataka...</div>;
  if(err)     return <div style={{padding:32,background:C.bg,minHeight:"100vh",fontSize:13,color:C.red}}><strong>Greška:</strong> {err}</div>;

  return (
    <div style={{fontFamily:"-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",background:C.bg,minHeight:"100vh",fontSize:13,color:C.text}}>

      {/* Nav — mobilni: flexWrap + manji padding */}
      <div style={{
        background:C.navy,
        padding:isMobile?"8px 12px":"0 16px",
        display:"flex",alignItems:"center",
        minHeight:52,gap:8,flexWrap:"wrap",
        position:"sticky",top:0,zIndex:100,
      }}>
        <div style={{display:"flex",alignItems:"center",gap:10,marginRight:"auto"}}>
          <div style={{width:28,height:28,borderRadius:6,background:"rgba(255,255,255,.15)",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <span style={{color:"#fff",fontSize:11,fontWeight:700}}>BW</span>
          </div>
          <span style={{color:"#fff",fontSize:isMobile?13:14,fontWeight:600}}>Market Intelligence</span>
        </div>

        {/* Source switcher */}
        <div style={{display:"flex",gap:2,background:"rgba(255,255,255,.08)",borderRadius:8,padding:3}}>
          {Object.values(SOURCES).map(s=>(
            <button key={s.key} onClick={()=>setSource(s.key)} style={{
              padding:isMobile?"3px 8px":"4px 12px",
              fontSize:isMobile?11:11,fontWeight:500,borderRadius:6,border:"none",cursor:"pointer",
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
              padding:isMobile?"3px 8px":"4px 14px",
              fontSize:isMobile?11:12,fontWeight:500,borderRadius:6,border:"none",cursor:"pointer",
              background:mode===k?"#fff":"transparent",color:mode===k?C.navy:"rgba(255,255,255,.7)",
              transition:"all .15s",
            }}>{l}</button>
          ))}
        </div>

        {!isMobile && <span style={{color:"rgba(255,255,255,.4)",fontSize:10}}>{scraped}</span>}
      </div>

      {!latest && (
        <div style={{background:"#FEF3C7",borderBottom:"1px solid #FDE68A",padding:"8px 16px",fontSize:12,color:"#92400E",textAlign:"center"}}>
          ⚠️ Podaci za {srcCfg.label} — {mode} još nisu dostupni.
        </div>
      )}

      <div style={{padding:isMobile?"12px":"16px 24px"}}>

        {/* Info bar */}
        <div style={{background:C.white,borderRadius:10,padding:"8px 14px",marginBottom:12,display:"flex",alignItems:"center",gap:10,boxShadow:C.shadow,flexWrap:"wrap"}}>
          <span style={{fontSize:11,fontWeight:600,padding:"3px 10px",borderRadius:20,background:C.navy+"12",color:C.navy}}>{srcCfg.label}</span>
          <span style={{fontSize:12,color:C.textS}}>📅 <strong style={{color:C.text}}>{scraped}</strong></span>
        </div>

        {/* FILTERI — tri reda: ZGRADA / TIP PRODAJE / STRUKTURA (kao NB) */}
        {latest && (
          <>
            <BuildingFilter buildings={allBuildings} selected={selBlds} onToggle={toggleBld} onClear={()=>setSelBlds([])}/>

            {mode==="prodaja" && (
              <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:10,alignItems:"center"}}>
                <span style={{fontSize:11,fontWeight:600,color:C.textS,textTransform:"uppercase",letterSpacing:.5,marginRight:4}}>Tip prodaje</span>
                {[["sve","Sve"],["direktna","Direktna prodaja"],["resale","Resale"]].map(([k,l])=>(
                  <button key={k} onClick={()=>setSaleType(k)}
                    style={{fontSize:12,fontWeight:600,padding:"5px 12px",borderRadius:20,cursor:"pointer",
                      border:`1px solid ${saleType===k?C.navy:C.border}`,
                      background:saleType===k?C.navy:C.white,
                      color:saleType===k?"#fff":C.textS}}>
                    {l}
                  </button>
                ))}
              </div>
            )}

            <StrFilter segByStr={segByStr} selStr={selStr} setSelStr={setSelStr}/>
          </>
        )}

        {/* Tab nav — horizontalni scroll na mobilnom */}
        <div style={{display:"flex",gap:0,borderBottom:`1px solid ${C.border}`,marginBottom:16,overflowX:"auto",WebkitOverflowScrolling:"touch"}}>
          {[["pregled","Segmentacija"],["zgrade","Zgrade"],["trend","Trend"],["listinzi","Listinzi"],["agencije","Agencije"]].map(([k,l])=>(
            <button key={k} onClick={()=>setTab(k)} style={{
              padding:isMobile?"8px 12px":"10px 18px",
              fontSize:isMobile?12:13,fontWeight:tab===k?600:400,
              background:"transparent",border:"none",whiteSpace:"nowrap",
              borderBottom:tab===k?`2px solid ${C.navy}`:"2px solid transparent",
              color:tab===k?C.navy:C.textS,cursor:"pointer",marginBottom:-1,
            }}>
              {l}
              {k==="agencije"&&<span style={{marginLeft:4,fontSize:10,padding:"2px 6px",borderRadius:10,background:mode==="prodaja"?C.navy+"18":C.blue+"18",color:mode==="prodaja"?C.navy:C.blue,fontWeight:600}}>{mode==="prodaja"?"P":"R"}</span>}
            </button>
          ))}
        </div>

        {/* AGENCIJE TAB */}
        {tab==="agencije" && latest && (
          <AgencijeTab mode={mode} listings={agListings} agMapping={agMapping} agMode={srcCfg.agMode} nrsAgMapping={nrsAgMapping}/>
        )}

        {/* OSTALI TABOVI */}
        {tab!=="agencije" && latest && (<>
          {/* KPI row — preko celog ekrana (kao NB) */}
          <div style={{display:"grid",gridTemplateColumns:isMobile?"repeat(2,1fr)":"repeat(auto-fit,minmax(170px,1fr))",gap:10,marginBottom:16}}>
            <KPI label="Unique nekretnine" value={fmt(summary.cnt)} sub={isFiltered?`od ${latest?.total_unique} ukupno`:`${latest?.total_raw??0} oglasa, ${latest?.total_dups??0} dup.`}/>
            <KPI label="Duplikati" value={fmt(summary.dups)} sub={isFiltered?"za selektovane zgrade":"ista nkrt, više agencija"}/>
            <div onClick={()=>{setShowNew(true);setTab("listinzi");}} style={{cursor:"pointer"}}>
              <KPI label="Novi danas ↗" value={`+${diffSummary.newCount}`} sub={`−${diffSummary.removedCount} skinuto · klikni`} valueColor={C.green}/>
            </div>
            <KPI label="Cena raspon" value={summary.minC?(mode==="renta"?`${fmtKRenta(summary.minC)}–${fmtKRenta(summary.maxC)} €`:`${fmtK(summary.minC)}–${fmtK(summary.maxC)} €`):"–"}/>
            <KPI label="Prosek €/m²" value={summary.avgM2?`${fmt(summary.avgM2)} €`:"–"} sub={isFiltered?"selektovane zgrade":"sve strukture"}/>
          </div>

          {/* PREGLED */}
          {tab==="pregled"&&(
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(260px,1fr))",gap:14}}>
              {STR_ORDER.filter(s=>segByStr[s]&&(!selStr||selStr===s)).map(s=>{
                const v=segByStr[s], col=STR_COLOR[s];
                const c=v.cena??{}, m=v.cena_m2??{}, sz=v.m2??{};
                return (
                  <div key={s} onClick={()=>setSelStr(selStr===s?null:s)}
                    style={{background:C.white,borderRadius:12,padding:"16px 18px",boxShadow:selStr===s?`0 0 0 2px ${col}`:C.shadow,cursor:"pointer",transition:"box-shadow .15s"}}>
                    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:12}}>
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

          {/* ZGRADE */}
          {tab==="zgrade"&&(
            <div style={{background:C.white,borderRadius:12,boxShadow:C.shadow,overflow:"hidden"}}>
              {/* Header traka — navy kontekstna kao NB */}
              <div style={{background:C.navyD||C.navy,padding:"14px 20px",display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8}}>
                <div>
                  <div style={{color:"#fff",fontWeight:700,fontSize:14}}>Listinzi po zgradi</div>
                  <div style={{color:"#94a3b8",fontSize:11,marginTop:2}}>
                    {mode==="prodaja"?"Prodaja":"Renta"} · klikni kolonu za sortiranje
                  </div>
                </div>
                <div style={{background:mode==="prodaja"?"#2563eb":"#16a34a",color:"#fff",padding:"3px 10px",borderRadius:6,fontSize:11,fontWeight:600}}>
                  {mode==="prodaja"?"🏠 PRODAJA":"🔑 RENTA"}
                </div>
              </div>
              <div style={{padding:"10px 18px",borderBottom:`1px solid ${C.border}`,display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:6,background:"#f8fafc"}}>
                <div style={{fontSize:12,color:C.textS}}>
                  {bldRanking.length} zgrada · {fmt(bldTotalUnique)} unique listinga
                </div>
                <span style={{fontSize:11,color:C.textS}}>sortirano po {bldSortLabel} {bldSortDir<0?"↓":"↑"}</span>
              </div>
              <div style={{overflowX:"auto"}}>
                <div style={{minWidth:mode==="prodaja"?560:480}}>
                  <div style={{display:"grid",gridTemplateColumns:mode==="prodaja"?"minmax(120px,1.4fr) 3fr 64px 92px 80px 78px":"minmax(120px,1.4fr) 3fr 64px 92px 78px",gap:10,padding:"7px 18px",borderBottom:`1px solid ${C.border}`,fontSize:10,fontWeight:600,color:C.textXS,letterSpacing:.3,textTransform:"uppercase"}}>
                    {(()=>{const arrow=k=>bldSortKey===k?(bldSortDir<0?" ↓":" ↑"):" ↕";const hs={cursor:"pointer",userSelect:"none"};const act=k=>bldSortKey===k?{color:C.navy}:{opacity:.85};const dim=k=>bldSortKey===k?{}:{opacity:.35};return(<>
                      <span style={{...hs,...act("zgrada")}} onClick={()=>toggleBldSort("zgrada")}>Zgrada<span style={{fontSize:9,...dim("zgrada")}}>{arrow("zgrada")}</span></span>
                      <span>Distribucija</span>
                      <span style={{textAlign:"center",...hs,...act("count")}} onClick={()=>toggleBldSort("count")}>Oglasi<span style={{fontSize:9,...dim("count")}}>{arrow("count")}</span></span>
                      <span style={{textAlign:"right",...hs,...act("avg_m2")}} onClick={()=>toggleBldSort("avg_m2")}>€/m²<span style={{fontSize:9,...dim("avg_m2")}}>{arrow("avg_m2")}</span></span>
                      {mode==="prodaja"&&<span style={{textAlign:"right",...hs,...act("yield")}} onClick={()=>toggleBldSort("yield")} title="Bruto yield: 12 × prosečna renta iste zgrade i strukture / tražena cena. Min 2 renta oglasa po kombinaciji.">Yield<span style={{fontSize:9,...dim("yield")}}>{arrow("yield")}</span></span>}
                      <span/>
                    </>);})()}
                  </div>
                  {bldSorted.map((b,i)=>{
                    const col=b.color;
                    return (
                      <div key={b.zgrada}
                        style={{display:"grid",gridTemplateColumns:mode==="prodaja"?"minmax(120px,1.4fr) 3fr 64px 92px 80px 78px":"minmax(120px,1.4fr) 3fr 64px 92px 78px",gap:10,
                          padding:"5px 18px",alignItems:"center",
                          borderBottom:i<bldSorted.length-1?`1px solid ${C.border}80`:"none",fontSize:13}}>
                        <div style={{display:"flex",alignItems:"center",gap:8,minWidth:0}}>
                          <div style={{width:8,height:8,borderRadius:"50%",background:col,flexShrink:0}}/>
                          <span style={{fontWeight:600,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{b.zgrada.replace("BW ","")}</span>
                        </div>
                        <div style={{background:C.bg,borderRadius:6,height:6,overflow:"hidden"}}>
                          <div style={{width:`${Math.min(100,Math.max(3,b.count/bldMaxCount*100))}%`,height:"100%",background:col,borderRadius:6}}/>
                        </div>
                        <span style={{textAlign:"center"}}>
                          <span style={{fontSize:12,fontWeight:600,color:col,background:col+"1A",padding:"2px 9px",borderRadius:20}}>{b.count}</span>
                        </span>
                        <span style={{textAlign:"right",fontWeight:500,color:b.avg_m2?C.text:C.textXS}}>{b.avg_m2?`${fmt(b.avg_m2)} €`:"–"}</span>
                        {mode==="prodaja"&&<span style={{textAlign:"right",fontWeight:700,color:b.avg_yield?"#16a34a":C.textXS}}>{b.avg_yield?`${b.avg_yield.toFixed(2)}%`:"/"}</span>}
                        <button onClick={()=>{setSelBlds([b.zgrada]);setTab("listinzi");}}
                          onMouseEnter={e=>{e.currentTarget.style.background=C.blue;e.currentTarget.style.color="#fff";e.currentTarget.style.borderColor=C.blue;}}
                          onMouseLeave={e=>{e.currentTarget.style.background="transparent";e.currentTarget.style.color=C.blue;e.currentTarget.style.borderColor=C.border;}}
                          style={{fontSize:11,fontWeight:600,color:C.blue,background:"transparent",border:`1px solid ${C.border}`,borderRadius:6,padding:"4px 10px",cursor:"pointer",whiteSpace:"nowrap",transition:"all .15s"}}>
                          Listinzi ↗
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TREND */}
          {tab==="trend"&&(
            <div style={{display:"grid",gridTemplateColumns:isMobile?"1fr":"1fr 1fr",gap:14}}>
              <div style={{background:C.white,borderRadius:12,padding:"18px",boxShadow:C.shadow,gridColumn:"1/-1"}}>
                <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:14,flexWrap:"wrap",gap:8}}>
                  <div>
                    <div style={{fontSize:14,fontWeight:600,marginBottom:8}}>Broj oglasa na tržištu</div>
                    <div style={{display:"flex",gap:14,flexWrap:"wrap"}}>
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
                {histSlice.length>=2 ? <Spark data={histSlice} color={C.blue} height={100}/> : <div style={{height:80,display:"flex",alignItems:"center",justifyContent:"center",color:C.textS,fontSize:12}}>Nema dovoljno podataka za trend.</div>}
                {histSlice.length>=2&&<div style={{display:"flex",justifyContent:"space-between",fontSize:11,color:C.textXS,marginTop:8}}><span>{histSlice[0]?.date}</span><span>{histSlice[histSlice.length-1]?.date}</span></div>}
              </div>
              {[{l:"Novi oglasi danas",v:`+${diff.new?.length??0}`,sub:"vs juče",n:diff.new?.length},{l:"Skinuti oglasi",v:`−${diff.removed?.length??0}`,sub:"vs juče",n:-(diff.removed?.length??0)}].map(({l,v,sub,n})=>(
                <KPI key={l} label={l} value={v} sub={sub} valueColor={pctColor(n)}/>
              ))}
              {histSlice.length>0&&(
                <div style={{background:C.white,borderRadius:12,padding:"18px",boxShadow:C.shadow,gridColumn:"1/-1"}}>
                  <div style={{fontSize:14,fontWeight:600,marginBottom:12}}>Dnevna istorija</div>
                  <div style={{overflowX:"auto"}}>
                    <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
                      <thead><tr style={{borderBottom:`1px solid ${C.border}`}}>{["Datum","Raw","Unique","Dup.","Novi","Skinuti","Avg €/m²"].map(h=><th key={h} style={{textAlign:"left",padding:"8px 10px",fontSize:11,fontWeight:600,color:C.textS,whiteSpace:"nowrap"}}>{h}</th>)}</tr></thead>
                      <tbody>
                        {[...histSlice].reverse().map((h,i)=>(
                          <tr key={i} style={{borderBottom:`1px solid ${C.border}`}} onMouseEnter={e=>e.currentTarget.style.background="#F9FAFB"} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
                            <td style={{padding:"8px 10px",fontWeight:600,whiteSpace:"nowrap"}}>{h.date}</td>
                            <td style={{padding:"8px 10px"}}>{fmt(h.total_raw)}</td>
                            <td style={{padding:"8px 10px",fontWeight:600}}>{fmt(h.total_unique)}</td>
                            <td style={{padding:"8px 10px",color:C.textS}}>{fmt(h.total_dups)}</td>
                            <td style={{padding:"8px 10px",color:C.green}}>{h.diff_new>0?`+${h.diff_new}`:"–"}</td>
                            <td style={{padding:"8px 10px",color:C.red}}>{h.diff_removed>0?`−${h.diff_removed}`:"–"}</td>
                            <td style={{padding:"8px 10px",color:C.textS}}>{h.avg_m2?fmt(h.avg_m2)+" €":"–"}</td>
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
                  style={{flex:1,minWidth:120,fontSize:13,padding:"7px 12px",border:`1px solid ${C.border}`,borderRadius:8,outline:"none"}}/>
                {showNew&&<span style={{padding:"4px 10px",borderRadius:20,background:C.green+"18",color:C.green,fontSize:12,fontWeight:600}}>🟢 Novi ({diffSummary.newCount})</span>}
                <span style={{fontSize:12,color:C.textS}}>{filtered.length} res.</span>
                {(selStr||selBlds.length>0||search||showNew)&&(
                  <button onClick={()=>{setSelStr(null);setSelBlds([]);setSearch("");setShowNew(false);}} style={{fontSize:12,padding:"6px 10px",cursor:"pointer",border:`1px solid ${C.border}`,borderRadius:8,background:C.white,color:C.textS}}>✕ Reset</button>
                )}
              </div>
              <div style={{overflowX:"auto"}}>
                <table style={{width:"100%",borderCollapse:"collapse",fontSize:13,tableLayout:"fixed",minWidth:600}}>
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
                              <span style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{l.zgrada?.replace("BW ","")}</span>
                              {isNew&&showNew&&<span style={{fontSize:10,fontWeight:700,color:C.green,marginLeft:2}}>NEW</span>}
                            </div>
                          </td>
                          <td style={{padding:"10px 16px",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",fontSize:12,color:agNaziv?C.text:C.textXS}}>{agNaziv||"–"}</td>
                          <td style={{padding:"10px 16px"}}><span style={{display:"inline-block",padding:"3px 9px",borderRadius:20,fontSize:11,fontWeight:600,background:col+"18",color:col}}>{lbl}</span></td>
                          <td style={{padding:"10px 16px",color:C.textS,textAlign:"right"}}>{l.m2!=null?fmtDec(l.m2,2):"–"}</td>
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
