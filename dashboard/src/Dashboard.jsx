import { useState, useEffect, useCallback, useMemo } from "react";

// ─── CONFIG ─── zameni sa tvojim repo imenom
const REPO = "https://raw.githubusercontent.com/niknedeljko/bnv-tracker/main/data";

// ─── CONSTANTS ───────────────────────────────────────────────────────────────
const STR_ORDER  = ["0.5","1.0","1.5","2.0","2.5","3.0","3.5","4.0","4.5","5.0"];
const STR_LABEL  = {"0.5":"Garsonjera","1.0":"Jednosoban","1.5":"Jednoiposoban","2.0":"Dvosoban","2.5":"Dvoiposoban","3.0":"Trosoban","3.5":"Troiposoban","4.0":"Četvorosoban","4.5":"Četvoriposoban","5.0":"Petosoban+"};
const STR_SHORT  = {"0.5":"Garsonjera","1.0":"1-soban","1.5":"1.5-soban","2.0":"2-soban","2.5":"2.5-soban","3.0":"3-soban","3.5":"3.5-soban","4.0":"4-soban","4.5":"4.5-soban","5.0":"5-soban+"};
const STR_COLOR  = {"0.5":"#059669","1.0":"#2563eb","1.5":"#db2777","2.0":"#d97706","2.5":"#7c3aed","3.0":"#16a34a","3.5":"#0891b2","4.0":"#ea580c","4.5":"#65a30d","5.0":"#dc2626"};
const PERIODS    = [{k:"7",l:"7d"},{k:"30",l:"30d"},{k:"60",l:"60d"},{k:"90",l:"90d"},{k:"365",l:"1g"}];

// ─── HELPERS ─────────────────────────────────────────────────────────────────
const fmtEur  = (n,compact=false) => {
  if(n==null) return "–";
  if(compact && n>=1000000) return (n/1000000).toFixed(1)+"M €";
  if(compact && n>=1000)    return (n/1000).toFixed(0)+"k €";
  return new Intl.NumberFormat("sr-RS").format(Math.round(n))+" €";
};
const fmtM2   = n => n==null?"–":new Intl.NumberFormat("sr-RS").format(Math.round(n))+" €/m²";
const fmtPct  = n => n==null?"–":(n>=0?"+":"")+n.toFixed(2)+"%";
const pctCls  = n => n>0?"clr-up":n<0?"clr-dn":"clr-neu";
const fmtDate = s => s?.slice(0,10)??"-";

// ─── MINI CHART (SVG, no deps) ────────────────────────────────────────────────
function MiniLine({data, color="#2563eb", h=60}) {
  if(!data||data.length<2) return null;
  const W=300, P=4;
  const vals = data.map(d=>typeof d==="number"?d:d.val);
  const min=Math.min(...vals), max=Math.max(...vals), range=max-min||1;
  const x = i => P + (i/(vals.length-1))*(W-2*P);
  const y = v => P + (h-2*P) - ((v-min)/range)*(h-2*P);
  const pts = vals.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = vals.length-1;
  return (
    <svg viewBox={`0 0 ${W} ${h}`} preserveAspectRatio="none"
      style={{width:"100%",height:h,display:"block"}}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx={x(last)} cy={y(vals[last])} r="3" fill={color}/>
    </svg>
  );
}

// ─── RANGE BAR ────────────────────────────────────────────────────────────────
function RangeBar({min,max,globalMax,color}) {
  const left = Math.round(min/globalMax*100);
  const width= Math.max(Math.round((max-min)/globalMax*100),1);
  return (
    <div style={{height:5,background:"var(--color-border-tertiary)",borderRadius:3,position:"relative",overflow:"hidden"}}>
      <div style={{position:"absolute",left:left+"%",width:width+"%",height:"100%",background:color,borderRadius:3}}/>
    </div>
  );
}

