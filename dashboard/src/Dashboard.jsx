import { useState, useEffect, useCallback, useMemo, useRef } from "react";

const REPO = "https://raw.githubusercontent.com/niknedeljko/bnv-tracker/main/data";

const STR_ORDER  = ["0.5","1.0","1.5","2.0","2.5","3.0","3.5","4.0","5.0"];
const STR_LABELS = {"0.5":"Garsonjera","1.0":"Jednosoban","1.5":"Jednoiposoban","2.0":"Dvosoban","2.5":"Dvoiposoban","3.0":"Trosoban","3.5":"Troiposoban","4.0":"Četvorosoban","5.0":"Petosoban+"};
const STR_SHORT  = {"0.5":"Garsonjera","1.0":"Jednosoban","1.5":"1.5-soban","2.0":"Dvosoban","2.5":"2.5-soban","3.0":"Trosoban","3.5":"3.5-soban","4.0":"Četvorosoban","5.0":"Petosoban+"};
const STR_COLORS = {"0.5":"#1D9E75","1.0":"#378ADD","1.5":"#D4537E","2.0":"#BA7517","2.5":"#534AB7","3.0":"#639922","3.5":"#0891b2","4.0":"#D85A30","5.0":"#E24B4A"};
const PERIODS    = [{k:7,l:"7d"},{k:30,l:"30d"},{k:90,l:"90d"},{k:365,l:"1g"}];

