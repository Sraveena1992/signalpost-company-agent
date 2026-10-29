/* Signalpost company evidence dashboard: progressive enhancement, no backend changes. */
(() => {
  'use strict';
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = x => x === null || x === undefined || x === '' ? 'Not reported' : esc(typeof x === 'object' ? JSON.stringify(x) : x);
  const safeUrl = x => { try { const u = new URL(String(x)); return ['https:','http:'].includes(u.protocol) ? u.href : ''; } catch { return ''; } };
  const link = (url, text='View source ↗') => safeUrl(url) ? `<a href="${esc(safeUrl(url))}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>` : '<span>Source URL unavailable</span>';
  const list = x => Array.isArray(x) ? x : [];
  const status = x => String(x || 'unknown').replaceAll('_',' ');
  const evidenceCard = (label, e, content) => `<section class="sp-card"><div class="sp-card-head"><h3>${esc(label)}</h3><span class="sp-pill">${esc(status(e?.status))}</span></div>${content}<div class="sp-provenance">${link(e?.source_url)}<span>Retrieved: ${fmt(e?.retrieved_at)}</span>${e?.note ? `<span>${esc(e.note)}</span>` : ''}</div></section>`;
  // Use responsive definition-list cards instead of HTML tables: the host page has
  // legacy `.result table` CSS that collapses columns into vertical characters.
  const table = (heads, rows) => rows.length ? `<div class="sp-records">${rows.map(row => {
    const cells = Array.isArray(row) ? row : [];
    return `<div class="sp-record">${heads.map((h,i)=>`<div class="sp-field"><span class="sp-field-label">${esc(h)}</span><span class="sp-field-value">${cells[i] ?? 'Not reported'}</span></div>`).join('')}</div>`;
  }).join('')}</div>` : '<p class="sp-empty">No records returned for this company.</p>';
  const cell = x => fmt(x);
  const period = x => { if (x == null || x === '') return 'Not reported'; if (typeof x !== 'object') return String(x); const start=x.from||x.start||x.start_date||x.fra||x.fom; const end=x.to||x.end||x.end_date||x.til||x.tom; if(start || end) return [start,end].filter(Boolean).join(' – '); if(x.year||x.aar) return String(x.year||x.aar); return Object.entries(x).filter(([,v])=>v!=null&&typeof v!=='object').map(([k,v])=>`${k}: ${v}`).join(' · ') || 'Period not specified'; };
  const money = (x,c) => x === null || x === undefined || x === '' ? 'Not reported' : `${x} ${c || ''}`.trim();
  function render(data) {
    const p=data.profile||{}, e=p.evidence||{}, reg=e.registry?.value||{};
    const fin=list(e.financials?.value?.records), roles=list(e.roles?.value?.roles), loc=list(e.locations?.value?.locations);
    const name=p.name||data.company?.name||'Company';
    const org=p.organisation_number||data.company?.organisation_number||'';
    const overview = table(['Field','Value'], [
      ['Organisation number',org],['Legal form',p.legal_form],['Municipality',p.municipality],['Industry',p.industry_label],['Industry code',p.industry_code],['Employees',p.employees],['Latest submitted accounts',p.latest_submitted_accounts],['Bankrupt',p.bankrupt === true ? 'Yes' : p.bankrupt === false ? 'No' : null],['Liquidating',p.liquidating === true ? 'Yes' : p.liquidating === false ? 'No' : null]
    ].map(([k,v])=>[esc(k),cell(v)]));
    const financials = table(['Period','Revenue','Operating result','Annual result','Assets','Equity','Debt'],fin.map(r=>[period(r.period),money(r.revenue,r.currency),money(r.operating_result,r.currency),money(r.annual_result,r.currency),money(r.assets,r.currency),money(r.equity,r.currency),money(r.debt,r.currency)].map(cell)));
    const leadership = table(['Name','Role','Group','Last changed','Inactive'],roles.map(r=>[r.name,r.role||r.role_code,r.group||r.group_code,r.last_changed,r.inactive === true?'Yes':r.inactive === false?'No':null].map(cell)));
    const pretty = x => { if(x == null) return null; if(typeof x !== 'object') return String(x); if(Array.isArray(x)) return x.map(pretty).filter(Boolean).join(', '); const keys=['adresse','address','postnummer','poststed','kommune','land','beskrivelse','kode']; const vals=keys.map(k=>x[k]).filter(v=>v!=null&&v!=='').map(pretty); return vals.join(', ') || Object.values(x).filter(v=>v!=null&&typeof v!=='object').join(', ') || 'Not reported'; };
    const locations = table(['Name','Organisation','Address','Industry','Employees'],loc.map(r=>[r.name,r.organisation_number,pretty(r.address),pretty(r.industry),r.employees].map(cell)));
    const website = e.website?.value ? `<pre class="sp-json">${esc(JSON.stringify(e.website.value,null,2))}</pre>` : `<p class="sp-empty">No verified website research record returned. ${esc(e.website?.note||'')}</p>`;
    const audit = table(['Evidence module','Status','Source','Retrieved'],Object.entries(e).map(([key,v])=>[esc(key.replaceAll('_',' ')),cell(status(v?.status)),link(v?.source_url),cell(v?.retrieved_at)]));
    const sections = [
      ['Overview',e.registry,overview],['Financials',e.financials,financials],['Leadership',e.roles,leadership],['Locations',e.locations,locations],['Website',e.website,website],['Evidence & audit',null,audit]
    ];
    const root=document.createElement('section'); root.className='sp-dashboard';
    root.innerHTML=`<div class="sp-head"><span class="sp-eyebrow">SOURCE-LINKED COMPANY RESEARCH</span><h2>${esc(name)}</h2><p>Organisation ${fmt(org)} · Run ${fmt(data.run_id)} · ${fmt(data.terminal?.terminal_state||data.terminal?.status||'Status not reported')}</p><div class="sp-metrics"><div><strong>${fin.length}</strong><span>Financial records</span></div><div><strong>${roles.length}</strong><span>Role records</span></div><div><strong>${loc.length}</strong><span>Location records</span></div></div></div><nav class="sp-tabs" aria-label="Company research sections">${sections.map((s,i)=>`<button type="button" class="sp-tab${i===0?' active':''}" data-index="${i}" aria-pressed="${i===0}">${esc(s[0])}</button>`).join('')}</nav><div class="sp-panels">${sections.map((s,i)=>`<div class="sp-panel" ${i?'hidden':''}>${evidenceCard(s[0],s[1],s[2])}</div>`).join('')}</div><p class="sp-disclaimer">Evidence states describe returned source records, not independent guarantees of completeness or correctness. ${esc(data.scope_note||'')}</p>`;
    root.querySelectorAll('.sp-tab').forEach(b=>b.addEventListener('click',()=>{
      const idx=Number(b.dataset.index);
      root.querySelectorAll('.sp-tab').forEach((tab,i)=>{tab.classList.toggle('active',i===idx);tab.setAttribute('aria-pressed',String(i===idx));});
      root.querySelectorAll('.sp-panel').forEach((panel,i)=>{panel.hidden=i!==idx;});
    }));
    return root;
  }
  const style=document.createElement('style');style.textContent=`
  .sp-dashboard{margin:24px 0;border:1px solid #dce4ee;border-radius:22px;background:white;overflow:hidden;box-shadow:0 16px 45px #15223812;color:#152238}.sp-head{padding:28px;background:linear-gradient(130deg,#12283b,#194c50);color:white}.sp-eyebrow{color:#7fe2d0;font-size:11px;font-weight:800;letter-spacing:2px}.sp-head h2{font-size:clamp(25px,4vw,38px);line-height:1.15;margin:10px 0}.sp-head p{color:#d5e6e7;overflow-wrap:anywhere}.sp-metrics{display:flex;gap:12px;flex-wrap:wrap;margin-top:22px}.sp-metrics div{display:flex;flex-direction:column;min-width:120px;background:#ffffff14;border:1px solid #ffffff22;padding:12px 18px;border-radius:12px}.sp-metrics strong{font-size:25px}.sp-metrics span{font-size:12px;color:#c7dfdd}.sp-tabs{display:flex;gap:6px;overflow-x:auto;padding:14px;border-bottom:1px solid #e4ebf2}.sp-tab{border:1px solid transparent;background:transparent;border-radius:10px;padding:10px 14px;white-space:nowrap;font:inherit;font-size:13px;font-weight:750;color:#52637b;cursor:pointer}.sp-tab.active{background:#e1f5f1;border-color:#a5ded3;color:#075f58}.sp-tab:focus-visible{outline:3px solid #0b958b}.sp-panels{padding:20px}.sp-panel[hidden]{display:none}.sp-card h3{font-size:20px;margin:0}.sp-card-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px}.sp-pill{border-radius:999px;background:#eff3f8;padding:5px 10px;color:#42556d;font-size:12px}.sp-scroll{max-width:100%;overflow-x:auto;overscroll-behavior-x:contain}.result .sp-dashboard .sp-scroll{overflow-x:auto}.result .sp-dashboard .sp-table{display:table;table-layout:auto;width:100%;min-width:900px;max-width:none;overflow:visible}.result .sp-dashboard .sp-table th,.result .sp-dashboard .sp-table td{width:auto;min-width:112px;white-space:normal;overflow-wrap:normal;word-break:normal}.result .sp-dashboard .sp-table th:first-child,.result .sp-dashboard .sp-table td:first-child{min-width:150px}.result .sp-dashboard .sp-table th{white-space:nowrap}.sp-table{border-collapse:collapse;width:100%;min-width:540px;font-size:13px}.sp-table th,.sp-table td{text-align:left;padding:12px;border-bottom:1px solid #e5ebf2;overflow-wrap:anywhere;vertical-align:top}.sp-table th{font-weight:700;color:#52637b}.sp-table td{color:#152238}.sp-provenance{display:flex;gap:12px;flex-wrap:wrap;border-top:1px solid #e5ebf2;padding-top:15px;margin-top:20px;font-size:12px;color:#58677c;overflow-wrap:anywhere}.sp-provenance a,.sp-table a{color:#087f78}.sp-empty{color:#66758b}.sp-json{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.sp-disclaimer{padding:0 20px 20px;font-size:12px;color:#58677c} .sp-records{display:grid;gap:12px;min-width:0}.sp-record{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:14px;padding:18px;border:1px solid #e0e8f0;border-radius:14px;background:#f9fbfd;min-width:0}.sp-field{display:flex;flex-direction:column;gap:5px;min-width:0}.sp-field-label{font-size:11px;letter-spacing:.04em;text-transform:uppercase;font-weight:750;color:#61728a}.sp-field-value{font-size:14px;line-height:1.5;color:#152238;overflow-wrap:anywhere;word-break:normal;white-space:normal}.sp-field-value a{color:#087f78}.sp-dashboard{width:100%;min-width:0}.sp-dashboard .sp-panels{min-width:0} @media(max-width:640px){.sp-head{padding:20px}.sp-panels{padding:14px}.sp-metrics div{min-width:95px;flex:1}.sp-table{min-width:480px}}`;
  document.head.appendChild(style);
  // Hook the existing button without altering its API request or fallback UI.
  const button=document.getElementById('run-research');
  const output=document.getElementById('research-output');
  if(!button||!output)return;
  // Capture the successful response once, while allowing the existing renderer to run.
  const nativeFetch=window.fetch.bind(window);
  window.fetch=async function(input,init){
    const response=await nativeFetch(input,init);
    const url=typeof input==='string'?input:input?.url||'';
    if(url.startsWith('/api/research/')&&response.ok){
      response.clone().json().then(data=>{
        if(!data?.profile)return;
        // Existing handler awaits response.json() and updates the same container first.
        setTimeout(()=>{
          if(!output.isConnected)return;
          output.replaceChildren(render(data));
        },50);
      }).catch(()=>{});
    }
    return response;
  };
})();