// ─── MAIN DASHBOARD ──────────────────────────────────────────────────────────
export default function Dashboard() {
  const [mode,   setMode]   = useState("prodaja");
  const [latest, setLatest] = useState(null);
  const [hist,   setHist]   = useState([]);
  const [err,    setErr]    = useState(null);
  const [loading,setLoading]= useState(true);
  const [tab,    setTab]    = useState("pregled");
  const [period, setPeriod] = useState("30");
  const [selZ,   setSelZ]   = useState(new Set());  // selected buildings
  const [selS,   setSelS]   = useState(new Set());  // selected structures
  const [sortKey,setSortKey]= useState("zgrada");
  const [sortDir,setSortDir]= useState(1);
  const [search, setSearch] = useState("");

  // ── Fetch data ──
  useEffect(()=>{
    const base = mode==="prodaja" ? `${REPO}/latest.json` : `${REPO}/latest_renta.json`;
    Promise.all([
      fetch(base).then(r=>{ if(!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      fetch(`${REPO}/history.json`).then(r=>r.json()).catch(()=>[]),
    ])
    .then(([l,h])=>{ setLatest(l); setHist(h); setLoading(false); })
    .catch(e=>{ setErr(e.message); setLoading(false); });
  },[mode]);

  // ── Derived ──
  const listings   = useMemo(()=>latest?.listings??[],[latest]);
  const stats      = useMemo(()=>latest?.stats??{},[latest]);
  const diff       = useMemo(()=>latest?.diff??{},[latest]);
  const byStr      = useMemo(()=>stats.po_strukturi??{},[stats]);
  const byZgrada   = useMemo(()=>stats.po_zgradi??{},[stats]);
  const allBuildings= useMemo(()=>Object.keys(byZgrada).sort(),[byZgrada]);
  const histSlice  = useMemo(()=>{
    const n=parseInt(period); return hist.slice(-n);
  },[hist,period]);

  // ── Price index calcs ──
  const priceIdx = useMemo(()=>{
    if(hist.length<2) return {dod:null,ytd:null};
    const last = hist[hist.length-1];
    const prev = hist[hist.length-2];
    const ytdRef= hist.find(h=>h.date?.startsWith(new Date().getFullYear()+"-01"))??hist[0];
    const getAvg= h=>h.avg_m2??(h.by_struktura ? Object.values(h.by_struktura).reduce((s,v)=>s+(v.avg_m2??0),0)/Math.max(Object.keys(h.by_struktura).length,1) : null);
    const lv=getAvg(last), pv=getAvg(prev), yv=getAvg(ytdRef);
    return {
      dod: lv&&pv ? ((lv-pv)/pv*100) : null,
      ytd: lv&&yv ? ((lv-yv)/yv*100) : null,
    };
  },[hist]);

  // ── Filtered listings ──
  const filtered = useMemo(()=>{
    let d = listings;
    if(selZ.size) d = d.filter(l=>selZ.has(l.zgrada));
    if(selS.size) d = d.filter(l=>selS.has(l.struktura));
    if(search)    d = d.filter(l=>(l.zgrada+l.naslov).toLowerCase().includes(search.toLowerCase()));
    return d.slice().sort((a,b)=>{
      const v = x => sortKey==="zgrada"?x.zgrada||"":sortKey==="str"?parseFloat(x.struktura||99):sortKey==="m2"?(x.m2||0):sortKey==="cena"?(x.cena||0):x.cena_m2||0;
      const va=v(a),vb=v(b);
      if(typeof va==="string") return va.localeCompare(vb)*sortDir;
      return (va-vb)*sortDir;
    });
  },[listings,selZ,selS,search,sortKey,sortDir]);

  // ── Toggle helpers ──
  const toggleZ = useCallback(z=>setSelZ(s=>{ const n=new Set(s); n.has(z)?n.delete(z):n.add(z); return n; }),[]);
  const toggleS = useCallback(s=>setSelS(v=>{ const n=new Set(v); n.has(s)?n.delete(s):n.add(s); return n; }),[]);
  const toggleSort = k=>{ if(sortKey===k)setSortDir(d=>-d); else{setSortKey(k);setSortDir(1);} };
  const arr = k => sortKey===k?(sortDir===1?" ↑":" ↓"):"";

  // ── Summaries for filtered set ──
  const summary = useMemo(()=>{
    const prices = filtered.filter(l=>l.cena).map(l=>l.cena);
    const m2s    = filtered.filter(l=>l.cena_m2).map(l=>l.cena_m2);
    return {
      count: filtered.length,
      minC: prices.length?Math.min(...prices):null,
      maxC: prices.length?Math.max(...prices):null,
      avgM2: m2s.length?m2s.reduce((a,b)=>a+b)/m2s.length:null,
      minM2: m2s.length?Math.min(...m2s):null,
      maxM2: m2s.length?Math.max(...m2s):null,
    };
  },[filtered]);

  // ── Renta summary per structure (monthly) ──
  const rentSummary = useMemo(()=>{
    if(mode!=="renta") return {};
    const out={};
    STR_ORDER.forEach(s=>{
      const items = listings.filter(l=>l.struktura===s&&l.cena);
      if(!items.length) return;
      const cene = items.map(l=>l.cena);
      out[s]={ min:Math.min(...cene), max:Math.max(...cene), avg:cene.reduce((a,b)=>a+b)/cene.length, count:items.length };
    });
    return out;
  },[listings,mode]);

  // ─────────────────────────────────────────────────────────────────────────
  if(loading) return <div style={{display:"flex",alignItems:"center",justifyContent:"center",height:200,color:"var(--color-text-secondary)",fontSize:14}}>Učitavanje podataka...</div>;
  if(err)     return <div style={{padding:24,color:"var(--color-text-danger)",fontSize:13}}><b>Greška:</b> {err}<br/><br/>Proveri da si zamenio niknedeljko/REPONAME i da je repo javan.</div>;

  const scraped = latest?.scraped_at?.slice(0,16).replace("T"," ")+" UTC";

  return (
    <div style={{fontFamily:"var(--font-sans)",fontSize:13,color:"var(--color-text-primary)",maxWidth:700,margin:"0 auto",padding:"0 0 3rem"}}>

      {/* ── NAV ── */}
      <div style={{display:"flex",alignItems:"center",gap:8,padding:"14px 0 10px",borderBottom:"0.5px solid var(--color-border-tertiary)",marginBottom:14,flexWrap:"wrap"}}>
        <span style={{fontSize:16,fontWeight:500,marginRight:4}}>BnV Market</span>
        <div style={{display:"flex",border:"0.5px solid var(--color-border-secondary)",borderRadius:"var(--border-radius-md)",overflow:"hidden"}}>
          {[["prodaja","Prodaja"],["renta","Renta"]].map(([k,l])=>(
            <button key={k} onClick={()=>setMode(k)} style={{
              padding:"5px 14px",fontSize:12,background:mode===k?"var(--color-background-secondary)":"transparent",
              border:"none",borderRight:k==="prodaja"?"0.5px solid var(--color-border-secondary)":"none",
              color:mode===k?"var(--color-text-primary)":"var(--color-text-secondary)",
              fontWeight:mode===k?500:400,cursor:"pointer"}}>
              {l}
            </button>
          ))}
        </div>
        <span style={{fontSize:10,color:"var(--color-text-secondary)",marginLeft:"auto"}}>
          Update: <b>{scraped}</b>
        </span>
      </div>

      {/* ── FILTERI ── */}
      <div style={{marginBottom:12}}>
        <div style={{fontSize:10,fontWeight:500,color:"var(--color-text-secondary)",textTransform:"uppercase",letterSpacing:.5,marginBottom:5}}>Zgrada</div>
        <div style={{display:"flex",flexWrap:"wrap",gap:4,marginBottom:10}}>
          <button onClick={()=>setSelZ(new Set())} style={{
            padding:"3px 10px",borderRadius:20,fontSize:11,border:"0.5px solid var(--color-border-secondary)",
            background:selZ.size===0?"var(--color-text-primary)":"transparent",
            color:selZ.size===0?"var(--color-background-primary)":"var(--color-text-secondary)",cursor:"pointer"}}>
            Sve zgrade
          </button>
          {allBuildings.map(z=>{
            const on=selZ.has(z);
            return <button key={z} onClick={()=>toggleZ(z)} style={{
              padding:"3px 10px",borderRadius:20,fontSize:11,border:"0.5px solid var(--color-border-secondary)",
              background:on?"var(--color-text-primary)":"transparent",
              color:on?"var(--color-background-primary)":"var(--color-text-secondary)",cursor:"pointer"}}>
              {z.replace("BW ","")}
            </button>;
          })}
        </div>
        <div style={{fontSize:10,fontWeight:500,color:"var(--color-text-secondary)",textTransform:"uppercase",letterSpacing:.5,marginBottom:5}}>Struktura</div>
        <div style={{display:"flex",flexWrap:"wrap",gap:4}}>
          <button onClick={()=>setSelS(new Set())} style={{
            padding:"3px 10px",borderRadius:20,fontSize:11,border:"0.5px solid var(--color-border-secondary)",
            background:selS.size===0?"var(--color-text-primary)":"transparent",
            color:selS.size===0?"var(--color-background-primary)":"var(--color-text-secondary)",cursor:"pointer"}}>
            Sve strukture
          </button>
          {STR_ORDER.filter(s=>byStr[s]).map(s=>{
            const on=selS.has(s);
            const col=STR_COLOR[s];
            return <button key={s} onClick={()=>toggleS(s)} style={{
              padding:"3px 10px",borderRadius:20,fontSize:11,cursor:"pointer",
              border:`0.5px solid ${on?col:col+"55"}`,
              background:on?col:"transparent",
              color:on?"#fff":col}}>
              {STR_SHORT[s]}
            </button>;
          })}
        </div>
      </div>

      {/* ── METRIC CARDS ── */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(110px,1fr))",gap:8,marginBottom:14}}>
        {[
          ["Oglasa (site)",  latest?.total_raw??0,      null],
          ["Unique nkrt.",   latest?.total_unique??0,    null],
          ["Prikazano",      summary.count,              null],
          ["Cena min",       fmtEur(summary.minC,true),  null],
          ["Cena max",       fmtEur(summary.maxC,true),  null],
          ["Avg €/m²",       fmtM2(summary.avgM2),       null],
          ["DoD indeks",     <span className={pctCls(priceIdx.dod)}>{fmtPct(priceIdx.dod)}</span>, null],
          ["YTD indeks",     <span className={pctCls(priceIdx.ytd)}>{fmtPct(priceIdx.ytd)}</span>, null],
        ].map(([lbl,val])=>(
          <div key={lbl} style={{background:"var(--color-background-secondary)",borderRadius:"var(--border-radius-md)",padding:"9px 11px"}}>
            <div style={{fontSize:10,color:"var(--color-text-secondary)",textTransform:"uppercase",letterSpacing:.4,marginBottom:3}}>{lbl}</div>
            <div style={{fontSize:16,fontWeight:500,lineHeight:1.2}}>{val}</div>
          </div>
        ))}
      </div>

      {/* ── TABS ── */}
      <div style={{display:"flex",gap:2,borderBottom:"0.5px solid var(--color-border-tertiary)",marginBottom:14}}>
        {[["pregled","Pregled"],["zgrade","Zgrade"],["trend","Trend & Indeks"],["listinzi","Listinzi"]].map(([k,l])=>(
          <button key={k} onClick={()=>setTab(k)} style={{
            padding:"7px 13px",fontSize:12,background:"transparent",border:"none",
            borderBottom:tab===k?"2px solid var(--color-text-primary)":"2px solid transparent",
            color:tab===k?"var(--color-text-primary)":"var(--color-text-secondary)",
            fontWeight:tab===k?500:400,cursor:"pointer",marginBottom:-1}}>
            {l}
          </button>
        ))}
      </div>

      {/* ════════════════ PREGLED ════════════════ */}
      {tab==="pregled" && (()=>{
        const relevant = STR_ORDER.filter(s=>byStr[s]&&(selS.size===0||selS.has(s)));
        if(mode==="prodaja") {
          const globalMaxC  = Math.max(...relevant.map(s=>byStr[s]?.cena?.max??0));
          const globalMaxM2 = Math.max(...relevant.map(s=>byStr[s]?.cena_m2?.max??0));
          return (
            <div style={{display:"flex",flexDirection:"column",gap:10}}>
              {relevant.map(s=>{
                const v=byStr[s]; if(!v) return null;
                const c=v.cena??{}, m=v.cena_m2??{}, sz=v.m2??{};
                const col=STR_COLOR[s];
                return (
                  <div key={s} style={{background:"var(--color-background-primary)",border:"0.5px solid var(--color-border-tertiary)",borderRadius:"var(--border-radius-lg)",padding:"11px 14px"}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                      <span style={{display:"inline-block",width:8,height:8,borderRadius:"50%",background:col,flexShrink:0}}/>
                      <span style={{fontWeight:500,fontSize:13,flex:1}}>{STR_LABEL[s]}</span>
                      <span style={{fontSize:11,color:"var(--color-text-secondary)"}}>{v.count} oglas{v.count===1?"":"a"}</span>
                      {sz.min&&<span style={{fontSize:10,color:"var(--color-text-secondary)"}}>{sz.min}–{sz.max} m²</span>}
                    </div>
                    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
                      <div>
                        <div style={{fontSize:10,color:"var(--color-text-secondary)",marginBottom:3}}>Apsolutna cena</div>
                        <RangeBar min={c.min??0} max={c.max??0} globalMax={globalMaxC} color={col}/>
                        <div style={{display:"flex",justifyContent:"space-between",fontSize:10,color:"var(--color-text-secondary)",marginTop:3}}>
                          <span>{fmtEur(c.min,true)}</span><span>{fmtEur(c.max,true)}</span>
                        </div>
                      </div>
                      <div>
                        <div style={{fontSize:10,color:"var(--color-text-secondary)",marginBottom:3}}>Cena po m²</div>
                        <RangeBar min={m.min??0} max={m.max??0} globalMax={globalMaxM2} color={col}/>
                        <div style={{display:"flex",justifyContent:"space-between",fontSize:10,color:"var(--color-text-secondary)",marginTop:3}}>
                          <span>{fmtM2(m.min)}</span><span>{fmtM2(m.max)}</span>
                        </div>
                        {m.avg&&<div style={{fontSize:10,color:"var(--color-text-secondary)",opacity:.7,textAlign:"right"}}>~{fmtM2(m.avg)}</div>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        } else {
          // RENTA MODE — samo mesečni iznosi, bez €/m²
          return (
            <div style={{display:"flex",flexDirection:"column",gap:10}}>
              {relevant.map(s=>{
                const r=rentSummary[s]; if(!r) return null;
                const col=STR_COLOR[s];
                return (
                  <div key={s} style={{background:"var(--color-background-primary)",border:"0.5px solid var(--color-border-tertiary)",borderRadius:"var(--border-radius-lg)",padding:"11px 14px"}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                      <span style={{display:"inline-block",width:8,height:8,borderRadius:"50%",background:col,flexShrink:0}}/>
                      <span style={{fontWeight:500,flex:1}}>{STR_LABEL[s]}</span>
                      <span style={{fontSize:11,color:"var(--color-text-secondary)"}}>{r.count} oglas{r.count===1?"":"a"}</span>
                    </div>
                    <div style={{display:"flex",alignItems:"baseline",gap:12}}>
                      <div>
                        <div style={{fontSize:10,color:"var(--color-text-secondary)"}}>Mesečna zakupnina</div>
                        <div style={{fontWeight:500,fontSize:15,marginTop:2}}>
                          {fmtEur(r.min,true)} – {fmtEur(r.max,true)}<span style={{fontSize:10,color:"var(--color-text-secondary)",fontWeight:400}}>/mj</span>
                        </div>
                        <div style={{fontSize:11,color:"var(--color-text-secondary)",marginTop:2}}>prosek ~{fmtEur(r.avg,true)}/mj</div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        }
      })()}

      {/* ════════════════ ZGRADE ════════════════ */}
      {tab==="zgrade" && (
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(150px,1fr))",gap:8}}>
          {allBuildings
            .filter(z=>selS.size===0||listings.some(l=>l.zgrada===z&&selS.has(l.struktura)))
            .map(z=>{
              const v=byZgrada[z]; if(!v) return null;
              const on=selZ.has(z);
              const structs=(v.strukture||[]).filter(s=>selS.size===0||selS.has(s)).sort((a,b)=>parseFloat(a)-parseFloat(b));
              const c=mode==="renta"?null:v.cena;
              return (
                <div key={z} onClick={()=>toggleZ(z)} style={{
                  background:"var(--color-background-primary)",
                  border:on?"1px solid var(--color-border-info)":"0.5px solid var(--color-border-tertiary)",
                  borderRadius:"var(--border-radius-lg)",padding:"10px 12px",cursor:"pointer",
                  transition:"border-color .12s"}}>
                  <div style={{fontWeight:500,fontSize:12,marginBottom:4,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{z}</div>
                  <div style={{fontSize:10,color:"var(--color-text-secondary)",marginBottom:4}}>{v.count} oglas{v.count===1?"":"a"}</div>
                  <div style={{display:"flex",flexWrap:"wrap",gap:2,marginBottom:4}}>
                    {structs.map(s=>(
                      <span key={s} style={{display:"inline-block",width:7,height:7,borderRadius:"50%",background:STR_COLOR[s]||"#ccc"}}/>
                    ))}
                  </div>
                  {c&&<div style={{fontSize:11,fontWeight:500}}>{fmtEur(c.min,true)}–{fmtEur(c.max,true)}</div>}
                  {c?.avg&&mode==="prodaja"&&v.cena_m2?.avg&&<div style={{fontSize:10,color:"var(--color-text-secondary)"}}>~{fmtM2(v.cena_m2.avg)}</div>}
                </div>
              );
            })}
        </div>
      )}

      {/* ════════════════ TREND ════════════════ */}
      {tab==="trend" && (
        <div style={{display:"flex",flexDirection:"column",gap:12}}>
          {/* Period selector */}
          <div style={{display:"flex",gap:4}}>
            {PERIODS.map(p=>(
              <button key={p.k} onClick={()=>setPeriod(p.k)} style={{
                padding:"4px 10px",fontSize:11,border:"0.5px solid var(--color-border-secondary)",
                borderRadius:"var(--border-radius-md)",background:period===p.k?"var(--color-background-secondary)":"transparent",
                color:period===p.k?"var(--color-text-primary)":"var(--color-text-secondary)",
                fontWeight:period===p.k?500:400,cursor:"pointer"}}>
                {p.l}
              </button>
            ))}
          </div>

          {/* Index cards */}
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr 1fr",gap:8}}>
            {[
              ["Indeks cena DoD", fmtPct(priceIdx.dod), pctCls(priceIdx.dod), "vs juče"],
              ["Indeks cena YTD", fmtPct(priceIdx.ytd), pctCls(priceIdx.ytd), "od 01.01."],
              ["Novi oglasi",     `+${diff.new?.length??0}`,  "clr-up",  "danas"],
              ["Skinuti oglasi",  `-${diff.removed?.length??0}`,"clr-dn","danas"],
            ].map(([l,v,cls,sub])=>(
              <div key={l} style={{background:"var(--color-background-secondary)",borderRadius:"var(--border-radius-md)",padding:"9px 11px"}}>
                <div style={{fontSize:10,color:"var(--color-text-secondary)",marginBottom:3}}>{l}</div>
                <div style={{fontSize:18,fontWeight:500}} className={cls}>{v}</div>
                <div style={{fontSize:10,color:"var(--color-text-secondary)",marginTop:1}}>{sub}</div>
              </div>
            ))}
          </div>

          {/* Chart 1: broj oglasa */}
          <div style={{background:"var(--color-background-primary)",border:"0.5px solid var(--color-border-tertiary)",borderRadius:"var(--border-radius-lg)",padding:"12px 14px"}}>
            <div style={{fontSize:11,fontWeight:500,color:"var(--color-text-secondary)",marginBottom:6}}>Broj oglasa</div>
            {histSlice.length>1
              ? <MiniLine data={histSlice.map(h=>h.total_unique??h.total_raw)} color="#2563eb" h={70}/>
              : <div style={{height:70,display:"flex",alignItems:"center",justifyContent:"center",color:"var(--color-text-secondary)",fontSize:11}}>Nema dovoljno podataka za period</div>
            }
            <div style={{display:"flex",justifyContent:"space-between",fontSize:10,color:"var(--color-text-secondary)",marginTop:4}}>
              <span>{histSlice[0]?.date}</span><span>{histSlice[histSlice.length-1]?.date}</span>
            </div>
          </div>

          {/* Chart 2: avg €/m² */}
          <div style={{background:"var(--color-background-primary)",border:"0.5px solid var(--color-border-tertiary)",borderRadius:"var(--border-radius-lg)",padding:"12px 14px"}}>
            <div style={{fontSize:11,fontWeight:500,color:"var(--color-text-secondary)",marginBottom:6}}>Prosečna cena €/m²</div>
            {histSlice.some(h=>h.avg_m2)
              ? <MiniLine data={histSlice.map(h=>h.avg_m2).filter(Boolean)} color="#059669" h={70}/>
              : <div style={{height:70,display:"flex",alignItems:"center",justifyContent:"center",color:"var(--color-text-secondary)",fontSize:11}}>Podaci o €/m² dostupni od sledećeg scrape-a</div>
            }
            <div style={{display:"flex",justifyContent:"space-between",fontSize:10,color:"var(--color-text-secondary)",marginTop:4}}>
              <span>{histSlice[0]?.date}</span><span>{histSlice[histSlice.length-1]?.date}</span>
            </div>
          </div>

          {/* Tabela po danima */}
          {histSlice.length>0 && (
            <div style={{background:"var(--color-background-primary)",border:"0.5px solid var(--color-border-tertiary)",borderRadius:"var(--border-radius-lg)",padding:"12px 14px"}}>
              <div style={{fontSize:11,fontWeight:500,color:"var(--color-text-secondary)",marginBottom:8}}>Dnevna istorija</div>
              <div style={{overflowX:"auto"}}>
                <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                  <thead>
                    <tr style={{borderBottom:"0.5px solid var(--color-border-tertiary)"}}>
                      {["Datum","Oglasi","Unique","Novi","Skinuti","Neto","€/m² avg"].map(h=>(
                        <th key={h} style={{textAlign:h==="Datum"?"left":"right",padding:"4px 6px",fontWeight:500,color:"var(--color-text-secondary)",fontSize:10}}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...histSlice].reverse().map((h,i)=>(
                      <tr key={i} style={{borderBottom:"0.5px solid var(--color-border-tertiary)"}}>
                        <td style={{padding:"5px 6px",fontWeight:500}}>{h.date}</td>
                        <td style={{padding:"5px 6px",textAlign:"right"}}>{h.total_raw??"-"}</td>
                        <td style={{padding:"5px 6px",textAlign:"right",fontWeight:500}}>{h.total_unique??"-"}</td>
                        <td style={{padding:"5px 6px",textAlign:"right",color:"var(--color-text-success)"}}>{h.diff_new>0?`+${h.diff_new}`:"-"}</td>
                        <td style={{padding:"5px 6px",textAlign:"right",color:"var(--color-text-danger)"}}>{h.diff_removed>0?`-${h.diff_removed}`:"-"}</td>
                        <td style={{padding:"5px 6px",textAlign:"right"}}>
                          {h.diff_new!=null?<span className={pctCls((h.diff_new-h.diff_removed))}>{h.diff_new-h.diff_removed>0?"+":""}{h.diff_new-h.diff_removed}</span>:"-"}
                        </td>
                        <td style={{padding:"5px 6px",textAlign:"right",color:"var(--color-text-secondary)"}}>{h.avg_m2?fmtM2(h.avg_m2):"-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ════════════════ LISTINZI ════════════════ */}
      {tab==="listinzi" && (
        <div>
          <div style={{display:"flex",gap:8,marginBottom:10,alignItems:"center",flexWrap:"wrap"}}>
            <input value={search} onChange={e=>setSearch(e.target.value)}
              placeholder="Pretraži..." style={{flex:1,minWidth:140,fontSize:12,padding:"5px 10px"}}/>
            <span style={{fontSize:11,color:"var(--color-text-secondary)",whiteSpace:"nowrap"}}>{filtered.length} rezultata</span>
            {(selZ.size||selS.size||search) && (
              <button onClick={()=>{setSelZ(new Set());setSelS(new Set());setSearch("");}} style={{fontSize:11,padding:"4px 10px",cursor:"pointer"}}>
                ✕ Reset
              </button>
            )}
          </div>
          <div style={{overflowX:"auto"}}>
            <table style={{width:"100%",borderCollapse:"collapse",fontSize:12,tableLayout:"fixed"}}>
              <thead>
                <tr style={{borderBottom:"0.5px solid var(--color-border-tertiary)"}}>
                  {[["zgrada","Zgrada",38],["str","Tip",15],["m2","m²",9],["cena",mode==="prodaja"?"Cena":"Mj. renta",16],mode==="prodaja"&&["m2p","€/m²",12],["sp","Sprat",10]].filter(Boolean).map(([k,l,w])=>(
                    <th key={k} onClick={()=>toggleSort(k)} style={{width:w+"%",textAlign:"left",padding:"6px 6px",fontSize:10,color:"var(--color-text-secondary)",fontWeight:500,cursor:"pointer",userSelect:"none"}}>
                      {l}{arr(k)}
                    </th>
                  ))}
                  <th style={{width:"6%"}}></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(l=>{
                  const col=STR_COLOR[l.struktura]||"#888";
                  return (
                    <tr key={l.id} style={{borderBottom:"0.5px solid var(--color-border-tertiary)"}}
                      onMouseEnter={e=>e.currentTarget.style.background="var(--color-background-secondary)"}
                      onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
                      <td style={{padding:"7px 6px",fontWeight:500,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                        <span style={{display:"inline-block",width:7,height:7,borderRadius:"50%",background:col,marginRight:5,flexShrink:0}}/>
                        {l.zgrada}
                      </td>
                      <td style={{padding:"7px 6px",fontSize:11,color:col,fontWeight:500,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{STR_SHORT[l.struktura]||l.str_label||l.struktura||"?"}</td>
                      <td style={{padding:"7px 6px"}}>{l.m2?`${l.m2}`:"-"}</td>
                      <td style={{padding:"7px 6px",fontWeight:500}}>{l.cena?fmtEur(l.cena,true):"na upit"}{mode==="renta"&&l.cena?<span style={{fontSize:10,fontWeight:400,color:"var(--color-text-secondary)"}}>/mj</span>:null}</td>
                      {mode==="prodaja"&&<td style={{padding:"7px 6px",color:"var(--color-text-secondary)"}}>{l.cena_m2?fmtM2(l.cena_m2):"-"}</td>}
                      <td style={{padding:"7px 6px",color:"var(--color-text-secondary)",fontSize:11}}>{l.sprat||"-"}</td>
                      <td style={{padding:"7px 6px",textAlign:"right"}}>
                        <a href={l.url} target="_blank" rel="noreferrer" style={{color:"#2563eb",textDecoration:"none"}}>↗</a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <style>{`
        .clr-up { color: var(--color-text-success); }
        .clr-dn { color: var(--color-text-danger); }
        .clr-neu { color: var(--color-text-secondary); }
      `}</style>
    </div>
  );
}