const fmt    = n => n == null ? "–" : new Intl.NumberFormat("sr-RS").format(Math.round(n));
const fmtK   = n => n == null ? "–" : n >= 1e6 ? (n/1e6).toFixed(1)+"M" : n >= 1e3 ? (n/1e3).toFixed(0)+"k" : String(Math.round(n));
const fmtPct = n => n == null ? "–" : (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
const pctCls = n => n > 0 ? "up" : n < 0 ? "dn" : "neu";

function Dot({ color, size = 7 }) {
  return <span style={{ display:"inline-block", width:size, height:size, borderRadius:"50%", background:color, flexShrink:0 }} />;
}

function RangeBar({ min, max, globalMax, color }) {
  const left  = Math.round((min || 0) / globalMax * 100);
  const width = Math.max(Math.round(((max || 0) - (min || 0)) / globalMax * 100), 1);
  return (
    <div style={{ height:3, background:"var(--color-border-tertiary)", borderRadius:2, position:"relative", overflow:"hidden" }}>
      <div style={{ position:"absolute", left:left+"%", width:width+"%", height:"100%", background:color, borderRadius:2 }} />
    </div>
  );
}

function SparkLine({ data, color = "#378ADD", height = 90 }) {
  const canvasRef = useRef(null);
  useEffect(() => {
    if (!data || data.length < 2 || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx    = canvas.getContext("2d");
    const W = canvas.offsetWidth * window.devicePixelRatio;
    const H = height * window.devicePixelRatio;
    canvas.width  = W;
    canvas.height = H;
    const P = 8 * window.devicePixelRatio;
    const vals  = data.map(d => d.count);
    const minV  = Math.min(...vals) * 0.98;
    const maxV  = Math.max(...vals) * 1.02;
    const range = maxV - minV || 1;
    const x = i => P + (i / (vals.length - 1)) * (W - 2 * P);
    const y = v => P + (H - 2 * P) - ((v - minV) / range) * (H - 2 * P);

    const isDark = window.matchMedia("(prefers-color-scheme:dark)").matches;
    const gridColor = isDark ? "rgba(255,255,255,.06)" : "rgba(0,0,0,.05)";

    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = gridColor;
    ctx.lineWidth   = 0.5 * window.devicePixelRatio;
    [0.25, 0.5, 0.75].forEach(f => {
      const yy = P + (H - 2 * P) * f;
      ctx.beginPath(); ctx.moveTo(P, yy); ctx.lineTo(W - P, yy); ctx.stroke();
    });

    // Line
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1.5 * window.devicePixelRatio;
    ctx.lineJoin    = "round";
    ctx.lineCap     = "round";
    vals.forEach((v, i) => i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)));
    ctx.stroke();

    // End dot
    const lx = x(vals.length - 1), ly = y(vals[vals.length - 1]);
    ctx.beginPath();
    ctx.arc(lx, ly, 3 * window.devicePixelRatio, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }, [data, color, height]);

  return <canvas ref={canvasRef} style={{ width:"100%", height, display:"block" }} />;
}

export default function Dashboard() {
  const [mode,     setModeState] = useState("prodaja");
  const [latest,   setLatest]    = useState(null);
  const [hist,     setHist]      = useState([]);
  const [loading,  setLoading]   = useState(true);
  const [err,      setErr]       = useState(null);
  const [period,   setPeriod]    = useState(30);
  const [selStr,   setSelStr]    = useState(null);
  const [selBld,   setSelBld]    = useState(null);
  const [search,   setSearch]    = useState("");
  const [sortKey,  setSortKey]   = useState("zgrada");
  const [sortDir,  setSortDir]   = useState(1);

  useEffect(() => {
    const base = mode === "prodaja" ? `${REPO}/latest.json` : `${REPO}/latest_renta.json`;
    setLoading(true);
    Promise.all([
      fetch(base).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      fetch(`${REPO}/history.json`).then(r => r.json()).catch(() => []),
    ])
    .then(([l, h]) => { setLatest(l); setHist(h); setLoading(false); })
    .catch(e => { setErr(e.message); setLoading(false); });
  }, [mode]);

  const listings     = useMemo(() => latest?.listings ?? [], [latest]);
  const diff         = useMemo(() => latest?.diff ?? {}, [latest]);
  const byStr        = useMemo(() => latest?.stats?.po_strukturi ?? {}, [latest]);
  const byZgrada     = useMemo(() => latest?.stats?.po_zgradi ?? {}, [latest]);
  const allBuildings = useMemo(() => Object.keys(byZgrada).sort(), [byZgrada]);
  const histSlice    = useMemo(() => hist.slice(-period), [hist, period]);

  const priceIdx = useMemo(() => {
    if (hist.length < 2) return { dod: null, ytd: null };
    const last   = hist[hist.length - 1];
    const prev   = hist[hist.length - 2];
    const ytdRef = hist.find(h => h.date?.startsWith(new Date().getFullYear() + "-01")) ?? hist[0];
    const g = h => h.avg_m2 ?? null;
    const lv = g(last), pv = g(prev), yv = g(ytdRef);
    return {
      dod: lv && pv ? ((lv - pv) / pv * 100) : null,
      ytd: lv && yv ? ((lv - yv) / yv * 100) : null,
    };
  }, [hist]);

  const summary = useMemo(() => {
    const prices = listings.filter(l => l.cena).map(l => l.cena);
    const m2s    = listings.filter(l => l.cena_m2).map(l => l.cena_m2);
    return {
      minC:  prices.length ? Math.min(...prices) : null,
      maxC:  prices.length ? Math.max(...prices) : null,
      avgM2: m2s.length ? Math.round(m2s.reduce((a, b) => a + b) / m2s.length) : null,
    };
  }, [listings]);

  const filtered = useMemo(() => {
    let d = listings;
    if (selStr) d = d.filter(l => l.struktura === selStr);
    if (selBld) d = d.filter(l => l.zgrada === selBld);
    if (search) d = d.filter(l => (l.zgrada + (l.naslov || "")).toLowerCase().includes(search.toLowerCase()));
    return d.slice().sort((a, b) => {
      const v = x => sortKey === "zgrada" ? (x.zgrada || "") : sortKey === "str" ? parseFloat(x.struktura || 99) : sortKey === "m2" ? (x.m2 || 0) : sortKey === "cena" ? (x.cena || 0) : (x.cena_m2 || 0);
      const va = v(a), vb = v(b);
      if (typeof va === "string") return va.localeCompare(vb) * sortDir;
      return (va - vb) * sortDir;
    });
  }, [listings, selStr, selBld, search, sortKey, sortDir]);

  const toggleSort = k => { if (sortKey === k) setSortDir(d => -d); else { setSortKey(k); setSortDir(1); } };
  const arr = k => sortKey === k ? (sortDir === 1 ? " ↑" : " ↓") : "";

  const trendLast = histSlice[histSlice.length - 1];
  const trendPrev = histSlice[Math.max(0, histSlice.length - 2)];
  const cntDelta  = trendLast && trendPrev ? trendLast.count - trendPrev.count : null;
  const m2TrendPct = histSlice.length >= 2 && histSlice[0].avg_m2 && trendLast?.avg_m2
    ? ((trendLast.avg_m2 - histSlice[0].avg_m2) / histSlice[0].avg_m2 * 100) : null;

  const maxC  = Math.max(...STR_ORDER.map(s => byStr[s]?.cena?.max || 0));
  const maxM2 = Math.max(...STR_ORDER.map(s => byStr[s]?.cena_m2?.max || 0));

  const ss = {
    page:    { fontFamily:"var(--font-sans)", fontSize:13, color:"var(--color-text-primary)", maxWidth:900, margin:"0 auto", padding:"0 0 3rem" },
    topBar:  { display:"flex", alignItems:"center", justifyContent:"space-between", padding:"16px 0 14px", borderBottom:"0.5px solid var(--color-border-tertiary)", marginBottom:20, gap:12, flexWrap:"wrap" },
    logoMark:{ width:28, height:28, borderRadius:6, background:"var(--color-text-primary)", display:"flex", alignItems:"center", justifyContent:"center" },
    kpiGrid: { display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(120px,1fr))", gap:8, marginBottom:20 },
    kpiCard: { background:"var(--color-background-secondary)", borderRadius:"var(--border-radius-md)", padding:"12px 14px" },
    kpiLbl:  { fontSize:10, color:"var(--color-text-secondary)", textTransform:"uppercase", letterSpacing:.5, marginBottom:6 },
    kpiVal:  { fontSize:22, fontWeight:500, lineHeight:1, marginBottom:4 },
    kpiSub:  { fontSize:11 },
    divider: { height:"0.5px", background:"var(--color-border-tertiary)", margin:"0 0 20px" },
    secLbl:  { fontSize:10, fontWeight:500, color:"var(--color-text-secondary)", textTransform:"uppercase", letterSpacing:.6, marginBottom:10 },
    mktGrid: { display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(200px,1fr))", gap:8, marginBottom:20 },
    mktCard: { background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:"var(--border-radius-lg)", padding:"12px 14px" },
    trendBox:{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:"var(--border-radius-lg)", padding:"14px 16px", marginBottom:20 },
    bldGrid: { display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(110px,1fr))", gap:6, marginBottom:20 },
    tblWrap: { background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:"var(--border-radius-lg)", overflow:"hidden", marginBottom:20 },
  };

  if (loading) return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:200, color:"var(--color-text-secondary)", fontSize:13 }}>
      Učitavanje podataka...
    </div>
  );
  if (err) return (
    <div style={{ padding:24, color:"var(--color-text-danger)", fontSize:13 }}>
      <strong>Greška:</strong> {err}<br /><br />
      Proveri da je scraper uspešno pokrenuo i da postoji <code>data/latest.json</code> u repou.
    </div>
  );

  const scraped = latest?.scraped_at?.slice(0, 10) + " · " + latest?.scraped_at?.slice(11, 16) + " UTC";

  return (
    <div style={ss.page}>

      {/* ── Top bar ── */}
      <div style={ss.topBar}>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          <div style={ss.logoMark}>
            <span style={{ color:"var(--color-background-primary)", fontSize:11, fontWeight:500, letterSpacing:"-.3px" }}>BnV</span>
          </div>
          <div>
            <div style={{ fontSize:14, fontWeight:500 }}>Market Intelligence</div>
            <div style={{ fontSize:11, color:"var(--color-text-secondary)", marginTop:1 }}>Beograd na vodi · Savski venac</div>
          </div>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:10, flexShrink:0 }}>
          <div style={{ display:"flex", border:"0.5px solid var(--color-border-secondary)", borderRadius:"var(--border-radius-md)", overflow:"hidden" }}>
            {[["prodaja","Prodaja"],["renta","Renta"]].map(([k, l]) => (
              <button key={k} onClick={() => setModeState(k)} style={{
                padding:"5px 12px", fontSize:12, background: mode === k ? "var(--color-background-secondary)" : "transparent",
                border:"none", borderRight: k === "prodaja" ? "0.5px solid var(--color-border-secondary)" : "none",
                color: mode === k ? "var(--color-text-primary)" : "var(--color-text-secondary)",
                fontWeight: mode === k ? 500 : 400, cursor:"pointer"
              }}>{l}</button>
            ))}
          </div>
          <span style={{ fontSize:11, color:"var(--color-text-secondary)" }}>Update {scraped}</span>
        </div>
      </div>

      {/* ── KPI row ── */}
      <div style={ss.kpiGrid}>
        {[
          { lbl:"Oglasa na tržištu",   val:fmt(latest?.total_raw),   sub:null },
          { lbl:"Unique nekretnine",   val:fmt(latest?.total_unique), sub:`${latest?.total_dups ?? 0} duplikata`, subCls:"neu" },
          { lbl:"Novi danas",          val:`+${diff.new?.length ?? 0}`, subVal: diff.removed?.length, sub:`−${diff.removed?.length ?? 0} skinuto`, subCls:"neu" },
          { lbl:"Cena raspon",         val: summary.minC ? `${fmtK(summary.minC)}–${fmtK(summary.maxC)} €` : "–", sub:null },
          { lbl:"Prosek €/m²",         val: fmt(summary.avgM2) + (summary.avgM2 ? " €" : ""), sub:mode==="prodaja"?"sve strukture":null, subCls:"neu" },
          { lbl:"Indeks cena DoD",     val: fmtPct(priceIdx.dod),  sub:"vs juče",     subCls:pctCls(priceIdx.dod), valCls:pctCls(priceIdx.dod) },
          { lbl:"Indeks cena YTD",     val: fmtPct(priceIdx.ytd),  sub:"od 01.01.",   subCls:pctCls(priceIdx.ytd), valCls:pctCls(priceIdx.ytd) },
        ].map(({ lbl, val, sub, subCls, valCls }) => (
          <div key={lbl} style={ss.kpiCard}>
            <div style={ss.kpiLbl}>{lbl}</div>
            <div style={{ ...ss.kpiVal, color: valCls === "up" ? "#1D9E75" : valCls === "dn" ? "#E24B4A" : "var(--color-text-primary)" }}>{val}</div>
            {sub && <div style={{ ...ss.kpiSub, color: subCls === "up" ? "#1D9E75" : subCls === "dn" ? "#E24B4A" : "var(--color-text-secondary)" }}>{sub}</div>}
          </div>
        ))}
      </div>

      <div style={ss.divider} />

      {/* ── Market segmentation ── */}
      <div style={ss.secLbl}>Tržišna segmentacija</div>
      <div style={ss.mktGrid}>
        {STR_ORDER.filter(s => byStr[s]).map(s => {
          const v   = byStr[s];
          const col = STR_COLORS[s];
          const c   = v.cena    ?? {};
          const m   = v.cena_m2 ?? {};
          const sz  = v.m2      ?? {};
          return (
            <div key={s} style={ss.mktCard} onClick={() => setSelStr(selStr === s ? null : s)}
              onMouseEnter={e => e.currentTarget.style.borderColor = "var(--color-border-primary)"}
              onMouseLeave={e => e.currentTarget.style.borderColor = selStr === s ? "var(--color-border-primary)" : "var(--color-border-tertiary)"}
            >
              <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:10 }}>
                <div style={{ display:"flex", alignItems:"center", gap:6, fontSize:12, fontWeight:500 }}>
                  <Dot color={col} />
                  {v.label}
                </div>
                <span style={{ fontSize:11, color:"var(--color-text-secondary)" }}>{v.count}</span>
              </div>
              <div style={{ marginBottom:6 }}>
                <div style={{ fontSize:10, color:"var(--color-text-secondary)", marginBottom:3 }}>Cena apsolutna</div>
                <RangeBar min={c.min} max={c.max} globalMax={maxC} color={col} />
                <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:"var(--color-text-secondary)", marginTop:3 }}>
                  <span>{fmtK(c.min)} €</span><span>{fmtK(c.max)} €</span>
                </div>
              </div>
              {mode === "prodaja" ? (
                <div>
                  <div style={{ fontSize:10, color:"var(--color-text-secondary)", marginBottom:3 }}>Cena po m²</div>
                  <RangeBar min={m.min} max={m.max} globalMax={maxM2} color={col} />
                  <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:"var(--color-text-secondary)", marginTop:3 }}>
                    <span>{fmt(m.min)} €/m²</span><span>{fmt(m.max)} €/m²</span>
                  </div>
                  {m.avg && <div style={{ fontSize:10, color:"var(--color-text-secondary)", textAlign:"right", marginTop:2, opacity:.7 }}>~{fmt(m.avg)} €/m²</div>}
                </div>
              ) : (
                <div style={{ fontSize:10, color:"var(--color-text-secondary)", marginTop:4 }}>
                  {sz.min && `${sz.min}–${sz.max} m²`}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Trend chart ── */}
      <div style={ss.trendBox}>
        <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", marginBottom:14, flexWrap:"wrap", gap:8 }}>
          <div style={{ display:"flex", gap:20, flexWrap:"wrap" }}>
            {[
              { lbl:"Oglasa danas",      val: trendLast ? fmt(trendLast.count) : "–",        cls:null },
              { lbl:"Promena 24h",       val: cntDelta != null ? (cntDelta >= 0 ? "+" : "") + cntDelta : "–", cls: pctCls(cntDelta) },
              { lbl:`Prosek €/m²`,       val: trendLast?.avg_m2 ? fmt(trendLast.avg_m2)+" €" : "–", cls:null },
              { lbl:`Promena ${period}d`,val: fmtPct(m2TrendPct),  cls: pctCls(m2TrendPct) },
            ].map(({ lbl, val, cls }) => (
              <div key={lbl} style={{ fontSize:11, color:"var(--color-text-secondary)" }}>
                <div style={{ fontSize:13, fontWeight:500, color: cls === "up" ? "#1D9E75" : cls === "dn" ? "#E24B4A" : "var(--color-text-primary)", marginBottom:1 }}>{val}</div>
                {lbl}
              </div>
            ))}
          </div>
          <div style={{ display:"flex", gap:4 }}>
            {PERIODS.map(p => (
              <button key={p.k} onClick={() => setPeriod(p.k)} style={{
                padding:"3px 8px", fontSize:10, cursor:"pointer",
                border:"0.5px solid var(--color-border-secondary)", borderRadius:4,
                background: period === p.k ? "var(--color-background-secondary)" : "transparent",
                color: period === p.k ? "var(--color-text-primary)" : "var(--color-text-secondary)",
                fontWeight: period === p.k ? 500 : 400,
              }}>{p.l}</button>
            ))}
          </div>
        </div>
        {histSlice.length >= 2
          ? <SparkLine data={histSlice} height={90} />
          : <div style={{ height:90, display:"flex", alignItems:"center", justifyContent:"center", fontSize:12, color:"var(--color-text-secondary)" }}>
              Nema dovoljno podataka — grafikon se puni od sutra.
            </div>
        }
        {histSlice.length >= 2 && (
          <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:"var(--color-text-secondary)", marginTop:6 }}>
            <span>{histSlice[0]?.date}</span>
            <span>{histSlice[histSlice.length - 1]?.date}</span>
          </div>
        )}
      </div>

      {/* ── Buildings ── */}
      <div style={ss.secLbl}>Zgrade</div>
      <div style={ss.bldGrid}>
        {allBuildings.map(z => {
          const v   = byZgrada[z];
          const on  = selBld === z;
          const c   = v.cena ?? {};
          const strs= (v.strukture ?? []).sort((a, b) => parseFloat(a) - parseFloat(b));
          return (
            <div key={z} onClick={() => setSelBld(selBld === z ? null : z)}
              style={{
                border: on ? "1px solid var(--color-border-primary)" : "0.5px solid var(--color-border-tertiary)",
                borderRadius:"var(--border-radius-md)", padding:"8px 10px", cursor:"pointer",
                background: on ? "var(--color-background-secondary)" : "var(--color-background-primary)",
                transition:"border-color .12s",
              }}
              onMouseEnter={e => !on && (e.currentTarget.style.borderColor = "var(--color-border-secondary)")}
              onMouseLeave={e => !on && (e.currentTarget.style.borderColor = "var(--color-border-tertiary)")}
            >
              <div style={{ fontSize:11, fontWeight:500, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", marginBottom:3 }}>{z}</div>
              <div style={{ fontSize:10, color:"var(--color-text-secondary)", lineHeight:1.5 }}>
                {v.count} oglas{v.count === 1 ? "" : "a"}
              </div>
              {c.min && <div style={{ fontSize:10, color:"var(--color-text-secondary)", marginTop:2 }}>{fmtK(c.min)}–{fmtK(c.max)} €</div>}
              <div style={{ display:"flex", gap:2, marginTop:4 }}>
                {strs.map(s => <Dot key={s} color={STR_COLORS[s] ?? "#ccc"} size={5} />)}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Table ── */}
      <div style={ss.tblWrap}>
        <div style={{ display:"flex", alignItems:"center", gap:8, padding:"10px 14px", borderBottom:"0.5px solid var(--color-border-tertiary)", flexWrap:"wrap" }}>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Pretraži oglase..."
            style={{ flex:1, minWidth:130, fontSize:12, padding:"5px 9px", border:"0.5px solid var(--color-border-secondary)", borderRadius:"var(--border-radius-md)", background:"transparent", color:"var(--color-text-primary)" }} />
          <div style={{ display:"flex", gap:3, flexWrap:"wrap" }}>
            {STR_ORDER.filter(s => byStr[s]).map(s => {
              const col = STR_COLORS[s];
              const on  = selStr === s;
              return (
                <button key={s} onClick={() => setSelStr(selStr === s ? null : s)} style={{
                  padding:"3px 8px", borderRadius:20, fontSize:10, fontWeight:500, cursor:"pointer", border:"none",
                  background: on ? col : col + "18", color: on ? "#fff" : col, transition:"opacity .12s",
                }}>{STR_SHORT[s]}</button>
              );
            })}
          </div>
          <span style={{ fontSize:11, color:"var(--color-text-secondary)", marginLeft:"auto", whiteSpace:"nowrap" }}>{filtered.length} rezultata</span>
          {(selStr || selBld || search) && (
            <button onClick={() => { setSelStr(null); setSelBld(null); setSearch(""); }} style={{
              fontSize:11, padding:"4px 8px", cursor:"pointer", border:"0.5px solid var(--color-border-secondary)",
              borderRadius:"var(--border-radius-md)", background:"transparent", color:"var(--color-text-secondary)",
            }}>✕ Reset</button>
          )}
        </div>
        <div style={{ overflowX:"auto" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12, tableLayout:"fixed" }}>
            <thead>
              <tr style={{ borderBottom:"0.5px solid var(--color-border-tertiary)" }}>
                {[
                  ["zgrada","Zgrada","30%"],["str","Tip","15%"],["m2","m²","9%"],
                  ["cena", mode === "prodaja" ? "Cena" : "Renta","17%"],
                  ...(mode === "prodaja" ? [["m2p","€/m²","12%"]] : []),
                  [null,"Sprat","10%"],[null,"","7%"]
                ].map(([k, l, w], i) => (
                  <th key={i} onClick={k ? () => toggleSort(k) : undefined}
                    style={{ width:w, textAlign:"left", padding:"8px 12px", fontSize:10, fontWeight:500,
                      color:"var(--color-text-secondary)", cursor: k ? "pointer" : "default", userSelect:"none", whiteSpace:"nowrap" }}>
                    {l}{k ? arr(k) : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(l => {
                const col  = STR_COLORS[l.struktura] ?? "#888";
                const lbl  = STR_SHORT[l.struktura]  ?? l.str_label ?? "–";
                return (
                  <tr key={l.id}
                    onMouseEnter={e => e.currentTarget.style.background = "var(--color-background-secondary)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                    style={{ borderBottom:"0.5px solid var(--color-border-tertiary)" }}>
                    <td style={{ padding:"9px 12px", fontWeight:500, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                      <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                        <Dot color={col} />
                        <span style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{l.zgrada}</span>
                      </div>
                    </td>
                    <td style={{ padding:"9px 12px" }}>
                      <span style={{ display:"inline-block", padding:"2px 7px", borderRadius:10, fontSize:10, fontWeight:500, background: col+"18", color: col }}>{lbl}</span>
                    </td>
                    <td style={{ padding:"9px 12px", color:"var(--color-text-secondary)" }}>{l.m2 ? `${l.m2}` : "–"}</td>
                    <td style={{ padding:"9px 12px", fontWeight:500 }}>
                      {l.cena ? `${fmt(l.cena)} €` : "na upit"}
                      {mode === "renta" && l.cena ? <span style={{ fontSize:10, fontWeight:400, color:"var(--color-text-secondary)" }}>/mj</span> : null}
                    </td>
                    {mode === "prodaja" && <td style={{ padding:"9px 12px", color:"var(--color-text-secondary)" }}>{l.cena_m2 ? fmt(l.cena_m2) : "–"}</td>}
                    <td style={{ padding:"9px 12px", color:"var(--color-text-secondary)", fontSize:11 }}>{l.sprat || "–"}</td>
                    <td style={{ padding:"9px 12px", textAlign:"right" }}>
                      <a href={l.url} target="_blank" rel="noreferrer" style={{ color:"var(--color-text-secondary)", textDecoration:"none", fontSize:14 }}>↗</a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
